from __future__ import annotations

from textual.widgets import Static

from tailscale_manager.core.config import AppConfig
from tailscale_manager.repositories.state_repository import StateRepository


class StatusPanel(Static):
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
            is_ok = result == "ok"
            icon = "[green]●[/green]" if is_ok else "[red]●[/red]"
            ts_str = str(ts)[:19] if not isinstance(ts, str) else ts[:19]
            lines.append(f"Last apply: {ts_str}")
            lines.append(f"  Result: {icon} {result}")
            if result == "ok":
                add = self.last_apply.get("add_count", 0)
                chg = self.last_apply.get("change_count", 0)
                rem = self.last_apply.get("remove_count", 0)
                lines.append(f"  Changes: +{add} ~{chg} -{rem}")
            err = self.last_apply.get("error_message")
            if err:
                lines.append(f"  [red]Error: {str(err)[:80]}[/red]")
        else:
            lines.append("Last apply: [yellow]never[/yellow]")

        lines.append("")
        state_file = self.config.state_dir / "terraform.tfstate"
        tf_icon = "[green]●[/green]" if state_file.exists() else "[red]●[/red]"
        tf_found = "found" if state_file.exists() else "not found"
        lines.append(f"Terraform state: {tf_icon} {tf_found}")

        backup_dir = self.config.state_dir / "backups"
        if backup_dir.exists():
            bcount = len(list(backup_dir.glob("*.tfstate")))
        else:
            bcount = 0
        lines.append(f"Backups: {bcount} retained")

        repo = StateRepository(self.config.state_dir)
        device_count = len(repo.get_devices())
        lines.append(f"Devices: {device_count} discovered")

        if not repo.check_state_file_permissions():
            lines.append("[yellow]⚠ tfstate permissions wider than 0600[/yellow]")

        lines.append("")
        lines.append(f"State dir: [dim]{self.config.state_dir}[/dim]")
        lines.append(f"Tailnet: [dim]{self.config.tailnet}[/dim]")
        self.update("\n".join(lines))
