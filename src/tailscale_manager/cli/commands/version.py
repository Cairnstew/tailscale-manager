from __future__ import annotations

import importlib.metadata

import typer


def register(parent: typer.Typer) -> None:
    @parent.command()
    def version() -> None:
        v = importlib.metadata.version("tailscale-manager")
        print(f"tailscale-manager {v}")
