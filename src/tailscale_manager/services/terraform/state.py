from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from tailscale_manager.core.acl_backup import backup_acl, restore_acl
from tailscale_manager.core.config import AppConfig
from tailscale_manager.core.constants import BACKUP_DIR, STATE_FILE
from tailscale_manager.repositories.state_repository import StateRepository


class TerraformStateService:
    def __init__(self, config: AppConfig, state_repo: StateRepository) -> None:
        self.config = config
        self.state_repo = state_repo

    def backup_state(self) -> Path | None:
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

    def restore_state(self) -> None:
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

    def backup_acl(self) -> None:
        if not self.config.acl_enable or not self.config.acl_policy:
            return
        backup_dir = self.config.state_dir / BACKUP_DIR
        self._fetch_and_backup_acl(backup_dir)

    def _fetch_and_backup_acl(self, backup_dir: Path) -> None:
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

    def restore_acl(self) -> None:
        if not self.config.acl_enable or not self.config.acl_policy:
            return
        backup_dir = self.config.state_dir / BACKUP_DIR
        restored = restore_acl(backup_dir)
        if restored is not None:
            self.config.acl_policy = restored
