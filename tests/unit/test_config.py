from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from tailscale_manager.core.config import AppConfig
from tailscale_manager.core.exceptions import ConfigurationError


class TestTailnetDefault:
    def test_tailnet_defaults_to_dash(self) -> None:
        config = AppConfig(state_dir=Path("/tmp"))
        assert config.tailnet == "-"

    def test_tailnet_empty_string_becomes_dash(self) -> None:
        config = AppConfig(tailnet="", state_dir=Path("/tmp"))
        assert config.tailnet == "-"

    def test_tailnet_explicit_value_preserved(self) -> None:
        config = AppConfig(tailnet="my-tailnet.ts.net", state_dir=Path("/tmp"))
        assert config.tailnet == "my-tailnet.ts.net"

    def test_from_env_without_env_var(self, monkeypatch) -> None:
        monkeypatch.delenv("TAILSCALE_TAILNET", raising=False)
        config = AppConfig.from_env()
        assert config.tailnet == "-"

    def test_from_env_with_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_TAILNET", "custom.ts.net")
        config = AppConfig.from_env()
        assert config.tailnet == "custom.ts.net"

    def test_from_env_with_empty_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_TAILNET", "")
        config = AppConfig.from_env()
        assert config.tailnet == "-"

    def test_oauth_tailnet_fallback(self, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_TAILNET", "")
        monkeypatch.setenv("TAILSCALE_OAUTH_TAILNET", "fallback.ts.net")
        config = AppConfig.from_env()
        assert config.tailnet == "fallback.ts.net"


class TestAssertCredentials:
    def test_raises_when_oauth_client_id_missing(self, monkeypatch) -> None:
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_ID", raising=False)
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_SECRET", raising=False)
        config = AppConfig(state_dir=Path("/tmp"))
        with pytest.raises(ConfigurationError) as excinfo:
            config.assert_credentials()
        assert excinfo.value.field == "TAILSCALE_OAUTH_CLIENT_ID"

    def test_raises_when_oauth_client_secret_missing(self, monkeypatch) -> None:
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_ID", raising=False)
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_SECRET", raising=False)
        config = AppConfig(
            state_dir=Path("/tmp"),
            oauth_client_id="tskey-client-xxx",
        )
        with pytest.raises(ConfigurationError) as excinfo:
            config.assert_credentials()
        assert excinfo.value.field == "TAILSCALE_OAUTH_CLIENT_SECRET"

    def test_passes_when_both_set(self) -> None:
        config = AppConfig(
            state_dir=Path("/tmp"),
            oauth_client_id="tskey-client-xxx",
            oauth_client_secret="secret",
        )
        config.assert_credentials()

    def test_can_instantiate_without_credentials(self, monkeypatch) -> None:
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_ID", raising=False)
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_SECRET", raising=False)
        config = AppConfig(state_dir=Path("/tmp"))
        assert config.oauth_client_id == ""
        assert config.oauth_client_secret == ""

    def test_can_instantiate_in_dev_with_partial_creds(self, monkeypatch) -> None:
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_ID", raising=False)
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_SECRET", raising=False)
        config = AppConfig(
            state_dir=Path("/tmp"),
            oauth_client_id="tskey-client-xxx",
        )
        assert config.oauth_client_id == "tskey-client-xxx"
        assert config.oauth_client_secret == ""


class TestCredentialLoading:
    def test_credentials_loaded_from_env(self, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_OAUTH_CLIENT_ID", "tskey-client-env-id")
        monkeypatch.setenv("TAILSCALE_OAUTH_CLIENT_SECRET", "env-secret")
        config = AppConfig.from_env()
        assert config.oauth_client_id == "tskey-client-env-id"
        assert config.oauth_client_secret == "env-secret"

    def test_credentials_loaded_from_creds_dir(self, monkeypatch, tmp_path: Path) -> None:
        creds_dir = tmp_path / "creds"
        creds_dir.mkdir()
        cred_file = creds_dir / "tailscale-oauth"
        cred_file.write_text(
            "TAILSCALE_OAUTH_CLIENT_ID=tskey-client-file-id\n"
            "TAILSCALE_OAUTH_CLIENT_SECRET=file-secret\n"
        )
        monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(creds_dir))
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_ID", raising=False)
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_SECRET", raising=False)
        config = AppConfig.from_env()
        assert config.oauth_client_id == "tskey-client-file-id"
        assert config.oauth_client_secret == "file-secret"

    def test_creds_dir_preferred_over_env(self, monkeypatch, tmp_path: Path) -> None:
        creds_dir = tmp_path / "creds"
        creds_dir.mkdir()
        cred_file = creds_dir / "tailscale-oauth"
        cred_file.write_text(
            "TAILSCALE_OAUTH_CLIENT_ID=tskey-client-file-id\n"
            "TAILSCALE_OAUTH_CLIENT_SECRET=file-secret\n"
        )
        monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(creds_dir))
        monkeypatch.setenv("TAILSCALE_OAUTH_CLIENT_ID", "env-id")
        monkeypatch.setenv("TAILSCALE_OAUTH_CLIENT_SECRET", "env-secret")
        config = AppConfig.from_env()
        assert config.oauth_client_id == "tskey-client-file-id"
        assert config.oauth_client_secret == "file-secret"


