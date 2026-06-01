from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime
from typing import Any

from tailscale_manager.models.auth_key import TailscaleAuthKey

API_BASE = "https://api.tailscale.com/api/v2"


class TailscaleAPIError(Exception):
    pass


def _get_oauth_token() -> str:
    client_id = os.environ.get("TAILSCALE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("TAILSCALE_OAUTH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise TailscaleAPIError("TAILSCALE_OAUTH_CLIENT_ID and TAILSCALE_OAUTH_CLIENT_SECRET must be set")

    import base64
    creds = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(creds.encode()).decode()
    req = urllib.request.Request(
        f"{API_BASE}/oauth/token",
        data=json.dumps({"grant_type": "client_credentials"}).encode(),
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data["access_token"]


def _api_get(path: str) -> Any:
    token = _get_oauth_token()
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _parse_ts(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def fetch_auth_keys(tailnet: str = "-") -> list[TailscaleAuthKey]:
    data = _api_get(f"/tailnet/{tailnet}/keys")
    keys: list[TailscaleAuthKey] = []
    for k in data.get("keys", []):
        if k.get("keyType") != "auth":
            continue
        caps = k.get("capabilities", {}).get("devices", {}).get("create", {})
        keys.append(TailscaleAuthKey(
            id=k.get("id", ""),
            description=k.get("description", ""),
            tags=caps.get("tags", []),
            expiry=_parse_ts(k.get("expires")),
            revoked=k.get("revoked", False),
            reusable=caps.get("reusable", False),
            ephemeral=caps.get("ephemeral", False),
            preauthorized=caps.get("preauthorized", False),
            created_at=_parse_ts(k.get("created")),
            key=None,
        ))
    return keys
