from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from pathlib import Path

from tailscale_manager.core.config import AppConfig

_logger = logging.getLogger(__name__)


class PolicyWatcher:
    def __init__(
        self,
        config: AppConfig,
        apply_fn: Callable[[], dict],
        poll_interval: int = 2,
        debounce: int = 2,
    ) -> None:
        self._config = config
        self._apply_fn = apply_fn
        self._poll_interval = poll_interval
        self._debounce = debounce
        self._running = False
        self._files: dict[Path, str | None] = {}
        self._init_files()

    def _init_files(self) -> None:
        candidates: list[Path] = []
        if self._config.acl_policy_path:
            candidates.append(self._config.acl_policy_path)
        if self._config.auth_keys_path:
            candidates.append(self._config.auth_keys_path)
        for p in candidates:
            if p.exists():
                self._files[p] = self._hash_file(p)

    @staticmethod
    def _hash_file(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _refresh_files(self) -> None:
        disappeared = [p for p in self._files if not p.exists()]
        for p in disappeared:
            _logger.warning("Watched file disappeared: %s", p)
            del self._files[p]

        if self._config.acl_policy_path and self._config.acl_policy_path.exists():
            if self._config.acl_policy_path not in self._files:
                self._files[self._config.acl_policy_path] = self._hash_file(self._config.acl_policy_path)
                _logger.info("Now watching: %s", self._config.acl_policy_path)
        if self._config.auth_keys_path and self._config.auth_keys_path.exists():
            if self._config.auth_keys_path not in self._files:
                self._files[self._config.auth_keys_path] = self._hash_file(self._config.auth_keys_path)
                _logger.info("Now watching: %s", self._config.auth_keys_path)

    def _check_changes(self) -> bool:
        changed = False
        for path in list(self._files):
            if path.exists():
                current = self._hash_file(path)
                stored = self._files[path]
                if current != stored:
                    self._files[path] = current
                    changed = True
        return changed

    def run(self) -> None:
        if not self._files:
            _logger.info("No files to watch. Exiting.")
            return

        self._running = True
        _logger.info(
            "Watching %d file(s) for changes (poll every %ds)...",
            len(self._files),
            self._poll_interval,
        )
        while self._running:
            time.sleep(self._poll_interval)
            self._refresh_files()
            if self._check_changes():
                _logger.info("File change detected, waiting for quiet period...")
                time.sleep(self._debounce)
                if self._check_changes():
                    continue
                _logger.info("File settled — running apply")
                result = self._apply_fn()
                if result.get("result") == "ok":
                    _logger.info("Apply succeeded")
                else:
                    _logger.error("Apply failed: %s", result.get("error_message"))

    def stop(self) -> None:
        self._running = False