class TestAuthKeysFromFile:
    def test_loads_auth_keys_from_path(self, tmp_path: Path) -> None:
        auth_file = tmp_path / "auth-keys.json"
        auth_file.write_text('''
        {
            "ci-key": {
                "description": "CI key",
                "tags": ["tag:ci"],
                "ephemeral": true
            }
        }
        ''')
        config = AppConfig(
            tailnet="test.ts.net",
            state_dir=tmp_path,
            auth_keys_path=auth_file,
        )
        assert "ci-key" in config.auth_keys
        assert config.auth_keys["ci-key"]["description"] == "CI key"
        assert config.auth_keys["ci-key"]["ephemeral"] is True

    def test_auth_keys_defaults_to_empty(self) -> None:
        config = AppConfig(tailnet="test.ts.net", state_dir=Path("/tmp"))
        assert config.auth_keys == {}

    def test_auth_keys_path_non_existent_ignored(self, tmp_path: Path) -> None:
        config = AppConfig(
            tailnet="test.ts.net",
            state_dir=tmp_path,
            auth_keys_path=tmp_path / "nonexistent.json",
        )
        assert config.auth_keys == {}


class TestTagValidator:
    def test_rejects_tags_without_prefix(self) -> None:
        with pytest.raises(ValidationError):
            AppConfig(tailnet="test.ts.net", tags=["server", "tag:ci"], state_dir=Path("/tmp"))

    def test_accepts_valid_tags(self) -> None:
        cfg = AppConfig(tailnet="test.ts.net", tags=["tag:server", "tag:ci"], state_dir=Path("/tmp"))
        assert cfg.tags == ["tag:server", "tag:ci"]


class TestFromEnvCoverage:
    def test_from_env_sets_all_fields(self, monkeypatch) -> None:
        monkeypatch.setenv("TAILSCALE_TAILNET", "t.ts.net")
        monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", "/custom/state")
        monkeypatch.setenv("TAILSCALE_MANAGER_TERRAFORM_BIN", "/custom/tf")
        monkeypatch.setenv("TAILSCALE_MANAGER_BACKUP_COUNT", "3")
        monkeypatch.setenv("TAILSCALE_MANAGER_TAGS", "tag:a,tag:b")
        monkeypatch.setenv("TAILSCALE_MANAGER_RECREATE_IF_INVALID", "never")
        monkeypatch.setenv("TAILSCALE_MANAGER_PROVIDER_VERSION", "~> 1.0")
        monkeypatch.setenv("TAILSCALE_MANAGER_DNS_NAMESERVERS", "1.1.1.1,8.8.8.8")
        monkeypatch.setenv("TAILSCALE_MANAGER_DNS_MAGIC_DNS", "true")
        monkeypatch.setenv("TAILSCALE_MANAGER_ACL_ENABLE", "true")
        monkeypatch.setenv("TAILSCALE_MANAGER_ACL_FORMAT", "json")

        config = AppConfig.from_env()
        assert config.tailnet == "t.ts.net"
        assert config.state_dir == Path("/custom/state")
        assert config.terraform_bin == Path("/custom/tf")
        assert config.backup_count == 3
        assert config.tags == ["tag:a", "tag:b"]
        assert config.recreate_if_invalid == "never"
        assert config.provider_version == "~> 1.0"
        assert config.dns_nameservers == ["1.1.1.1", "8.8.8.8"]
        assert config.dns_magic_dns is True
        assert config.acl_enable is True
        assert config.acl_format == "json"

    def test_from_env_defaults(self, monkeypatch) -> None:
        monkeypatch.delenv("TAILSCALE_MANAGER_STATE_DIR", raising=False)
        monkeypatch.delenv("TAILSCALE_MANAGER_TERRAFORM_BIN", raising=False)
        monkeypatch.delenv("TAILSCALE_MANAGER_BACKUP_COUNT", raising=False)
        monkeypatch.delenv("TAILSCALE_MANAGER_TAGS", raising=False)
        monkeypatch.delenv("TAILSCALE_MANAGER_RECREATE_IF_INVALID", raising=False)
        monkeypatch.delenv("TAILSCALE_MANAGER_PROVIDER_VERSION", raising=False)
        monkeypatch.delenv("TAILSCALE_MANAGER_DNS_NAMESERVERS", raising=False)
        monkeypatch.delenv("TAILSCALE_MANAGER_DNS_MAGIC_DNS", raising=False)
        monkeypatch.delenv("TAILSCALE_MANAGER_ACL_ENABLE", raising=False)
        monkeypatch.delenv("TAILSCALE_MANAGER_ACL_FORMAT", raising=False)
        monkeypatch.delenv("TAILSCALE_TAILNET", raising=False)
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_ID", raising=False)
        monkeypatch.delenv("TAILSCALE_OAUTH_CLIENT_SECRET", raising=False)
        config = AppConfig.from_env()
        assert config.state_dir == Path("/var/lib/tailscale-manager")
        assert config.terraform_bin == Path("terraform")
        assert config.backup_count == 5
        assert config.tags == []
        assert config.recreate_if_invalid == "always"
        assert config.provider_version == "~> 0.29"
        assert config.dns_nameservers == []
        assert config.dns_magic_dns is False
        assert config.acl_enable is False
        assert config.acl_format == "hujson"
