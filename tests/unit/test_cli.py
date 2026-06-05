from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tailscale_manager.cli import (
    _convert_pydantic_error,
    _render_configuration_error,
    _render_terraform_error,
    app,
)
from tailscale_manager.core.exceptions import ConfigurationError, TerraformError

runner = CliRunner()


def test_help_shows_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ["init", "plan", "apply", "destroy", "status", "devices", "doctor", "backup-state", "restore-state", "auth-keys"]:
        assert cmd in result.stdout


def test_status_json_no_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TAILSCALE_TAILNET", "test.ts.net")
    monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "last_apply" in data
    assert "managed_keys" in data


def test_status_json_with_last_apply_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TAILSCALE_TAILNET", "test.ts.net")
    monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))

    last_apply = tmp_path / "last-apply.json"
    last_apply.write_text(
        json.dumps({"timestamp": "2024-01-01T00:00:00", "result": "error", "error_message": "oops"})
    )

    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["last_apply"]["result"] == "error"


def test_status_json_with_last_apply(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TAILSCALE_TAILNET", "test.ts.net")
    monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))

    last_apply = tmp_path / "last-apply.json"
    last_apply.write_text(
        json.dumps({"timestamp": "2024-01-01T00:00:00", "result": "ok"})
    )

    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["last_apply"]["result"] == "ok"


def test_init_shows_scope_warnings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TAILSCALE_TAILNET", "test.ts.net")
    monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("TAILSCALE_MANAGER_DNS_NAMESERVERS", "1.1.1.1")
    monkeypatch.setenv("TAILSCALE_MANAGER_ACL_ENABLE", "true")
    result = runner.invoke(app, ["init"])
    # preflight warnings print before terraform init, even if init fails
    assert "Preflight" in result.stdout
    assert "dns:write" in result.stdout
    assert "tailnet:acls" in result.stdout


def test_init_no_scope_warnings_when_not_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TAILSCALE_TAILNET", "test.ts.net")
    monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
    result = runner.invoke(app, ["init"])
    assert "Preflight" not in result.stdout


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "tailscale-manager" in result.output


# ── Error rendering tests ────────────────────────────────────


class TestErrorRendering:
    def test_configure_error_renders_panel_text(self, capsys) -> None:
        err = ConfigurationError(
            message="OAuth client ID is required",
            field="TAILSCALE_OAUTH_CLIENT_ID",
            hint="Set it in your credentials file",
        )
        _render_configuration_error(err)
        captured = capsys.readouterr()
        assert "Configuration Error" in captured.err
        assert "TAILSCALE_OAUTH_CLIENT_ID" in captured.err
        assert "OAuth client ID is required" in captured.err
        assert "Set it in your credentials file" in captured.err

    def test_configure_error_with_docs_url(self, capsys) -> None:
        err = ConfigurationError(
            message="Something went wrong",
            field="SOME_FIELD",
            hint="Try this fix",
            docs_url="https://example.com/docs",
        )
        _render_configuration_error(err)
        captured = capsys.readouterr()
        assert "https://example.com/docs" in captured.err

    def test_terraform_error_renders_panel_text(self, capsys) -> None:
        err = TerraformError(
            command="apply",
            exit_code=1,
            stdout="",
            stderr="Error: Invalid provider configuration",
            hint="Check your configuration",
        )
        _render_terraform_error(err)
        captured = capsys.readouterr()
        assert "Terraform Error" in captured.err
        assert "terraform apply" in captured.err
        assert "Exit code: 1" in captured.err
        assert "Check your configuration" in captured.err

    def test_terraform_error_truncates_long_output(self, capsys) -> None:
        long_stderr = "\n".join(f"line {i}" for i in range(50))
        err = TerraformError(
            command="init",
            exit_code=1,
            stdout="",
            stderr=long_stderr,
        )
        _render_terraform_error(err)
        captured = capsys.readouterr()
        lines = captured.err.splitlines()
        output_lines = [l for l in lines if l.strip().startswith("line ")]
        assert len(output_lines) <= 20

    def test_convert_pydantic_error_from_tag_validation(self) -> None:
        from pydantic import ValidationError as PydanticValErr
        from tailscale_manager.core.config import AppConfig as Cfg

        try:
            Cfg(tailnet="test", tags=["bad"], state_dir=Path("/tmp"))
        except PydanticValErr as exc:
            cfg_err = _convert_pydantic_error(exc)
            assert isinstance(cfg_err, ConfigurationError)
            assert "tag:" in cfg_err.message


# ── Doctor tests ─────────────────────────────────────────────


