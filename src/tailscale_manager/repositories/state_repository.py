from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from tailscale_manager.models.auth_key import TailscaleAuthKey
from tailscale_manager.models.device import TailscaleDevice
from tailscale_manager.repositories.base import BaseRepository


class StateRepository(BaseRepository):
    def __init__(self, state_dir: Path) -> None:
        super().__init__(state_dir)
        self.state_file = state_dir / "terraform.tfstate"
        self.last_apply_file = state_dir / "last-apply.json"

    def read_state(self) -> dict | None:
        if not self.state_file.exists():
            return None
        raw = self.state_file.read_text()
        return json.loads(raw)

    def get_key_by_name(self, name: str) -> TailscaleAuthKey | None:
        """Look up a single key by its Terraform resource name."""
        state = self.read_state()
        if state is None:
            return None
        for res in state.get("resources", []):
            if res.get("type") != "tailscale_tailnet_key":
                continue
            if res.get("name") != name:
                continue
            for instance in res.get("instances", []):
                attrs = instance.get("attributes", {})
                return TailscaleAuthKey(
                    id=attrs.get("id", ""),
                    description=attrs.get("description", ""),
                    tags=attrs.get("tags", []),
                    expiry=self._parse_ts(attrs.get("expires")),
                    revoked=attrs.get("revoked", False),
                    reusable=attrs.get("reusable", True),
                    ephemeral=attrs.get("ephemeral", False),
                    preauthorized=attrs.get("preauthorized", True),
                    created_at=self._parse_ts(attrs.get("created_at")),
                    key=attrs.get("key"),
                )
        return None

    def get_managed_key_value(self) -> str | None:
        """Extract the raw key secret from the 'managed_key' resource in tfstate."""
        state = self.read_state()
        if state is None:
            return None
        for res in state.get("resources", []):
            if res.get("type") == "tailscale_tailnet_key" and res.get("name") == "managed_key":
                instances = res.get("instances", [])
                if len(instances) > 1:
                    raise ValueError(
                        f"expected 1 instance for tailscale_tailnet_key.managed_key, "
                        f"found {len(instances)}"
                    )
                for instance in instances:
                    attrs = instance.get("attributes", {})
                    key = attrs.get("key")
                    if key:
                        return key
        return None

    def get_managed_keys(self) -> list[TailscaleAuthKey]:
        state = self.read_state()
        if state is None:
            return []

        keys: list[TailscaleAuthKey] = []
        resources = state.get("resources", [])
        for res in resources:
            if res.get("type") != "tailscale_tailnet_key":
                continue
            for instance in res.get("instances", []):
                attrs = instance.get("attributes", {})
                key = TailscaleAuthKey(
                    id=attrs.get("id", ""),
                    description=attrs.get("description", ""),
                    tags=attrs.get("tags", []),
                    expiry=self._parse_ts(attrs.get("expires")),
                    revoked=attrs.get("revoked", False),
                    reusable=attrs.get("reusable", True),
                    ephemeral=attrs.get("ephemeral", False),
                    preauthorized=attrs.get("preauthorized", True),
                    created_at=self._parse_ts(attrs.get("created_at")),
                    key=attrs.get("key"),
                )
                keys.append(key)
        return keys

    def get_devices(self) -> list[TailscaleDevice]:
        state = self.read_state()
        if state is None:
            return []

        devices: list[TailscaleDevice] = []
        resources = state.get("resources", [])
        for res in resources:
            if res.get("type") != "tailscale_devices":
                continue
            if res.get("mode") != "data":
                continue
            for instance in res.get("instances", []):
                attrs = instance.get("attributes", {})
                raw_devices = attrs.get("devices", [])
                for d in raw_devices:
                    devices.append(TailscaleDevice(
                        addresses=d.get("addresses", []),
                        hostname=d.get("hostname", ""),
                        id=d.get("id", ""),
                        name=d.get("name", ""),
                        node_id=d.get("node_id", ""),
                        tags=d.get("tags", []),
                        user=d.get("user", ""),
                    ))
        return devices

    def check_state_file_permissions(self) -> bool:
        """Return True if tfstate permissions are 0o600 or tighter, False if wider."""
        if not self.state_file.exists():
            return True
        mode = self.state_file.stat().st_mode & 0o777
        return mode == 0o600

    def read_last_apply(self) -> dict | None:
        if not self.last_apply_file.exists():
            return None
        raw = self.last_apply_file.read_text()
        return json.loads(raw)

    def write_last_apply(self, data: dict) -> None:
        self.last_apply_file.parent.mkdir(parents=True, exist_ok=True)
        self.last_apply_file.write_text(json.dumps(data, indent=2) + "\n")

    @staticmethod
    def _parse_ts(value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
