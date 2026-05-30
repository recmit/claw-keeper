"""Small Git command helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional, Sequence


class GitError(Exception):
    """Raised when a Git command fails in an expected operational path."""


def run_git(args: Sequence[str], cwd: Path) -> str:
    command = ["git"] + list(args)
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise GitError("git {0} failed: {1}".format(" ".join(args), message))
    return completed.stdout.strip()


def is_git_repo(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return run_git(["rev-parse", "--is-inside-work-tree"], path) == "true"
    except GitError:
        return False


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if not is_git_repo(path):
        run_git(["init"], path)


def has_commits(path: Path) -> bool:
    try:
        run_git(["rev-parse", "--verify", "HEAD"], path)
        return True
    except GitError:
        return False


def current_branch(path: Path) -> Optional[str]:
    try:
        return run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], path)
    except GitError:
        return None


def ensure_branch(path: Path, branch: str) -> None:
    current = current_branch(path)
    if current == branch:
        return
    if has_commits(path):
        raise GitError(
            "repository already has commits on branch {0}; refusing to switch to {1}".format(
                current or "<detached>",
                branch,
            )
        )
    run_git(["checkout", "-B", branch], path)


def working_tree_porcelain(path: Path) -> List[str]:
    output = run_git(["status", "--porcelain"], path)
    if not output:
        return []
    return output.splitlines()


def latest_commit_subject(path: Path) -> Optional[str]:
    if not has_commits(path):
        return None
    return run_git(["log", "-1", "--pretty=format:%h %s"], path)


def remote_url(path: Path, name: str = "origin") -> Optional[str]:
    try:
        return run_git(["remote", "get-url", name], path)
    except GitError:
        return None


def ensure_remote(path: Path, url: str, name: str = "origin") -> None:
    existing = remote_url(path, name)
    if existing == url:
        return
    if existing is not None:
        raise GitError(
            "remote {0} already points to {1}; refusing to replace it with {2}".format(
                name,
                existing,
                url,
            )
        )
    run_git(["remote", "add", name, url], path)


def write_default_gitignore(path: Path, lines: Sequence[str]) -> None:
    gitignore = path / ".gitignore"
    existing = []
    if gitignore.exists():
        existing = gitignore.read_text(encoding="utf-8").splitlines()

    merged = list(existing)
    for line in lines:
        if line not in merged:
            merged.append(line)

    gitignore.write_text("\n".join(merged).rstrip() + "\n", encoding="utf-8")
