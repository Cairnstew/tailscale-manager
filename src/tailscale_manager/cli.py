from __future__ import annotations

import base64
import importlib.metadata
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel

from tailscale_manager.core.config import AppConfig
from tailscale_manager.core.exceptions import ConfigurationError, TerraformError
from tailscale_manager.models.auth_key import TailscaleAuthKey
from tailscale_manager.repositories.state_repository import StateRepository
from tailscale_manager.services.api_client import create_auth_key, fetch_auth_keys, revoke_auth_key
from tailscale_manager.services.terraform_service import TerraformService
from tailscale_manager.utils.subprocess_helpers import _find_hint, run_terraform

app = typer.Typer(
    name="tailscale-manager",
    help="Manage Tailscale auth keys via Terraform",
)

_error_console = Console(stderr=True)
_console = Console()


@dataclass
class CheckResult:
    name: str
    status: Literal["pass", "fail", "skip"]
    detail: str
    hint: str | None = None


def _load_config() -> AppConfig:
    config = AppConfig.from_env()
    config.state_dir.mkdir(parents=True, exist_ok=True)
    return config


@app.callback()
def _main() -> None:
    pass


def _print_scope_warnings(config: AppConfig) -> None:
    """Print non-blocking warnings about required OAuth scopes."""
    warnings: list[str] = []
    if config.dns_nameservers or config.dns_magic_dns or config.dns_split_nameservers:
        warnings.append("  ⚠ DNS management configured — OAuth scope 'dns:write' may be required")
    if config.acl_enable:
        warnings.append("  ⚠ ACL management configured — OAuth scope 'tailnet:acls' may be required")
    if warnings:
        print("Preflight:")
        for w in warnings:
            print(w)
        print()


def _render_configuration_error(err: ConfigurationError) -> None:
    sections: list[str] = []
    if err.field:
        sections.append(f"  Field:   {err.field}")
    sections.append(f"  Problem: {err.message}")
    if err.hint:
        sections.append("")
        sections.append("  How to fix:")
        sections.append(f"    {err.hint}")
    if err.docs_url:
        sections.append("")
        sections.append(f"  Docs: {err.docs_url}")

    _error_console.print()
    _error_console.print(Panel(
        "\n".join(sections),
        title="Configuration Error",
        border_style="red",
    ))
    _error_console.print()


def _render_terraform_error(err: TerraformError) -> None:
    sections: list[str] = [
        f"  Command: terraform {err.command}",
        f"  Exit code: {err.exit_code}",
    ]
    if err.stderr:
        sections.append("")
        sections.append("  Output:")
        for line in err.stderr.splitlines()[:20]:
            sections.append(f"    {line}")
    if err.hint:
        sections.append("")
        sections.append(f"  Hint: {err.hint}")

    _error_console.print()
    _error_console.print(Panel(
        "\n".join(sections),
        title="Terraform Error",
        border_style="red",
    ))
    _error_console.print()


def _convert_pydantic_error(err: ValidationError) -> ConfigurationError:
    errors = err.errors()
    if errors:
        first = errors[0]
        field = ".".join(str(loc) for loc in first.get("loc", [])) if first.get("loc") else None
        msg = first.get("msg", str(err))
        hint = None
        if field and ("oauth_client_id" in field or "oauth_client_secret" in field):
            hint = (
                "Set credentials via credentialsFile (NixOS) or "
                "export TAILSCALE_OAUTH_CLIENT_ID / TAILSCALE_OAUTH_CLIENT_SECRET= (dev)"
            )
        return ConfigurationError(message=msg, field=field, hint=hint)
    return ConfigurationError(message=str(err))


@app.command()
def init() -> None:
    config = _load_config()
    svc = TerraformService(config)
    svc.write_configs()

    tf_init_dir = config.state_dir / ".terraform"
    if not tf_init_dir.exists():
        _console.print()
        _console.print("First run detected — state directory is empty.")
        _console.print()
        _console.print("Next steps:")
        _console.print("  1. tailscale-manager doctor     Check your configuration")
        _console.print("  2. tailscale-manager init       Download the Terraform provider")
        _console.print("  3. tailscale-manager plan       Preview what will be created")
        _console.print("  4. tailscale-manager apply      Create your managed resources")
        _console.print()
        _console.print("Documentation: https://github.com/Cairnstew/tailscale-manager#readme")
        _console.print()

    _print_scope_warnings(config)
    output = svc.init()
    print(output)


