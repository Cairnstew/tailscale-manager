from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


__all__ = [
    "BaseSubprocessRunner",
]


class BaseSubprocessRunner(ABC):
    @abstractmethod
    def run(
        self,
        args: list[str],
        cwd: Path,
        timeout: int = 120,
    ) -> str:
        ...
