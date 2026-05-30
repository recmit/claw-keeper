"""Path matching helpers for safe OpenClaw state mirroring."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Iterable, List, Sequence


GENERATED_MANAGED_PATHS = (
    ".gitignore",
    "manifests/",
    "reports/",
)


def normalize_relative_path(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized == ".":
        return "."
    return normalized.rstrip("/")


def path_to_posix(path: Path) -> str:
    return path.as_posix().lstrip("/")


def is_excluded(relative_path: str, patterns: Sequence[str], is_dir: bool = False) -> bool:
    path = normalize_relative_path(relative_path)
    basename = path.rsplit("/", 1)[-1]
    dir_path = path + "/" if is_dir and not path.endswith("/") else path

    for pattern in patterns:
        clean_pattern = pattern.replace("\\", "/").lstrip("/")
        if clean_pattern.endswith("/"):
            directory = clean_pattern.rstrip("/")
            if path == directory or path.startswith(directory + "/"):
                return True
            if directory in path.split("/"):
                return True
            continue
        if fnmatch.fnmatch(path, clean_pattern) or fnmatch.fnmatch(basename, clean_pattern):
            return True
        if is_dir and fnmatch.fnmatch(dir_path, clean_pattern):
            return True
    return False


def managed_prefixes(include_paths: Iterable[str]) -> List[str]:
    prefixes = [normalize_relative_path(path) for path in include_paths]
    prefixes.extend(normalize_relative_path(path) for path in GENERATED_MANAGED_PATHS)
    return prefixes


def is_managed_repo_path(relative_path: str, include_paths: Iterable[str]) -> bool:
    path = normalize_relative_path(relative_path)
    for prefix in managed_prefixes(include_paths):
        if prefix == ".":
            return True
        if prefix.endswith("/"):
            clean_prefix = prefix.rstrip("/")
            if path == clean_prefix or path.startswith(clean_prefix + "/"):
                return True
        elif path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def status_paths(status_line: str) -> List[str]:
    path = status_line[3:]
    if " -> " in path:
        return [part.strip() for part in path.split(" -> ", 1)]
    return [path.strip()]
