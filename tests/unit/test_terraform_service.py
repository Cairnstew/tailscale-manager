from __future__ import annotations

import json
from pathlib import Path

from tailscale_manager.core.config import AppConfig
from tailscale_manager.services.terraform_service import TerraformService


def test_generate_config_produces_valid_json(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        tags=["tag:test"],
    )
    svc = TerraformService(config)
    result = svc.generate_config()

    assert result.exists()
    data = json.loads(result.read_text())
    assert "terraform" in data
    assert "provider" in data
    assert "resource" in data


def test_generate_config_includes_tags(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        tags=["tag:infra", "tag:managed"],
    )
    svc = TerraformService(config)
    result = svc.generate_config()
    data = json.loads(result.read_text())
    tags = (
        data["resource"]["tailscale_tailnet_key"]["managed_key"]["tags"]
    )
    assert tags == ["tag:infra", "tag:managed"]


def test_generate_config_default_tags_empty(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    result = svc.generate_config()
    data = json.loads(result.read_text())
    tags = (
        data["resource"]["tailscale_tailnet_key"]["managed_key"]["tags"]
    )
    assert tags == []


def test_generate_config_has_empty_provider_block(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    result = svc.generate_config()
    data = json.loads(result.read_text())

    assert data["provider"]["tailscale"] == {}
    content = result.read_text()
    # No secrets should appear in the generated file — the Tailscale provider
    # picks up TAILSCALE_OAUTH_CLIENT_ID / TAILSCALE_OAUTH_CLIENT_SECRET from env.
    assert "oauth_client_id" not in content
    assert "oauth_client_secret" not in content


def test_generate_config_has_correct_provider_version(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    result = svc.generate_config()
    data = json.loads(result.read_text())

    provider = data["terraform"]["required_providers"]["tailscale"]
    assert provider["source"] == "tailscale/tailscale"
    assert provider["version"] == "~> 0.29"


def test_generate_config_includes_recreate_if_invalid(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    result = svc.generate_config()
    data = json.loads(result.read_text())

    key = data["resource"]["tailscale_tailnet_key"]["managed_key"]
    assert key["recreate_if_invalid"] == "always"


def test_backup_and_restore_state(tmp_path: Path) -> None:
    state_file = tmp_path / "terraform.tfstate"
    state_file.write_text('{"version": 1}')

    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        backup_count=3,
    )
    svc = TerraformService(config)

    svc._backup_state()

    backup_dir = tmp_path / "backups"
    assert backup_dir.exists()
    backups = list(backup_dir.glob("*.tfstate"))
    assert len(backups) == 1

    state_file.write_text('{"version": 2}')
    svc._restore_state()
    restored = json.loads(state_file.read_text())
    assert restored["version"] == 1


def test_backup_pruning(tmp_path: Path) -> None:
    state_file = tmp_path / "terraform.tfstate"
    state_file.write_text("{}")

    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        backup_count=2,
    )
    svc = TerraformService(config)

    for _ in range(5):
        svc._backup_state()

    backup_dir = tmp_path / "backups"
    backups = sorted(backup_dir.glob("*.tfstate"))
    assert len(backups) == 2
