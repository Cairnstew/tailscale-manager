from __future__ import annotations

from tailscale_manager.services.features.dns import build_dns_config


def test_build_dns_config_empty_returns_empty() -> None:
    cfg = build_dns_config(nameservers=[], magic_dns=False, split_nameservers={})
    assert cfg == {}


def test_build_dns_config_nameservers_only() -> None:
    cfg = build_dns_config(
        nameservers=["1.1.1.1", "8.8.8.8"],
        magic_dns=False,
        split_nameservers={},
    )
    assert "resource" in cfg
    assert cfg["resource"]["tailscale_dns_nameservers"]["global"]["nameservers"] == [
        "1.1.1.1", "8.8.8.8"
    ]


def test_build_dns_config_magic_dns() -> None:
    cfg = build_dns_config(nameservers=[], magic_dns=True, split_nameservers={})
    assert "resource" in cfg
    assert cfg["resource"]["tailscale_dns_preferences"]["prefs"]["magic_dns"] is True


def test_build_dns_config_split_single() -> None:
    cfg = build_dns_config(
        nameservers=[],
        magic_dns=False,
        split_nameservers={"corp.example.com": ["10.0.0.53"]},
    )
    assert "resource" in cfg
    key = "tailscale_dns_split_nameservers_corp_example_com"
    assert key in cfg["resource"]
    assert cfg["resource"][key]["domain"]["domain"] == "corp.example.com"
    assert cfg["resource"][key]["domain"]["nameservers"] == ["10.0.0.53"]


def test_build_dns_config_split_multiple() -> None:
    cfg = build_dns_config(
        nameservers=[],
        magic_dns=False,
        split_nameservers={
            "corp.example.com": ["10.0.0.53"],
            "internal-net.local": ["10.0.0.54", "10.0.0.55"],
        },
    )
    assert "resource" in cfg
    assert "tailscale_dns_split_nameservers_corp_example_com" in cfg["resource"]
    assert "tailscale_dns_split_nameservers_internal_net_local" in cfg["resource"]


def test_build_dns_config_split_sanitization() -> None:
    """Dots and hyphens must be replaced with underscores in resource names."""
    cfg = build_dns_config(
        nameservers=[],
        magic_dns=False,
        split_nameservers={
            "corp.example.com": ["10.0.0.53"],
            "internal-net.local": ["10.0.0.54"],
        },
    )
    keys = list(cfg["resource"].keys())
    assert "tailscale_dns_split_nameservers_corp_example_com" in keys
    assert "tailscale_dns_split_nameservers_internal_net_local" in keys
    assert "tailscale_dns_split_nameservers_corp.example.com" not in keys
    assert "tailscale_dns_split_nameservers_internal-net.local" not in keys


def test_build_dns_config_all_features() -> None:
    cfg = build_dns_config(
        nameservers=["1.1.1.1"],
        magic_dns=True,
        split_nameservers={"corp.example.com": ["10.0.0.53"]},
    )
    assert "resource" in cfg
    assert "tailscale_dns_nameservers" in cfg["resource"]
    assert "tailscale_dns_preferences" in cfg["resource"]
    assert "tailscale_dns_split_nameservers_corp_example_com" in cfg["resource"]


def test_build_dns_config_preferences_emitted_for_magic_dns_only() -> None:
    """When only magic_dns is set, preferences resource should still be emitted."""
    cfg = build_dns_config(nameservers=[], magic_dns=True, split_nameservers={})
    assert cfg == {
        "resource": {
            "tailscale_dns_preferences": {
                "prefs": {"magic_dns": True}
            }
        }
    }
