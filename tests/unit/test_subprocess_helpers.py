from __future__ import annotations

from tailscale_manager.utils.subprocess_helpers import _find_hint


class TestFindHint:
    def test_hint_tag_ownership(self) -> None:
        stderr = 'Error: oauth client does not own tag:server'
        hint = _find_hint(stderr, "apply")
        assert hint is not None
        assert "tag" in hint.lower()

    def test_hint_oauth_client(self) -> None:
        stderr = 'Error: invalid oauth client credentials'
        hint = _find_hint(stderr, "apply")
        assert hint is not None
        assert "OAuth" in hint

    def test_hint_permission_denied(self) -> None:
        stderr = 'permission denied: tailscale: ...'
        hint = _find_hint(stderr, "apply")
        assert hint is not None
        assert "scope" in hint.lower()

    def test_hint_no_such_tailnet(self) -> None:
        stderr = 'no such tailnet "example.ts.net"'
        hint = _find_hint(stderr, "apply")
        assert hint is not None
        assert "auto-resolve" in hint

    def test_hint_registry_terraform_io(self) -> None:
        stderr = 'Failed to query available provider packages from registry.terraform.io'
        hint = _find_hint(stderr, "init")
        assert hint is not None
        assert "network" in hint.lower()

    def test_hint_by_command_init(self) -> None:
        hint = _find_hint("some unrelated error", "init")
        assert hint == "Check network connectivity and terraform binary path"

    def test_hint_by_command_plan(self) -> None:
        hint = _find_hint("some unrelated error", "plan")
        assert hint == "Check your Tailscale OAuth scopes and tailnet name"

    def test_hint_by_command_apply(self) -> None:
        hint = _find_hint("some unrelated error", "apply")
        assert hint == "Check last-apply.json for details; run `tailscale-manager doctor`"

    def test_hint_by_command_destroy(self) -> None:
        hint = _find_hint("some unrelated error", "destroy")
        assert hint == "Ensure state file is present and uncorrupted"

    def test_no_match_no_command(self) -> None:
        hint = _find_hint("unknown error message", "unknown")
        assert hint is None

    def test_pattern_case_insensitive(self) -> None:
        stderr = 'OAUTH CLIENT does not own tag'
        hint = _find_hint(stderr, "apply")
        assert hint is not None
