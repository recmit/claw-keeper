import json
from pathlib import Path

import pytest

from claw_keeper.config import ConfigError, default_config_path, load_config, make_config, normalize_path, write_config
from claw_keeper.policy import DEFAULT_BRANCH, DEFAULT_EXCLUDE_PATTERNS, DEFAULT_INCLUDE_PATHS


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
    assert "openclaw.json" in config.include_paths
    assert "." not in config.include_paths
    assert config.exclude_patterns == DEFAULT_EXCLUDE_PATTERNS
    assert "secrets/" in config.exclude_patterns
    assert "logs/" in config.exclude_patterns
    assert config.remote is None


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
