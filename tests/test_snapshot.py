import pytest

from claw_keeper.cli import main
from claw_keeper.config import load_config
from claw_keeper.git import run_git
from claw_keeper.runtime import RuntimeState, SnapshotLock
from claw_keeper.snapshot import run_snapshot


def init_fixture(tmp_path, monkeypatch, remote=None):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    source = tmp_path / "source"
    repo = tmp_path / "history"
    config_path = tmp_path / "config.json"
    (source / "workspace").mkdir(parents=True)
    (source / "workspace" / "AGENTS.md").write_text("hello\n", encoding="utf-8")
    args = ["init", "--source", str(source), "--repo", str(repo), "--config", str(config_path)]
    if remote:
        args.extend(["--remote", remote])
    assert main(args) == 0
    return source, repo, config_path


def test_snapshot_creates_first_commit(tmp_path, monkeypatch, capsys):
    source, repo, config_path = init_fixture(tmp_path, monkeypatch)
    capsys.readouterr()

    result = main(["snapshot", "--reason", "initial", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert result == 0
    assert "committed" in captured.out
    assert (repo / "workspace" / "AGENTS.md").read_text(encoding="utf-8") == "hello\n"
    assert (repo / "manifests" / "latest.json").exists()
    assert list((repo / "reports").glob("*-risk-scan.md"))
    assert "Snapshot reason: initial" in run_git(["log", "-1", "--pretty=format:%B"], repo)


def test_snapshot_without_changes_exits_cleanly(tmp_path, monkeypatch, capsys):
    _source, repo, config_path = init_fixture(tmp_path, monkeypatch)
    assert main(["snapshot", "--reason", "initial", "--config", str(config_path)]) == 0
    first_head = run_git(["rev-parse", "HEAD"], repo)
    capsys.readouterr()

    result = main(["snapshot", "--reason", "again", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert result == 0
    assert "no changes" in captured.out
    assert run_git(["rev-parse", "HEAD"], repo) == first_head


def test_snapshot_push_failure_keeps_local_commit(tmp_path, monkeypatch, capsys):
    remote = str(tmp_path / "not-a-git-repo")
    _source, repo, config_path = init_fixture(tmp_path, monkeypatch, remote=remote)
    capsys.readouterr()

    result = main(["snapshot", "--reason", "initial", "--push", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert result == 1
    assert "push failed after local commit" in captured.err
    assert run_git(["rev-parse", "--verify", "HEAD"], repo)


def test_snapshot_records_pending_when_lock_is_busy(tmp_path, monkeypatch):
    _source, _repo, config_path = init_fixture(tmp_path, monkeypatch)
    config = load_config(config_path)
    state = RuntimeState.for_repo(config.repo_path)
    lock = SnapshotLock(state)
    assert lock.acquire()
    try:
        result = run_snapshot(config, reason="manual")
    finally:
        lock.release()

    assert result.pending_recorded
    assert state.has_pending()


def test_snapshot_runs_one_followup_for_pending_created_during_first_attempt(tmp_path, monkeypatch):
    _source, _repo, config_path = init_fixture(tmp_path, monkeypatch)
    config = load_config(config_path)
    state = RuntimeState.for_repo(config.repo_path)
    seen = []

    def after_attempt(index, _attempt, runtime_state):
        seen.append(index)
        if index == 0:
            runtime_state.touch_pending()

    result = run_snapshot(config, reason="manual", after_attempt=after_attempt)

    assert result.followup_ran
    assert seen == [0, 1]
    assert not state.has_pending()


def test_snapshot_leaves_pending_created_during_followup_for_next_trigger(tmp_path, monkeypatch):
    _source, _repo, config_path = init_fixture(tmp_path, monkeypatch)
    config = load_config(config_path)
    state = RuntimeState.for_repo(config.repo_path)

    def after_attempt(index, _attempt, runtime_state):
        runtime_state.touch_pending()

    result = run_snapshot(config, reason="manual", after_attempt=after_attempt)

    assert result.followup_ran
    assert state.has_pending()


def test_snapshot_refuses_dirty_unmanaged_repo_path(tmp_path, monkeypatch, capsys):
    _source, repo, config_path = init_fixture(tmp_path, monkeypatch)
    (repo / "README.md").write_text("user edit\n", encoding="utf-8")

    result = main(["snapshot", "--reason", "manual", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert result == 1
    assert "dirty files outside managed paths" in captured.err


def test_snapshot_refuses_high_risk_content(tmp_path, monkeypatch, capsys):
    source, repo, config_path = init_fixture(tmp_path, monkeypatch)
    (source / "workspace" / "SECRET.md").write_text("BEGIN OPENSSH PRIVATE KEY\n", encoding="utf-8")

    result = main(["snapshot", "--reason", "manual", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert result == 1
    assert "HIGH risk findings" in captured.err
    with pytest.raises(Exception):
        run_git(["rev-parse", "--verify", "HEAD"], repo)


def test_snapshot_skips_symlinks(tmp_path, monkeypatch, capsys):
    source, repo, config_path = init_fixture(tmp_path, monkeypatch)
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (source / "workspace" / "outside-link").symlink_to(outside)

    result = main(["snapshot", "--reason", "manual", "--config", str(config_path)])

    capsys.readouterr()
    assert result == 0
    assert not (repo / "workspace" / "outside-link").exists()
