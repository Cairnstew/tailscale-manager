from __future__ import annotations

import json
from pathlib import Path

from tailscale_manager.core.config import AppConfig
from tailscale_manager.core.constants import (
    ACL_TF_FILE,
    DATA_TF_FILE,
    DNS_TF_FILE,
    KEYS_TF_FILE,
    LOCAL_PROVIDER_VERSION,
    MAIN_TF_FILE,
    STATE_FILE,
)
from tailscale_manager.core.exceptions import ConfigurationError
from tailscale_manager.services.features import (
    AclFeatureBuilder,
    DeviceFeatureBuilder,
    DnsFeatureBuilder,
    KeyFeatureBuilder,
)


class TerraformConfigWriter:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def write_all(self) -> bool:
        self.config.state_dir.mkdir(parents=True, exist_ok=True)

        if self.config.state_backend is not None:
            local_state = self.config.state_dir / STATE_FILE
            if local_state.exists():
                raise ConfigurationError(
                    message=(
                        f"local terraform.tfstate exists at {local_state} but a remote backend is configured. "
                        f"Run `terraform state push` to migrate state, then remove the local file, or unset stateBackend."
                    ),
                    field="TAILSCALE_MANAGER_STATE_BACKEND",
                    hint="Remove the local tfstate file or unset the backend configuration",
                )

        tags = self.config.tags
        auth_keys = self.config.auth_keys or None
        auth_key_exports = self.config.auth_key_exports or None

        main_cfg: dict = {
            "terraform": {
                "required_providers": {
                    "tailscale": {
                        "source": "tailscale/tailscale",
                        "version": self.config.provider_version,
                    }
                }
            },
            "provider": {
                "tailscale": {}
            },
        }

        keys_cfg = KeyFeatureBuilder(
            tags=tags,
            recreate_if_invalid=self.config.recreate_if_invalid,
            auth_keys=auth_keys,
            auth_key_exports=auth_key_exports,
        ).build()

        if auth_key_exports:
            main_cfg["terraform"]["required_providers"]["local"] = {
                "source": "hashicorp/local",
                "version": LOCAL_PROVIDER_VERSION,
            }

        if self.config.state_backend is not None:
            main_cfg["terraform"]["backend"] = self.config.state_backend

        data_cfg = DeviceFeatureBuilder().build()

        dns_cfg = DnsFeatureBuilder(
            nameservers=self.config.dns_nameservers,
            magic_dns=self.config.dns_magic_dns,
            split_nameservers=self.config.dns_split_nameservers,
        ).build()

        acl_cfg = AclFeatureBuilder(
            enable=self.config.acl_enable,
            fmt=self.config.acl_format,
            policy=self.config.acl_policy,
        ).build()

        files: dict[str, dict] = {
            MAIN_TF_FILE: main_cfg,
            KEYS_TF_FILE: keys_cfg,
            DATA_TF_FILE: data_cfg,
        }

        if dns_cfg:
            files[DNS_TF_FILE] = dns_cfg

        if acl_cfg:
            files[ACL_TF_FILE] = acl_cfg

        written = False
        for filename, cfg in files.items():
            tf_path = self.config.state_dir / filename
            new_content = json.dumps(cfg, indent=2) + "\n"
            if tf_path.exists():
                existing = tf_path.read_text()
                if existing == new_content:
                    continue
            self._write_sensitive(tf_path, new_content)
            written = True
        return written

    def _write_sensitive(self, path: Path, content: str) -> None:
        path.write_text(content)
        path.chmod(0o600)
