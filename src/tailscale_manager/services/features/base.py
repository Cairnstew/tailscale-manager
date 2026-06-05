from __future__ import annotations

from abc import ABC, abstractmethod


__all__ = [
    "BaseFeatureBuilder",
]


class BaseFeatureBuilder(ABC):
    @abstractmethod
    def build(self) -> dict:
        ...
