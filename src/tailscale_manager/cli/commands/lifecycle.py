from __future__ import annotations

import json
import sys

import typer
from rich.console import Console

from tailscale_manager.cli.app import app, load_config
from tailscale_manager.services.terraform import TerraformService

_console = Console()


def register(parent: typer.Typer) -> None:
    @parent.command()
    def init() -> None:
        config = load_config()
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

        from tailscale_manager.cli.renderers import print_scope_warnings
        print_scope_warnings(config)
        output = svc.init()
        print(output)

    @parent.command()
    def plan() -> None:
        config = load_config()
        config.assert_credentials()
        svc = TerraformService(config)
        svc.write_configs()
        svc.init()
        output = svc.plan()
        print(output)

    @parent.command()
    def apply(
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            "--plan-only",
            help="Print the plan without applying changes",
        ),
    ) -> None:
        config = load_config()
        svc = TerraformService(config)

        if dry_run:
            svc.write_configs()
            svc.init()
            output = svc.plan()
            print(output)
            return

        tf_init_dir = config.state_dir / ".terraform"
        if not tf_init_dir.exists():
            _console.print("✗ Terraform is not initialized. Run `tailscale-manager init` first.")
            raise typer.Exit(1)
        config.assert_credentials()
        result = svc.apply()
        print(json.dumps(result, indent=2))
        if result["result"] == "ok":
            print("Apply succeeded")
        else:
            print(f"Apply failed: {result.get('error_message', '')}", file=sys.stderr)
            raise typer.Exit(1)

    @parent.command()
    def destroy() -> None:
        config = load_config()
        config.assert_credentials()
        svc = TerraformService(config)
        result = svc.destroy()
        print(json.dumps(result, indent=2))
        if result["result"] == "ok":
            print("Destroy succeeded")
        else:
            print(f"Destroy failed: {result.get('error_message', '')}", file=sys.stderr)
            raise typer.Exit(1)

    @parent.command()
    def backup_state() -> None:
        config = load_config()
        svc = TerraformService(config)
        svc._backup_state()
        print(f"Backed up state in {config.state_dir / 'backups'}")

    @parent.command()
    def restore_state() -> None:
        config = load_config()
        svc = TerraformService(config)
        svc._restore_state()
        print("Restored most recent state backup")
