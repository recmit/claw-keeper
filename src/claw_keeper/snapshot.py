"""Snapshot implementation for Claw Keeper."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence

from .config import KeeperConfig
from .git import (
    GitError,
    add_all,
    commit_with_message,
    is_git_repo,
    push as git_push,
    staged_name_status,
    working_tree_porcelain,
)
from .matching import (
    is_managed_repo_path,
    normalize_relative_path,
    path_to_posix,
    status_paths,
)
from .mirror import classify_path, skipped_entry
from .policy import DEFAULT_PRUNE_PATHS
from .risk import (
    RiskFinding,
    has_high_risk,
    render_report,
    scan_tree,
    summarize_findings,
)
from .runtime import RuntimeState, SnapshotLock


class SnapshotError(Exception):
    """Raised when a snapshot cannot be completed safely."""


@dataclass
class SnapshotResult:
    committed: bool = False
    changed_files: List[str] = field(default_factory=list)
    pending_recorded: bool = False
    followup_ran: bool = False
    push_attempted: bool = False
    push_failed: bool = False
    dry_run: bool = False
    message: str = ""


@dataclass
class SnapshotAttempt:
    committed: bool
    changed_files: List[str]
    push_attempted: bool = False
    push_failed: bool = False
    dry_run: bool = False
    message: str = ""


AfterAttempt = Callable[[int, SnapshotAttempt, RuntimeState], None]


def run_snapshot(
    config: KeeperConfig,
    reason: str,
    push: bool = False,
    dry_run: bool = False,
    max_followups: int = 1,
    after_attempt: Optional[AfterAttempt] = None,
) -> SnapshotResult:
    state = RuntimeState.for_repo(config.repo_path)
    lock = SnapshotLock(state)
    if not lock.acquire():
        state.touch_pending()
        return SnapshotResult(
            pending_recorded=True,
            message="snapshot already running; pending request recorded",
        )

    try:
        state.clear_pending()
        attempts = []
        attempt = _run_snapshot_once(
            config, reason, push=push, dry_run=dry_run, state=state
        )
        attempts.append(attempt)
        if after_attempt:
            after_attempt(0, attempt, state)

        followups = 0
        while followups < max_followups and state.has_pending():
            state.clear_pending()
            followup = _run_snapshot_once(
                config, reason, push=push, dry_run=dry_run, state=state
            )
            attempts.append(followup)
            followups += 1
            if after_attempt:
                after_attempt(followups, followup, state)

        return _combine_attempts(attempts, followup_ran=followups > 0)
    finally:
        lock.release()


def _combine_attempts(
    attempts: Sequence[SnapshotAttempt], followup_ran: bool
) -> SnapshotResult:
    changed = []
    for attempt in attempts:
        changed.extend(attempt.changed_files)
    return SnapshotResult(
        committed=any(attempt.committed for attempt in attempts),
        changed_files=changed,
        followup_ran=followup_ran,
        push_attempted=any(attempt.push_attempted for attempt in attempts),
        push_failed=any(attempt.push_failed for attempt in attempts),
        dry_run=any(attempt.dry_run for attempt in attempts),
        message=attempts[-1].message if attempts else "",
    )


def _run_snapshot_once(
    config: KeeperConfig,
    reason: str,
    push: bool,
    dry_run: bool,
    state: RuntimeState,
) -> SnapshotAttempt:
    repo_path = Path(config.repo_path)
    if not is_git_repo(repo_path):
        raise SnapshotError(
            "history repo is not a Git repository: {0}".format(repo_path)
        )
    _ensure_no_unmanaged_dirty_paths(config)

    staging_root = _build_staging_tree(config, state)
    try:
        findings = scan_tree(staging_root, skip_prefixes=("manifests/",))
        if has_high_risk(findings):
            report_path = state.root / "last-risk-scan.md"
            report_path.write_text(render_report(findings), encoding="utf-8")
            raise SnapshotError(
                "HIGH risk findings detected; refusing to commit. Report: {0}".format(
                    report_path
                )
            )

        if dry_run:
            files = _list_tree_files(staging_root)
            return SnapshotAttempt(
                committed=False,
                changed_files=files,
                dry_run=True,
                message="dry run prepared {0} files; {1}".format(
                    len(files), summarize_findings(findings)
                ),
            )

        _apply_staging_tree(config, staging_root)
    finally:
        shutil.rmtree(str(staging_root), ignore_errors=True)
    add_all(repo_path)
    changed = staged_name_status(repo_path)
    if not changed:
        return SnapshotAttempt(committed=False, changed_files=[], message="no changes")

    report_path = _write_repo_risk_report(repo_path, findings)
    add_all(repo_path)
    changed = staged_name_status(repo_path)
    changed_files = _changed_files_from_name_status(changed)
    message_file = _write_commit_message(
        repo_path, reason, changed_files, findings, report_path
    )
    commit_with_message(repo_path, message_file)

    push_attempted = False
    push_failed = False
    if push:
        push_attempted = True
        try:
            git_push(repo_path, "origin", config.branch)
        except GitError:
            push_failed = True

    return SnapshotAttempt(
        committed=True,
        changed_files=changed_files,
        push_attempted=push_attempted,
        push_failed=push_failed,
        message="committed {0} files".format(len(changed_files)),
    )


def _ensure_no_unmanaged_dirty_paths(config: KeeperConfig) -> None:
    dirty = working_tree_porcelain(Path(config.repo_path))
    unmanaged = []
    for line in dirty:
        for path in status_paths(line):
            if path and not is_managed_repo_path(
                path, _managed_paths_for_cleanup(config)
            ):
                unmanaged.append(path)
    if unmanaged:
        raise SnapshotError(
            "history repo has dirty files outside managed paths: {0}".format(
                ", ".join(sorted(unmanaged))
            )
        )


def _build_staging_tree(config: KeeperConfig, state: RuntimeState) -> Path:
    state.ensure()
    staging_root = state.tmp_dir / "snapshot-{0}".format(uuid.uuid4().hex)
    staging_root.mkdir(parents=True, exist_ok=False)
    source_root = Path(config.source_path)
    entries = []
    skipped = []
    missing_includes = []

    for include in config.include_paths:
        relative = normalize_relative_path(include)
        source = source_root if relative == "." else source_root / relative
        if not source.exists():
            missing_includes.append(relative)
            continue
        destination = staging_root if relative == "." else staging_root / relative
        copied, skipped_paths = _copy_source_path(
            source_root, source, destination, staging_root, config.exclude_patterns
        )
        entries.extend(copied)
        skipped.extend(skipped_paths)

    _write_manifest(staging_root, config, entries, skipped, missing_includes)
    return staging_root


def _copy_source_path(
    source_root: Path,
    source: Path,
    destination: Path,
    staging_root: Path,
    excludes: Sequence[str],
) -> tuple[List[dict], List[dict]]:
    copied = []
    skipped = []
    relative = path_to_posix(source.relative_to(source_root))
    decision = classify_path(source, relative, excludes, is_dir=source.is_dir())
    if not decision.include:
        return copied, [skipped_entry(source, relative, decision.reason)]
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(destination), follow_symlinks=False)
        return [
            _manifest_entry_for_file(destination, destination.relative_to(staging_root))
        ], skipped

    for root, dirs, files in os.walk(source, topdown=True, followlinks=False):
        root_path = Path(root)
        kept_dirs = []
        for dirname in sorted(dirs):
            child = root_path / dirname
            child_relative = path_to_posix(child.relative_to(source_root))
            child_decision = classify_path(child, child_relative, excludes, is_dir=True)
            if child_decision.include:
                kept_dirs.append(dirname)
            else:
                skipped.append(
                    skipped_entry(child, child_relative, child_decision.reason)
                )
        dirs[:] = kept_dirs

        for filename in sorted(files):
            child = root_path / filename
            child_relative = path_to_posix(child.relative_to(source_root))
            child_decision = classify_path(child, child_relative, excludes)
            if not child_decision.include:
                skipped.append(
                    skipped_entry(child, child_relative, child_decision.reason)
                )
                continue
            child_destination = destination / child.relative_to(source)
            child_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(child), str(child_destination), follow_symlinks=False)
            copied.append(
                _manifest_entry_for_file(
                    child_destination, child_destination.relative_to(staging_root)
                )
            )
    return copied, skipped


def _manifest_entry_for_file(path: Path, relative: Path) -> dict:
    data = path.read_bytes() if path.is_file() else b""
    return {
        "path": relative.as_posix(),
        "size": path.lstat().st_size,
        "sha256": hashlib.sha256(data).hexdigest(),
        "symlink": False,
    }


def _write_manifest(
    staging_root: Path,
    config: KeeperConfig,
    entries: Iterable[dict],
    skipped: Iterable[dict],
    missing_includes: Sequence[str],
) -> None:
    manifest = {
        "version": 1,
        "policy_version": config.policy_version,
        "source_path": config.source_path,
        "include_paths": list(config.include_paths),
        "exclude_patterns": list(config.exclude_patterns),
        "prune_paths": list(DEFAULT_PRUNE_PATHS),
        "missing_includes": sorted(missing_includes),
        "files": sorted(entries, key=lambda item: item["path"]),
        "skipped": sorted(skipped, key=lambda item: item["path"]),
    }
    manifest_path = staging_root / "manifests" / "latest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _apply_staging_tree(config: KeeperConfig, staging_root: Path) -> None:
    repo_path = Path(config.repo_path)
    for include in _managed_paths_for_cleanup(config):
        relative = normalize_relative_path(include)
        if relative == ".":
            _remove_repo_contents(repo_path)
        else:
            _remove_path(repo_path / relative)
    _remove_path(repo_path / "manifests" / "latest.json")
    _copy_tree_contents(staging_root, repo_path)


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(str(path))


def _remove_repo_contents(repo_path: Path) -> None:
    for child in repo_path.iterdir():
        if child.name == ".git":
            continue
        _remove_path(child)


def _copy_tree_contents(source: Path, destination: Path) -> None:
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file() and not item.is_symlink():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(item), str(target), follow_symlinks=False)


def _write_repo_risk_report(repo_path: Path, findings: Sequence[RiskFinding]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = repo_path / "reports" / "{0}-risk-scan.md".format(timestamp)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(findings), encoding="utf-8")
    return report_path


def _write_commit_message(
    repo_path: Path,
    reason: str,
    changed_files: Sequence[str],
    findings: Sequence[RiskFinding],
    report_path: Path,
) -> Path:
    lines = [
        "chore(agent-state): snapshot OpenClaw state",
        "",
        "Snapshot reason: {0}".format(reason),
        "",
        "Changed files:",
    ]
    lines.extend("- {0}".format(path) for path in changed_files)
    lines.extend(
        [
            "",
            "Risk notes:",
            "- {0}".format(summarize_findings(findings)),
            "- Risk report: {0}".format(report_path.relative_to(repo_path).as_posix()),
            "",
        ]
    )
    message_path = repo_path / ".claw-keeper" / "commit-message.txt"
    message_path.parent.mkdir(parents=True, exist_ok=True)
    message_path.write_text("\n".join(lines), encoding="utf-8")
    return message_path


def _changed_files_from_name_status(lines: Sequence[str]) -> List[str]:
    files = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) >= 2:
            files.append(parts[-1])
    return files


def _list_tree_files(root: Path) -> List[str]:
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    )


def _managed_paths_for_cleanup(config: KeeperConfig) -> tuple[str, ...]:
    configured = tuple(config.include_paths)
    extras = tuple(path for path in DEFAULT_PRUNE_PATHS if path not in configured)
    return configured + extras
