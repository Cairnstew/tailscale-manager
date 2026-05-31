from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tailscale_manager.models.settings import TailnetSettings


class AppConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

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

    dns_nameservers: list[str] = Field(
        default_factory=list,
        description=(
            "Global DNS nameserver IPs. "
            "Set via TAILSCALE_MANAGER_DNS_NAMESERVERS as comma-separated values: "
            "e.g. TAILSCALE_MANAGER_DNS_NAMESERVERS='1.1.1.1,8.8.8.8'."
        ),
    )
    dns_magic_dns: bool = Field(
        default=False,
        description=(
            "Enable MagicDNS. "
            "Set via TAILSCALE_MANAGER_DNS_MAGIC_DNS."
        ),
    )
    dns_split_nameservers: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Per-domain split DNS (domain → list of nameserver IPs). Configurable via NixOS only.",
    )

    tailnet_settings: TailnetSettings | None = Field(
        default=None,
        description="Declarative tailnet-wide settings. Configurable via NixOS only.",
    )

    acl_enable: bool = Field(
        default=False,
        description=(
            "Enable ACL management. WARNING: applying overwrites the entire tailnet policy. "
            "Set via TAILSCALE_MANAGER_ACL_ENABLE."
        ),
    )
    acl_format: Literal["hujson", "json"] = Field(
        default="hujson",
        description=(
            "Policy file format. hujson is native Tailscale; json is standard JSON. "
            "Set via TAILSCALE_MANAGER_ACL_FORMAT."
        ),
    )
    acl_policy: str = Field(
        default="",
        description="Full ACL policy string (HuJSON or JSON). Populated from acl_policy_path if set.",
    )
    acl_policy_path: Path | None = Field(
        default=None,
        validation_alias="TAILSCALE_MANAGER_ACL_POLICY_PATH",
        description=(
            "Path to a file containing the ACL policy JSON. "
            "Set via TAILSCALE_MANAGER_ACL_POLICY_PATH. "
            "If set, the file content is loaded into acl_policy."
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

    @model_validator(mode="after")
    def load_policy_file(self) -> AppConfig:
        if self.acl_policy_path is not None:
            path = Path(self.acl_policy_path)
            if path.exists():
                self.acl_policy = path.read_text()
        return self

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

        dns_nameservers_raw = os.environ.get("TAILSCALE_MANAGER_DNS_NAMESERVERS", "")
        dns_nameservers = [s.strip() for s in dns_nameservers_raw.split(",") if s.strip()]

        dns_magic_dns = os.environ.get(
            "TAILSCALE_MANAGER_DNS_MAGIC_DNS", "false"
        ).lower() in ("true", "1", "yes")

        acl_enable = os.environ.get(
            "TAILSCALE_MANAGER_ACL_ENABLE", "false"
        ).lower() in ("true", "1", "yes")

        acl_format = os.environ.get(
            "TAILSCALE_MANAGER_ACL_FORMAT", "hujson"
        )

        acl_policy_path_raw = os.environ.get(
            "TAILSCALE_MANAGER_ACL_POLICY_PATH", ""
        )
        acl_policy_path = Path(acl_policy_path_raw) if acl_policy_path_raw else None

        return cls(
            tailnet=tailnet,
            state_dir=state_dir,
            terraform_bin=terraform_bin,
            backup_count=backup_count,
            tags=tags,
            recreate_if_invalid=recreate_if_invalid,
            provider_version=provider_version,
            dns_nameservers=dns_nameservers,
            dns_magic_dns=dns_magic_dns,
            acl_enable=acl_enable,
            acl_format=acl_format,
            acl_policy_path=acl_policy_path,
        )


class ConfigurationError(Exception):
    pass
