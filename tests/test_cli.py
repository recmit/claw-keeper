from claw_keeper.cli import main
from claw_keeper.config import load_config
from claw_keeper.git import run_git


REMOTE_URL = "git@github-claw-keeper-history:example/openclaw-history.git"


def test_init_creates_config_and_history_repo(tmp_path, capsys):
    source = tmp_path / "source"
    repo = tmp_path / "history"
    config_path = tmp_path / "config.json"
    source.mkdir()

    result = main(
        [
            "init",
            "--source",
            str(source),
            "--repo",
            str(repo),
            "--config",
            str(config_path),
        ]
    )

    captured = capsys.readouterr()
    config = load_config(config_path)

    assert result == 0
    assert "Initialized Claw Keeper" in captured.out
    assert (repo / ".git").exists()
    assert (
        run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], repo) == "raw-history"
    )
    assert config.source_path == str(source)
    assert config.repo_path == str(repo)
    assert config.branch == "raw-history"
    assert "Included paths are relative to source." in captured.out
    assert ".env" in (repo / ".gitignore").read_text(encoding="utf-8")


def test_init_configures_private_history_remote_when_provided(tmp_path, capsys):
    source = tmp_path / "source"
    repo = tmp_path / "history"
    config_path = tmp_path / "config.json"
    source.mkdir()

    result = main(
        [
            "init",
            "--source",
            str(source),
            "--repo",
            str(repo),
            "--remote",
            REMOTE_URL,
            "--config",
            str(config_path),
        ]
    )

    captured = capsys.readouterr()
    config = load_config(config_path)

    assert result == 0
    assert config.remote == REMOTE_URL
    assert "Remote: {0}".format(REMOTE_URL) in captured.out
    assert run_git(["remote", "get-url", "origin"], repo) == REMOTE_URL


def test_init_is_idempotent_and_does_not_duplicate_gitignore(tmp_path):
    source = tmp_path / "source"
    repo = tmp_path / "history"
    config_path = tmp_path / "config.json"
    source.mkdir()

    args = [
        "init",
        "--source",
        str(source),
        "--repo",
        str(repo),
        "--config",
        str(config_path),
    ]

    assert main(args) == 0
    assert main(args) == 0

    lines = (repo / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert lines.count(".env") == 1
    assert lines.count("id_ed25519") == 1


def test_status_works_before_any_commits(tmp_path, capsys):
    source = tmp_path / "source"
    repo = tmp_path / "history"
    config_path = tmp_path / "config.json"
    source.mkdir()
    assert (
        main(
            [
                "init",
                "--source",
                str(source),
                "--repo",
                str(repo),
                "--config",
                str(config_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    result = main(["status", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert result == 0
    assert "Claw Keeper status" in captured.out
    assert "Version: 0.1.1" in captured.out
    assert "Git repo: yes" in captured.out
    assert "Configured remote: not configured" in captured.out
    assert "Git origin: not configured" in captured.out
    assert "Included paths: workspace/" in captured.out
    assert "Current branch: raw-history" in captured.out
    assert "Latest commit: none yet" in captured.out
    assert (
        "Implemented commands: init, status, snapshot, watch, install-systemd"
        in captured.out
    )
    assert "Not implemented yet: restore-plan, restore" in captured.out


def test_status_reports_missing_config_cleanly(tmp_path, capsys):
    result = main(["status", "--config", str(tmp_path / "missing.json")])

    captured = capsys.readouterr()
    assert result == 1
    assert "config file not found" in captured.err


def test_init_refuses_to_switch_non_empty_repo_branch(tmp_path, capsys):
    repo = tmp_path / "history"
    source = tmp_path / "source"
    config_path = tmp_path / "config.json"
    repo.mkdir()
    source.mkdir()
    run_git(["init"], repo)
    (repo / "README.md").write_text("existing\n", encoding="utf-8")
    run_git(["add", "README.md"], repo)
    run_git(
        [
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "initial",
        ],
        repo,
    )

    result = main(
        [
            "init",
            "--source",
            str(source),
            "--repo",
            str(repo),
            "--branch",
            "raw-history",
            "--config",
            str(config_path),
        ]
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "refusing to switch" in captured.err
    assert not config_path.exists()


def test_init_refuses_to_replace_existing_origin(tmp_path, capsys):
    source = tmp_path / "source"
    repo = tmp_path / "history"
    config_path = tmp_path / "config.json"
    source.mkdir()
    repo.mkdir()
    run_git(["init"], repo)
    run_git(["remote", "add", "origin", "git@github.com:example/existing.git"], repo)

    result = main(
        [
            "init",
            "--source",
            str(source),
            "--repo",
            str(repo),
            "--remote",
            REMOTE_URL,
            "--config",
            str(config_path),
        ]
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "refusing to replace" in captured.err
    assert not config_path.exists()
