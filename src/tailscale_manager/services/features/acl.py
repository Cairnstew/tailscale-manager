from __future__ import annotations

from tailscale_manager.services.features.base import BaseFeatureBuilder


__all__ = [
    "AclFeatureBuilder",
    "build_acl_config",
]


class AclFeatureBuilder(BaseFeatureBuilder):
    def __init__(self, enable: bool, fmt: str, policy: str) -> None:
        self._enable = enable
        self._fmt = fmt
        self._policy = policy

    def build(self) -> dict:
        if not self._enable or not self._policy:
            return {}
        return {
            "resource": {
                "tailscale_acl": {
                    "tailnet_policy": {
                        "acl": self._policy,
                        "overwrite_existing_content": True,
                    }
                }
            }
        }


def build_acl_config(enable: bool, fmt: str, policy: str) -> dict:
    return AclFeatureBuilder(enable=enable, fmt=fmt, policy=policy).build()
