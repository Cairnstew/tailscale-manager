from __future__ import annotations

import json
import re
import sys

import typer
from rich.console import Console

from tailscale_manager.cli.app import load_config
from tailscale_manager.repositories.state_repository import StateRepository
from tailscale_manager.services.api.client import TailscaleApiClient
from tailscale_manager.services.api.oauth import OAuthClient
from tailscale_manager.core.config import AppConfig

_console = Console()
_error_console = Console(stderr=True)


def _make_client(config: AppConfig) -> TailscaleApiClient:
    return TailscaleApiClient(
        oauth=OAuthClient(
            client_id=config.oauth_client_id,
            client_secret=config.oauth_client_secret,
        ),
        tailnet=config.tailnet,
    )


def register(parent: typer.Typer) -> None:
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
        config = load_config()
        config.assert_credentials()

        expiry_seconds: int | None = None
        if expiry:
            m = re.match(r"^(\d+)([smhd])$", expiry)
            if not m:
                _error_console.print(f"Invalid expiry format: {expiry}")
                _error_console.print("Use e.g. 30m, 24h, 7d")
                raise typer.Exit(1)
            value, unit = int(m.group(1)), m.group(2)
            multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
            expiry_seconds = value * multipliers[unit]

        _console.print("Creating auth key...")
        client = _make_client(config)
        result = client.create_auth_key(
            description=description,
            tags=tags,
            reusable=reusable,
            ephemeral=ephemeral,
            preauthorized=preauthorized,
            expiry_seconds=expiry_seconds,
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
        config = load_config()
        config.assert_credentials()

        client = _make_client(config)
        keys = client.fetch_auth_keys()

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
        config = load_config()
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
        config = load_config()
        config.assert_credentials()

        client = _make_client(config)
        client.revoke_auth_key(key_id=key_id)
        _console.print(f"Auth key [cyan]{key_id}[/] revoked.")

    parent.add_typer(auth_keys_app)
