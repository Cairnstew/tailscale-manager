from __future__ import annotations

import re
from typing import Any


def _sanitize_resource_name(name: str) -> str:
    """Convert a key name to a valid Terraform resource name."""
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    if name[0].isdigit():
        name = "_" + name
    return name


def build_keys_config(
    tags: list[str],
    recreate_if_invalid: str,
    auth_keys: dict[str, Any] | None = None,
) -> dict:
    if auth_keys:
        resources: dict[str, Any] = {}
        for name, key in auth_keys.items():
            resource = _sanitize_resource_name(name)
            resources[resource] = {
                "reusable": key.get("reusable", True),
                "ephemeral": key.get("ephemeral", False),
                "preauthorized": key.get("preauthorized", True),
                "tags": key.get("tags", []),
                "recreate_if_invalid": key.get("recreateIfInvalid", "always"),
                "description": key.get("description", name),
            }
        return {"resource": {"tailscale_tailnet_key": resources}}
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
