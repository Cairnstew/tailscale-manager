from __future__ import annotations

import os
import subprocess

from textual.app import App as TextualAppBase
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static, TextArea

from tailscale_manager.core.config import AppConfig
from tailscale_manager.models.auth_key import TailscaleAuthKey
from tailscale_manager.models.device import TailscaleDevice
from tailscale_manager.repositories.state_repository import StateRepository


def run_status_app(
    config: AppConfig,
    keys: list[TailscaleAuthKey],
    last_apply: dict | None,
) -> None:
    app = TailscaleManagerApp(config, keys, last_apply)
    app.run()


class SystemStatus(Static):
    config: AppConfig
    last_apply: dict | None

    def __init__(
        self,
        config: AppConfig,
        last_apply: dict | None,
    ) -> None:
        super().__init__()
        self.config = config
        self.last_apply = last_apply

    def on_mount(self) -> None:
        self.refresh_content()

    def refresh_content(self) -> None:
        repo = StateRepository(self.config.state_dir)
        last = repo.read_last_apply()
        if last:
            self.last_apply = last

        lines: list[str] = []
        lines.append("[bold]System Status[/bold]")
        lines.append("")

        if self.last_apply:
            ts = self.last_apply.get("timestamp", "unknown")
            result = self.last_apply.get("result", "unknown")
            icon = "✓" if result == "ok" else "✗"
            ts_str = str(ts)[:19] if not isinstance(ts, str) else ts[:19]
            lines.append(f"Last apply: {ts_str}")
            lines.append(f"  Result: {icon} {result}")
            err = self.last_apply.get("error_message")
            if err:
                lines.append(f"  Error: {str(err)[:80]}")
        else:
            lines.append("Last apply: never")

        lines.append("")
        state_file = self.config.state_dir / "terraform.tfstate"
        tf_found = "found" if state_file.exists() else "not found"
        lines.append(f"Terraform state: {tf_found}")

        has_id = bool(os.environ.get("TAILSCALE_OAUTH_CLIENT_ID"))
        has_secret = bool(os.environ.get("TAILSCALE_OAUTH_CLIENT_SECRET"))
        creds_status = "found" if has_id and has_secret else "not set"
        lines.append(f"Credentials: {creds_status}")

        backup_dir = self.config.state_dir / "backups"
        if backup_dir.exists():
            bcount = len(list(backup_dir.glob("*.tfstate")))
        else:
            bcount = 0
        lines.append(f"Backups: {bcount} retained")

        repo = StateRepository(self.config.state_dir)
        device_count = len(repo.get_devices())
        lines.append(f"Devices: {device_count} discovered")

        lines.append("")
        lines.append(f"State dir: {self.config.state_dir}")
        lines.append(f"Tailnet: {self.config.tailnet}")
        self.update("\n".join(lines))


class LogViewer(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield TextArea("Loading logs...", read_only=True)
        yield Footer()

    BINDINGS = [("escape", "dismiss", "Back")]

    def on_mount(self) -> None:
        try:
            result = subprocess.run(
                ["journalctl", "-u", "tailscale-manager.service", "--no-pager", "-n", "30"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            content = result.stdout or "No logs found"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            content = "Unable to fetch logs"
        ta = self.query_one(TextArea)
        ta.text = content


class TailscaleManagerApp(TextualAppBase):
    CSS = """
    Screen {
        layout: horizontal;
    }

    .left-panel {
        width: 40%;
        height: 100%;
        border: solid $primary;
        padding: 0 1;
    }

    .center-panel {
        width: 35%;
        height: 100%;
        border: solid $primary;
        padding: 0 1;
    }

    .right-panel {
        width: 25%;
        height: 100%;
        border: solid $primary;
        padding: 0 1;
    }

    .hidden {
        display: none;
    }
    """

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
        self.initial_keys = keys
        self.initial_last_apply = last_apply
        self.devices_visible = True

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(classes="left-panel"):
                yield DataTable(id="keys-table")
            with Vertical(classes="center-panel", id="devices-panel"):
                yield DataTable(id="devices-table")
            with Vertical(classes="right-panel"):
                yield SystemStatus(self.app_config, self.initial_last_apply)
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"Tailscale Manager — {self.app_config.tailnet}"
        self._populate_table(self.initial_keys)
        self._populate_devices()
        self.set_interval(30, self.action_refresh)

    def _populate_table(self, keys: list[TailscaleAuthKey]) -> None:
        table = self.query_one("#keys-table", DataTable)
        table.clear(columns=True)
        table.add_columns("ID", "Description", "Tags", "Expiry", "Status")
        for k in keys:
            status = "✓" if not k.revoked else "✗"
            expiry = k.expiry.strftime("%Y-%m-%d") if k.expiry else "-"
            tags = ", ".join(k.tags) if k.tags else "-"
            table.add_row(
                k.id[:16] if k.id else "-",
                k.description or "-",
                tags,
                expiry,
                status,
            )
        if not keys:
            table.add_row("(no keys managed)", "", "", "", "")

    def _populate_devices(self) -> None:
        table = self.query_one("#devices-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Name", "Hostname", "Addresses", "Tags", "User")
        repo = StateRepository(self.app_config.state_dir)
        devices = repo.get_devices()
        for d in devices:
            addrs = ", ".join(d.addresses[:3]) if d.addresses else "-"
            tags = ", ".join(d.tags[:3]) if d.tags else "-"
            table.add_row(
                d.name or "-",
                d.hostname or "-",
                addrs,
                tags,
                d.user or "-",
            )
        if not devices:
            table.add_row("(run apply to discover devices)", "", "", "", "")

    def action_refresh(self) -> None:
        repo = StateRepository(self.app_config.state_dir)
        keys = repo.get_managed_keys()
        self._populate_table(keys)
        self._populate_devices()
        sys_panel = self.query_one(SystemStatus)
        sys_panel.refresh_content()

    def action_view_logs(self) -> None:
        self.push_screen(LogViewer())

    def action_toggle_devices(self) -> None:
        panel = self.query_one("#devices-panel", Vertical)
        self.devices_visible = not self.devices_visible
        if self.devices_visible:
            panel.remove_class("hidden")
        else:
            panel.add_class("hidden")
