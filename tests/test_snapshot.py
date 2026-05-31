import pytest
import json

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
    args = [
        "init",
        "--source",
        str(source),
        "--repo",
        str(repo),
        "--config",
        str(config_path),
    ]
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
    assert "Snapshot reason: initial" in run_git(
        ["log", "-1", "--pretty=format:%B"], repo
    )


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

    result = main(
        ["snapshot", "--reason", "initial", "--push", "--config", str(config_path)]
    )

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


def test_snapshot_runs_one_followup_for_pending_created_during_first_attempt(
    tmp_path, monkeypatch
):
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


def test_snapshot_leaves_pending_created_during_followup_for_next_trigger(
    tmp_path, monkeypatch
):
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
    (source / "workspace" / "SECRET.md").write_text(
        "BEGIN OPENSSH PRIVATE KEY\n", encoding="utf-8"
    )

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


def test_snapshot_uses_openclaw_text_first_policy(tmp_path, monkeypatch, capsys):
    source, repo, config_path = init_fixture(tmp_path, monkeypatch)
    (source / "openclaw.json").write_text('{"workspace":"ok"}\n', encoding="utf-8")
    (source / "agents" / "main" / "agent" / "codex-home").mkdir(parents=True)
    (
        source / "agents" / "main" / "agent" / "codex-home" / "logs_2.sqlite-wal"
    ).write_bytes(b"db")
    (source / "agents" / "main" / "notes.md").write_text(
        "agent notes\n", encoding="utf-8"
    )
    (source / "identity").mkdir()
    (source / "identity" / "profile.md").write_text(
        "public identity notes\n", encoding="utf-8"
    )
    (source / "identity" / "device-auth.json").write_text(
        '{"token":"nope"}\n', encoding="utf-8"
    )
    (source / "memory").mkdir()
    (source / "memory" / "reflection.md").write_text("memory notes\n", encoding="utf-8")
    (source / "flows").mkdir()
    (source / "flows" / "handoff.md").write_text("flow notes\n", encoding="utf-8")
    (source / "tasks").mkdir()
    (source / "tasks" / "task.md").write_text("task notes\n", encoding="utf-8")
    (source / "tasks" / "runs.sqlite-shm").write_bytes(b"db")
    (source / "workspace" / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (source / "workspace" / "notes.md").write_text("safe text\n", encoding="utf-8")

    result = main(["snapshot", "--reason", "manual", "--config", str(config_path)])

    capsys.readouterr()
    assert result == 0
    assert (repo / "workspace" / "notes.md").exists()
    assert (repo / "openclaw.json").exists()
    assert (repo / "agents" / "main" / "notes.md").exists()
    assert (repo / "identity" / "profile.md").exists()
    assert (repo / "memory" / "reflection.md").exists()
    assert (repo / "flows" / "handoff.md").exists()
    assert (repo / "tasks" / "task.md").exists()
    assert not (repo / "agents" / "main" / "agent" / "codex-home").exists()
    assert not (repo / "identity" / "device-auth.json").exists()
    assert not (repo / "tasks" / "runs.sqlite-shm").exists()
    assert not (repo / "workspace" / "image.png").exists()

    manifest = json.loads(
        (repo / "manifests" / "latest.json").read_text(encoding="utf-8")
    )
    assert manifest["policy_version"] == 3
    skipped = {item["path"]: item["reason"] for item in manifest["skipped"]}
    assert skipped["agents/main/agent/codex-home"] == "excluded-pattern"
    assert skipped["identity/device-auth.json"] == "excluded-pattern"
    assert skipped["tasks/runs.sqlite-shm"] == "excluded-pattern"
    assert skipped["workspace/image.png"] == "non-text-extension"


def test_snapshot_prunes_paths_from_legacy_broad_policy(tmp_path, monkeypatch, capsys):
    source, repo, config_path = init_fixture(tmp_path, monkeypatch)
    (source / "agents" / "main").mkdir(parents=True)
    (source / "agents" / "main" / "notes.md").write_text("safe now\n", encoding="utf-8")
    (repo / "agents" / "main").mkdir(parents=True)
    (repo / "agents" / "main" / "old.log").write_text("old\n", encoding="utf-8")
    run_git(["add", "-A"], repo)
    run_git(
        [
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "legacy broad mirror",
        ],
        repo,
    )

    result = main(["snapshot", "--reason", "prune", "--config", str(config_path)])

    capsys.readouterr()
    assert result == 0
    assert not (repo / "agents" / "main" / "old.log").exists()
    assert (repo / "agents" / "main" / "notes.md").exists()
