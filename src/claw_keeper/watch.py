"""Polling watcher for the POC."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, Optional

from .config import KeeperConfig
from .matching import normalize_relative_path, path_to_posix
from .mirror import classify_path
from .runtime import RuntimeState
from .snapshot import run_snapshot


def run_watch(
    config: KeeperConfig,
    debounce: float = 60,
    interval: float = 5,
    push: bool = False,
    max_iterations: Optional[int] = None,
) -> None:
    state = RuntimeState.for_repo(config.repo_path)
    state.ensure()
    previous = _load_watch_state(state)
    if previous is None:
        previous = scan_source_state(config)
        _write_watch_state(state, previous)

    pending_since = None
    pending_state = None
    iterations = 0

    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        current = scan_source_state(config)
        now = time.monotonic()
        if current != previous:
            if pending_since is None:
                pending_since = now
            pending_state = current

        if pending_since is not None and now - pending_since >= debounce:
            run_snapshot(config, reason="watch", push=push)
            previous = pending_state or current
            _write_watch_state(state, previous)
            pending_since = None
            pending_state = None
        elif state.has_pending() and pending_since is None:
            result = run_snapshot(config, reason="watch-pending", push=push)
            if not result.pending_recorded:
                previous = scan_source_state(config)
                _write_watch_state(state, previous)

        if max_iterations is None or iterations < max_iterations:
            time.sleep(interval)


def scan_source_state(config: KeeperConfig) -> Dict[str, str]:
    source_root = Path(config.source_path)
    state = {}
    for include in config.include_paths:
        relative = normalize_relative_path(include)
        source = source_root if relative == "." else source_root / relative
        if not source.exists():
            continue
        if source.is_symlink():
            continue
        if source.is_file():
            rel = path_to_posix(source.relative_to(source_root))
            if classify_path(source, rel, config.exclude_patterns).include:
                state[rel] = _file_signature(source)
            continue
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                continue
            rel = path_to_posix(path.relative_to(source_root))
            if (
                path.is_file()
                and classify_path(path, rel, config.exclude_patterns).include
            ):
                state[rel] = _file_signature(path)
    return state


def _file_signature(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return "{0}:{1}".format(stat.st_size, digest.hexdigest())


def _load_watch_state(state: RuntimeState) -> Optional[Dict[str, str]]:
    try:
        with state.watch_state_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return {str(key): str(value) for key, value in data.items()}


def _write_watch_state(state: RuntimeState, data: Dict[str, str]) -> None:
    state.ensure()
    state.watch_state_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
