from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tailscale_manager.core.config import AppConfig
from tailscale_manager.services.terraform_service import TerraformService


def test_write_config_produces_valid_json(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        tags=["tag:test"],
    )
    svc = TerraformService(config)
    written = svc.write_config()

    assert written is True
    tf_path = tmp_path / "main.tf.json"
    assert tf_path.exists()
    data = json.loads(tf_path.read_text())
    assert "terraform" in data
    assert "provider" in data
    assert "resource" in data


def test_write_config_returns_false_when_unchanged(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        tags=["tag:test"],
    )
    svc = TerraformService(config)
    svc.write_config()

    tf_path = tmp_path / "main.tf.json"
    mtime_before = tf_path.stat().st_mtime_ns

    written = svc.write_config()
    assert written is False

    mtime_after = tf_path.stat().st_mtime_ns
    assert mtime_after == mtime_before


def test_write_config_includes_tags(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        tags=["tag:infra", "tag:managed"],
    )
    svc = TerraformService(config)
    svc.write_config()
    data = json.loads((tmp_path / "main.tf.json").read_text())
    tags = (
        data["resource"]["tailscale_tailnet_key"]["managed_key"]["tags"]
    )
    assert tags == ["tag:infra", "tag:managed"]


def test_write_config_default_tags_empty(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    svc.write_config()
    data = json.loads((tmp_path / "main.tf.json").read_text())
    tags = (
        data["resource"]["tailscale_tailnet_key"]["managed_key"]["tags"]
    )
    assert tags == []


def test_write_config_has_empty_provider_block(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    svc.write_config()
    data = json.loads((tmp_path / "main.tf.json").read_text())

    assert data["provider"]["tailscale"] == {}
    content = (tmp_path / "main.tf.json").read_text()
    assert "oauth_client_id" not in content
    assert "oauth_client_secret" not in content


def test_write_config_has_correct_provider_version(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    svc.write_config()
    data = json.loads((tmp_path / "main.tf.json").read_text())

    provider = data["terraform"]["required_providers"]["tailscale"]
    assert provider["source"] == "tailscale/tailscale"
    assert provider["version"] == "~> 0.29"


def test_write_config_uses_custom_provider_version(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        provider_version="~> 0.40",
    )
    svc = TerraformService(config)
    svc.write_config()
    data = json.loads((tmp_path / "main.tf.json").read_text())

    version = data["terraform"]["required_providers"]["tailscale"]["version"]
    assert version == "~> 0.40"


def test_write_config_honors_recreate_if_invalid(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        recreate_if_invalid="never",
    )
    svc = TerraformService(config)
    svc.write_config()
    data = json.loads((tmp_path / "main.tf.json").read_text())

    key = data["resource"]["tailscale_tailnet_key"]["managed_key"]
    assert key["recreate_if_invalid"] == "never"


def test_app_config_rejects_tags_without_prefix() -> None:
    with pytest.raises(ValidationError):
        AppConfig(
            tailnet="test.ts.net",
            tags=["server", "tag:ci"],
        )


def test_app_config_accepts_valid_tags() -> None:
    cfg = AppConfig(
        tailnet="test.ts.net",
        tags=["tag:server", "tag:ci"],
    )
    assert cfg.tags == ["tag:server", "tag:ci"]


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
