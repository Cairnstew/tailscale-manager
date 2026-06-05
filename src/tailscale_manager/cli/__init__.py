from __future__ import annotations

from typing import Any

import typer
from pydantic import ValidationError

from tailscale_manager.cli.app import app, load_config
from tailscale_manager.cli.commands import register_all
from tailscale_manager.cli.renderers import (
    CheckResult,
    convert_pydantic_error,
    print_scope_warnings,
    render_configuration_error,
    render_terraform_error,
)
from tailscale_manager.core.exceptions import ConfigurationError, TerraformError

register_all()

# Backward-compat aliases for tests and external callers
_convert_pydantic_error = convert_pydantic_error
_render_configuration_error = render_configuration_error
_render_terraform_error = render_terraform_error
_print_scope_warnings = print_scope_warnings

__all__ = [
    "app",
    "main",
    "load_config",
    "CheckResult",
    "_convert_pydantic_error",
    "_print_scope_warnings",
    "_render_configuration_error",
    "_render_terraform_error",
]


def main(args: list[str] | None = None) -> None:
    try:
        app(args=args)
    except ConfigurationError as exc:
        render_configuration_error(exc)
        raise typer.Exit(1) from None
    except TerraformError as exc:
        render_terraform_error(exc)
        raise typer.Exit(1) from None
    except ValidationError as exc:
        cfg_err = convert_pydantic_error(exc)
        render_configuration_error(cfg_err)
        raise typer.Exit(1) from None
