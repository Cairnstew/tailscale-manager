from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from tailscale_manager.cli import app

runner = CliRunner()


def test_help_shows_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ["init", "plan", "apply", "destroy", "status", "devices", "backup-state", "restore-state"]:
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
