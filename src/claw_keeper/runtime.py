"""Runtime state and snapshot locking."""

from __future__ import annotations

import fcntl
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def runtime_root() -> Path:
    return Path.home() / ".cache" / "claw-keeper"


def repo_hash(repo_path: str) -> str:
    return hashlib.sha256(
        str(Path(repo_path).expanduser().resolve()).encode("utf-8")
    ).hexdigest()[:16]


@dataclass(frozen=True)
class RuntimeState:
    root: Path
    lock_path: Path
    pending_path: Path
    watch_state_path: Path
    tmp_dir: Path

    @classmethod
    def for_repo(cls, repo_path: str) -> "RuntimeState":
        root = runtime_root() / repo_hash(repo_path)
        return cls(
            root=root,
            lock_path=root / "snapshot.lock",
            pending_path=root / "snapshot.pending",
            watch_state_path=root / "watch-state.json",
            tmp_dir=root / "tmp",
        )

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def touch_pending(self) -> None:
        self.ensure()
        self.pending_path.write_text("pending\n", encoding="utf-8")

    def clear_pending(self) -> None:
        try:
            self.pending_path.unlink()
        except FileNotFoundError:
            pass

    def has_pending(self) -> bool:
        return self.pending_path.exists()


class SnapshotLock:
    def __init__(self, state: RuntimeState):
        self.state = state
        self._handle = None

    def acquire(self) -> bool:
        self.state.ensure()
        self._handle = self.state.lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._handle.close()
            self._handle = None
            return False
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write("locked\n")
        self._handle.flush()
        return True

    def release(self) -> None:
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "SnapshotLock":
        acquired = self.acquire()
        if not acquired:
            raise RuntimeError("snapshot lock is already held")
        return self

    def __exit__(self, exc_type, exc, tb) -> Optional[bool]:
        self.release()
        return None
