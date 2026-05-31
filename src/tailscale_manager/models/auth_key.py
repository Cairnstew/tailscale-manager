from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TailscaleAuthKey:
    id: str
    description: str
    tags: list[str] = field(default_factory=list)
    expiry: datetime | None = None
    revoked: bool = False
    reusable: bool = True
    ephemeral: bool = False
    preauthorized: bool = True
    created_at: datetime | None = None
    key: str | None = None
