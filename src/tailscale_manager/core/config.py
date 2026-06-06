from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tailscale_manager.core.exceptions import ConfigurationError


class AppConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tailnet: str = Field(
        default="-",
        description=(
            "Tailscale tailnet name. Use '-' to auto-resolve from the OAuth credential. "
            "This is the recommended default for most users."
        ),
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

    state_backend: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional Terraform backend configuration. "
            "Loaded from TAILSCALE_MANAGER_STATE_BACKEND env var (JSON string). "
            "When set, placed verbatim under the 'backend' key in the terraform block."
        ),
    )

    auth_keys: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Auth keys declared via Nix module. "
            "Loaded from TAILSCALE_MANAGER_AUTH_KEYS_PATH JSON file."
        ),
    )
    auth_keys_path: Path | None = Field(
        default=None,
        validation_alias="TAILSCALE_MANAGER_AUTH_KEYS_PATH",
        description=(
            "Path to a JSON file containing declared auth keys. "
            "Set via TAILSCALE_MANAGER_AUTH_KEYS_PATH."
        ),
    )
    auth_key_exports: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description=(
            "Map of key name → {path, owner, group, mode} for keys with exportPath.enable = true. "
            "Auto-populated from TAILSCALE_MANAGER_AUTH_KEY_EXPORTS env var (JSON)."
        ),
    )

    agenix_integration_enabled: bool = Field(
        default=False,
        description=(
            "After a successful terraform apply, extract the generated Tailscale "
            "auth key from tfstate and push it into agenix-manager as an encrypted "
            "secret. Set via TAILSCALE_MANAGER_AGENIX_ENABLE."
        ),
    )
    agenix_secret_name: str = Field(
        default="tailscale-auth-key",
        description=(
            "Name of the agenix secret to create or overwrite. "
            "Set via TAILSCALE_MANAGER_AGENIX_SECRET_NAME."
        ),
    )
    agenix_secret_scope: str = Field(
        default="systems",
        description=(
            "Key scope passed to agenix-manager new --scope. "
            "Set via TAILSCALE_MANAGER_AGENIX_SECRET_SCOPE."
        ),
    )
    agenix_manager_bin: str = Field(
        default="agenix-manager",
        description=(
            "Path to the agenix-manager binary. "
            "Set via TAILSCALE_MANAGER_AGENIX_BIN."
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

    oauth_client_id: str = Field(
        default="",
        description="Tailscale OAuth client ID. Loaded from LoadCredential file or TAILSCALE_OAUTH_CLIENT_ID.",
    )
    oauth_client_secret: str = Field(
        default="",
        description="Tailscale OAuth client secret. Loaded from LoadCredential file or TAILSCALE_OAUTH_CLIENT_SECRET.",
    )

    @field_validator("tailnet")
    @classmethod
    def validate_tailnet(cls, v: str) -> str:
        if v == "":
            return "-"
        return v

    @field_validator("auth_key_exports")
    @classmethod
    def validate_auth_key_exports(cls, v: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        required_keys = {"path", "owner", "group", "mode"}
        for name, entry in v.items():
            missing = required_keys - set(entry.keys())
            if missing:
                raise ValueError(
                    f"auth_key_exports[{name!r}] is missing required keys: "
                    f"{', '.join(sorted(missing))}. "
                    f"Each export must have path, owner, group, and mode."
                )
        return v

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

    @model_validator(mode="before")
    @classmethod
    def load_credentials(cls, data: Any) -> Any:
        """Load OAuth credentials from LoadCredential file or environment.

        Priority:
        1. CREDENTIALS_DIRECTORY env var -> read $CREDENTIALS_DIRECTORY/tailscale-oauth
        2. TAILSCALE_OAUTH_CLIENT_ID / TAILSCALE_OAUTH_CLIENT_SECRET env vars (backwards compat)
        """
        if not isinstance(data, dict):
            return data
        if data.get("oauth_client_id") and data.get("oauth_client_secret"):
            return data
        creds_dir = os.environ.get("CREDENTIALS_DIRECTORY", "")
        if creds_dir:
            cred_file = Path(creds_dir) / "tailscale-oauth"
            if cred_file.exists():
                creds: dict[str, str] = {}
                for line in cred_file.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    key, _, value = line.partition("=")
                    creds[key.strip()] = value.strip()
                data.setdefault("oauth_client_id", creds.get("TAILSCALE_OAUTH_CLIENT_ID", ""))
                data.setdefault("oauth_client_secret", creds.get("TAILSCALE_OAUTH_CLIENT_SECRET", ""))
                return data
        data.setdefault("oauth_client_id", os.environ.get("TAILSCALE_OAUTH_CLIENT_ID", ""))
        data.setdefault("oauth_client_secret", os.environ.get("TAILSCALE_OAUTH_CLIENT_SECRET", ""))
        return data

    @model_validator(mode="after")
    def load_policy_file(self) -> AppConfig:
        if self.acl_policy_path is not None:
            path = Path(self.acl_policy_path)
            if path.exists():
                self.acl_policy = path.read_text()
        if self.auth_keys_path is not None:
            path = Path(self.auth_keys_path)
            if path.exists():
                self.auth_keys = json.loads(path.read_text())
        return self

    def assert_credentials(self) -> None:
        """Validate that all credential-requiring fields are present.

        This is called explicitly by commands that need credentials (plan, apply, destroy),
        NOT on construction, so that AppConfig can be instantiated in dev/CI, unit tests,
        and the doctor command's partial-config path without requiring credentials.

        Only the first error is raised; the doctor command is the right place to
        enumerate all failures at once.
        """
        if not self.oauth_client_id:
            raise ConfigurationError(
                message="OAuth client ID is required but was not found",
                field="TAILSCALE_OAUTH_CLIENT_ID",
                hint=(
                    "Set TAILSCALE_OAUTH_CLIENT_ID in your credentials file "
                    "(NixOS: credentialsFile) or environment (dev: export "
                    "TAILSCALE_OAUTH_CLIENT_ID=...)"
                ),
            )
        if not self.oauth_client_secret:
            raise ConfigurationError(
                message="OAuth client secret is required but was not found",
                field="TAILSCALE_OAUTH_CLIENT_SECRET",
                hint=(
                    "Set TAILSCALE_OAUTH_CLIENT_SECRET in your credentials file "
                    "(NixOS: credentialsFile) or environment (dev: export "
                    "TAILSCALE_OAUTH_CLIENT_SECRET=...)"
                ),
            )

    def terraform_env_extra(self) -> dict[str, str]:
        """Extra env vars needed by the Tailscale Terraform provider."""
        return {
            "TAILSCALE_OAUTH_CLIENT_ID": self.oauth_client_id,
            "TAILSCALE_OAUTH_CLIENT_SECRET": self.oauth_client_secret,
        }

    @classmethod
    def from_env(cls) -> AppConfig:
        tailnet = os.environ.get("TAILSCALE_TAILNET", "-")
        if not tailnet:
            tailnet = os.environ.get("TAILSCALE_OAUTH_TAILNET", "-")
        if not tailnet:
            tailnet = "-"
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

        agenix_integration_enabled = os.environ.get(
            "TAILSCALE_MANAGER_AGENIX_ENABLE", ""
        ).lower() in ("true", "1", "yes")
        agenix_secret_name = os.environ.get(
            "TAILSCALE_MANAGER_AGENIX_SECRET_NAME", "tailscale-auth-key"
        )
        agenix_secret_scope = os.environ.get(
            "TAILSCALE_MANAGER_AGENIX_SECRET_SCOPE", "systems"
        )
        agenix_manager_bin = os.environ.get(
            "TAILSCALE_MANAGER_AGENIX_BIN", "agenix-manager"
        )

        state_backend_raw = os.environ.get("TAILSCALE_MANAGER_STATE_BACKEND", "")
        state_backend: dict[str, Any] | None = None
        if state_backend_raw:
            try:
                state_backend = json.loads(state_backend_raw)
            except json.JSONDecodeError:
                state_backend = None

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

        auth_keys_path_raw = os.environ.get(
            "TAILSCALE_MANAGER_AUTH_KEYS_PATH", ""
        )
        auth_keys_path = Path(auth_keys_path_raw) if auth_keys_path_raw else None

        auth_key_exports_raw = os.environ.get("TAILSCALE_MANAGER_AUTH_KEY_EXPORTS", "{}")
        try:
            auth_key_exports = json.loads(auth_key_exports_raw)
        except json.JSONDecodeError:
            auth_key_exports = {}

        return cls(
            tailnet=tailnet,
            state_dir=state_dir,
            terraform_bin=terraform_bin,
            backup_count=backup_count,
            tags=tags,
            recreate_if_invalid=recreate_if_invalid,
            provider_version=provider_version,
            state_backend=state_backend,
            dns_nameservers=dns_nameservers,
            dns_magic_dns=dns_magic_dns,
            acl_enable=acl_enable,
            acl_format=acl_format,
            acl_policy_path=acl_policy_path,
            auth_keys_path=auth_keys_path,
            auth_key_exports=auth_key_exports,
            agenix_integration_enabled=agenix_integration_enabled,
            agenix_secret_name=agenix_secret_name,
            agenix_secret_scope=agenix_secret_scope,
            agenix_manager_bin=agenix_manager_bin,
        )
