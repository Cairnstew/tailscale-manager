from __future__ import annotations

from textual.app import App as TextualAppBase, ComposeResult

from tailscale_manager.core.config import AppConfig
from tailscale_manager.models.auth_key import TailscaleAuthKey
from textual_ui.screens.main_screen import MainScreen


class TailscaleManagerApp(TextualAppBase):
    CSS = """
    Screen {
        layout: horizontal;
        background: #0a0e14;
    }

    Header {
        background: #131a22;
        color: #c8d6e5;
        text-style: bold;
    }

    Footer {
        background: #131a22;
        color: #536277;
    }

    Footer > .footer--key {
        color: #4dabf7;
        text-style: bold;
    }

    Footer > .footer--description {
        color: #8395a7;
    }

    .left-column {
        width: 75%;
        height: 100%;
        layout: vertical;
        border: solid rgba(40, 55, 75, 0.6);
        background: rgba(15, 22, 30, 0.85);
        padding: 0 1;
    }

    .left-column > .panel {
        height: 50%;
    }

    #devices-section {
        border-bottom: solid rgba(40, 55, 75, 0.3);
    }

    .right-panel {
        width: 25%;
        height: 100%;
        border: solid rgba(40, 55, 75, 0.6);
        background: rgba(15, 22, 30, 0.85);
        padding: 0 1;
        margin: 0 0;
    }

    .hidden {
        display: none;
    }

    DataTable {
        height: 100%;
        background: transparent;
        border: none;
    }

    DataTable > .datatable--header {
        background: rgba(40, 55, 75, 0.4);
        color: #4dabf7;
        text-style: bold;
    }

    DataTable > .datatable--row {
        background: transparent;
        color: #c8d6e5;
    }

    DataTable > .datatable--row:hover {
        background: rgba(77, 171, 247, 0.08);
    }

    DataTable > .datatable--cursor {
        background: rgba(77, 171, 247, 0.12);
    }

    DataTable > .datatable--odd-row {
        background: rgba(255, 255, 255, 0.02);
    }

    DataTable > .datatable--even-row {
        background: transparent;
    }

    #auth-keys-table {
        height: 100%;
    }

    #devices-table {
        height: 100%;
    }

    .section-title {
        text-style: bold;
        color: #4dabf7;
        padding: 0 0 0 1;
        height: 1;
    }

    StatusPanel {
        padding: 1 1;
        background: transparent;
        color: #c8d6e5;
    }

    LogViewerScreen Screen {
        background: #0a0e14;
    }

    TextArea {
        background: rgba(15, 22, 30, 0.85);
        color: #c8d6e5;
        border: solid rgba(40, 55, 75, 0.6);
    }
    """

    def __init__(
        self,
        config: AppConfig,
        keys: list[TailscaleAuthKey],
        last_apply: dict | None,
    ) -> None:
        super().__init__()
        self.app_config = config
        self.keys = keys
        self.last_apply = last_apply

    def compose(self) -> ComposeResult:
        yield MainScreen(self.app_config, self.keys, self.last_apply)

    def on_mount(self) -> None:
        self.title = f"Tailscale Manager — {self.app_config.tailnet}"


def run_status_app(
    config: AppConfig,
    keys: list[TailscaleAuthKey],
    last_apply: dict | None,
) -> None:
    app = TailscaleManagerApp(config, keys, last_apply)
    app.run()
