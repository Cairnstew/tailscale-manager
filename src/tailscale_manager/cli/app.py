from __future__ import annotations

import typer

from tailscale_manager.core.config import AppConfig

app = typer.Typer(
    name="tailscale-manager",
    help="Manage Tailscale auth keys via Terraform",
)


@app.callback()
def _main() -> None:
    pass


def load_config() -> AppConfig:
    config = AppConfig.from_env()
    config.state_dir.mkdir(parents=True, exist_ok=True)
    return config
