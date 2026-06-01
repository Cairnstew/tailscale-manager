from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from tailscale_manager.core.config import AppConfig
from tailscale_manager.core.constants import (
    BACKUP_DIR,
    KEYS_TF_FILE,
    DATA_TF_FILE,
    DNS_TF_FILE,
    ACL_TF_FILE,
    MAIN_TF_FILE,
    STATE_FILE,
)
from tailscale_manager.core.acl_backup import backup_acl, prune_acl_backups, restore_acl
from tailscale_manager.core.exceptions import TerraformError
from tailscale_manager.repositories.state_repository import StateRepository
from tailscale_manager.services.features import (
    build_acl_config,
    build_devices_config,
    build_dns_config,
)
from tailscale_manager.utils.subprocess_helpers import run_terraform


class TerraformService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state_repo = StateRepository(config.state_dir)

    def write_configs(self) -> bool:
        """Write all .tf.json files. Returns True if any file was written/changed."""
        self.config.state_dir.mkdir(parents=True, exist_ok=True)

        tags = self.config.tags

        main_cfg = {
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

        keys_cfg = {
            "resource": {
                "tailscale_tailnet_key": {
                    "managed_key": {
                        "reusable": True,
                        "ephemeral": False,
                        "preauthorized": True,
                        "tags": tags,
                        "recreate_if_invalid": self.config.recreate_if_invalid,
                    }
                }
            },
        }

        data_cfg = build_devices_config()

        dns_cfg = build_dns_config(
            nameservers=self.config.dns_nameservers,
            magic_dns=self.config.dns_magic_dns,
            split_nameservers=self.config.dns_split_nameservers,
        )

        acl_cfg = build_acl_config(
            enable=self.config.acl_enable,
            fmt=self.config.acl_format,
            policy=self.config.acl_policy,
        )

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
            tf_path.write_text(new_content)
            written = True
        return written

    def init(self) -> str:
        return run_terraform(
            self.config.terraform_bin,
            ["init", "-input=false"],
            cwd=self.config.state_dir,
        )

    def plan(self) -> str:
        return run_terraform(
            self.config.terraform_bin,
            ["plan", "-input=false", "-detailed-exitcode"],
            cwd=self.config.state_dir,
            timeout=60,
        )

    def apply(self) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            self._backup_state()
            self._backup_acl()
            self.write_configs()
            self.init()
            run_terraform(
                self.config.terraform_bin,
                [
                    "apply",
                    "-input=false",
                    "-auto-approve",
                ],
                cwd=self.config.state_dir,
                timeout=180,
            )
            result = {
                "timestamp": timestamp,
                "result": "ok",
            }
        except TerraformError as exc:
            self._restore_state()
            self._restore_acl()
            result = {
                "timestamp": timestamp,
                "result": "error",
                "error_message": str(exc),
            }
        self.state_repo.write_last_apply(result)
        return result

    def destroy(self) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            self._backup_state()
            run_terraform(
                self.config.terraform_bin,
                [
                    "destroy",
                    "-input=false",
                    "-auto-approve",
                ],
                cwd=self.config.state_dir,
                timeout=180,
            )
            result = {
                "timestamp": timestamp,
                "result": "ok",
                "action": "destroy",
            }
        except TerraformError as exc:
            self._restore_state()
            result = {
                "timestamp": timestamp,
                "result": "error",
                "error_message": str(exc),
                "action": "destroy",
            }
        self.state_repo.write_last_apply(result)
        return result

    def _backup_acl(self) -> None:
        """Backup current ACL policy if ACL management is enabled."""
        if not self.config.acl_enable or not self.config.acl_policy:
            return
        backup_dir = self.config.state_dir / BACKUP_DIR
        self._fetch_and_backup_acl(backup_dir)

    def _fetch_and_backup_acl(self, backup_dir: Path) -> None:
        """Fetch current ACL from Tailscale API and write to backup file.
        
        This attempts to read the current ACL from the Terraform state (if it
        was previously applied). If no state exists, it creates a backup marker
        noting that no prior policy was found.
        """
        state = self.state_repo.read_state()
        current_policy = ""
        if state:
            resources = state.get("resources", [])
            for res in resources:
                if res.get("type") != "tailscale_acl":
                    continue
                for instance in res.get("instances", []):
                    attrs = instance.get("attributes", {})
                    cached = attrs.get("acl", "")
                    if cached:
                        current_policy = cached
                        break
        if current_policy:
            backup_acl(backup_dir, current_policy)

    def _restore_acl(self) -> None:
        """Restore ACL from the most recent backup if ACL management is enabled."""
        if not self.config.acl_enable or not self.config.acl_policy:
            return
        backup_dir = self.config.state_dir / BACKUP_DIR
        restored = restore_acl(backup_dir)
        if restored is not None:
            self.config.acl_policy = restored

    def _backup_state(self) -> None:
        state_file = self.config.state_dir / STATE_FILE
        if not state_file.exists():
            return
        backup_dir = self.config.state_dir / BACKUP_DIR
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        backup_path = backup_dir / f"{ts}.tfstate"
        shutil.copy2(state_file, backup_path)
        self._prune_backups()

    def _restore_state(self) -> None:
        backup_dir = self.config.state_dir / BACKUP_DIR
        if not backup_dir.exists():
            return
        backups = sorted(backup_dir.glob("*.tfstate"))
        if not backups:
            return
        latest = backups[-1]
        state_file = self.config.state_dir / STATE_FILE
        shutil.copy2(latest, state_file)

    def _prune_backups(self) -> None:
        backup_dir = self.config.state_dir / BACKUP_DIR
        backups = sorted(backup_dir.glob("*.tfstate"))
        while len(backups) > self.config.backup_count:
            backups[0].unlink()
            backups = backups[1:]
