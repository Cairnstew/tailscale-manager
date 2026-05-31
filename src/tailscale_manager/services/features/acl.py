from __future__ import annotations


def build_acl_config(enable: bool, fmt: str, policy: str) -> dict:
    if not enable or not policy:
        return {}
    return {
        "resource": {
            "tailscale_acl": {
                "tailnet_policy": {
                    "acl": policy,
                    "overwrite_existing_content": True,
                }
            }
        }
    }
