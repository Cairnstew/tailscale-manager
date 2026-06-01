from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

from tailscale_manager.core.exceptions import TerraformError

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


def _build_terraform_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build a strict allowlist environment for terraform subprocess calls.

    SSL_CERT_FILE and NIX_SSL_CERT_FILE are required on NixOS because the
    Terraform provider makes HTTPS calls to the Tailscale API and the system
    certificate store is not at the standard FHS path. Missing these causes
    TLS verification failures at terraform apply time.
    """
    full_env = dict(os.environ)
    env = {k: full_env[k] for k in ALLOWED_ENV_KEYS if k in full_env}
    if extra:
        env.update(extra)
    return env


def run_terraform(
    terraform_bin: Path,
    args: list[str],
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout: int = 120,
) -> str:
    effective_env = _build_terraform_env() if env is None else dict(env)
    cmd = [str(terraform_bin), *args]
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
            msg = (
                f"terraform {' '.join(args)} failed (exit {result.returncode}):\n"
                f"{result.stderr.strip()}"
            )
            raise TerraformError(msg)
        return result.stdout.strip()
    except FileNotFoundError:
        raise TerraformError(
            f"terraform binary not found at {terraform_bin}"
        )
    except subprocess.TimeoutExpired:
        raise TerraformError(
            f"terraform {' '.join(args)} timed out after {timeout}s"
        )
