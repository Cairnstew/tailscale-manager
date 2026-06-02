from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tailscale_manager.core.config import AppConfig
from tailscale_manager.services.terraform_service import TerraformService


def test_write_configs_produces_multiple_files(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        tags=["tag:test"],
    )
    svc = TerraformService(config)
    written = svc.write_configs()

    assert written is True
    assert (tmp_path / "main.tf.json").exists()
    assert (tmp_path / "keys.tf.json").exists()
    assert (tmp_path / "data.tf.json").exists()


def test_write_configs_produces_valid_json(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        tags=["tag:test"],
    )
    svc = TerraformService(config)
    svc.write_configs()

    for fname in ["main.tf.json", "keys.tf.json", "data.tf.json"]:
        data = json.loads((tmp_path / fname).read_text())
        assert isinstance(data, dict)


def test_write_configs_returns_false_when_unchanged(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        tags=["tag:test"],
    )
    svc = TerraformService(config)
    svc.write_configs()

    written = svc.write_configs()
    assert written is False


def test_main_tf_has_terraform_and_provider(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    svc.write_configs()
    data = json.loads((tmp_path / "main.tf.json").read_text())

    assert "terraform" in data
    assert "provider" in data
    assert "resource" not in data
    assert "data" not in data


def test_main_tf_has_correct_provider_version(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    svc.write_configs()
    data = json.loads((tmp_path / "main.tf.json").read_text())

    provider = data["terraform"]["required_providers"]["tailscale"]
    assert provider["source"] == "tailscale/tailscale"
    assert provider["version"] == "~> 0.29"


def test_main_tf_uses_custom_provider_version(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        provider_version="~> 0.40",
    )
    svc = TerraformService(config)
    svc.write_configs()
    data = json.loads((tmp_path / "main.tf.json").read_text())

    version = data["terraform"]["required_providers"]["tailscale"]["version"]
    assert version == "~> 0.40"


def test_main_tf_has_empty_provider_block(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    svc.write_configs()
    data = json.loads((tmp_path / "main.tf.json").read_text())

    assert data["provider"]["tailscale"] == {}
    content = (tmp_path / "main.tf.json").read_text()
    assert "oauth_client_id" not in content
    assert "oauth_client_secret" not in content


def test_keys_tf_includes_tags(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        tags=["tag:infra", "tag:managed"],
    )
    svc = TerraformService(config)
    svc.write_configs()
    data = json.loads((tmp_path / "keys.tf.json").read_text())
    tags = (
        data["resource"]["tailscale_tailnet_key"]["managed_key"]["tags"]
    )
    assert tags == ["tag:infra", "tag:managed"]


def test_keys_tf_default_tags_empty(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    svc.write_configs()
    data = json.loads((tmp_path / "keys.tf.json").read_text())
    tags = (
        data["resource"]["tailscale_tailnet_key"]["managed_key"]["tags"]
    )
    assert tags == []


def test_keys_tf_honors_recreate_if_invalid(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        recreate_if_invalid="never",
    )
    svc = TerraformService(config)
    svc.write_configs()
    data = json.loads((tmp_path / "keys.tf.json").read_text())

    key = data["resource"]["tailscale_tailnet_key"]["managed_key"]
    assert key["recreate_if_invalid"] == "never"


def test_dns_tf_written_when_configured(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        dns_nameservers=["1.1.1.1"],
        dns_magic_dns=True,
    )
    svc = TerraformService(config)
    svc.write_configs()
    assert (tmp_path / "dns.tf.json").exists()
    data = json.loads((tmp_path / "dns.tf.json").read_text())
    assert "tailscale_dns_nameservers" in data["resource"]
    assert "tailscale_dns_preferences" in data["resource"]


def test_dns_tf_not_written_when_not_configured(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    svc.write_configs()
    assert not (tmp_path / "dns.tf.json").exists()


def test_acl_tf_written_when_enabled(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        acl_enable=True,
        acl_policy='{"acls": []}',
    )
    svc = TerraformService(config)
    svc.write_configs()
    assert (tmp_path / "acl.tf.json").exists()
    data = json.loads((tmp_path / "acl.tf.json").read_text())
    assert "tailscale_acl" in data["resource"]


def test_acl_tf_not_written_when_disabled(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        acl_enable=False,
        acl_policy='{"acls": []}',
    )
    svc = TerraformService(config)
    svc.write_configs()
    assert not (tmp_path / "acl.tf.json").exists()


def test_acl_tf_not_written_when_enabled_but_no_policy(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        acl_enable=True,
        acl_policy="",
    )
    svc = TerraformService(config)
    svc.write_configs()
    assert not (tmp_path / "acl.tf.json").exists()


def test_data_tf_has_devices_data_source(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
    )
    svc = TerraformService(config)
    svc.write_configs()
    data = json.loads((tmp_path / "data.tf.json").read_text())

    assert "data" in data
    assert "tailscale_devices" in data["data"]
    assert "all" in data["data"]["tailscale_devices"]


def test_keys_tf_uses_auth_keys_when_provided(tmp_path: Path) -> None:
    auth_keys = {
        "ci-key": {
            "description": "CI pipeline key",
            "tags": ["tag:ci"],
            "reusable": True,
            "ephemeral": True,
            "preauthorized": False,
            "recreateIfInvalid": "always",
        },
        "monitoring": {
            "description": "Monitoring key",
            "tags": ["tag:monitoring"],
            "reusable": False,
            "ephemeral": False,
            "preauthorized": True,
            "recreateIfInvalid": "never",
        },
    }
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        auth_keys=auth_keys,
    )
    svc = TerraformService(config)
    svc.write_configs()
    data = json.loads((tmp_path / "keys.tf.json").read_text())

    keys = data["resource"]["tailscale_tailnet_key"]
    assert "ci-key" in keys
    assert "monitoring" in keys
    assert keys["ci-key"]["description"] == "CI pipeline key"
    assert keys["ci-key"]["tags"] == ["tag:ci"]
    assert keys["ci-key"]["ephemeral"] is True
    assert keys["ci-key"]["preauthorized"] is False
    assert keys["monitoring"]["reusable"] is False
    assert keys["monitoring"]["recreate_if_invalid"] == "never"


def test_keys_tf_falls_back_to_legacy_when_no_keys(tmp_path: Path) -> None:
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        tags=["tag:legacy"],
    )
    svc = TerraformService(config)
    svc.write_configs()
    data = json.loads((tmp_path / "keys.tf.json").read_text())

    keys = data["resource"]["tailscale_tailnet_key"]
    assert "managed_key" in keys
    assert keys["managed_key"]["tags"] == ["tag:legacy"]


def test_keys_tf_sanitizes_resource_names(tmp_path: Path) -> None:
    auth_keys = {
        "my-ci-key": {
            "description": "ci",
            "tags": [],
        },
        "123start_with_digit": {
            "description": "digit start",
            "tags": [],
        },
    }
    config = AppConfig(
        tailnet="test.ts.net",
        state_dir=tmp_path,
        auth_keys=auth_keys,
    )
    svc = TerraformService(config)
    svc.write_configs()
    data = json.loads((tmp_path / "keys.tf.json").read_text())
    keys = data["resource"]["tailscale_tailnet_key"]
    assert "my-ci-key" in keys
    assert "_123start_with_digit" in keys


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
