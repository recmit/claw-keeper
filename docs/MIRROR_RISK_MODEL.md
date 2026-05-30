# Claw Keeper Mirror Risk Model

Claw Keeper's first useful job is monitoring: make OpenClaw's durable, human-meaningful evolution visible in Git. It is not currently a complete OpenClaw backup or restore system.

The default policy is intentionally text-first and OpenClaw-aware. That means it captures the files most likely to explain what changed, while excluding runtime state that is noisy, secret-bearing, binary, or hard to restore safely.

## What The Mirror Captures Well

- Workspace Markdown such as `AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `USER.md`, `TOOLS.md`, and `HEARTBEAT.md`.
- User-created workspace notes and text memory files under `workspace/`.
- Safe Markdown and other small text files under OpenClaw context directories such as `identity/`, `memory/`, `agents/`, `flows/`, and `tasks/`.
- Skill source files under `workspace/`, `skills/`, and `plugin-skills/`, when they are text and under the size limit.
- Safe text config such as `openclaw.json`, subject to risk scanning.
- A manifest of copied files and skipped files, including reasons for skipped paths.

This is enough for the main monitoring question: "What did the agent's editable state and instructions become over time?"

## What The Mirror Deliberately Misses

- Auth and identity material such as `identity/device-auth.json`, tokens, OAuth files, provider credentials, secrets, and SSH keys.
- Runtime databases and sidecars such as `*.sqlite`, `*.sqlite-wal`, `*.sqlite-shm`, `*.db`, `*.wal`, and `*.shm`.
- OpenClaw/Codex runtime areas inside the mirrored trees, such as `codex-home/`, `cache/`, `plugins/cache/`, `shell_snapshots/`, `tmp/`, logs, sessions, devices, completions, and generated task/flow database state.
- Large files and files that do not look like UTF-8 text.
- Binary assets, even if they are part of a plugin or skill, unless a future policy explicitly opts them in.

Some of these files may matter for exact runtime continuity. They are excluded because committing them to Git creates higher risk than value for the monitoring use case.

## Open Questions

- Which OpenClaw SQLite databases are canonical user state, and which are runtime/cache state?
- Which plugin or skill assets are required for faithful restore versus merely useful for UI polish?
- Whether a future "backup profile" should exist separately from the current "monitoring profile".
- Whether selected database summaries, such as table names, row counts, and hashes, would provide useful audit value without committing raw database contents.

Until these are better understood, Claw Keeper should avoid claiming it can restore a full OpenClaw installation.

## Restore Risk

Restore is currently out of scope. When it is added, it must not restore by deleting and replacing whole directories.

That would be dangerous because a live directory can contain both tracked files and excluded files. If restore replaced the whole directory, excluded live files could be deleted even though they were never backed up.

Future restore should:

- Default to dry-run.
- Restore only files tracked in the selected snapshot manifest.
- Overlay tracked files instead of replacing mixed directories wholesale.
- Show explicit overwrite and delete operations before applying.
- Never restore excluded auth, secret, database, or runtime files.
- Record any applied rollback as a new snapshot commit instead of rewriting history.

## Binary And Large File Risk

Git LFS is not part of the current design. It adds setup burden and does not solve the main risk: knowing whether binary files are safe and meaningful to preserve.

For now, the safer default is:

- Do not commit binary or large file contents.
- Record skipped file metadata in the manifest.
- Add explicit opt-ins later for known-safe assets if a restore use case needs them.

If exact restore ever becomes a priority, binary handling should be designed as a separate feature, not slipped into the monitoring defaults.

## Git And Key Custody Risk

The private history repo should use a dedicated deploy key scoped only to that repo. This limits blast radius, but it does not isolate the key from OpenClaw if both run as the same Unix user.

For extra history protection, users should protect the history branch, usually `raw-history`, by disabling force pushes and branch deletion. This makes the repo more append-only, even if the agent can still append commits.

True key isolation requires a separate OS user or another permission boundary. That is future hardening work, not part of the default setup.

## Current Recommended Position

Claw Keeper should be described as:

> A Git-backed monitoring and audit trail for selected safe OpenClaw state.

It should not yet be described as:

> A complete OpenClaw backup and restore system.

That distinction keeps the defaults conservative and makes the tool useful before every OpenClaw runtime file is fully understood.
