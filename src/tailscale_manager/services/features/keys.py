from __future__ import annotations

import re
from typing import Any


def _sanitize_resource_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if name[0].isdigit():
        name = "_" + name
    return name


def build_keys_config(
    tags: list[str],
    recreate_if_invalid: str,
    auth_keys: dict[str, Any] | None = None,
    auth_key_exports: dict[str, dict[str, str]] | None = None,
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
        config: dict[str, Any] = {"resource": {"tailscale_tailnet_key": resources}}
    else:
        config = {
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

    if auth_key_exports:
        local_files: dict[str, Any] = {}
        for key_name, export_cfg in auth_key_exports.items():
            resource = _sanitize_resource_name(key_name)
            tf_key_ref = f"tailscale_tailnet_key.{resource}.key"
            local_files[f"key_{resource}"] = {
                "sensitive_content": f"${{{tf_key_ref}}}",
                "filename": export_cfg["path"],
                "file_permission": "0600",
            }
        config["resource"]["local_sensitive_file"] = local_files

    return config
