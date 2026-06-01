from __future__ import annotations


def build_keys_config(tags: list[str], recreate_if_invalid: str) -> dict:
    return {
        "resource": {
            "tailscale_tailnet_key": {
                "managed_key": {
                    "reusable": True,
                    "ephemeral": False,
                    "preauthorized": True,
                    "tags": tags,
                    "recreate_if_invalid": recreate_if_invalid,
                }
            }
        },
    }
