from __future__ import annotations

from pydantic import BaseModel


class TailnetSettings(BaseModel):
    devices_approval_on: bool | None = None
    devices_auto_updates_on: bool | None = None
    devices_key_duration_days: int | None = None
    users_approval_on: bool | None = None
    acls_externally_managed_on: bool | None = None
    acls_external_link: str | None = None
    posture_identity_collection_on: bool | None = None
    https_enabled: bool | None = None
    regional_routing_on: bool | None = None
    users_role_allowed_to_join_external_tailnet: str | None = None
