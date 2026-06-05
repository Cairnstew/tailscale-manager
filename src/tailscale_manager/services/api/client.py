from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from typing import Any

from tailscale_manager.models.auth_key import TailscaleAuthKey
from tailscale_manager.services.api.base import BaseApiClient, TailscaleAPIError
from tailscale_manager.services.api.oauth import OAuthClient


__all__ = [
    "TailscaleApiClient",
]


API_BASE = "https://api.tailscale.com/api/v2"


class TailscaleApiClient(BaseApiClient):
    def __init__(self, oauth: OAuthClient, tailnet: str = "-") -> None:
        self._oauth = oauth
        self._tailnet = tailnet

    def _request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
    ) -> Any:
        token = self._oauth.get_token()
        url = f"{API_BASE}{path}"
        headers = {"Authorization": f"Bearer {token}"}
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read()
            if resp_body:
                return json.loads(resp_body)
            return None

    def fetch_auth_keys(self) -> list[TailscaleAuthKey]:
        data = self._request("GET", f"/tailnet/{self._tailnet}/keys")
        keys: list[TailscaleAuthKey] = []
        for k in data.get("keys", []):
            if k.get("keyType") != "auth":
                continue
            caps = k.get("capabilities", {}).get("devices", {}).get("create", {})
            keys.append(TailscaleAuthKey(
                id=k.get("id", ""),
                description=k.get("description", ""),
                tags=caps.get("tags", []),
                expiry=self._parse_ts(k.get("expires")),
                revoked=k.get("revoked", False),
                reusable=caps.get("reusable", False),
                ephemeral=caps.get("ephemeral", False),
                preauthorized=caps.get("preauthorized", False),
                created_at=self._parse_ts(k.get("created")),
                key=None,
            ))
        return keys

    def create_auth_key(
        self,
        description: str = "",
        tags: list[str] | None = None,
        reusable: bool = True,
        ephemeral: bool = False,
        preauthorized: bool = True,
        expiry_seconds: int | None = None,
    ) -> TailscaleAuthKey:
        body: dict[str, Any] = {
            "capabilities": {
                "devices": {
                    "create": {
                        "reusable": reusable,
                        "ephemeral": ephemeral,
                        "preauthorized": preauthorized,
                        "tags": tags or [],
                    }
                }
            },
            "description": description,
        }
        if expiry_seconds is not None:
            body["expirySeconds"] = expiry_seconds

        data = self._request("POST", f"/tailnet/{self._tailnet}/keys", data=body)
        caps = data.get("capabilities", {}).get("devices", {}).get("create", {})
        return TailscaleAuthKey(
            id=data.get("id", ""),
            description=data.get("description", ""),
            tags=caps.get("tags", []),
            expiry=self._parse_ts(data.get("expires")),
            revoked=False,
            reusable=caps.get("reusable", False),
            ephemeral=caps.get("ephemeral", False),
            preauthorized=caps.get("preauthorized", False),
            created_at=self._parse_ts(data.get("created")),
            key=data.get("key"),
        )

    def revoke_auth_key(self, key_id: str) -> None:
        self._request("POST", f"/tailnet/{self._tailnet}/keys/{key_id}/revoke", data={})

    @staticmethod
    def _parse_ts(value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
