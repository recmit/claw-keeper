# Claw Keeper

Claw Keeper is a small CLI for keeping a Git-backed history of selected, safe OpenClaw state.

The intended setup uses two repositories:

- A public or shareable **tool repo** for this package, installed with `uv`.
- A private **history repo** that receives OpenClaw state snapshots.

The tool repo must not contain OpenClaw state, credentials, tokens, OAuth material, or SSH keys. The history repo should also avoid credentials; Claw Keeper defaults are conservative and exclude known risky paths.

## Install the Tool

During development:

```bash
uv tool install -e .
```

From a public Git repo:

```bash
uv tool install "git+ssh://git@github.com/recmit/claw-keeper.git"
```

Public tool repository:

```text
git@github.com:recmit/claw-keeper.git
```

## Development Workflow

Install the tracked Git hooks once per checkout:

```bash
scripts/install-git-hooks
```

Run the full local check suite:

```bash
scripts/check
```

Every committed change should bump the package version in both `pyproject.toml`
and `uv.lock`. The pre-commit hook enforces the version bump and runs the same
check suite as CI.

## Create the Private History Repo

Create a private GitHub repository for snapshots, for example:

```text
<owner>/openclaw-history
```

This private repo is separate from the Claw Keeper tool repo. It is the destination for snapshot commits and should use a scoped SSH credential that can write only to this one history repo.

## Create a Scoped SSH Key

On the OpenClaw VM, generate a dedicated key for the private history repo:

```bash
mkdir -p ~/.ssh
ssh-keygen -t ed25519 -C "claw-keeper openclaw-history" -f ~/.ssh/claw_keeper_history_ed25519
chmod 700 ~/.ssh
chmod 600 ~/.ssh/claw_keeper_history_ed25519
```

Add the public key to the private GitHub history repo as a deploy key with write access:

```bash
cat ~/.ssh/claw_keeper_history_ed25519.pub
```

Use a host alias so this key is scoped to the history repo remote:

```sshconfig
Host github-claw-keeper-history
  HostName github.com
  User git
  IdentityFile ~/.ssh/claw_keeper_history_ed25519
  IdentitiesOnly yes
```

Then use this remote URL:

```text
git@github-claw-keeper-history:<owner>/openclaw-history.git
```

If you store the private key through OpenClaw's secret system, keep it outside tracked snapshot content. When `--source ~/.openclaw` is used, Claw Keeper excludes `secrets/` by default, but the safest pattern is still to keep operational SSH material outside the history repo and verify exclusions before the first snapshot.

## Initialize Claw Keeper

For the current OpenClaw layout, use the OpenClaw state root as the source:

```bash
claw-keeper init \
  --source ~/.openclaw \
  --repo ~/openclaw-history \
  --remote git@github-claw-keeper-history:<owner>/openclaw-history.git
```

Include paths are relative to `--source`. The default mirror policy is OpenClaw-aware and text-first. It starts from:

```text
workspace/
identity/
memory/
agents/
flows/
tasks/
plugin-skills/
skills/
openclaw.json
```

Within those paths, Claw Keeper mirrors text files under a conservative size limit and records skipped files in `manifests/latest.json`. The default exclude policy avoids risky or noisy OpenClaw runtime state inside those trees, such as:

```text
secrets/
logs/
completions/
devices/
npm/
sessions/
codex-home/
cache/
plugins/cache/
shell_snapshots/
tmp/
identity/device-auth.json
*.sqlite
*.sqlite-*
*.sqlite-wal
*.sqlite-shm
*.db
*.db-*
*.wal
*.shm
*.pem
*.key
id_rsa
id_ed25519
*auth*
*token*
*secret*
*credential*
openclaw.json.bak*
openclaw.json.last-good
```

See `docs/MIRROR_RISK_MODEL.md` for the current monitoring-first risk model and the limits of text-first mirroring.

Check the setup:

```bash
claw-keeper status
```

Create the first deterministic snapshot and push it:

```bash
claw-keeper snapshot --reason initial --push
```

For foreground testing, start the polling watcher:

```bash
claw-keeper watch --debounce 60 --interval 5 --push
```

For a restartable user service, preview and install the systemd unit:

```bash
claw-keeper install-systemd --dry-run --push --debounce 60
claw-keeper install-systemd --apply --push --debounce 60
systemctl --user daemon-reload
systemctl --user enable --now claw-keeper-watch
```

The service uses `Restart=always`. After upgrading the tool on the VM, restart the watcher so it uses the new code:

```bash
uv tool upgrade claw-keeper
systemctl --user restart claw-keeper-watch
```

## Current MVP Status

Implemented:

```text
claw-keeper init
claw-keeper status
claw-keeper snapshot
claw-keeper watch
claw-keeper install-systemd
```

Not implemented yet:

```text
claw-keeper restore-plan
claw-keeper restore
```

Snapshots use a deterministic no-LLM commit message in the current POC. Pushes use the configured private remote and the dedicated SSH key above.

## Optional OpenClaw Skill

This repo includes an OpenClaw skill at:

```text
skills/claw-keeper/SKILL.md
```

Install the skill into OpenClaw when you want an agent to guide the setup. The skill tells OpenClaw to ask for the private history repo URI and then run the install/init flow using this public tool repo:

```text
git@github.com:recmit/claw-keeper.git
```

The OpenClaw skill installer expects `SKILL.md` at the root of a Git archive, so this repo publishes a dedicated skill branch:

```bash
openclaw skills install git:recmit/claw-keeper@openclaw-skill --as claw-keeper --force
```

The canonical skill source still lives in `skills/claw-keeper/SKILL.md` on `main`; the `openclaw-skill` branch exists only to make Git-based skill installation straightforward. A GitHub Action syncs the canonical skill into root `SKILL.md` on that branch when the skill changes on `main`.

Then ask OpenClaw to use the Claw Keeper skill to install and configure Claw Keeper.
