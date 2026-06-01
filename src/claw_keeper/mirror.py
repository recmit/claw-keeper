"""OpenClaw-aware mirror policy decisions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from .matching import is_excluded
from .policy import (
    DEFAULT_MAX_TEXT_FILE_BYTES,
    DEFAULT_TEXT_EXTENSIONS,
    DEFAULT_TEXT_FILENAMES,
)


@dataclass(frozen=True)
class MirrorDecision:
    include: bool
    reason: str


def classify_path(
    path: Path,
    relative_path: str,
    exclude_patterns: Sequence[str],
    is_dir: bool = False,
) -> MirrorDecision:
    if is_excluded(relative_path, exclude_patterns, is_dir=is_dir):
        return MirrorDecision(False, "excluded-pattern")
    if path.is_symlink():
        return MirrorDecision(False, "symlink")
    if is_dir:
        return MirrorDecision(True, "directory")
    if not path.is_file():
        return MirrorDecision(False, "special-file")
    if path.stat().st_size > DEFAULT_MAX_TEXT_FILE_BYTES:
        return MirrorDecision(False, "large-file")
    if not _has_text_name(path):
        return MirrorDecision(False, "non-text-extension")
    if not _looks_like_utf8_text(path):
        return MirrorDecision(False, "non-text-content")
    return MirrorDecision(True, "text")


def skipped_entry(path: Path, relative_path: str, reason: str) -> dict:
    entry = {
        "path": relative_path,
        "reason": reason,
        "kind": _path_kind(path),
    }
    try:
        stat = path.lstat()
    except OSError:
        return entry
    entry["size"] = stat.st_size
    if (
        reason in ("large-file", "non-text-extension", "non-text-content")
        and path.is_file()
        and not path.is_symlink()
    ):
        entry["sha256"] = _sha256(path)
    return entry


def _has_text_name(path: Path) -> bool:
    name = path.name
    if name in DEFAULT_TEXT_FILENAMES:
        return True
    if path.suffix.lower() in DEFAULT_TEXT_EXTENSIONS:
        return True
    return False


def _looks_like_utf8_text(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except OSError:
        return False
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _path_kind(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    return "special"


def _sha256(path: Path) -> Optional[str]:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()
