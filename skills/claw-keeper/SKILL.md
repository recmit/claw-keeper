---
name: claw-keeper
description: Use when the user asks to install, configure, snapshot, inspect, or roll back OpenClaw durable state with Claw Keeper. Guides setup of the public Claw Keeper tool repo and the user's private Git-backed OpenClaw history repo, asking for required inputs before running commands.
---

# Claw Keeper

Use this skill to install and configure Claw Keeper for OpenClaw state history.

Claw Keeper uses two Git repositories:

- Tool repo: `git@github.com:recmit/claw-keeper.git`
- Private history repo: provided by the user; receives safe OpenClaw state snapshots

Never store SSH private keys, API keys, OAuth material, provider credentials, raw logs, or session/completion databases in the history repo.

## Required Inputs

Before running install or init commands, ask the user for:

- Private history repo URI, for example `git@github-claw-keeper-history:<owner>/openclaw-history.git`
- OpenClaw state root, default `~/.openclaw`
- Local history repo path, default `~/openclaw-history`
- Whether a dedicated SSH key already exists for the private history repo

If a dedicated key does not exist, ask permission before creating one.

## Install Tool

Install Claw Keeper from the public tool repo:

```bash
uv tool install "git+ssh://git@github.com/recmit/claw-keeper.git"
```

If `uv` cannot use the SSH form, use a local checkout or the equivalent HTTPS URL for the public repo if available.

Verify:

```bash
claw-keeper --help
```

## Configure Private History Repo SSH

Prefer a dedicated SSH key that can write only to the private history repo.

If the user confirms a new key should be created:

```bash
mkdir -p ~/.ssh
ssh-keygen -t ed25519 -C "claw-keeper openclaw-history" -f ~/.ssh/claw_keeper_history_ed25519
chmod 700 ~/.ssh
chmod 600 ~/.ssh/claw_keeper_history_ed25519
cat ~/.ssh/claw_keeper_history_ed25519.pub
```

Tell the user to add the public key as a write-enabled deploy key on the private history repo.

Use this SSH host alias in `~/.ssh/config`:

```sshconfig
Host github-claw-keeper-history
  HostName github.com
  User git
  IdentityFile ~/.ssh/claw_keeper_history_ed25519
  IdentitiesOnly yes
```

Then the private repo URI should look like:

```text
git@github-claw-keeper-history:<owner>/openclaw-history.git
```

## Initialize

After the user provides the private history repo URI, run:

```bash
claw-keeper init \
  --source ~/.openclaw \
  --repo ~/openclaw-history \
  --remote git@github-claw-keeper-history:<owner>/openclaw-history.git
```

Replace paths and remote with the user's answers.

Check status:

```bash
claw-keeper status
```

Create the first snapshot:

```bash
claw-keeper snapshot --reason initial --push
```

Install the restartable watcher service:

```bash
claw-keeper install-systemd --dry-run --push --debounce 60
claw-keeper install-systemd --apply --push --debounce 60
systemctl --user daemon-reload
systemctl --user enable --now claw-keeper-watch
```

When testing upgraded versions of the tool, restart the service after upgrading:

```bash
uv tool upgrade claw-keeper
systemctl --user restart claw-keeper-watch
```

## Current Command Support

Implemented now:

- `claw-keeper init`
- `claw-keeper status`
- `claw-keeper snapshot`
- `claw-keeper watch`
- `claw-keeper install-systemd`

Not implemented yet:

- `claw-keeper restore-plan`
- `claw-keeper restore`

If the user asks to restore before those commands exist, explain that the installed version does not support restore yet and suggest checking `claw-keeper --help`.
