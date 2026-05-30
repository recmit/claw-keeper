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
uv tool install git+https://github.com/<owner>/claw-keeper
```

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

Include paths are relative to `--source`. The default include policy starts with:

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

The default exclude policy includes risky or noisy state such as:

```text
secrets/
logs/
completions/
devices/
npm/
sessions/
*.sqlite
*.db
*.pem
*.key
id_rsa
id_ed25519
openclaw.json.bak*
openclaw.json.last-good
```

Check the setup:

```bash
claw-keeper status
```

## Current MVP Status

Implemented:

```text
claw-keeper init
claw-keeper status
```

Not implemented yet:

```text
claw-keeper snapshot
claw-keeper watch
claw-keeper restore-plan
claw-keeper restore
```

When snapshot support lands, pushes should use the configured private remote and the dedicated SSH key above.