@app.command()
def plan() -> None:
    config = _load_config()
    config.assert_credentials()
    svc = TerraformService(config)
    svc.write_configs()
    svc.init()
    output = svc.plan()
    print(output)


@app.command()
def apply() -> None:
    config = _load_config()
    tf_init_dir = config.state_dir / ".terraform"
    if not tf_init_dir.exists():
        _console.print("✗ Terraform is not initialized. Run `tailscale-manager init` first.")
        raise typer.Exit(1)
    config.assert_credentials()
    svc = TerraformService(config)
    result = svc.apply()
    print(json.dumps(result, indent=2))
    if result["result"] == "ok":
        print("Apply succeeded")
    else:
        print(f"Apply failed: {result.get('error_message', '')}", file=sys.stderr)
        raise typer.Exit(1)


@app.command()
def destroy() -> None:
    config = _load_config()
    config.assert_credentials()
    svc = TerraformService(config)
    result = svc.destroy()
    print(json.dumps(result, indent=2))
    if result["result"] == "ok":
        print("Destroy succeeded")
    else:
        print(f"Destroy failed: {result.get('error_message', '')}", file=sys.stderr)
        raise typer.Exit(1)


@app.command()
def status(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print last-apply.json to stdout instead of launching TUI",
    ),
) -> None:
    config = _load_config()
    repo = StateRepository(config.state_dir)
    keys = repo.get_managed_keys()
    last = repo.read_last_apply()

    if json_output:
        output: dict = {
            "last_apply": last or {},
            "managed_keys": [
                {
                    "id": k.id,
                    "description": k.description,
                    "tags": k.tags,
                    "revoked": k.revoked,
                }
                for k in keys
            ],
        }
        print(json.dumps(output, indent=2, default=str))
        if last and last.get("result") == "error":
            raise typer.Exit(1)
        return

    print(f"Tailscale Manager — {config.tailnet}")
    print(f"State dir: {config.state_dir}")
    print()

    if last:
        print(f"Last apply: {last.get('timestamp', 'unknown')}")
        print(f"  Result: {last.get('result', 'unknown')}")
        err = last.get("error_message")
        if err:
            print(f"  Error: {err}")
    else:
        print("No apply has been run yet.")

    print()
    keys_file = config.state_dir / "terraform.tfstate"
    print(f"Terraform state: {'found' if keys_file.exists() else 'not found'}")
    if not repo.check_state_file_permissions():
        print("  ⚠ tfstate permissions wider than 0600 — run chmod 0600")

    print(f"Managed keys: {len(keys)}")
    for k in keys:
        status_icon = "✗" if k.revoked else "✓"
        print(f"  {status_icon} {k.id[:16] if k.id else '<no id>'} — {k.description or '<no desc>'}")
        if k.tags:
            print(f"     tags: {', '.join(k.tags)}")

    # Try launching TUI if available
    try:
        from textual_ui import run_status_app  # type: ignore[import-untyped]

        run_status_app(config, keys, last)
    except ImportError:
        pass
    except Exception as exc:
        print(f"TUI unavailable: {exc}", file=sys.stderr)


@app.command()
def devices(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print devices as JSON array",
    ),
) -> None:
    """List discovered Tailscale devices from Terraform state."""
    config = _load_config()
    repo = StateRepository(config.state_dir)
    devices = repo.get_devices()

    if json_output:
        print(json.dumps(
            [
                {
                    "id": d.id,
                    "hostname": d.hostname,
                    "name": d.name,
                    "addresses": d.addresses,
                    "tags": d.tags,
                    "user": d.user,
                }
                for d in devices
            ],
            indent=2,
            default=str,
        ))
        return

    if not devices:
        print("No devices discovered. Run 'tailscale-manager apply' first.")
        return

    print(f"Discovered {len(devices)} device(s):")
    print()
    for d in devices:
        print(f"  {d.hostname or d.name}")
        print(f"    ID:        {d.id}")
        addrs = ", ".join(d.addresses) if d.addresses else "-"
        print(f"    Addresses: {addrs}")
        tags = ", ".join(d.tags) if d.tags else "-"
        print(f"    Tags:      {tags}")
        print(f"    User:      {d.user or '-'}")
        print()


