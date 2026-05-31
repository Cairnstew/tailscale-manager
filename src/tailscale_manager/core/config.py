from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


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
        description="Tags to apply to the managed auth key",
    )

    @classmethod
    def from_env(cls) -> AppConfig:
        tailnet = os.environ.get("TAILSCALE_TAILNET")
        if not tailnet:
            # Fallback: the Tailscale Terraform provider's canonical env var
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

        return cls(
            tailnet=tailnet,
            state_dir=state_dir,
            terraform_bin=terraform_bin,
            backup_count=backup_count,
            tags=tags,
        )


class ConfigurationError(Exception):
    pass
