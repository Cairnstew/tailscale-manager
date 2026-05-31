from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TailscaleDevice:
    addresses: list[str] = field(default_factory=list)
    hostname: str = ""
    id: str = ""
    name: str = ""
    node_id: str = ""
    tags: list[str] = field(default_factory=list)
    user: str = ""
