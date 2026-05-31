from __future__ import annotations

from tailscale_manager.services.features.acl import build_acl_config


def test_build_acl_config_disabled_returns_empty() -> None:
    cfg = build_acl_config(enable=False, fmt="hujson", policy='{"acls": []}')
    assert cfg == {}


def test_build_acl_config_enabled_hujson() -> None:
    policy = '{"acls": [{"action": "accept", "src": ["*"], "dst": ["*:*"]}]}'
    cfg = build_acl_config(enable=True, fmt="hujson", policy=policy)
    assert cfg == {
        "resource": {
            "tailscale_acl": {
                "tailnet_policy": {
                    "acl": policy,
                    "overwrite_existing_content": True,
                }
            }
        }
    }


def test_build_acl_config_enabled_json() -> None:
    policy = '{"acls":[{"action":"accept","src":["*"],"dst":["*:*"]}]}'
    cfg = build_acl_config(enable=True, fmt="json", policy=policy)
    assert cfg["resource"]["tailscale_acl"]["tailnet_policy"]["acl"] == policy


def test_build_acl_config_empty_policy() -> None:
    cfg = build_acl_config(enable=True, fmt="hujson", policy="")
    assert cfg == {}


def test_build_acl_config_disabled_with_policy() -> None:
    cfg = build_acl_config(enable=False, fmt="hujson", policy='{"acls": []}')
    assert cfg == {}
