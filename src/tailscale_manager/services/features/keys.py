from __future__ import annotations

import re
from typing import Any

from tailscale_manager.services.features.base import BaseFeatureBuilder


__all__ = [
    "KeyFeatureBuilder",
    "build_keys_config",
    "_sanitize_resource_name",
]


def _sanitize_resource_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if name[0].isdigit():
        name = "_" + name
    return name


class KeyFeatureBuilder(BaseFeatureBuilder):
    def __init__(
        self,
        tags: list[str],
        recreate_if_invalid: str,
        auth_keys: dict[str, Any] | None = None,
        auth_key_exports: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self._tags = tags
        self._recreate_if_invalid = recreate_if_invalid
        self._auth_keys = auth_keys
        self._auth_key_exports = auth_key_exports

    def build(self) -> dict:
        if self._auth_keys:
            resources: dict[str, Any] = {}
            for name, key in self._auth_keys.items():
                resource = _sanitize_resource_name(name)
                resources[resource] = {
                    "reusable": key.get("reusable", True),
                    "ephemeral": key.get("ephemeral", False),
                    "preauthorized": key.get("preauthorized", True),
                    "tags": key.get("tags", []),
                    "recreate_if_invalid": key.get("recreateIfInvalid", "always"),
                    "description": key.get("description", name),
                    "lifecycle": {"create_before_destroy": True},
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
                            "tags": self._tags,
                            "recreate_if_invalid": self._recreate_if_invalid,
                            "lifecycle": {"create_before_destroy": True},
                        }
                    }
                },
            }

        if self._auth_key_exports:
            local_files: dict[str, Any] = {}
            for key_name, export_cfg in self._auth_key_exports.items():
                resource = _sanitize_resource_name(key_name)
                tf_key_ref = f"tailscale_tailnet_key.{resource}.key"
                local_files[f"key_{resource}"] = {
                    "content": f"${{{tf_key_ref}}}",
                    "filename": export_cfg["path"],
                    "file_permission": "0600",
                }
            config["resource"]["local_sensitive_file"] = local_files

        return config


def build_keys_config(
    tags: list[str],
    recreate_if_invalid: str,
    auth_keys: dict[str, Any] | None = None,
    auth_key_exports: dict[str, dict[str, str]] | None = None,
) -> dict:
    return KeyFeatureBuilder(
        tags=tags,
        recreate_if_invalid=recreate_if_invalid,
        auth_keys=auth_keys,
        auth_key_exports=auth_key_exports,
    ).build()
