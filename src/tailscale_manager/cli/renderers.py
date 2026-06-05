from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel

from tailscale_manager.core.config import AppConfig
from tailscale_manager.core.exceptions import ConfigurationError, TerraformError

_error_console = Console(stderr=True)
_console = Console()


@dataclass
class CheckResult:
    name: str
    status: Literal["pass", "fail", "skip"]
    detail: str
    hint: str | None = None


def render_configuration_error(err: ConfigurationError) -> None:
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


def render_terraform_error(err: TerraformError) -> None:
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


def convert_pydantic_error(err: ValidationError) -> ConfigurationError:
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


def print_scope_warnings(config: AppConfig) -> None:
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
