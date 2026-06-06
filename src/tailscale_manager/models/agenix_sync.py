from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class AgenixSyncResult:
    status: Literal["ok", "error", "skipped"]
    secret_name: str
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "secret_name": self.secret_name,
            "error_message": self.error_message,
        }
