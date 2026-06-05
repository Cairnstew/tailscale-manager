from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


__all__ = [
    "BaseApiClient",
    "TailscaleAPIError",
]


class TailscaleAPIError(Exception):
    pass


class BaseApiClient(ABC):
    @abstractmethod
    def _request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
    ) -> Any:
        ...
