from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from tailscale_manager.core.config import AppConfig
from tailscale_manager.models.auth_key import TailscaleAuthKey
from tailscale_manager.models.device import TailscaleDevice
from tailscale_manager.repositories.state_repository import StateRepository


class StatusPanel(Static):
    def __init__(
        self,
        config: AppConfig,
        last_apply: dict | None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.last_apply = last_apply

    def on_mount(self) -> None:
        self._update_content()

    def _update_content(self) -> None:
        lines: list[str] = [
            "[bold]System Status[/bold]",
            "",
            f"Tailnet: {self.config.tailnet}",
            f"State dir: {self.config.state_dir}",
            "",
            "[bold]Terraform[/bold]",
        ]
        state_file = self.config.state_dir / "terraform.tfstate"
        lines.append("State: present" if state_file.exists() else "State: not found")

        if self.config.oauth_client_id and self.config.oauth_client_secret:
            lines.append("Credentials: found")
        else:
            lines.append("Credentials: not found")

        backup_dir = self.config.state_dir / "backups"
        backup_count = (
            len(list(backup_dir.glob("terraform.tfstate.*")))
            if backup_dir.exists()
            else 0
        )
        lines.append(f"Backups: {backup_count}")

        repo = StateRepository(self.config.state_dir)
        device_count = len(repo.get_devices())
        lines.append(f"Devices: {device_count}")

        lines.extend(["", "[bold]Last Apply[/bold]"])
        if self.last_apply:
            lines.append(f"Timestamp: {self.last_apply.get('timestamp', 'unknown')}")
            lines.append(f"Result: {self.last_apply.get('result', 'unknown')}")
            err = self.last_apply.get("error_message")
            if err:
                lines.append(f"Error: {err}")
        else:
            lines.append("No apply has been run yet.")

        self.update("\n".join(lines))


class KeyTable(DataTable):
    def __init__(self, keys: list[TailscaleAuthKey], **kwargs) -> None:
        super().__init__(**kwargs)
        self._keys = keys

    def on_mount(self) -> None:
        self.add_columns("ID", "Description", "Tags", "Status")
        self._populate()

    def _populate(self) -> None:
        self.clear()
        rows = [
            (
                k.id[:16] if k.id else "",
                k.description or "",
                ", ".join(k.tags) if k.tags else "",
                "\u2713" if not k.revoked else "\u2717",
            )
            for k in self._keys
        ]
        if rows:
            self.add_rows(rows)
        else:
            self.add_row("(no auth keys managed)", "", "", "")


class DeviceTable(DataTable):
    def __init__(self, devices: list[TailscaleDevice], **kwargs) -> None:
        super().__init__(**kwargs)
        self._devices = devices

    def on_mount(self) -> None:
        self.add_columns("Hostname", "Addresses", "Tags", "User")
        self._populate()

    def _populate(self) -> None:
        self.clear()
        rows = [
            (
                d.hostname or d.name or "",
                ", ".join(d.addresses) if d.addresses else "",
                ", ".join(d.tags) if d.tags else "",
                d.user or "",
            )
            for d in self._devices
        ]
        if rows:
            self.add_rows(rows)
        else:
            self.add_row("(no devices discovered)", "", "", "")


class LogViewerScreen(Screen):
    BINDINGS = [
        Binding("escape", "dismiss", "Back"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, last_apply: dict | None) -> None:
        super().__init__()
        self.last_apply = last_apply

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._format_log())
        yield Footer()

    def _format_log(self) -> str:
        if not self.last_apply:
            return "No apply has been run yet."
        lines: list[str] = [
            "[bold]Last Apply Details[/bold]",
            "",
            f"Timestamp: {self.last_apply.get('timestamp', 'unknown')}",
            f"Result: {self.last_apply.get('result', 'unknown')}",
        ]
        stdout = self.last_apply.get("stdout")
        if stdout:
            lines.extend(["", "[bold]Terraform Output[/bold]", "", stdout])
        stderr = self.last_apply.get("stderr")
        if stderr:
            lines.extend(["", "[bold]Terraform Errors[/bold]", "", stderr])
        error = self.last_apply.get("error_message")
        if error:
            lines.append(f"\n[red]Error: {error}[/red]")
        return "\n".join(lines)


class StatusApp(App):
    CSS = """
    Horizontal {
        height: 1fr;
    }

    #keys-table {
        width: 35%;
        border: solid $accent;
    }

    #devices-table {
        width: 40%;
        border: solid $accent;
    }

    #status-content {
        width: 25%;
        border: solid $accent;
    }

    DataTable {
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_data", "Refresh"),
        Binding("l", "view_logs", "Logs"),
        Binding("d", "toggle_devices", "Devices"),
    ]

    show_devices = reactive(True)

    def __init__(
        self,
        config: AppConfig,
        keys: list[TailscaleAuthKey],
        last_apply: dict | None,
    ) -> None:
        super().__init__()
        self.config = config
        self.keys = keys
        self.last_apply = last_apply
        self._repo = StateRepository(config.state_dir)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield KeyTable(self.keys, id="keys-table")
            yield DeviceTable(self._repo.get_devices(), id="devices-table")
            yield StatusPanel(self.config, self.last_apply, id="status-content")
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"Tailscale Manager \u2014 {self.config.tailnet}"
        self.set_interval(30, self.action_refresh_data)

    def action_refresh_data(self) -> None:
        self.keys = self._repo.get_managed_keys()
        self.last_apply = self._repo.read_last_apply()
        devices = self._repo.get_devices()

        self.query_one("#keys-table", KeyTable)._keys = self.keys
        self.query_one("#keys-table", KeyTable)._populate()
        self.query_one("#devices-table", DeviceTable)._devices = devices
        self.query_one("#devices-table", DeviceTable)._populate()

        panel = self.query_one("#status-content", StatusPanel)
        panel.last_apply = self.last_apply
        panel._update_content()

    def action_view_logs(self) -> None:
        self.push_screen(LogViewerScreen(self.last_apply))

    def watch_show_devices(self, show: bool) -> None:
        self.query_one("#devices-table").display = show

    def action_toggle_devices(self) -> None:
        self.show_devices = not self.show_devices


def run_status_app(
    config: AppConfig,
    keys: list[TailscaleAuthKey],
    last: dict | None,
) -> None:
    StatusApp(config=config, keys=keys, last_apply=last).run()
