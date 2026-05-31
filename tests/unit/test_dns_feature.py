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
    assert "tailscale_dns_split_nameservers" in cfg["resource"]
    entries = cfg["resource"]["tailscale_dns_split_nameservers"]
    assert entries["corp_example_com"] == {
        "domain": "corp.example.com",
        "nameservers": ["10.0.0.53"],
    }


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
    assert "tailscale_dns_split_nameservers" in cfg["resource"]
    entries = cfg["resource"]["tailscale_dns_split_nameservers"]
    assert "corp_example_com" in entries
    assert entries["corp_example_com"] == {
        "domain": "corp.example.com",
        "nameservers": ["10.0.0.53"],
    }
    assert "internal_net_local" in entries
    assert entries["internal_net_local"] == {
        "domain": "internal-net.local",
        "nameservers": ["10.0.0.54", "10.0.0.55"],
    }


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
    assert "tailscale_dns_split_nameservers" in keys
    entries = cfg["resource"]["tailscale_dns_split_nameservers"]
    assert "corp_example_com" in entries
    assert "internal_net_local" in entries
    assert "corp.example.com" not in entries
    assert "internal-net.local" not in entries


def test_build_dns_config_all_features() -> None:
    cfg = build_dns_config(
        nameservers=["1.1.1.1"],
        magic_dns=True,
        split_nameservers={"corp.example.com": ["10.0.0.53"]},
    )
    assert "resource" in cfg
    assert "tailscale_dns_nameservers" in cfg["resource"]
    assert "tailscale_dns_preferences" in cfg["resource"]
    assert "tailscale_dns_split_nameservers" in cfg["resource"]
    entries = cfg["resource"]["tailscale_dns_split_nameservers"]
    assert entries["corp_example_com"] == {
        "domain": "corp.example.com",
        "nameservers": ["10.0.0.53"],
    }


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
