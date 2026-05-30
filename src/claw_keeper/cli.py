"""Command-line interface for Claw Keeper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .config import ConfigError, default_config_path, load_config, make_config, write_config
from .git import (
    GitError,
    current_branch,
    ensure_branch,
    ensure_remote,
    init_repo,
    is_git_repo,
    latest_commit_subject,
    remote_url,
    working_tree_porcelain,
    write_default_gitignore,
)
from .policy import DEFAULT_BRANCH, DEFAULT_GITIGNORE_LINES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claw-keeper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize Claw Keeper config and history repo")
    init_parser.add_argument("--source", required=True, help="OpenClaw state root, usually ~/.openclaw")
    init_parser.add_argument("--repo", required=True, help="Git history repo path")
    init_parser.add_argument("--branch", default=DEFAULT_BRANCH, help="history branch name")
    init_parser.add_argument("--remote", help="private history repo remote URL to configure as origin")
    init_parser.add_argument("--config", help="config file path")
    init_parser.set_defaults(handler=handle_init)

    status_parser = subparsers.add_parser("status", help="show Claw Keeper status")
    status_parser.add_argument("--config", help="config file path")
    status_parser.set_defaults(handler=handle_status)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (ConfigError, GitError) as exc:
        print("error: {0}".format(exc), file=sys.stderr)
        return 1


def handle_init(args: argparse.Namespace) -> int:
    config_path = _config_path(args.config)
    config = make_config(args.source, args.repo, args.branch, remote=args.remote)
    repo_path = Path(config.repo_path)

    init_repo(repo_path)
    ensure_branch(repo_path, config.branch)
    if config.remote:
        ensure_remote(repo_path, config.remote)
    write_default_gitignore(repo_path, DEFAULT_GITIGNORE_LINES)
    write_config(config_path, config)

    print("Initialized Claw Keeper")
    print("Config: {0}".format(config_path))
    print("Source: {0}".format(config.source_path))
    print("History repo: {0}".format(config.repo_path))
    print("Branch: {0}".format(config.branch))
    print("Remote: {0}".format(config.remote or "not configured"))
    print("Included paths are relative to source.")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    config_path = _config_path(args.config)
    config = load_config(config_path)
    source_path = Path(config.source_path)
    repo_path = Path(config.repo_path)
    repo_exists = repo_path.exists()
    git_repo = is_git_repo(repo_path)

    print("Claw Keeper status")
    print("Config: {0}".format(config_path))
    print("")
    print("Source:")
    print("  Path: {0}".format(config.source_path))
    print("  Exists: {0}".format(_yes_no(source_path.exists())))
    print("  Included paths: {0}".format(", ".join(config.include_paths)))
    print("")
    print("History repo:")
    print("  Path: {0}".format(config.repo_path))
    print("  Exists: {0}".format(_yes_no(repo_exists)))
    print("  Git repo: {0}".format(_yes_no(git_repo)))
    print("  Configured branch: {0}".format(config.branch))
    print("  Configured remote: {0}".format(config.remote or "not configured"))

    if git_repo:
        branch = current_branch(repo_path) or "<detached>"
        changes = working_tree_porcelain(repo_path)
        latest = latest_commit_subject(repo_path)
        origin = remote_url(repo_path) or "not configured"
        print("  Current branch: {0}".format(branch))
        print("  Git origin: {0}".format(origin))
        print("  Working tree: {0}".format("clean" if not changes else "dirty ({0} changes)".format(len(changes))))
        print("  Latest commit: {0}".format(latest or "none yet"))
    else:
        print("  Current branch: unavailable")
        print("  Working tree: unavailable")
        print("  Latest commit: none yet")

    print("")
    print("Implemented commands: init, status")
    print("Not implemented yet: snapshot, watch, restore-plan, restore")
    return 0


def _config_path(value: Optional[str]) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return default_config_path().resolve()


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


if __name__ == "__main__":
    raise SystemExit(main())
