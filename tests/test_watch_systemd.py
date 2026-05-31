from pathlib import Path

from claw_keeper.cli import main
from claw_keeper.config import load_config
from claw_keeper.git import run_git
from claw_keeper import watch as watch_module
from claw_keeper.watch import run_watch


def init_fixture(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    source = tmp_path / "source"
    repo = tmp_path / "history"
    config_path = tmp_path / "config.json"
    (source / "workspace").mkdir(parents=True)
    (source / "workspace" / "AGENTS.md").write_text("hello\n", encoding="utf-8")
    assert main(["init", "--source", str(source), "--repo", str(repo), "--config", str(config_path)]) == 0
    return source, repo, config_path


def test_watch_detects_change_and_commits(tmp_path, monkeypatch):
    source, repo, config_path = init_fixture(tmp_path, monkeypatch)
    config = load_config(config_path)

    run_watch(config, debounce=0, interval=0, max_iterations=1)
    (source / "workspace" / "AGENTS.md").write_text("changed\n", encoding="utf-8")
    run_watch(config, debounce=0, interval=0, max_iterations=1)

    assert (repo / "workspace" / "AGENTS.md").read_text(encoding="utf-8") == "changed\n"
    assert run_git(["rev-parse", "--verify", "HEAD"], repo)


def test_watch_ignores_excluded_runtime_changes(tmp_path, monkeypatch):
    source, repo, config_path = init_fixture(tmp_path, monkeypatch)
    config = load_config(config_path)

    run_watch(config, debounce=0, interval=0, max_iterations=1)
    (source / "agents" / "main" / "agent" / "codex-home").mkdir(parents=True)
    (source / "agents" / "main" / "agent" / "codex-home" / "logs_2.sqlite-wal").write_bytes(b"db")
    run_watch(config, debounce=0, interval=0, max_iterations=1)

    assert not (repo / "agents").exists()
    try:
        run_git(["rev-parse", "--verify", "HEAD"], repo)
        committed = True
    except Exception:
        committed = False
    assert not committed


def test_watch_detects_safe_openclaw_context_change(tmp_path, monkeypatch):
    source, repo, config_path = init_fixture(tmp_path, monkeypatch)
    config = load_config(config_path)

    run_watch(config, debounce=0, interval=0, max_iterations=1)
    (source / "agents" / "main").mkdir(parents=True)
    (source / "agents" / "main" / "notes.md").write_text("agent note\n", encoding="utf-8")
    run_watch(config, debounce=0, interval=0, max_iterations=1)

    assert (repo / "agents" / "main" / "notes.md").read_text(encoding="utf-8") == "agent note\n"
    assert run_git(["rev-parse", "--verify", "HEAD"], repo)


def test_watch_debounce_does_not_reset_while_changes_continue(tmp_path, monkeypatch):
    _source, _repo, config_path = init_fixture(tmp_path, monkeypatch)
    config = load_config(config_path)
    snapshots = []
    states = iter(
        [
            {"workspace/USER.md": "v0"},
            {"workspace/USER.md": "v1"},
            {"workspace/USER.md": "v2"},
            {"workspace/USER.md": "v3"},
        ]
    )
    times = iter([0, 5, 11])

    monkeypatch.setattr(watch_module, "scan_source_state", lambda _config: next(states))
    monkeypatch.setattr(watch_module.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(watch_module.time, "sleep", lambda _interval: None)
    monkeypatch.setattr(watch_module, "run_snapshot", lambda *_args, **_kwargs: snapshots.append("snapshot"))

    run_watch(config, debounce=10, interval=0, max_iterations=3)

    assert snapshots == ["snapshot"]


def test_install_systemd_dry_run_emits_service(tmp_path, monkeypatch, capsys):
    _source, _repo, config_path = init_fixture(tmp_path, monkeypatch)
    capsys.readouterr()

    result = main(
        [
            "install-systemd",
            "--dry-run",
            "--push",
            "--debounce",
            "42",
            "--config",
            str(config_path),
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "claw-keeper watch" in captured.out
    assert "--config {0}".format(config_path) in captured.out
    assert "--debounce 42" in captured.out
    assert "--push" in captured.out
    assert "Restart=always" in captured.out