@app.command()
def output(
    output_file: str | None = typer.Option(
        None,
        "--output-file",
        help="Write key to file (mode 0600) instead of stdout",
    ),
) -> None:
    """Print the managed auth key secret from Terraform state."""
    config = _load_config()
    repo = StateRepository(config.state_dir)

    state_file = config.state_dir / "terraform.tfstate"
    if not state_file.exists():
        _error_console.print(f"Error: no Terraform state found at {state_file}")
        raise typer.Exit(1)

    try:
        key = repo.get_managed_key_value()
    except ValueError as exc:
        _error_console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc
    if key is None:
        _error_console.print("Error: managed key not found in state")
        raise typer.Exit(1)

    if output_file:
        try:
            path = Path(output_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(key)
        except OSError as exc:
            _error_console.print(f"Error: cannot write to {output_file}: {exc}")
            raise typer.Exit(1) from exc
    else:
        sys.stdout.write(key)


@app.command()
def backup_state() -> None:
    config = _load_config()
    svc = TerraformService(config)
    svc._backup_state()
    print(f"Backed up state in {config.state_dir / 'backups'}")


@app.command()
def restore_state() -> None:
    config = _load_config()
    svc = TerraformService(config)
    svc._restore_state()
    print("Restored most recent state backup")


@app.command()
def version() -> None:
    """Show tailscale-manager version."""
    v = importlib.metadata.version("tailscale-manager")
    print(f"tailscale-manager {v}")


# ── auth-keys subcommand ──────────────────────────────────────

auth_keys_app = typer.Typer(
    name="auth-keys",
    help="Manage Tailscale auth keys via the Tailscale API",
    rich_help_panel="Management",
)


@auth_keys_app.command()
def create(
    description: str = typer.Option(
        ..., "--description", "-d",
        help="Human-readable description for the key",
    ),
    tags: list[str] = typer.Option(
        [], "--tag", "-t",
        help="Tags to apply (e.g. tag:ci). Repeatable.",
    ),
    reusable: bool = typer.Option(
        True, "--reusable/--no-reusable",
        help="Allow multiple devices to use this key",
    ),
    ephemeral: bool = typer.Option(
        False, "--ephemeral/--persistent",
        help="Ephemeral devices are removed on disconnect",
    ),
    preauthorized: bool = typer.Option(
        True, "--preauthorized/--not-preauthorized",
        help="Pre-approve devices using this key",
    ),
    expiry: str | None = typer.Option(
        None, "--expiry", "-e",
        help="Key expiry duration (e.g. 24h, 7d). Omit for no expiry.",
    ),
) -> None:
    """Create a new auth key and print it once."""
    config = _load_config()
    config.assert_credentials()

    expiry_seconds: int | None = None
    if expiry:
        import re
        m = re.match(r"^(\d+)([smhd])$", expiry)
        if not m:
            _error_console.print(f"Invalid expiry format: {expiry}")
            _error_console.print("Use e.g. 30m, 24h, 7d")
            raise typer.Exit(1)
        value, unit = int(m.group(1)), m.group(2)
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        expiry_seconds = value * multipliers[unit]

    _console.print("Creating auth key...")
    result = create_auth_key(
        tailnet=config.tailnet,
        description=description,
        tags=tags,
        reusable=reusable,
        ephemeral=ephemeral,
        preauthorized=preauthorized,
        expiry_seconds=expiry_seconds,
        client_id=config.oauth_client_id,
        client_secret=config.oauth_client_secret,
    )
    _console.print()
    _console.print("Auth key created:")
    _console.print(f"  ID:          {result.id}")
    _console.print(f"  Description: {result.description}")
    _console.print(f"  Tags:        {', '.join(result.tags) if result.tags else '-'}")
    _console.print(f"  Reusable:    {result.reusable}")
    _console.print(f"  Ephemeral:   {result.ephemeral}")
    _console.print(f"  Preauth:     {result.preauthorized}")
    if result.expiry:
        _console.print(f"  Expires:     {result.expiry.isoformat()}")
    _console.print()
    _console.print("[bold yellow]Key value (shown once):[/]")
    _console.print(f"[bold cyan]{result.key}[/]")
    _console.print()
    _console.print("[yellow]⚠ Store this key securely. It cannot be retrieved again.[/]")


@auth_keys_app.command("list")
def _list_keys(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON array",
    ),
) -> None:
    """List all auth keys on the tailnet."""
    config = _load_config()
    config.assert_credentials()

    keys = fetch_auth_keys(
        tailnet=config.tailnet,
        client_id=config.oauth_client_id,
        client_secret=config.oauth_client_secret,
    )

    if json_output:
        print(json.dumps(
            [
                {
                    "id": k.id,
                    "description": k.description,
                    "tags": k.tags,
                    "expiry": k.expiry.isoformat() if k.expiry else None,
                    "revoked": k.revoked,
                    "reusable": k.reusable,
                    "ephemeral": k.ephemeral,
                    "preauthorized": k.preauthorized,
                    "created_at": k.created_at.isoformat() if k.created_at else None,
                }
                for k in keys
            ],
            indent=2,
            default=str,
        ))
        return

    if not keys:
        _console.print("No auth keys found.")
        return

    _console.print(f"Auth keys ({len(keys)}):")
    _console.print()
    for k in keys:
        status = "✓" if not k.revoked else "✗ (revoked)"
        _console.print(f"  {status}  {k.id}")
        _console.print(f"         {k.description or '<no description>'}")
        if k.tags:
            _console.print(f"         tags: {', '.join(k.tags)}")
        if k.expiry:
            _console.print(f"         expires: {k.expiry.isoformat()}")
        _console.print()


