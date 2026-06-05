from __future__ import annotations

from pathlib import Path

from tailscale_manager.core.config import AppConfig
from tailscale_manager.models.auth_key import TailscaleAuthKey
from tailscale_manager.models.device import TailscaleDevice


def test_widgets_importable() -> None:
    from textual_ui.widgets.auth_keys_table import AuthKeysTable
    from textual_ui.widgets.devices_table import DevicesTable
    from textual_ui.widgets.status_panel import StatusPanel
    assert AuthKeysTable is not None
    assert DevicesTable is not None
    assert StatusPanel is not None


def test_screens_importable() -> None:
    from textual_ui.screens.log_viewer import LogViewerScreen
    from textual_ui.screens.main_screen import MainScreen
    assert LogViewerScreen is not None
    assert MainScreen is not None


def test_app_importable() -> None:
    from textual_ui.app import TailscaleManagerApp, run_status_app
    assert TailscaleManagerApp is not None
    assert callable(run_status_app)


def test_app_constructable() -> None:
    config = AppConfig(
        tailnet="test",
        state_dir=Path("/tmp/test-tailscale"),
        oauth_client_id="test-id",
        oauth_client_secret="test-secret",
    )
    keys = [
        TailscaleAuthKey(
            id="k123",
            description="test key",
            tags=["tag:test"],
            key="tskey-auth-xxx",
        )
    ]
    from textual_ui.app import TailscaleManagerApp

    app = TailscaleManagerApp(config=config, keys=keys, last_apply=None)
    assert app.app_config == config
    assert app.keys == keys
    assert app.last_apply is None


def test_widget_status_panel_constructable() -> None:
    config = AppConfig(
        tailnet="test",
        state_dir=Path("/tmp/test-tailscale"),
    )
    from textual_ui.widgets.status_panel import StatusPanel

    panel = StatusPanel(config=config, last_apply=None)
    assert panel.config == config


def test_run_status_app_importable() -> None:
    from textual_ui import run_status_app
    assert callable(run_status_app)
