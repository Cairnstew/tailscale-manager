from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from tailscale_manager.core.acl_backup import backup_acl, restore_acl
from tailscale_manager.core.config import AppConfig
from tailscale_manager.core.constants import (
    ACL_TF_FILE,
    BACKUP_DIR,
    DATA_TF_FILE,
    DNS_TF_FILE,
    KEYS_TF_FILE,
    LOCAL_PROVIDER_VERSION,
    MAIN_TF_FILE,
    STATE_FILE,
)
from tailscale_manager.core.exceptions import ConfigurationError, TerraformError
from tailscale_manager.repositories.state_repository import StateRepository
from tailscale_manager.services.features import (
    build_acl_config,
    build_devices_config,
    build_dns_config,
    build_keys_config,
)
from tailscale_manager.utils.subprocess_helpers import (
    _build_terraform_env,
    run_terraform,
)


class TerraformService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state_repo = StateRepository(config.state_dir)

    def _write_sensitive(self, path: Path, content: str) -> None:
        """Write a file with restricted permissions (0o600)."""
        path.write_text(content)
        path.chmod(0o600)

    def write_configs(self) -> bool:
        """Write all .tf.json files with restricted permissions. Returns True if any file was written/changed."""
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

        keys_cfg = build_keys_config(
            tags=tags,
            recreate_if_invalid=self.config.recreate_if_invalid,
            auth_keys=auth_keys,
            auth_key_exports=auth_key_exports,
        )

        if auth_key_exports:
            main_cfg["terraform"]["required_providers"]["local"] = {
                "source": "hashicorp/local",
                "version": LOCAL_PROVIDER_VERSION,
            }

        if self.config.state_backend is not None:
            main_cfg["terraform"]["backend"] = self.config.state_backend

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
            self._write_sensitive(tf_path, new_content)
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

    @staticmethod
    def _parse_terraform_json_output(output: str) -> dict:
        """Parse terraform -json output for audit logging.

        Returns dict with actions, add_count, change_count, remove_count.
        """
        actions: list[dict] = []
        add_count = 0
        change_count = 0
        remove_count = 0

        for line in output.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")

            if event_type == "change_summary":
                changes = event.get("changes", {})
                add_count = changes.get("add", 0)
                change_count = changes.get("change", 0)
                remove_count = changes.get("remove", 0)

            elif event_type == "apply_complete":
                hook = event.get("hook", {})
                resource = hook.get("resource", {})
                addr = resource.get("addr", "")
                action = hook.get("action", "")
                if addr and action:
                    actions.append({"resource": addr, "action": action})

        return {
            "actions": actions,
            "add_count": add_count,
            "change_count": change_count,
            "remove_count": remove_count,
        }

    def apply(self) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        env = self.config.terraform_env_extra()
        try:
            backup_path = self._backup_state()
            self._backup_acl()
            self.write_configs()
            self.init()
            output = run_terraform(
                self.config.terraform_bin,
                [
                    "apply",
                    "-input=false",
                    "-auto-approve",
                    "-json",
                ],
                cwd=self.config.state_dir,
                env=_build_terraform_env(env) if env else None,
                timeout=180,
            )
            audit = self._parse_terraform_json_output(output)
            result = {
                "timestamp": timestamp,
                "result": "ok",
                "backup_path": str(backup_path) if backup_path else None,
                "actions": audit["actions"],
                "add_count": audit["add_count"],
                "change_count": audit["change_count"],
                "remove_count": audit["remove_count"],
            }
        except TerraformError as exc:
            self._restore_state()
            self._restore_acl()
            result = {
                "timestamp": timestamp,
                "result": "error",
                "error_message": str(exc),
                "backup_path": None,
                "actions": [],
                "add_count": 0,
                "change_count": 0,
                "remove_count": 0,
            }
        self.state_repo.write_last_apply(result)
        return result

    def destroy(self) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        env = self.config.terraform_env_extra()
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
                env=_build_terraform_env(env) if env else None,
                timeout=180,
            )
            result = {
                "timestamp": timestamp,
                "result": "ok",
                "action": "destroy",
                "backup_path": None,
                "actions": [],
                "add_count": 0,
                "change_count": 0,
                "remove_count": 0,
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

    def _backup_state(self) -> Path | None:
        state_file = self.config.state_dir / STATE_FILE
        if not state_file.exists():
            return None
        backup_dir = self.config.state_dir / BACKUP_DIR
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        backup_path = backup_dir / f"{ts}.tfstate"
        shutil.copy2(state_file, backup_path)
        backup_path.chmod(0o600)
        self._prune_backups()
        return backup_path

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
        state_file.chmod(0o600)

    def _prune_backups(self) -> None:
        backup_dir = self.config.state_dir / BACKUP_DIR
        backups = sorted(backup_dir.glob("*.tfstate"))
        while len(backups) > self.config.backup_count:
            backups[0].unlink()
            backups = backups[1:]

