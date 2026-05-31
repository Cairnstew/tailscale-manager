from __future__ import annotations

from pathlib import Path

from tailscale_manager.core.acl_backup import (
    ACL_BACKUP_PREFIX,
    backup_acl,
    prune_acl_backups,
    restore_acl,
)


def test_backup_acl_writes_file(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    policy = '{"acls": []}'
    path = backup_acl(backup_dir, policy)
    assert path.exists()
    assert path.suffix == ".hujson"
    assert ACL_BACKUP_PREFIX in path.name
    assert path.read_text() == policy


def test_restore_acl_reads_latest_backup(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    backup_acl(backup_dir, '{"acls": [{"version": 1}]}')
    backup_acl(backup_dir, '{"acls": [{"version": 2}]}')

    restored = restore_acl(backup_dir)
    assert restored is not None
    assert '"version": 2' in restored


def test_restore_acl_no_backups_noop(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    assert restore_acl(backup_dir) is None


def test_prune_acl_backups_keeps_n(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    for _ in range(5):
        backup_acl(backup_dir, '{"acls": []}')

    prune_acl_backups(backup_dir, keep=2)
    remaining = sorted(backup_dir.glob(f"{ACL_BACKUP_PREFIX}*.hujson"))
    assert len(remaining) == 2


def test_prune_acl_backups_no_backups_noop(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    prune_acl_backups(backup_dir, keep=5)
    assert not backup_dir.exists() or len(list(backup_dir.iterdir())) == 0
