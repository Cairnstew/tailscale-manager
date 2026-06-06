from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tailscale_manager.core.exceptions import TerraformError
from tailscale_manager.models.agenix_sync import AgenixSyncResult
from tailscale_manager.services.terraform.lifecycle import (
    TerraformLifecycleService,
)


def _make_service(**config_overrides: object) -> TerraformLifecycleService:
    config = MagicMock()
    config.acl_enable = False
    config.acl_policy = ""
    config.agenix_integration_enabled = False
    for key, value in config_overrides.items():
        setattr(config, key, value)
    return TerraformLifecycleService(
        config=config,
        config_writer=MagicMock(),
        state_service=MagicMock(),
        terraform_runner=MagicMock(),
        state_repo=MagicMock(),
    )


class TestSyncKeyToAgenix:
    def test_sync_ok(self) -> None:
        svc = _make_service()
        with patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok\n", stderr=""
            )
            result = svc._sync_key_to_agenix(
                key_value="tskey-auth-k123",
                secret_name="tailscale-auth-key",
                secret_scope="systems",
                agenix_manager_bin="/usr/bin/agenix-manager",
            )

        assert result.status == "ok"
        assert result.secret_name == "tailscale-auth-key"
        assert result.error_message is None

        mock_run.assert_called_once_with(
            [
                "/usr/bin/agenix-manager",
                "new",
                "--name", "tailscale-auth-key",
                "--scope", "systems",
                "--stdin",
                "--overwrite",
            ],
            input="tskey-auth-k123",
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_sync_error_nonzero(self) -> None:
        svc = _make_service()
        with patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="some error\n"
            )
            result = svc._sync_key_to_agenix(
                key_value="tskey-auth-k123",
                secret_name="tailscale-auth-key",
                secret_scope="systems",
                agenix_manager_bin="agenix-manager",
            )

        assert result.status == "error"
        assert result.secret_name == "tailscale-auth-key"
        assert result.error_message == "some error"

    def test_sync_timeout(self) -> None:
        svc = _make_service()
        with patch.object(subprocess, "run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["agenix-manager"], timeout=60,
            )
            result = svc._sync_key_to_agenix(
                key_value="tskey-auth-k123",
                secret_name="tailscale-auth-key",
                secret_scope="systems",
                agenix_manager_bin="agenix-manager",
            )

        assert result.status == "error"
        assert result.error_message == "timeout after 60s"

    def test_key_never_in_subprocess_log(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG)
        svc = _make_service()
        with patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="generic error"
            )
            svc._sync_key_to_agenix(
                key_value="tskey-auth-secret-value",
                secret_name="tailscale-auth-key",
                secret_scope="systems",
                agenix_manager_bin="agenix-manager",
            )

        for record in caplog.records:
            assert "tskey-auth-secret-value" not in record.getMessage()

    def test_sync_returns_agenix_sync_result(self) -> None:
        svc = _make_service()
        with patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok\n", stderr=""
            )
            result = svc._sync_key_to_agenix(
                key_value="tskey-auth-k123",
                secret_name="tailscale-auth-key",
                secret_scope="systems",
                agenix_manager_bin="agenix-manager",
            )

        assert isinstance(result, AgenixSyncResult)
        assert result.to_dict() == {
            "status": "ok",
            "secret_name": "tailscale-auth-key",
            "error_message": None,
        }


class TestApplyHookWiring:
    def test_hook_not_called_when_disabled(self) -> None:
        svc = _make_service(agenix_integration_enabled=False)
        svc.terraform_runner.run.return_value = (
            '{"type":"change_summary","changes":{"add":1,"change":0,"remove":0}}\n'
            '{"type":"apply_complete","hook":{"resource":{"addr":"tailscale_tailnet_key.managed_key"},"action":"create"}}\n'
        )
        svc.state_repo.get_managed_key_value.return_value = "tskey-auth-k123"
        svc.state_service.backup_state.return_value = None
        svc.config_writer.write_all.return_value = True

        with patch.object(svc, "_sync_key_to_agenix") as mock_sync:
            result = svc.apply()

        assert result["result"] == "ok"
        mock_sync.assert_not_called()

    def test_hook_not_called_on_apply_error(self) -> None:
        svc = _make_service(agenix_integration_enabled=True)
        svc.terraform_runner.run.side_effect = TerraformError(
            command="apply",
            exit_code=1,
            stdout="",
            stderr="apply failed",
        )

        with patch.object(svc, "_sync_key_to_agenix") as mock_sync:
            result = svc.apply()

        assert result["result"] == "error"
        mock_sync.assert_not_called()

    def test_hook_skipped_when_no_key(self) -> None:
        svc = _make_service(agenix_integration_enabled=True)
        svc.terraform_runner.run.return_value = (
            '{"type":"change_summary","changes":{"add":0,"change":0,"remove":0}}\n'
            '{"type":"apply_complete","hook":{}}\n'
        )
        svc.state_repo.get_managed_key_value.return_value = None
        svc.state_service.backup_state.return_value = None
        svc.config_writer.write_all.return_value = True

        result = svc.apply()

        assert result["result"] == "ok"
        assert result["agenix_sync"]["status"] == "skipped"
        assert result["agenix_sync"]["error_message"] == "no key found in tfstate"

    def test_agenix_error_does_not_poison_result(self) -> None:
        svc = _make_service(agenix_integration_enabled=True)
        svc.terraform_runner.run.return_value = (
            '{"type":"change_summary","changes":{"add":1,"change":0,"remove":0}}\n'
            '{"type":"apply_complete","hook":{"resource":{"addr":"tailscale_tailnet_key.managed_key"},"action":"create"}}\n'
        )
        svc.state_repo.get_managed_key_value.return_value = "tskey-auth-k123"
        svc.state_service.backup_state.return_value = None
        svc.config_writer.write_all.return_value = True

        with patch.object(svc, "_sync_key_to_agenix") as mock_sync:
            mock_sync.return_value = AgenixSyncResult(
                status="error",
                secret_name="tailscale-auth-key",
                error_message="permission denied",
            )
            result = svc.apply()

        assert result["result"] == "ok"
        assert result["agenix_sync"]["status"] == "error"
        assert result["agenix_sync"]["error_message"] == "permission denied"

    def test_agenix_ok_written_to_last_apply(self) -> None:
        svc = _make_service(agenix_integration_enabled=True)
        svc.terraform_runner.run.return_value = (
            '{"type":"change_summary","changes":{"add":1,"change":0,"remove":0}}\n'
            '{"type":"apply_complete","hook":{"resource":{"addr":"tailscale_tailnet_key.managed_key"},"action":"create"}}\n'
        )
        svc.state_repo.get_managed_key_value.return_value = "tskey-auth-k123"
        svc.state_service.backup_state.return_value = None
        svc.config_writer.write_all.return_value = True

        with patch.object(svc, "_sync_key_to_agenix") as mock_sync:
            mock_sync.return_value = AgenixSyncResult(
                status="ok",
                secret_name="tailscale-auth-key",
            )
            result = svc.apply()

        assert result["result"] == "ok"
        assert result["agenix_sync"]["status"] == "ok"
        assert result["agenix_sync"]["secret_name"] == "tailscale-auth-key"

        svc.state_repo.write_last_apply.assert_called()
        written = svc.state_repo.write_last_apply.call_args[0][0]
        assert "agenix_sync" in written
        assert written["agenix_sync"]["status"] == "ok"
