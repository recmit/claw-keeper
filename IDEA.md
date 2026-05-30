# Claw Keeper — Git-backed evolution history for OpenClaw

## 1. Project summary

Claw Keeper is a lightweight persistence and audit tool for OpenClaw agents. It watches selected OpenClaw state directories, mirrors a safe subset into a Git repository, and creates descriptive snapshot commits whenever meaningful changes occur.

The goal is not to sandbox OpenClaw or prevent all bad behavior. The goal is to make the agent’s durable evolution visible, reviewable, and rollback-friendly.

Claw Keeper treats agent state changes as an evolving narrative:

- What changed?
- Which skills, memories, or configuration files were affected?
- Why does the change appear meaningful?
- Were any risky or secret-like files excluded?
- What commit can the user roll back to?

The initial version uses a single raw-history branch. It does not implement a curated/squashed branch. Any future curated branch should be a separate offline post-processing system.

---

## 2. Non-goals

Claw Keeper does not attempt to:

- Fully sandbox OpenClaw.
- Prevent OpenClaw from modifying files it has OS permission to modify.
- Intercept every OpenClaw tool call.
- Read or parse all model tokens.
- Replace OpenClaw’s built-in backup system.
- Back up credentials, API keys, OAuth tokens, or raw secrets.
- Rewrite Git history.
- Squash commits.
- Implement a full restore of all OpenClaw state.
- Run as a full OpenClaw plugin in the MVP.

The MVP is a CLI/daemon-style tool, optionally accompanied by an OpenClaw skill that teaches the agent how to use it.

---

## 3. Core idea

Claw Keeper maintains a Git mirror of selected safe OpenClaw state.

Example source state:

text ~/.openclaw/skills/ ~/.openclaw/memory/ ~/.openclaw/config/ ~/openclaw-workspace/ 

Example mirror repo:

text ~/openclaw-history/   skills/   memory/   config-redacted/   workspace-notes/   manifests/   reports/ 

The mirror repo is committed periodically or when files change.

Each commit should be a descriptive “state-transition” commit, not a terse code commit.

Example commit message:

text chore(agent-state): update finance review workflow  OpenClaw revised the finance-import skill to make transaction handling more review-oriented. The change emphasizes writing proposed normalized records instead of directly approving ledger entries.  Changed areas: - skills/finance-import/SKILL.md - manifests/latest.json - reports/secret-scan.md  Notable details: - Adds proposal-before-approval guidance. - Adds duplicate source-row checks. - Updates the manifest with the new skill hash.  Risk notes: - No credential-bearing files were included. - No raw session logs were committed. 

The message should be concise when the change is trivial, but rich enough to be useful later when the change is meaningful.

---

## 4. MVP commands

### claw-keeper init

Initialize a history repo and configuration.

Responsibilities:

- Create or validate the mirror Git repo.
- Create a default config file.
- Create .gitignore.
- Create initial manifest.
- Optionally create the first snapshot commit.

Example:

bash claw-keeper init \   --source ~/.openclaw \   --repo ~/openclaw-history 

---

### claw-keeper snapshot

Create one snapshot commit if there are meaningful changes.

Responsibilities:

1. Acquire snapshot lock.
2. Copy selected safe files from source to mirror repo.
3. Apply exclusion/redaction policy.
4. Generate manifest.
5. Run secret/risk scan.
6. Stage changes.
7. If no changes, exit cleanly.
8. Build diff package.
9. Generate commit message.
10. Commit.
11. Optionally push.
12. If a pending snapshot request exists, optionally run one follow-up snapshot.

Example:

bash claw-keeper snapshot 

Optional flags:

bash claw-keeper snapshot --reason manual claw-keeper snapshot --reason watch claw-keeper snapshot --no-llm claw-keeper snapshot --push claw-keeper snapshot --dry-run 

---

### claw-keeper watch

Watch source directories and trigger snapshots after a quiet period.

Example:

bash claw-keeper watch --debounce 60 

Behavior:

- Watch configured source paths.
- When a change occurs, wait for a quiet period.
- Then call the same snapshot path used by manual snapshots.
- Do not implement separate snapshot logic inside the watcher.
- If a snapshot is already running, mark a pending snapshot request and return.

