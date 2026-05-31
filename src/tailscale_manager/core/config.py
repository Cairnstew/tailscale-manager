from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AppConfig(BaseModel):
    tailnet: str = Field(
        description="Tailscale tailnet name (e.g. example.com)"
    )
    state_dir: Path = Field(
        default=Path("/var/lib/tailscale-manager"),
        description="Directory for Terraform state and backups",
    )
    terraform_bin: Path = Field(
        default=Path("terraform"),
        description="Path to the terraform binary",
    )
    backup_count: int = Field(
        default=5,
        ge=1,
        description="Number of tfstate backups to retain",
    )
    tags: list[str] = Field(
        default_factory=list,
        description=(
            "ACL tags for managed auth keys. "
            "Set via TAILSCALE_MANAGER_TAGS as comma-separated values: "
            "e.g. TAILSCALE_MANAGER_TAGS='tag:server,tag:ci'. "
            "All tags must start with 'tag:' and must be owned by the OAuth client."
        ),
    )
    recreate_if_invalid: Literal["always", "never"] = Field(
        default="always",
        description=(
            "Whether to recreate the key if it becomes invalid (expired, revoked). "
            "Set via TAILSCALE_MANAGER_RECREATE_IF_INVALID."
        ),
    )
    provider_version: str = Field(
        default="~> 0.29",
        description=(
            "Tailscale Terraform provider version constraint. "
            "Set via TAILSCALE_MANAGER_PROVIDER_VERSION."
        ),
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        invalid = [t for t in v if not t.startswith("tag:")]
        if invalid:
            raise ValueError(
                f"All tags must start with 'tag:' prefix. "
                f"Invalid tags: {invalid}. "
                f"Example: ['tag:server', 'tag:ci']"
            )
        return v

    @classmethod
    def from_env(cls) -> AppConfig:
        tailnet = os.environ.get("TAILSCALE_TAILNET")
        if not tailnet:
            tailnet = os.environ.get("TAILSCALE_OAUTH_TAILNET", "")
        if not tailnet:
            raise ConfigurationError(
                "TAILSCALE_TAILNET environment variable is required"
            )
        state_dir = Path(
            os.environ.get(
                "TAILSCALE_MANAGER_STATE_DIR",
                "/var/lib/tailscale-manager",
            )
        )
        terraform_bin = Path(
            os.environ.get(
                "TAILSCALE_MANAGER_TERRAFORM_BIN",
                "terraform",
            )
        )
        backup_count = int(
            os.environ.get("TAILSCALE_MANAGER_BACKUP_COUNT", "5")
        )
        tags_raw = os.environ.get("TAILSCALE_MANAGER_TAGS", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        recreate_if_invalid = os.environ.get(
            "TAILSCALE_MANAGER_RECREATE_IF_INVALID", "always"
        )
        provider_version = os.environ.get(
            "TAILSCALE_MANAGER_PROVIDER_VERSION", "~> 0.29"
        )

        return cls(
            tailnet=tailnet,
            state_dir=state_dir,
            terraform_bin=terraform_bin,
            backup_count=backup_count,
            tags=tags,
            recreate_if_invalid=recreate_if_invalid,
            provider_version=provider_version,
        )


class ConfigurationError(Exception):
    pass
