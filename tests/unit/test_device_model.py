from __future__ import annotations

from tailscale_manager.models.device import TailscaleDevice


def test_device_defaults() -> None:
    d = TailscaleDevice()
    assert d.addresses == []
    assert d.hostname == ""
    assert d.id == ""
    assert d.name == ""
    assert d.node_id == ""
    assert d.tags == []
    assert d.user == ""


def test_device_all_fields() -> None:
    d = TailscaleDevice(
        addresses=["100.1.2.3"],
        hostname="test-device",
        id="12345",
        name="test-device.ts.net",
        node_id="n67890",
        tags=["tag:server"],
        user="user@example.com",
    )
    assert d.addresses == ["100.1.2.3"]
    assert d.hostname == "test-device"
    assert d.id == "12345"
    assert d.name == "test-device.ts.net"
    assert d.node_id == "n67890"
    assert d.tags == ["tag:server"]
    assert d.user == "user@example.com"
