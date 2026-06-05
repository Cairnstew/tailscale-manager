from __future__ import annotations

import base64
import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console

from tailscale_manager.cli.app import app, load_config
from tailscale_manager.cli.renderers import (
    CheckResult,
    convert_pydantic_error,
    print_scope_warnings,
    render_configuration_error,
)
from tailscale_manager.core.config import AppConfig
from tailscale_manager.core.exceptions import TerraformError
from tailscale_manager.repositories.state_repository import StateRepository
from tailscale_manager.utils.subprocess import TerraformRunner

_console = Console()


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
        output = TerraformRunner(config.terraform_bin).run(
            ["version"], cwd=Path("/tmp"), timeout=5,
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


def register(parent: typer.Typer) -> None:
    @parent.command()
    def doctor(
        check_api: bool = typer.Option(
            False,
            "--check-api",
            help="Also test OAuth connectivity to the Tailscale API",
        ),
    ) -> None:
        try:
            config = AppConfig.from_env()
        except ValidationError as exc:
            convert_pydantic_error(exc)
            render_configuration_error(convert_pydantic_error(exc))
            raise typer.Exit(1) from None
        except Exception as exc:
            _console.print(f"Failed to load config: {exc}")
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
