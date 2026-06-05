from __future__ import annotations

from tailscale_manager.services.features.base import BaseFeatureBuilder


__all__ = [
    "DeviceFeatureBuilder",
    "build_devices_config",
]


class DeviceFeatureBuilder(BaseFeatureBuilder):
    def build(self) -> dict:
        return {
            "data": {
                "tailscale_devices": {
                    "all": {}
                }
            }
        }


def build_devices_config() -> dict:
    return DeviceFeatureBuilder().build()