---

### claw-keeper status

Show current state.

Example output:

text Claw Keeper status  Source:   ~/.openclaw  History repo:   ~/openclaw-history  Last snapshot:   2026-05-30 13:42:10   abc123 chore(agent-state): update finance review workflow  Working tree:   clean  Watcher:   not running  Pending snapshot:   no 

---

### claw-keeper restore-plan

Generate a restore plan from a previous commit.

Example:

bash claw-keeper restore-plan --from HEAD~1 --path skills/ 

This should not modify live OpenClaw files. It should show:

- Which files would be restored.
- Which files would be deleted.
- Which files are not tracked.
- Which excluded/secret-bearing state cannot be restored.
- Suggested command to apply the restore.

---

### claw-keeper restore

Restore selected tracked files from a previous commit.

MVP can default to dry-run.

Example:

bash claw-keeper restore --from HEAD~1 --path skills/ --dry-run claw-keeper restore --from HEAD~1 --path skills/ --apply 

Recommended behavior:

- Restore only tracked safe state.
- Do not restore credentials or excluded files.
- After applying restore, run snapshot --reason restore to record the rollback as a new commit.
- Do not rewrite Git history.

---

## 5. Trigger model

The MVP supports:

text manual snapshot watcher snapshot 

Cron/systemd is optional and should not be required for the MVP.

Future deployment may add:

text cron/systemd timer OpenClaw hook GitHub Action curator 

But all triggers should call the same idempotent snapshot() operation.

---

## 6. Concurrency model

Snapshots may be triggered by multiple sources. Claw Keeper should avoid overlapping Git operations.

Use:

text lock file pending flag 

Example files:

text /tmp/claw-keeper.lock /tmp/claw-keeper.pending 

Behavior:

text trigger arrives   ↓ try to acquire lock   ├── lock acquired:   │     run snapshot   │     if pending flag exists:   │       clear pending flag   │       optionally run one follow-up snapshot   └── lock unavailable:         touch pending flag         exit cleanly 

Do not build a real queue in the MVP. Backup jobs are coalescible: many change events should produce at most one or two commits representing the latest state.

The snapshot process should be idempotent:

- If no files changed, exit successfully.
- If LLM commit-message generation fails, use a deterministic fallback message.
- If a push fails, keep the local commit and report the push failure.

Do not hold the lock during watcher debounce. Hold the lock only during the critical snapshot operation.

---

## 7. Snapshot algorithm

High-level algorithm:

text snapshot(reason):   acquire lock or mark pending   load config   copy selected files into mirror repo   apply exclusions/redactions   write manifest   run secret/risk scan   git add -A   if git diff --cached is empty:       exit cleanly   build diff package   generate commit message   validate commit message   git commit   optionally git push   process pending flag if present 

Recommended Git commands:

bash git status --porcelain git add -A git diff --cached --stat git diff --cached --name-status git diff --cached --find-renames git diff --cached --unified=5 git log -5 --pretty=format:'- %s' git commit -F .claw-keeper/commit-message.txt 

Use staged diffs, not unstaged diffs, because the LLM should summarize exactly what will be committed.

---

## 8. Safe copy policy

Claw Keeper should copy only a selected safe subset of OpenClaw state.

Default included paths may include:

text skills/ memory/ safe config templates workspace docs manifests reports 

Default excluded paths should include:

text .env *.pem *.key id_rsa id_ed25519 *.sqlite *.db tokens* credentials* auth* oauth* sessions/ logs/ browser profiles provider credentials API keys bot tokens SSH keys raw session transcripts 

The default policy should be conservative. Users can opt into additional paths explicitly.

If a file matches a risky pattern, Claw Keeper should either:

1. Exclude it; or
2. Redact it; or
3. Refuse to commit and report the reason.

For MVP, exclusion is simpler than redaction.

---

## 9. Secret and risk scanning

Before committing, run a simple local risk scan over staged files and diffs.

Flag patterns such as:

