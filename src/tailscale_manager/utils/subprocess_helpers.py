from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

from tailscale_manager.core.exceptions import TerraformError


def run_terraform(
    terraform_bin: Path,
    args: list[str],
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout: int = 120,
) -> str:
    cmd = [str(terraform_bin), *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        # terraform plan -detailed-exitcode returns:
        #   0 = no changes, 1 = error, 2 = non-empty diff
        # Treat exit code 2 as success for plan (changes to apply).
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
