from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AclConfig(BaseModel):
    enable: bool = False
    format: Literal["hujson", "json"] = "hujson"
    policy: str = Field(default="", description="Full ACL policy string (HuJSON or JSON)")
