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

Do not guess the private repo URI. The private history repo must exist before `claw-keeper init --remote ...` runs. If the user has not created it yet, ask them to create a private GitHub repo first, then provide the SSH URI.

If a dedicated key does not exist, ask permission before creating one. Show only the public key. Never print, paste, or inspect the private key content.

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

For extra history protection, recommend that the user protect the private history branch, usually `raw-history`, in GitHub settings. At minimum, disable force pushes and branch deletion for that branch so Claw Keeper or OpenClaw can append commits but cannot rewrite or erase existing history.

Use a dedicated SSH host alias in `~/.ssh/config` so the private history repo uses only this deploy key:

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

Do not initialize Claw Keeper with a raw `git@github.com:<owner>/<repo>.git` remote if a deploy-key alias is intended. Convert it to the alias form first, then verify SSH access before taking the first snapshot:

```bash
ssh -T github-claw-keeper-history
```

If SSH access fails, stop and ask the user to confirm that the public key was added as a write-enabled deploy key.

## Key Custody

Be precise about what the setup protects. A deploy key under the same Unix user as OpenClaw, such as `~/.ssh/claw_keeper_history_ed25519`, is outside the mirrored snapshot paths but is still readable by processes running as that user. Do not claim it is outside OpenClaw's reach.

Key custody levels:

- If the user SSHes into the VM and creates/configures the deploy key manually under the OpenClaw Unix user, the private key avoids chat/tool-output exposure but is still readable by OpenClaw.
- For actual isolation from OpenClaw, use a separate OS user/service account for Claw Keeper, store the key under that account, and run the watcher service there. This is a future hardening task, not the default setup.

Only a separate OS account or root-owned unreadable path meaningfully moves the private key out of OpenClaw's reach. If the user wants that stronger model, pause and ask them to perform the privileged user/key/service setup out of band.

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