text OPENAI_API_KEY ANTHROPIC_API_KEY AWS_SECRET_ACCESS_KEY BEGIN PRIVATE KEY BEGIN OPENSSH PRIVATE KEY id_ed25519 id_rsa .env oauth access_token refresh_token bot token 

Risk levels:

text HIGH:   likely credential material or private key  MEDIUM:   credential-like path, auth config, token reference  LOW:   harmless but notable config or skill change 

MVP behavior:

- If HIGH risk is detected, refuse to commit by default.
- If MEDIUM risk is detected, commit only if policy allows it, and include risk notes.
- Always write a report under reports/.

Example:

text reports/2026-05-30T134210-secret-scan.md 

---

## 10. LLM-generated commit messages

The LLM should not be prompted as a normal code commit assistant. It should be prompted as a narrator of agent-state evolution.

The prompt should ask for a state-transition commit message.

Desired qualities:

- Descriptive but not bloated.
- Concise when the diff is trivial.
- More explanatory when the diff reflects a meaningful agent evolution.
- Honest about uncertainty.
- No invented intent.
- Include risk notes when relevant.
- Include changed areas.
- Mention rollback-relevant information if useful.
- Treat the commit as part of an audit/evolution log.

The LLM should receive:

text repository purpose reason for snapshot recent commit subjects changed file list diffstat name-status filtered staged diff secret/risk scan summary whether the diff was truncated desired output schema 

Suggested output schema:

json {   "subject": "chore(agent-state): update finance review workflow",   "body": [     "OpenClaw revised the finance-import skill to make transaction handling more review-oriented.",     "",     "Changed areas:",     "- skills/finance-import/SKILL.md",     "- manifests/latest.json",     "",     "Notable details:",     "- Adds proposal-before-approval guidance.",     "- Adds duplicate source-row checks.",     "",     "Risk notes:",     "- No credential-bearing files were included.",     "- No raw session logs were committed."   ] } 

Validation rules:

- subject must be a single line.
- subject should usually be between 50 and 100 characters.
- body should be optional for truly tiny changes, but preferred for meaningful changes.
- Total commit message should usually stay under 250 words.
- If output is invalid, use fallback message.

Fallback message:

text chore(agent-state): snapshot OpenClaw state  Changed files: - ... 

---

## 11. Suggested LLM prompt

text You are writing a Git commit message for Claw Keeper.  Claw Keeper stores a safe, redacted, Git-backed evolution history of an OpenClaw agent's durable state: skills, memory, safe config templates, manifests, and restore reports.  This is not a normal code repository. The commit message should read like a concise state-transition commentary for an agent evolution log. It should help a human understand later what changed, why it appears relevant, and whether there are any risk or restore notes.  Do not be verbose for trivial changes. If the change is small, write a short subject and a very small body or no body. If the change is meaningful, include a useful body with changed areas, notable details, and risk notes.  Do not invent intent that is not supported by the diff. If you are unsure, use phrases like "appears to" or "updates".  Return JSON only with this shape:  {   "subject": "...",   "body": ["...", "..."] }  Rules: - Subject must be one line. - Prefer a subject between 50 and 100 characters. - Body should usually be 3 to 10 short lines for meaningful changes. - Keep the whole message under 250 words. - Include "Risk notes" if risk scan findings are provided. - Mention excluded/redacted files only if relevant. - Do not include markdown fences. - Do not include raw secrets. 

Then include the data package:

text Snapshot reason: ...  Recent commit subjects: ...  Changed files: ...  Diffstat: ...  Name-status: ...  Risk scan: ...  Filtered staged diff: ... 

---

## 12. Rollback model

Rollback should be path-based and commit-based.

Claw Keeper should not claim to undo every side effect OpenClaw caused. It can restore only tracked safe state.

Example:

bash claw-keeper restore-plan --from abc123 --path skills/ claw-keeper restore --from abc123 --path skills/ --apply 

Restore process:

1. Identify target commit.
2. Identify selected path.
3. Show restore plan.
4. Copy version of selected path from mirror repo commit into live OpenClaw state.
5. Run snapshot --reason restore.
6. Commit the rollback as a new raw-history commit.

