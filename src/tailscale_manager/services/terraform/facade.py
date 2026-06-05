from __future__ import annotations

from pathlib import Path

from tailscale_manager.core.config import AppConfig
from tailscale_manager.repositories.state_repository import StateRepository
from tailscale_manager.services.terraform.config_writer import TerraformConfigWriter
from tailscale_manager.services.terraform.lifecycle import TerraformLifecycleService
from tailscale_manager.services.terraform.state import TerraformStateService
from tailscale_manager.utils.subprocess import TerraformRunner


class TerraformService:
    """Convenience facade that composes the decomposed terraform services.

    Creates TerraformConfigWriter, TerraformStateService, TerraformRunner,
    and TerraformLifecycleService from a single AppConfig.  Suitable for
    CLI commands and simple use cases.  For finer control (e.g. injecting
    mocks in tests), use the individual service classes directly.
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state_repo = StateRepository(config.state_dir)
        self._config_writer = TerraformConfigWriter(config)
        self._state_service = TerraformStateService(config, self.state_repo)
        self._terraform_runner = TerraformRunner(config.terraform_bin)
        self._lifecycle = TerraformLifecycleService(
            config=config,
            config_writer=self._config_writer,
            state_service=self._state_service,
            terraform_runner=self._terraform_runner,
            state_repo=self.state_repo,
        )

    def write_configs(self) -> bool:
        return self._config_writer.write_all()

    def init(self) -> str:
        return self._lifecycle.init()

    def plan(self) -> str:
        return self._lifecycle.plan()

    def plan_summary(self) -> dict:
        return self._lifecycle.plan_summary()

    def apply(self) -> dict:
        return self._lifecycle.apply()

    def destroy(self) -> dict:
        return self._lifecycle.destroy()

    def _backup_state(self) -> Path | None:
        return self._state_service.backup_state()

    def _restore_state(self) -> None:
        self._state_service.restore_state()

    def _backup_acl(self) -> None:
        self._state_service.backup_acl()

    def _restore_acl(self) -> None:
        self._state_service.restore_acl()
