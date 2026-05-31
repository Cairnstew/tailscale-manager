from __future__ import annotations

from tailscale_manager.models.settings import TailnetSettings
from tailscale_manager.services.features.settings import build_settings_config


def test_build_settings_config_null_returns_empty() -> None:
    cfg = build_settings_config(None)
    assert cfg == {}


def test_build_settings_config_defaults_excluded() -> None:
    """Default values (False, None) should be excluded from output."""
    settings = TailnetSettings()
    cfg = build_settings_config(settings)
    assert cfg == {
        "resource": {
            "tailscale_tailnet_settings": {
                "tailnet": {}
            }
        }
    }


def test_build_settings_config_custom_values() -> None:
    settings = TailnetSettings(
        devices_approval_on=True,
        https_enabled=True,
    )
    cfg = build_settings_config(settings)
    assert "resource" in cfg
    body = cfg["resource"]["tailscale_tailnet_settings"]["tailnet"]
    assert body["devices_approval_on"] is True
    assert body["https_enabled"] is True
    assert "devices_auto_updates_on" not in body


def test_build_settings_config_nullable_fields() -> None:
    """None fields like devices_key_duration_days should be excluded."""
    settings = TailnetSettings(
        devices_key_duration_days=None,
        devices_approval_on=True,
    )
    cfg = build_settings_config(settings)
    body = cfg["resource"]["tailscale_tailnet_settings"]["tailnet"]
    assert "devices_key_duration_days" not in body
    assert body["devices_approval_on"] is True


def test_build_settings_config_all_fields() -> None:
    settings = TailnetSettings(
        devices_approval_on=True,
        devices_auto_updates_on=True,
        devices_key_duration_days=90,
        users_approval_on=True,
        acls_externally_managed_on=True,
        acls_external_link="https://example.com/acls",
        posture_identity_collection_on=True,
        https_enabled=True,
        regional_routing_on=True,
        users_role_allowed_to_join_external_tailnet="member",
    )
    cfg = build_settings_config(settings)
    body = cfg["resource"]["tailscale_tailnet_settings"]["tailnet"]
    assert body == {
        "devices_approval_on": True,
        "devices_auto_updates_on": True,
        "devices_key_duration_days": 90,
        "users_approval_on": True,
        "acls_externally_managed_on": True,
        "acls_external_link": "https://example.com/acls",
        "posture_identity_collection_on": True,
        "https_enabled": True,
        "regional_routing_on": True,
        "users_role_allowed_to_join_external_tailnet": "member",
    }
