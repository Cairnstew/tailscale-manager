from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from tailscale_manager.core.config import AppConfig
from tailscale_manager.models.auth_key import TailscaleAuthKey
from tailscale_manager.repositories.state_repository import StateRepository
from tailscale_manager.services.api.client import TailscaleApiClient
from tailscale_manager.services.api.oauth import OAuthClient
from textual_ui.screens.log_viewer import LogViewerScreen
from textual_ui.widgets.auth_keys_table import AuthKeysTable
from textual_ui.widgets.devices_table import DevicesTable
from textual_ui.widgets.status_panel import StatusPanel


class MainScreen(Screen):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("l", "view_logs", "View Logs"),
        ("d", "toggle_devices", "Toggle Devices"),
    ]

    def __init__(
        self,
        config: AppConfig,
        keys: list[TailscaleAuthKey],
        last_apply: dict | None,
    ) -> None:
        super().__init__()
        self.app_config = config
        self.initial_last_apply = last_apply
        self.devices_visible = True

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(classes="left-column", id="left-column"):
                with Vertical(classes="panel", id="devices-section"):
                    yield Static("Devices", classes="section-title")
                    yield DevicesTable(id="devices-table")
                with Vertical(classes="panel"):
                    yield Static("Auth Keys", classes="section-title")
                    yield AuthKeysTable(id="auth-keys-table")
            with Vertical(classes="right-panel"):
                yield StatusPanel(self.app_config, self.initial_last_apply)
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"Tailscale Manager — {self.app_config.tailnet}"
        self._refresh_auth_keys()
        self._populate_devices()
        self.set_interval(30, self.action_refresh)

    def _refresh_auth_keys(self) -> None:
        try:
            client = TailscaleApiClient(
                oauth=OAuthClient(
                    client_id=self.app_config.oauth_client_id,
                    client_secret=self.app_config.oauth_client_secret,
                ),
                tailnet=self.app_config.tailnet,
            )
            keys = client.fetch_auth_keys()
        except Exception:
            try:
                repo = StateRepository(self.app_config.state_dir)
                keys = repo.get_managed_keys()
            except Exception:
                keys = []
        table = self.query_one(AuthKeysTable)
        table.load_keys(keys)

    def _populate_devices(self) -> None:
        try:
            repo = StateRepository(self.app_config.state_dir)
            devices = repo.get_devices()
        except Exception:
            devices = []
        table = self.query_one(DevicesTable)
        table.load_devices(devices)

    def action_refresh(self) -> None:
        self._refresh_auth_keys()
        self._populate_devices()
        sys_panel = self.query_one(StatusPanel)
        sys_panel.refresh_content()

    def action_view_logs(self) -> None:
        self.push_screen(LogViewerScreen())

    def action_toggle_devices(self) -> None:
        section = self.query_one("#devices-section", Vertical)
        self.devices_visible = not self.devices_visible
        if self.devices_visible:
            section.remove_class("hidden")
        else:
            section.add_class("hidden")