@auth_keys_app.command("show-key")
def _show_key(
    key_name: str = typer.Argument(
        ...,
        help="Terraform resource name of the auth key (e.g. ci-key)",
    ),
) -> None:
    """Retrieve a declared key's value from Terraform state.
    
    This reads the key value from the Terraform state file
    at TAILSCALE_MANAGER_STATE_DIR/terraform.tfstate.
    The value is stored there by Terraform when the key is created.
    
    The key is printed to stdout. A warning is printed to stderr.
    """
    config = _load_config()
    repo = StateRepository(config.state_dir)

    key = repo.get_key_by_name(key_name)
    if key is None:
        _error_console.print(
            f"Key [bold]{key_name}[/] not found in Terraform state.\n"
            f"  Run [bold]tailscale-manager apply[/] first to create it."
        )
        raise typer.Exit(1)

    if not key.key:
        _error_console.print(
            f"Key [bold]{key_name}[/] has no stored value.\n"
            f"  The key may have been created before this feature was added.\n"
            f"  Recreate it with [bold]tailscale-manager auth-keys create[/] "
            f"or remove and re-apply."
        )
        raise typer.Exit(1)

    print("WARNING: Key value shown once. Store it securely.", file=sys.stderr)
    print(key.key)


@auth_keys_app.command()
def revoke(
    key_id: str = typer.Argument(
        ...,
        help="ID of the auth key to revoke",
    ),
) -> None:
    """Revoke an auth key by ID."""
    config = _load_config()
    config.assert_credentials()

    revoke_auth_key(
        key_id=key_id,
        tailnet=config.tailnet,
        client_id=config.oauth_client_id,
        client_secret=config.oauth_client_secret,
    )
    _console.print(f"Auth key [cyan]{key_id}[/] revoked.")


app.add_typer(auth_keys_app)


# ── doctor command ────────────────────────────────────────────


def _check_credentials_source() -> CheckResult:
    creds_dir = os.environ.get("CREDENTIALS_DIRECTORY", "")
    if creds_dir:
        cred_file = Path(creds_dir) / "tailscale-oauth"
        if cred_file.exists():
            return CheckResult("Credentials file", "pass", f"Found at {cred_file}")
        return CheckResult(
            "Credentials file", "fail",
            f"CREDENTIALS_DIRECTORY is set to {creds_dir} but file not found",
            hint="Ensure LoadCredential path is correct in NixOS module",
        )
    env_id = os.environ.get("TAILSCALE_OAUTH_CLIENT_ID", "")
    env_secret = os.environ.get("TAILSCALE_OAUTH_CLIENT_SECRET", "")
    if env_id and env_secret:
        return CheckResult("Credentials env vars", "pass", "TAILSCALE_OAUTH_CLIENT_ID and SECRET set")
    return CheckResult(
        "Credentials", "fail",
        "No credentials found",
        hint="Set credentialsFile in NixOS module or export TAILSCALE_OAUTH_CLIENT_ID / SECRET",
    )


