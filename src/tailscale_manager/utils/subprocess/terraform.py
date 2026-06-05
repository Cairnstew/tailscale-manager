from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

from tailscale_manager.core.exceptions import TerraformError
from tailscale_manager.utils.subprocess.base import BaseSubprocessRunner


__all__ = [
    "TerraformRunner",
    "ALLOWED_ENV_KEYS",
]


ALLOWED_ENV_KEYS = frozenset({
    "HOME",
    "PATH",
    "TMPDIR",
    "TF_LOG",
    "TF_LOG_PATH",
    "TAILSCALE_OAUTH_CLIENT_ID",
    "TAILSCALE_OAUTH_CLIENT_SECRET",
    "TAILSCALE_TAILNET",
    "SSL_CERT_FILE",
    "NIX_SSL_CERT_FILE",
    "CREDENTIALS_DIRECTORY",
})

_KNOWN_ERROR_PATTERNS: list[tuple[str, str]] = [
    ("does not own tag:", "The OAuth client does not own this tag — add it in the Tailscale admin console under Settings → OAuth → Tag ownership"),
    ("oauth client", "Check your OAuth client ID and secret in credentialsFile"),
    ("permission denied", "The OAuth client lacks the required scope — verify scopes in the admin console"),
    ("no such tailnet", 'The tailnet name is incorrect — use "-" to auto-resolve'),
    ("registry.terraform.io", "Network error reaching Terraform registry — check internet connectivity"),
]

_HINT_BY_COMMAND: dict[str, str] = {
    "init": "Check network connectivity and terraform binary path",
    "plan": "Check your Tailscale OAuth scopes and tailnet name",
    "apply": "Check last-apply.json for details; run `tailscale-manager doctor`",
    "destroy": "Ensure state file is present and uncorrupted",
}


def _find_hint(stderr: str, command: str) -> str | None:
    for pattern, hint in _KNOWN_ERROR_PATTERNS:
        if pattern.lower() in stderr.lower():
            return hint
    return _HINT_BY_COMMAND.get(command)


def _build_terraform_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    full_env = dict(os.environ)
    env = {k: full_env[k] for k in ALLOWED_ENV_KEYS if k in full_env}
    if extra:
        env.update(extra)
    return env


class TerraformRunner(BaseSubprocessRunner):
    def __init__(self, terraform_bin: Path) -> None:
        self._terraform_bin = terraform_bin

    def run(
        self,
        args: list[str],
        cwd: Path,
        timeout: int = 120,
        env: Mapping[str, str] | None = None,
    ) -> str:
        effective_env = _build_terraform_env(extra=env)
        cmd = [str(self._terraform_bin), *args]
        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=effective_env,
            )
            if result.returncode != 0 and not (
                len(args) >= 1 and args[0] == "plan" and result.returncode == 2
            ):
                command = args[0] if args else "unknown"
                raise TerraformError(
                    command=command,
                    exit_code=result.returncode,
                    stdout=result.stdout.strip(),
                    stderr=result.stderr.strip(),
                    hint=_find_hint(result.stderr, command),
                )
            return result.stdout.strip()
        except FileNotFoundError:
            raise TerraformError(
                command=" ".join(args),
                exit_code=-1,
                stdout="",
                stderr="",
                hint=f"terraform binary not found at {self._terraform_bin} — ensure it is installed",
            )
        except subprocess.TimeoutExpired:
            command = args[0] if args else "unknown"
            raise TerraformError(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"timed out after {timeout}s",
                hint="Increase timeout or check network connectivity",
            )
