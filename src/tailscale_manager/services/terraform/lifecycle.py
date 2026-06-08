from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone

from tailscale_manager.core.config import AppConfig
from tailscale_manager.core.exceptions import TerraformError
from tailscale_manager.models.agenix_sync import AgenixSyncResult
from tailscale_manager.repositories.state_repository import StateRepository
from tailscale_manager.services.terraform.config_writer import TerraformConfigWriter
from tailscale_manager.services.terraform.state import TerraformStateService
from tailscale_manager.utils.subprocess import TerraformRunner

_logger = logging.getLogger(__name__)


def parse_plan_json_output(output: str) -> dict:
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


class TerraformLifecycleService:
    def __init__(
        self,
        config: AppConfig,
        config_writer: TerraformConfigWriter,
        state_service: TerraformStateService,
        terraform_runner: TerraformRunner,
        state_repo: StateRepository,
    ) -> None:
        self.config = config
        self.config_writer = config_writer
        self.state_service = state_service
        self.terraform_runner = terraform_runner
        self.state_repo = state_repo

    def init(self) -> str:
        return self.terraform_runner.run(
            args=["init", "-input=false"],
            cwd=self.config.state_dir,
        )

    def plan(self) -> str:
        return self.terraform_runner.run(
            args=["plan", "-input=false", "-detailed-exitcode"],
            cwd=self.config.state_dir,
            timeout=60,
        )

    def plan_summary(self) -> dict:
        output = self.terraform_runner.run(
            args=["plan", "-input=false", "-detailed-exitcode", "-json"],
            cwd=self.config.state_dir,
            timeout=60,
        )
        return parse_plan_json_output(output)

    def _sync_key_to_agenix(
        self,
        key_value: str,
        secret_name: str,
        secret_scope: str,
        agenix_manager_bin: str,
    ) -> AgenixSyncResult:
        cmd = [
            agenix_manager_bin,
            "new",
            "--name", secret_name,
            "--scope", secret_scope,
            "--stdin",
            "--overwrite",
        ]
        try:
            proc = subprocess.run(
                cmd,
                input=key_value,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            _logger.warning(
                "agenix-manager timed out for secret '%s'", secret_name
            )
            return AgenixSyncResult(
                status="error",
                secret_name=secret_name,
                error_message="timeout after 60s",
            )

        if proc.returncode == 0:
            _logger.info(
                "agenix-manager: secret '%s' synced ok", secret_name
            )
            return AgenixSyncResult(status="ok", secret_name=secret_name)

        stderr = proc.stderr.strip() if proc.stderr else f"exit code {proc.returncode}"
        _logger.warning(
            "agenix-manager failed for secret '%s': %s", secret_name, stderr
        )
        return AgenixSyncResult(
            status="error",
            secret_name=secret_name,
            error_message=stderr,
        )

    def apply(self) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        env = self.config.terraform_env_extra()
        try:
            backup_path = self.state_service.backup_state()
            self.state_service.backup_acl()
            self.config_writer.write_all()
            self.init()
            output = self.terraform_runner.run(
                args=[
                    "apply",
                    "-input=false",
                    "-auto-approve",
                    "-json",
                ],
                cwd=self.config.state_dir,
                env=env or None,
                timeout=180,
            )
            audit = parse_plan_json_output(output)
            result = {
                "timestamp": timestamp,
                "result": "ok",
                "backup_path": str(backup_path) if backup_path else None,
                "actions": audit["actions"],
                "add_count": audit["add_count"],
                "change_count": audit["change_count"],
                "remove_count": audit["remove_count"],
            }
            agenix_sync: AgenixSyncResult | None = None
            # TODO: multi-key — when authKeys grows beyond one entry, iterate over
            # all tailscale_tailnet_key resources and call _sync_key_to_agenix per
            # key, using the resource name as a suffix for the secret name.
            if self.config.agenix_integration_enabled:
                key_value = self.state_repo.get_managed_key_value()
                if key_value:
                    agenix_sync = self._sync_key_to_agenix(
                        key_value=key_value,
                        secret_name=self.config.agenix_secret_name,
                        secret_scope=self.config.agenix_secret_scope,
                        agenix_manager_bin=self.config.agenix_manager_bin,
                    )
                else:
                    agenix_sync = AgenixSyncResult(
                        status="skipped",
                        secret_name=self.config.agenix_secret_name,
                        error_message="no key found in tfstate",
                    )

            if agenix_sync is not None:
                result["agenix_sync"] = agenix_sync.to_dict()
        except TerraformError as exc:
            _logger.error(
                "Terraform apply failed (exit %d): %s",
                exc.exit_code,
                exc.stderr or exc.stdout,
            )
            self.state_service.restore_state()
            self.state_service.restore_acl()
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
            self.state_service.backup_state()
            self.terraform_runner.run(
                args=[
                    "destroy",
                    "-input=false",
                    "-auto-approve",
                ],
                cwd=self.config.state_dir,
                env=env or None,
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
            self.state_service.restore_state()
            result = {
                "timestamp": timestamp,
                "result": "error",
                "error_message": str(exc),
                "action": "destroy",
            }
        self.state_repo.write_last_apply(result)
        return result