def _check_oauth(config: AppConfig) -> list[CheckResult]:
    results: list[CheckResult] = []
    if config.oauth_client_id:
        masked = config.oauth_client_id[:16] + "..." if len(config.oauth_client_id) > 16 else "••••••••"
        results.append(CheckResult("OAuth client ID", "pass", f"Set ({masked})"))
    else:
        results.append(CheckResult(
            "OAuth client ID", "fail", "Missing TAILSCALE_OAUTH_CLIENT_ID",
            hint="Set in credentialsFile (NixOS) or export TAILSCALE_OAUTH_CLIENT_ID= (dev)",
        ))
    if config.oauth_client_secret:
        results.append(CheckResult("OAuth client secret", "pass", "Set (••••••••)"))
    else:
        results.append(CheckResult(
            "OAuth client secret", "fail", "Missing TAILSCALE_OAUTH_CLIENT_SECRET",
            hint="Set in credentialsFile (NixOS) or export TAILSCALE_OAUTH_CLIENT_SECRET= (dev)",
        ))
    return results


def _check_tailnet(config: AppConfig) -> CheckResult:
    if config.tailnet == "-":
        return CheckResult("Tailnet", "pass", "- (auto-resolve)")
    return CheckResult("Tailnet", "pass", config.tailnet)


def _check_terraform_bin(config: AppConfig) -> list[CheckResult]:
    results: list[CheckResult] = []
    bin_path = config.terraform_bin
    if bin_path.exists() and os.access(bin_path, os.X_OK):
        results.append(CheckResult("Terraform binary", "pass", str(bin_path)))
    else:
        resolved = shutil.which(str(bin_path))
        if resolved:
            results.append(CheckResult("Terraform binary", "pass", resolved))
        else:
            results.append(CheckResult(
                "Terraform binary", "fail", f"Binary not found at {bin_path}",
                hint="Ensure pkgs.terraform is in your NixOS config or set TAILSCALE_MANAGER_TERRAFORM_BIN",
            ))
            return results

    try:
        output = run_terraform(
            config.terraform_bin, ["version"],
            cwd=Path("/tmp"), timeout=5,
        )
        version_line = output.splitlines()[0] if output else "unknown"
        results.append(CheckResult("Terraform version", "pass", version_line))
    except TerraformError as exc:
        results.append(CheckResult(
            "Terraform version", "fail",
            "Could not determine terraform version",
            hint=exc.hint or "Check terraform binary path",
        ))

    return results


def _check_state_dir(config: AppConfig) -> CheckResult:
    sd = config.state_dir
    if sd.exists():
        if os.access(sd, os.W_OK):
            return CheckResult("State directory", "pass", f"{sd} (writable)")
        return CheckResult(
            "State directory", "fail", f"{sd} exists but is not writable",
            hint="Run as root or fix permissions: chmod 700 " + str(sd),
        )
    return CheckResult(
        "State directory", "fail", f"{sd} does not exist",
        hint=f"Create manually: mkdir -p {sd}",
    )


def _check_terraform_initialized(config: AppConfig) -> CheckResult:
    if (config.state_dir / ".terraform").is_dir():
        return CheckResult("Terraform initialized", "pass", ".terraform/ present")
    return CheckResult(
        "Terraform initialized", "fail", "Not initialized",
        hint="Run `tailscale-manager init`",
    )


def _check_state_file(config: AppConfig) -> list[CheckResult]:
    results: list[CheckResult] = []
    state_file = config.state_dir / "terraform.tfstate"
    if state_file.exists():
        results.append(CheckResult("State file", "pass", "terraform.tfstate present"))
        mode = state_file.stat().st_mode & 0o777
        if mode == 0o600:
            results.append(CheckResult("State file permissions", "pass", "0600"))
        else:
            results.append(CheckResult(
                "State file permissions", "fail", f"Permissions: {oct(mode)}",
                hint="Run: chmod 0600 " + str(state_file),
            ))
    else:
        results.append(CheckResult(
            "State file", "fail", "Not found",
            hint="Run `tailscale-manager init && tailscale-manager apply`",
        ))
    return results


def _check_last_apply(config: AppConfig) -> CheckResult:
    repo = StateRepository(config.state_dir)
    last = repo.read_last_apply()
    if last is None:
        return CheckResult("Last apply", "skip", "No apply history")
    if last.get("result") == "ok":
        ts = last.get("timestamp", "unknown")
        return CheckResult("Last apply", "pass", ts)
    err = last.get("error_message", "unknown error")
    return CheckResult(
        "Last apply", "fail", f"ERROR — {err}",
        hint="Run `tailscale-manager doctor` for details, then `tailscale-manager init` to re-initialize",
    )


