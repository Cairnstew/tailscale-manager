from __future__ import annotations

import base64
import json
import os
import urllib.request
from dataclasses import dataclass

from tailscale_manager.services.api.base import TailscaleAPIError


__all__ = [
    "OAuthClient",
]


API_BASE = "https://api.tailscale.com/api/v2"


@dataclass
class OAuthClient:
    client_id: str = ""
    client_secret: str = ""

    def get_token(self) -> str:
        cid = self.client_id or os.environ.get("TAILSCALE_OAUTH_CLIENT_ID", "")
        cs = self.client_secret or os.environ.get("TAILSCALE_OAUTH_CLIENT_SECRET", "")
        if not cid or not cs:
            raise TailscaleAPIError(
                "TAILSCALE_OAUTH_CLIENT_ID and TAILSCALE_OAUTH_CLIENT_SECRET must be set"
            )
        creds = f"{cid}:{cs}"
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
