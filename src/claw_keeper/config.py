"""Configuration loading and validation."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .policy import DEFAULT_BRANCH, DEFAULT_EXCLUDE_PATTERNS, DEFAULT_INCLUDE_PATHS


class ConfigError(Exception):
    """Raised when the Claw Keeper config is missing or invalid."""


@dataclass(frozen=True)
class KeeperConfig:
    source_path: str
    repo_path: str
    branch: str = DEFAULT_BRANCH
    include_paths: Tuple[str, ...] = DEFAULT_INCLUDE_PATHS
    exclude_patterns: Tuple[str, ...] = DEFAULT_EXCLUDE_PATTERNS
    remote: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "repo_path": self.repo_path,
            "branch": self.branch,
            "include_paths": list(self.include_paths),
            "exclude_patterns": list(self.exclude_patterns),
            "remote": self.remote,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KeeperConfig":
        if not isinstance(data, dict):
            raise ConfigError("config must be a JSON object")

        source_path = _require_string(data, "source_path")
        repo_path = _require_string(data, "repo_path")
        branch = data.get("branch", DEFAULT_BRANCH)
        if not isinstance(branch, str) or not branch.strip():
            raise ConfigError("branch must be a non-empty string")

        include_paths = _string_tuple(
            data.get("include_paths", DEFAULT_INCLUDE_PATHS),
            "include_paths",
        )
        exclude_patterns = _string_tuple(
            data.get("exclude_patterns", DEFAULT_EXCLUDE_PATTERNS),
            "exclude_patterns",
        )

        remote = data.get("remote")
        if remote is not None and not isinstance(remote, str):
            raise ConfigError("remote must be a string or null")

        return cls(
            source_path=normalize_path(source_path),
            repo_path=normalize_path(repo_path),
            branch=branch,
            include_paths=include_paths,
            exclude_patterns=exclude_patterns,
            remote=remote,
        )


def default_config_path(cwd: Optional[Path] = None) -> Path:
    base = cwd if cwd is not None else Path.cwd()
    return base / ".claw-keeper" / "config.json"


def normalize_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def make_config(
    source_path: str,
    repo_path: str,
    branch: str = DEFAULT_BRANCH,
    remote: Optional[str] = None,
) -> KeeperConfig:
    if remote is not None and not remote.strip():
        raise ConfigError("remote must be a non-empty string when provided")
    return KeeperConfig(
        source_path=normalize_path(source_path),
        repo_path=normalize_path(repo_path),
        branch=branch,
        remote=remote,
    )


def load_config(path: Path) -> KeeperConfig:
    if not path.exists():
        raise ConfigError("config file not found: {0}".format(path))
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigError("config file is not valid JSON: {0}".format(exc)) from exc
    return KeeperConfig.from_dict(data)


def write_config(path: Path, config: KeeperConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _require_string(data: Dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("{0} must be a non-empty string".format(key))
    return value


def _string_tuple(value: Any, key: str) -> Tuple[str, ...]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise ConfigError("{0} must be a list of strings".format(key))
    result = tuple(value)
    if not all(isinstance(item, str) and item for item in result):
        raise ConfigError("{0} must be a list of non-empty strings".format(key))
    return result