Do not use force-push or history rewriting for rollback.

---

## 13. Branch model

MVP uses one branch:

text raw-history 

or simply:

text main 

Recommended explicit branch:

text raw-history 

This branch is append-only-ish and granular. It is the source of truth for rollback.

Do not implement curated branch or squashing in MVP.

Future extension:

text curated-history 

This would be produced by an offline process, likely a GitHub Action, that summarizes raw commits into periodic digest files. It should not rewrite raw history.

---

## 14. Installation model

MVP installation can be simple:

bash uv tool install git+https://github.com/<user>/claw-keeper 

or during development:

bash uv tool install -e . 

A typical setup may also configure a private GitHub remote for the history repository so snapshots are replicated off-machine:

bash cd ~/openclaw-history git remote add origin git@github.com:<user>/openclaw-history.git git push -u origin raw-history 

Claw Keeper should focus on backing up explicitly approved OpenClaw state such as:

text ~/.openclaw/skills/ ~/.openclaw/memory/ selected config templates workspace notes/docs 

It should avoid copying OpenClaw secrets, auth state, browser profiles, or provider credentials by default.

Security statement:

text Claw Keeper is primarily a Git-backed history and recovery tool, not a sandbox. It works best when configured to mirror only known-safe OpenClaw folders into a local or private remote Git repository. 

---

## 15. Optional OpenClaw skill

The project may include a small OpenClaw skill:

text skills/claw-keeper/SKILL.md 

The skill should teach OpenClaw how to use Claw Keeper:

text Use Claw Keeper when the user asks to preserve, snapshot, inspect, or roll back OpenClaw's durable state.  Preferred commands: - claw-keeper status - claw-keeper snapshot --reason openclaw-request - claw-keeper restore-plan --from <commit> --path <path>  Rules: - Do not attempt to commit credentials, API keys, OAuth tokens, raw session logs, or SSH keys. - Do not modify Claw Keeper's own source code unless the user explicitly asks. - Prefer restore-plan before restore. - Explain that Claw Keeper is not a sandbox. 

The skill is an integration convenience, not a trust boundary.

---

## 16. MVP implementation checklist

### Required

- [ ] CLI project skeleton.
- [ ] Config file.
- [ ] init command.
- [ ] snapshot command.
- [ ] Safe copy policy.
- [ ] Basic exclude list.
- [ ] Git mirror repo.
- [ ] Lock file.
- [ ] Pending snapshot flag.
- [ ] Staged diff package.
- [ ] Deterministic fallback commit message.
- [ ] LLM commit message generation.
- [ ] Commit message validation.
- [ ] Basic secret/risk scan.
- [ ] status command.
- [ ] watch command with debounce.
- [ ] README demo instructions.

### Nice to have

- [ ] restore-plan.
- [ ] restore --dry-run.
- [ ] restore --apply.
- [ ] Optional push to remote.
- [ ] Generated Markdown report for each snapshot.
- [ ] OpenClaw skill installer.
- [ ] install-cron --dry-run.

### Explicitly defer

- [ ] Full plugin.
- [ ] Curated/squashed branch.
- [ ] GitHub Action curator.
- [ ] Signed commits.
- [ ] Separate Unix user installer.
- [ ] Docker sandbox integration.
- [ ] Full OpenClaw backup/restore of credentials and session DBs.

---

## 17. Demo script

1. Initialize Claw Keeper:

bash claw-keeper init --source ~/.openclaw --repo ~/openclaw-history 

2. Run first snapshot:

bash claw-keeper snapshot --reason initial 

3. Modify or create an OpenClaw skill.

4. Run:

bash claw-keeper snapshot --reason demo-change 

5. Show:

bash cd ~/openclaw-history git log --oneline git show HEAD 

6. Show that the commit message is descriptive and contains changed areas/risk notes.

7. Add a fake risky line to a skill, e.g. a reference to ~/.ssh/id_ed25519.

8. Run snapshot and show that Claw Keeper flags it.

9. Show restore plan:

bash claw-keeper restore-plan --from HEAD~1 --path skills/ 

10. Optionally start watcher:

bash claw-keeper watch
