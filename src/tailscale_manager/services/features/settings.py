from __future__ import annotations

from tailscale_manager.models.settings import TailnetSettings


def build_settings_config(settings: TailnetSettings | None) -> dict:
    if settings is None:
        return {}

    body = settings.model_dump(exclude_none=True)
    return {
        "resource": {
            "tailscale_tailnet_settings": {
                "tailnet": body
            }
        }
    }