class TestDoctor:
    def _clear_creds(self, monkeypatch) -> None:
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_ID", raising=False)
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_SECRET", raising=False)

    def test_doctor_empty_state_has_no_crash(self, tmp_path: Path, monkeypatch) -> None:
        self._clear_creds(monkeypatch)
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        monkeypatch.setenv("TAILSCALE_MANAGER_TERRAFORM_BIN", "/nonexistent/tf")
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "Checking tailscale-manager configuration" in result.stdout
        assert "Overall:" in result.stdout

    def test_doctor_missing_credentials(self, tmp_path: Path, monkeypatch) -> None:
        self._clear_creds(monkeypatch)
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        monkeypatch.setenv("TAILSCALE_MANAGER_TERRAFORM_BIN", "/nonexistent/tf")
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "Missing TAILSCALE_OAUTH_CLIENT_ID" in result.stdout or "No credentials found" in result.stdout

    def test_doctor_missing_tailnet_defaults(self, tmp_path: Path, monkeypatch) -> None:
        self._clear_creds(monkeypatch)
        monkeypatch.delenv("TAILSCALE_TAILNET", raising=False)
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        monkeypatch.setenv("TAILSCALE_MANAGER_TERRAFORM_BIN", "/nonexistent/tf")
        result = runner.invoke(app, ["doctor"])
        assert "auto-resolve" in result.stdout

    def test_help_shows_doctor(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "doctor" in result.stdout

    def test_doctor_with_check_api_no_creds(self, tmp_path: Path, monkeypatch) -> None:
        self._clear_creds(monkeypatch)
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        monkeypatch.setenv("TAILSCALE_MANAGER_TERRAFORM_BIN", "/nonexistent/tf")
        result = runner.invoke(app, ["doctor", "--check-api"])
        assert "API connectivity" in result.stdout
        assert "Skipped" in result.stdout


# ── Auth keys subcommand tests ────────────────────────────────


class TestShowKey:
    def test_show_key_prints_key_value(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        tfstate = tmp_path / "terraform.tfstate"
        tfstate.write_text(json.dumps({
            "resources": [{
                "mode": "managed",
                "type": "tailscale_tailnet_key",
                "name": "ci-key",
                "instances": [{
                    "attributes": {
                        "id": "k123",
                        "key": "tskey-auth-k123-abc",
                        "description": "CI key",
                        "tags": ["tag:ci"],
                    }
                }]
            }]
        }))
        result = runner.invoke(app, ["auth-keys", "show-key", "ci-key"])
        assert result.exit_code == 0, result.stdout
        assert "tskey-auth-k123-abc" in result.stdout
        assert "WARNING" in result.stderr

    def test_show_key_missing_name(self) -> None:
        result = runner.invoke(app, ["auth-keys", "show-key"])
        assert result.exit_code == 2

    def test_show_key_not_found(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        tfstate = tmp_path / "terraform.tfstate"
        tfstate.write_text(json.dumps({"resources": []}))
        result = runner.invoke(app, ["auth-keys", "show-key", "missing-key"])
        assert result.exit_code == 1
        assert "not found" in result.stderr

    def test_show_key_no_value_in_state(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        tfstate = tmp_path / "terraform.tfstate"
        tfstate.write_text(json.dumps({
            "resources": [{
                "mode": "managed",
                "type": "tailscale_tailnet_key",
                "name": "old-key",
                "instances": [{
                    "attributes": {
                        "id": "k456",
                        "key": None,
                        "description": "Old key",
                    }
                }]
            }]
        }))
        result = runner.invoke(app, ["auth-keys", "show-key", "old-key"])
        assert result.exit_code == 1
        assert "no stored value" in result.stderr

    def test_show_key_no_state_file(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        result = runner.invoke(app, ["auth-keys", "show-key", "ci-key"])
        assert result.exit_code == 1
        assert "not found" in result.stderr


class TestAuthKeys:
    def test_auth_keys_help_shows_subcommands(self) -> None:
        result = runner.invoke(app, ["auth-keys", "--help"])
        assert result.exit_code == 0
        for cmd in ["create", "list", "revoke"]:
            assert cmd in result.stdout

    def test_create_requires_credentials(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_ID", raising=False)
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_SECRET", raising=False)
        result = runner.invoke(app, [
            "auth-keys", "create",
            "--description", "test",
        ])
        assert result.exit_code == 1

    def test_list_requires_credentials(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_ID", raising=False)
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_SECRET", raising=False)
        result = runner.invoke(app, ["auth-keys", "list"])
        assert result.exit_code == 1

    def test_revoke_requires_key_id(self) -> None:
        result = runner.invoke(app, ["auth-keys", "revoke"])
        assert result.exit_code != 0
        assert result.exit_code == 2


# ── First-run guidance tests ─────────────────────────────────


class TestFirstRunGuidance:
    def test_init_shows_first_run_message(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        result = runner.invoke(app, ["init"])
        assert "First run detected" in result.stdout
        assert "tailscale-manager doctor" in result.stdout
        assert "tailscale-manager init" in result.stdout

    def test_apply_guards_against_uninitialized(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        result = runner.invoke(app, ["apply"])
        assert result.exit_code == 1
        assert "not initialized" in result.stdout

    def test_init_shows_doc_url(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        result = runner.invoke(app, ["init"])
        assert "github.com/Cairnstew/tailscale-manager" in result.stdout

    def test_init_skips_first_run_when_terraform_dir_exists(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        (tmp_path / ".terraform").mkdir()
        result = runner.invoke(app, ["init"])
        assert "First run detected" not in result.stdout


# ── Output command tests ──────────────────────────────────────


class TestOutput:
    def test_output_prints_key_to_stdout(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        tfstate = tmp_path / "terraform.tfstate"
        tfstate.write_text(json.dumps({
            "resources": [{
                "mode": "managed",
                "type": "tailscale_tailnet_key",
                "name": "managed_key",
                "instances": [{
                    "attributes": {
                        "id": "k123",
                        "key": "tskey-auth-k123-abc",
                    }
                }]
            }]
        }))
        result = runner.invoke(app, ["output"])
        assert result.exit_code == 0
        assert result.stdout == "tskey-auth-k123-abc"
        assert "tskey-auth-k123-abc" not in result.stderr

    def test_output_no_state_file(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        result = runner.invoke(app, ["output"])
        assert result.exit_code == 1
        assert "no Terraform state found" in result.stderr

    def test_output_key_not_found(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        tfstate = tmp_path / "terraform.tfstate"
        tfstate.write_text(json.dumps({"resources": []}))
        result = runner.invoke(app, ["output"])
        assert result.exit_code == 1
        assert "managed key not found" in result.stderr

    def test_output_key_is_none_in_state(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        tfstate = tmp_path / "terraform.tfstate"
        tfstate.write_text(json.dumps({
            "resources": [{
                "mode": "managed",
                "type": "tailscale_tailnet_key",
                "name": "managed_key",
                "instances": [{
                    "attributes": {
                        "id": "k123",
                        "key": None,
                    }
                }]
            }]
        }))
        result = runner.invoke(app, ["output"])
        assert result.exit_code == 1
        assert "managed key not found" in result.stderr

    def test_output_writes_file_with_mode_0600(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        tfstate = tmp_path / "terraform.tfstate"
        tfstate.write_text(json.dumps({
            "resources": [{
                "mode": "managed",
                "type": "tailscale_tailnet_key",
                "name": "managed_key",
                "instances": [{
                    "attributes": {
                        "id": "k123",
                        "key": "tskey-auth-k123-abc",
                    }
                }]
            }]
        }))
        out_path = tmp_path / "out" / "ts-key"
        result = runner.invoke(app, ["output", "--output-file", str(out_path)])
        assert result.exit_code == 0
        assert result.stdout == ""
        assert out_path.read_text() == "tskey-auth-k123-abc"
        assert oct(out_path.stat().st_mode & 0o777) == "0o600"

    def test_output_multiple_instances_errors(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        tfstate = tmp_path / "terraform.tfstate"
        tfstate.write_text(json.dumps({
            "resources": [{
                "mode": "managed",
                "type": "tailscale_tailnet_key",
                "name": "managed_key",
                "instances": [
                    {"attributes": {"id": "k1", "key": "key-one"}},
                    {"attributes": {"id": "k2", "key": "key-two"}},
                ],
            }]
        }))
        result = runner.invoke(app, ["output"])
        assert result.exit_code == 1
        assert "expected 1 instance" in result.stderr

    def test_output_file_unwritable_path(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
        tfstate = tmp_path / "terraform.tfstate"
        tfstate.write_text(json.dumps({
            "resources": [{
                "mode": "managed",
                "type": "tailscale_tailnet_key",
                "name": "managed_key",
                "instances": [{
                    "attributes": {
                        "id": "k123",
                        "key": "tskey-auth-k123-abc",
                    }
                }]
            }]
        }))
        # Create a file and try to use it as a directory — should fail
        file_path = tmp_path / "file"
        file_path.write_text("")
        bad_path = file_path / "nested" / "key"
        result = runner.invoke(app, ["output", "--output-file", str(bad_path)])
        assert result.exit_code == 1
        assert "cannot write" in result.stderr
