from __future__ import annotations

from textual.widgets import DataTable

from tailscale_manager.models.device import TailscaleDevice


class DevicesTable(DataTable):
    def on_mount(self) -> None:
        self.add_columns("Name", "Hostname", "Addresses", "Tags", "User")

    def load_devices(self, devices: list[TailscaleDevice]) -> None:
        self.clear()
        for d in devices:
            addrs = ", ".join(d.addresses[:3]) if d.addresses else "-"
            tags = ", ".join(d.tags[:3]) if d.tags else "-"
            self.add_row(
                d.name or "-",
                d.hostname or "-",
                addrs,
                tags,
                d.user or "-",
            )
        if not devices:
            self.add_row("(run apply to discover devices)", "", "", "", "")
