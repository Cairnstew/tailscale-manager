"""
ACL backup and restore utilities.

Unlike tfstate backup (which copies a JSON state file), ACL backup stores a
raw policy string. The backup file extension is always .hujson regardless of
the user's configured format, because the live policy fetched from the
Tailscale API is always HuJSON.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from tailscale_manager.core.constants import BACKUP_DIR


ACL_BACKUP_PREFIX = "acl-backup-"


def backup_acl(backup_dir: Path, policy: str) -> Path:
    """Write current ACL policy to a timestamped backup file. Returns the backup path."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    backup_path = backup_dir / f"{ACL_BACKUP_PREFIX}{ts}.hujson"
    backup_path.write_text(policy)
    return backup_path


def restore_acl(backup_dir: Path) -> str | None:
    """Restore the most recent ACL backup. Returns the policy string, or None."""
    if not backup_dir.exists():
        return None
    backups = sorted(backup_dir.glob(f"{ACL_BACKUP_PREFIX}*.hujson"))
    if not backups:
        return None
    latest = backups[-1]
    return latest.read_text()


def prune_acl_backups(backup_dir: Path, keep: int = 5) -> None:
    """Remove old ACL backups, keeping the `keep` most recent."""
    if not backup_dir.exists():
        return
    backups = sorted(backup_dir.glob(f"{ACL_BACKUP_PREFIX}*.hujson"))
    while len(backups) > keep:
        backups[0].unlink()
        backups = backups[1:]
