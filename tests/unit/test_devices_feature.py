from __future__ import annotations

from tailscale_manager.services.features.devices import build_devices_config


def test_build_devices_config_returns_data_block() -> None:
    cfg = build_devices_config()
    assert cfg == {
        "data": {
            "tailscale_devices": {
                "all": {}
            }
        }
    }


def test_build_devices_config_has_no_resource_key() -> None:
    cfg = build_devices_config()
    assert "resource" not in cfg
