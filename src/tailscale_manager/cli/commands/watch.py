from __future__ import annotations

import json
import logging
import signal
import sys

import typer
from rich.console import Console

from tailscale_manager.cli.app import app, load_config
from tailscale_manager.services.terraform import TerraformService
from tailscale_manager.services.watcher import PolicyWatcher

_logger = logging.getLogger(__name__)
_console = Console()
_error_console = Console(stderr=True)


def register(parent: typer.Typer) -> None:
    @parent.command()
    def watch() -> None:
        config = load_config()
        config.assert_credentials()

        tf_init_dir = config.state_dir / ".terraform"
        if not tf_init_dir.exists():
            _error_console.print(
                "✗ Terraform is not initialized. Run `tailscale-manager init` first."
            )
            raise typer.Exit(1)

        svc = TerraformService(config)

        result = svc.apply()
        print(json.dumps(result, indent=2))
        if result["result"] != "ok":
            _error_console.print(
                f"Initial apply failed: {result.get('error_message', '')}"
            )
            raise typer.Exit(1)

        watcher = PolicyWatcher(config, svc.apply)

        def _handle_signal(signum: int, _frame: object) -> None:
            signal_name = signal.Signals(signum).name
            _logger.info("Received %s, shutting down...", signal_name)
            watcher.stop()

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)

        print("Watching for changes... (Ctrl+C to stop)")
        sys.stdout.flush()
        watcher.run()
