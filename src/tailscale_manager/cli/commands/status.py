from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer
from rich.console import Console

from tailscale_manager.cli.app import app, load_config
from tailscale_manager.repositories.state_repository import StateRepository
from tailscale_manager.services.terraform import TerraformService

_console = Console()
_error_console = Console(stderr=True)


def register(parent: typer.Typer) -> None:
    @parent.command()
    def status(
        json_output: bool = typer.Option(
            False,
            "--json",
            help="Print last-apply.json to stdout instead of launching TUI",
        ),
        show_plan: bool = typer.Option(
            False,
            "--plan",
            help="Include Terraform plan summary in --json output (implies --json)",
        ),
    ) -> None:
        config = load_config()
        if config.tailnet == "-" and config.oauth_client_id and config.oauth_client_secret:
            try:
                from tailscale_manager.services.api.client import TailscaleApiClient
                from tailscale_manager.services.api.oauth import OAuthClient
                client = TailscaleApiClient(
                    OAuthClient(config.oauth_client_id, config.oauth_client_secret),
                )
                resolved = client.resolve_tailnet()
                if resolved != "-":
                    config.tailnet = resolved
            except Exception:
                pass
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
            if show_plan:
                try:
                    svc = TerraformService(config)
                    svc.write_configs()
                    svc.init()
                    plan = svc.plan_summary()
                    output["plan"] = plan
                except Exception as exc:
                    output["plan"] = {"error": str(exc)}
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

        if not sys.stdout.isatty():
            return

        try:
            from tailscale_manager.tui import run_status_app
            run_status_app(config, keys, last)
        except ImportError as exc:
            _error_console.print(f"TUI not available: {exc}")
            _error_console.print("Install textual: pip install textual")
        except Exception as exc:
            print(f"TUI unavailable: {exc}", file=sys.stderr)

    @parent.command()
    def devices(
        json_output: bool = typer.Option(
            False,
            "--json",
            help="Print devices as JSON array",
        ),
    ) -> None:
        config = load_config()
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

    @parent.command()
    def output(
        output_file: str | None = typer.Option(
            None,
            "--output-file",
            help="Write key to file (mode 0600) instead of stdout",
        ),
    ) -> None:
        config = load_config()
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
