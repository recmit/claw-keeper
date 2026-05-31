import json
from pathlib import Path

import pytest

from claw_keeper.config import ConfigError, default_config_path, load_config, make_config, normalize_path, write_config
from claw_keeper.policy import (
    DEFAULT_BRANCH,
    DEFAULT_EXCLUDE_PATTERNS,
    DEFAULT_INCLUDE_PATHS,
    LEGACY_BROAD_INCLUDE_PATHS,
    NARROW_TEXT_INCLUDE_PATHS,
    RETIRED_DIRECTORY_EXCLUDE_PATTERNS,
)


def test_default_config_path_uses_project_local_metadata_dir(tmp_path):
    assert default_config_path(tmp_path) == tmp_path / ".claw-keeper" / "config.json"


def test_make_config_expands_paths_and_applies_default_policy(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    config = make_config("~/openclaw", "./history")

    assert config.source_path == str(home / "openclaw")
    assert Path(config.repo_path).is_absolute()
    assert config.branch == DEFAULT_BRANCH
    assert config.include_paths == DEFAULT_INCLUDE_PATHS
    assert "workspace/" in config.include_paths
    assert "agents/" in config.include_paths
    assert "identity/" in config.include_paths
    assert "memory/" in config.include_paths
    assert "flows/" in config.include_paths
    assert "tasks/" in config.include_paths
    assert "openclaw.json" in config.include_paths
    assert "." not in config.include_paths
    assert config.exclude_patterns == DEFAULT_EXCLUDE_PATTERNS
    assert ".claw-keeper/" in config.exclude_patterns
    assert "agents/" not in config.exclude_patterns
    assert "identity/" not in config.exclude_patterns
    assert "memory/" not in config.exclude_patterns
    assert "flows/" not in config.exclude_patterns
    assert "tasks/" not in config.exclude_patterns
    assert "secrets/" in config.exclude_patterns
    assert "logs/" in config.exclude_patterns
    assert "identity/device*.json" in config.exclude_patterns
    assert "*.sqlite-wal" in config.exclude_patterns
    assert "*auth*" in config.exclude_patterns
    assert config.remote is None
    assert config.policy_version == 3


def test_config_round_trip(tmp_path):
    path = tmp_path / "keeper" / "config.json"
    config = make_config(
        str(tmp_path / "source"),
        str(tmp_path / "repo"),
        "raw-history",
        remote="git@github-claw-keeper-history:example/openclaw-history.git",
    )

    write_config(path, config)
    loaded = load_config(path)

    assert loaded == config


def test_make_config_rejects_blank_remote(tmp_path):
    with pytest.raises(ConfigError, match="remote"):
        make_config(str(tmp_path / "source"), str(tmp_path / "repo"), remote="")


def test_load_config_migrates_legacy_broad_default_policy(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "source_path": str(tmp_path / "source"),
                "repo_path": str(tmp_path / "repo"),
                "branch": "raw-history",
                "include_paths": list(LEGACY_BROAD_INCLUDE_PATHS),
                "exclude_patterns": [".env", "workspace/custom-secret.md"],
                "remote": None,
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.include_paths == DEFAULT_INCLUDE_PATHS
    assert "workspace/custom-secret.md" in config.exclude_patterns
    for pattern in DEFAULT_EXCLUDE_PATTERNS:
        assert pattern in config.exclude_patterns
    assert config.policy_version == 3


def test_load_config_migrates_narrow_text_default_policy(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "source_path": str(tmp_path / "source"),
                "repo_path": str(tmp_path / "repo"),
                "branch": "raw-history",
                "include_paths": list(NARROW_TEXT_INCLUDE_PATHS),
                "exclude_patterns": ["agents/", "identity/", "workspace/custom-secret.md"],
                "remote": None,
                "policy_version": 2,
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.include_paths == DEFAULT_INCLUDE_PATHS
    assert "workspace/custom-secret.md" in config.exclude_patterns
    for pattern in DEFAULT_EXCLUDE_PATTERNS:
        assert pattern in config.exclude_patterns
    for pattern in RETIRED_DIRECTORY_EXCLUDE_PATTERNS:
        assert pattern not in config.exclude_patterns
    assert config.policy_version == 3


def test_load_config_rejects_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="config file not found"):
        load_config(tmp_path / "missing.json")


def test_load_config_rejects_invalid_shape(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"source_path": "", "repo_path": "/tmp/repo"}), encoding="utf-8")

    with pytest.raises(ConfigError, match="source_path"):
        load_config(path)


def test_normalize_path_expands_user(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    assert normalize_path("~/state") == str(home / "state")
