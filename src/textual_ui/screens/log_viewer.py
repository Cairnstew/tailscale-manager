from __future__ import annotations

import subprocess

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, TextArea


class LogViewerScreen(Screen):
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
