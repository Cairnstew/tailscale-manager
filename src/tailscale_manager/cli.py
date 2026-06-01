from __future__ import annotations

import importlib.metadata
import json
import sys

import typer

from tailscale_manager.core.config import AppConfig
from tailscale_manager.repositories.state_repository import StateRepository
from tailscale_manager.services.terraform_service import TerraformService

app = typer.Typer(
    name="tailscale-manager",
    help="Manage Tailscale auth keys via Terraform",
)


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


@app.command()
def init() -> None:
    config = _load_config()
    svc = TerraformService(config)
    svc.write_configs()
    _print_scope_warnings(config)
    output = svc.init()
    print(output)


@app.command()
def plan() -> None:
    config = _load_config()
    svc = TerraformService(config)
    svc.write_configs()
    svc.init()
    output = svc.plan()
    print(output)


@app.command()
def apply() -> None:
    config = _load_config()
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


def main() -> None:
    app()
