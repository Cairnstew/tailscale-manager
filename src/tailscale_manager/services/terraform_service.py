from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from tailscale_manager.core.config import AppConfig
from tailscale_manager.core.constants import (
    BACKUP_DIR,
    MAIN_TF_FILE,
    PROVIDER_VERSION,
    STATE_FILE,
)
from tailscale_manager.core.exceptions import TerraformError
from tailscale_manager.repositories.state_repository import StateRepository
from tailscale_manager.utils.subprocess_helpers import run_terraform


class TerraformService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state_repo = StateRepository(config.state_dir)

    def generate_config(self) -> Path:
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        tf_path = self.config.state_dir / MAIN_TF_FILE

        tags = self.config.tags

        cfg = {
            "terraform": {
                "required_providers": {
                    "tailscale": {
                        "source": "tailscale/tailscale",
                        "version": PROVIDER_VERSION,
                    }
                }
            },
            "provider": {
                "tailscale": {}
            },
            "resource": {
                "tailscale_tailnet_key": {
                    "managed_key": {
                        "reusable": True,
                        "ephemeral": False,
                        "preauthorized": True,
                        "tags": tags,
                        "recreate_if_invalid": "always",
                    }
                }
            },
        }

        tf_path.write_text(json.dumps(cfg, indent=2) + "\n")
        return tf_path

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
            self.generate_config()
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
