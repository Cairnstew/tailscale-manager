from __future__ import annotations

from textual.widgets import DataTable

from tailscale_manager.models.auth_key import TailscaleAuthKey


class AuthKeysTable(DataTable):
    def on_mount(self) -> None:
        self.add_columns("ID", "Description", "Tags", "Expiry", "Status")

    def load_keys(self, keys: list[TailscaleAuthKey]) -> None:
        self.clear()
        for k in keys:
            status = "[green]●[/green]" if not k.revoked else "[red]●[/red]"
            expiry = k.expiry.strftime("%Y-%m-%d") if k.expiry else "-"
            tags = ", ".join(k.tags) if k.tags else "-"
            self.add_row(
                k.id[:16] if k.id else "-",
                k.description or "-",
                tags,
                expiry,
                status,
            )
        if not keys:
            self.add_row("(no auth keys managed)", "", "", "", "")
