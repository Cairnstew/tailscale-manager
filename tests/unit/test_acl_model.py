from __future__ import annotations

from tailscale_manager.models.acl import AclConfig


def test_acl_config_defaults() -> None:
    acl = AclConfig()
    assert acl.enable is False
    assert acl.format == "hujson"
    assert acl.policy == ""


def test_acl_config_custom() -> None:
    acl = AclConfig(enable=True, format="json", policy='{"acls":[]}')
    assert acl.enable is True
    assert acl.format == "json"
    assert acl.policy == '{"acls":[]}'
