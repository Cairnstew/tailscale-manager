from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


__all__ = [
    "BaseRepository",
]


class BaseRepository(ABC):
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir

    @abstractmethod
    def read_state(self) -> dict | None:
        ...
