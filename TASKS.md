# Claw Keeper Tasks

## Next POC Hardening

- [x] Tighten the OpenClaw-specific mirror policy.
  - Mirror safe text from OpenClaw context directories such as `identity/`, `memory/`, `agents/`, `flows/`, and `tasks/`.
  - Exclude OpenClaw/Codex runtime caches, logs, shell snapshots, temporary files, and plugin caches inside those directories.
  - Exclude auth/device identity files such as `identity/device-auth.json`.
  - Exclude SQLite sidecar files such as `*.sqlite-wal`, `*.sqlite-shm`, `*.db-wal`, and `*.db-shm`.
  - Prefer text-first monitoring by default; record excluded binary/database paths in manifests with reason, size, and hash where useful.

- [x] Add a GitHub Action to sync the OpenClaw skill branch.
  - Treat `skills/claw-keeper/SKILL.md` on `main` as canonical.
  - On changes to the canonical skill, copy it to root `SKILL.md` on `openclaw-skill`.
  - Commit and push only when the generated branch content changed.

## Future Enhancements

- [ ] Classify OpenClaw runtime databases and binary assets.
  - Determine which SQLite databases are canonical state versus cache/runtime state.
  - Consider safe metadata-only summaries for excluded databases.
  - Decide whether a future backup profile should opt into selected non-text assets.

- [ ] Add restore planning and restore support.
  - Default to dry-run restore plans.
  - Restore only tracked safe files from a selected commit.
  - Do not delete live excluded files when restoring mixed tracked/excluded directories.
  - Show explicit delete/overwrite operations before applying anything.

- [ ] Add hardened Claw Keeper service-account setup.
  - Support a documented mode where Claw Keeper runs as a separate OS user.
  - Store the deploy key under that user, outside OpenClaw's Unix permissions.
  - Grant Claw Keeper read access only to selected OpenClaw state paths.
  - Keep this out of the default skill flow until the setup can be made clear and safe.