def _check_acl_policy(config: AppConfig) -> CheckResult:
    if config.acl_enable and config.acl_policy:
        return CheckResult("ACL policy", "skip", "Configured (acl.enable = true)")
    return CheckResult("ACL policy", "skip", "Not configured (acl.enable = false)")


def _check_dns(config: AppConfig) -> CheckResult:
    if config.dns_nameservers or config.dns_magic_dns or config.dns_split_nameservers:
        details = []
        if config.dns_nameservers:
            details.append(f"nameservers: {', '.join(config.dns_nameservers)}")
        if config.dns_magic_dns:
            details.append("magicDNS: on")
        return CheckResult("DNS", "skip", "; ".join(details))
    return CheckResult("DNS", "skip", "Not configured")


def _check_api_connectivity(config: AppConfig) -> CheckResult:
    if not config.oauth_client_id or not config.oauth_client_secret:
        return CheckResult("API connectivity", "skip", "Skipped — OAuth credentials not available")
    credentials = base64.b64encode(
        f"{config.oauth_client_id}:{config.oauth_client_secret}".encode()
    ).decode()
    req = urllib.request.Request(
        "https://api.tailscale.com/api/v2/oauth/token",
        data=b"",
        headers={
            "Authorization": f"Basic {credentials}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            token = body.get("access_token", "")
            prefix = token[:16] + "..." if len(token) > 16 else "••••"
            return CheckResult("API connectivity", "pass", f"Token obtained ({prefix})")
    except urllib.error.HTTPError as exc:
        return CheckResult(
            "API connectivity", "fail",
            f"HTTP {exc.code}: {exc.reason}",
            hint="Check OAuth client ID, secret, and scopes in admin console",
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return CheckResult(
            "API connectivity", "fail",
            f"Connection failed: {exc}",
            hint="Check network connectivity to api.tailscale.com",
        )


@app.command()
def doctor(
    check_api: bool = typer.Option(
        False,
        "--check-api",
        help="Also test OAuth connectivity to the Tailscale API",
    ),
) -> None:
    """Run pre-flight checks and report configuration status."""
    try:
        config = AppConfig.from_env()
    except ValidationError as exc:
        _convert_pydantic_error(exc)
        _render_configuration_error(_convert_pydantic_error(exc))
        raise typer.Exit(1) from None
    except Exception as exc:
        _error_console.print(f"Failed to load config: {exc}")
        raise typer.Exit(1) from None

    checks: list[CheckResult] = []

    checks.append(_check_credentials_source())
    checks.extend(_check_oauth(config))
    checks.append(_check_tailnet(config))
    checks.extend(_check_terraform_bin(config))
    checks.append(_check_state_dir(config))
    checks.append(_check_terraform_initialized(config))
    checks.extend(_check_state_file(config))
    checks.append(_check_last_apply(config))
    checks.append(_check_acl_policy(config))
    checks.append(_check_dns(config))

    if check_api:
        checks.append(_check_api_connectivity(config))

    _console.print()
    _console.print("Checking tailscale-manager configuration...")
    _console.print()

    for check in checks:
        icons = {"pass": "✓", "fail": "✗", "skip": "~"}
        icon = icons.get(check.status, "?")
        _console.print(f"  {icon}  {check.name:<25} {check.detail}")
        if check.hint and check.status == "fail":
            _console.print(f"     {check.hint}")

    _console.print()
    fail_count = sum(1 for c in checks if c.status == "fail")
    if fail_count == 0:
        _console.print("Overall: All checks passed.")
    else:
        _console.print(
            f"Overall: {fail_count} check(s) failed. "
            f"Run `tailscale-manager init` to re-initialize."
        )
        raise typer.Exit(1)


# ── Entry point ──────────────────────────────────────────────


def main(args: list[str] | None = None) -> None:
    try:
        app(args=args)
    except ConfigurationError as exc:
        _render_configuration_error(exc)
        raise typer.Exit(1) from None
    except TerraformError as exc:
        _render_terraform_error(exc)
        raise typer.Exit(1) from None
    except ValidationError as exc:
        cfg_err = _convert_pydantic_error(exc)
        _render_configuration_error(cfg_err)
        raise typer.Exit(1) from None
