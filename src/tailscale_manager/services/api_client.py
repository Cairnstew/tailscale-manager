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


def _get_oauth_token(client_id: str = "", client_secret: str = "") -> str:
    if not client_id:
        client_id = os.environ.get("TAILSCALE_OAUTH_CLIENT_ID", "")
    if not client_secret:
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


def _api_get(path: str, client_id: str = "", client_secret: str = "") -> Any:
    token = _get_oauth_token(client_id, client_secret)
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _api_post(
    path: str,
    data: dict[str, Any],
    client_id: str = "",
    client_secret: str = "",
) -> Any:
    token = _get_oauth_token(client_id, client_secret)
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _api_delete(path: str, client_id: str = "", client_secret: str = "") -> None:
    token = _get_oauth_token(client_id, client_secret)
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        method="DELETE",
    )
    with urllib.request.urlopen(req):
        pass


def _parse_ts(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def fetch_auth_keys(tailnet: str = "-", client_id: str = "", client_secret: str = "") -> list[TailscaleAuthKey]:
    data = _api_get(f"/tailnet/{tailnet}/keys", client_id=client_id, client_secret=client_secret)
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


def create_auth_key(
    tailnet: str = "-",
    description: str = "",
    tags: list[str] | None = None,
    reusable: bool = True,
    ephemeral: bool = False,
    preauthorized: bool = True,
    expiry_seconds: int | None = None,
    client_id: str = "",
    client_secret: str = "",
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

    data = _api_post(
        f"/tailnet/{tailnet}/keys",
        data=body,
        client_id=client_id,
        client_secret=client_secret,
    )
    caps = data.get("capabilities", {}).get("devices", {}).get("create", {})
    return TailscaleAuthKey(
        id=data.get("id", ""),
        description=data.get("description", ""),
        tags=caps.get("tags", []),
        expiry=_parse_ts(data.get("expires")),
        revoked=False,
        reusable=caps.get("reusable", False),
        ephemeral=caps.get("ephemeral", False),
        preauthorized=caps.get("preauthorized", False),
        created_at=_parse_ts(data.get("created")),
        key=data.get("key"),
    )


def revoke_auth_key(
    key_id: str,
    tailnet: str = "-",
    client_id: str = "",
    client_secret: str = "",
) -> None:
    _api_post(
        f"/tailnet/{tailnet}/keys/{key_id}/revoke",
        data={},
        client_id=client_id,
        client_secret=client_secret,
    )
