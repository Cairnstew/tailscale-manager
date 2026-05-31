from __future__ import annotations

from tailscale_manager.models.settings import TailnetSettings


def test_tailnet_settings_defaults() -> None:
    s = TailnetSettings()
    assert s.devices_approval_on is None
    assert s.devices_auto_updates_on is None
    assert s.devices_key_duration_days is None
    assert s.users_approval_on is None
    assert s.acls_externally_managed_on is None
    assert s.acls_external_link is None
    assert s.posture_identity_collection_on is None
    assert s.https_enabled is None
    assert s.regional_routing_on is None
    assert s.users_role_allowed_to_join_external_tailnet is None


def test_tailnet_settings_model_dump_exclude_none() -> None:
    s = TailnetSettings(devices_approval_on=True)
    dumped = s.model_dump(exclude_none=True)
    assert "devices_approval_on" in dumped
    assert "devices_key_duration_days" not in dumped
    assert "acls_external_link" not in dumped


def test_tailnet_settings_custom() -> None:
    s = TailnetSettings(
        devices_approval_on=True,
        devices_key_duration_days=90,
    )
    assert s.devices_approval_on is True
    assert s.devices_key_duration_days == 90
