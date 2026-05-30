# OpenClaw VM Handoff

Date: 2026-05-30  
Host: `loro-claw.exe.xyz`  
VM user: `exedev`  
Control UI: `https://loro-claw.exe.xyz`  
Shelley UI: `https://loro-claw.shelley.exe.xyz`

## Current State

This is an exe.dev VM running OpenClaw. The setup is working. The active OpenClaw workspace is still the starter workspace:

```bash
/home/exedev/.openclaw/workspace
```

The Loro/GitHub workspace idea has **not** been attached. `~/work` was empty when checked. The starter workspace was lightly personalized into “Loro,” but it is not backed by the Loro repo.

## Runtime Architecture

OpenClaw is not running in Docker. It is a Node process managed by a systemd user service.

```text
Browser
  -> https://loro-claw.exe.xyz
  -> exe.dev HTTPS proxy to VM port 8000
  -> nginx on VM
  -> 127.0.0.1:18789
  -> OpenClaw Gateway
```

Gateway process:

```bash
/usr/bin/node /home/exedev/.npm-global/lib/node_modules/openclaw/dist/index.js gateway --port 18789
```

Service file:

```bash
~/.config/systemd/user/openclaw-gateway.service
```

Useful checks:

```bash
openclaw status
openclaw gateway status
openclaw health
openclaw agents list
```

## Versions

Observed:

```text
OpenClaw 2026.5.27
Node v24.15.0
npm 11.12.1
Ubuntu 24.04.4 LTS
```

CLI:

```bash
/home/exedev/.npm-global/bin/openclaw
```

## Active Workspace

Current active workspace:

```bash
~/.openclaw/workspace
```

Files:

```text
AGENTS.md
SOUL.md
IDENTITY.md
USER.md
TOOLS.md
HEARTBEAT.md
```

`BOOTSTRAP.md` is gone, likely because first-run bootstrap completed.

The workspace is a git repo but had no commits when checked:

```text
No commits yet on main
all files untracked
```

## Prompt / Harness Behavior

OpenClaw has a built-in harness prompt separate from Markdown files. The harness supplies runtime rules, tool behavior, safety guidance, workspace path, skills metadata, memory guidance, heartbeat/channel behavior, output directives, and OpenClaw control guidance.

Workspace Markdown files are injected as user-editable context.

Observed behavior for Codex-backed runs:

```text
AGENTS.md    loaded natively by Codex
TOOLS.md     inherited tool/developer-style guidance
SOUL.md      turn-scoped context
IDENTITY.md  turn-scoped context
USER.md      turn-scoped context
HEARTBEAT.md special heartbeat handling
MEMORY.md    referenced for durable memory; not always pasted wholesale
```

## Model Auth

Agent turns are using Codex OAuth.

Check:

```bash
openclaw models status
```

Observed default:

```text
openai/gpt-5.5
```

Observed runtime auth:

```text
openai via codex uses openai-codex
```

An OpenAI API key was also added via SecretRefs for direct OpenAI API surfaces such as embeddings/memory search and possible sidecar apps.

Secret provider summary:

```text
provider alias: openai
provider mode: singleValue
credential profile: profiles.openai.key
secret id: value
```

The secret file should contain only the raw key, not `OPENAI_API_KEY=...`.

Check/reload secrets:

```bash
openclaw secrets audit --check
openclaw secrets reload
```

If reload fails:

```bash
openclaw gateway restart
openclaw secrets reload
```

## API Quota

Memory search now finds the OpenAI API key, but embeddings failed with:

```text
429 insufficient_quota
```

So the key resolves, but the OpenAI Platform account/project does not currently have usable quota or billing for embeddings.

## Memory / Dreaming / Cron / Tasks

When checked:

```text
Memory DB records: 0
Cron jobs: 0
Task runs: 0
Flow runs: 0
Dreaming: off
```

Memory status:

```bash
openclaw memory status --deep
```

Current memory issue:

```text
memory directory missing (~/.openclaw/workspace/memory)
```

Create if needed:

```bash
mkdir -p ~/.openclaw/workspace/memory
```

Cron:

```bash
openclaw cron status
openclaw cron list
```

## Channels / Discord

No channels were configured when checked.

```bash
openclaw channels status
```

Discord skill exists:

```bash
~/.npm-global/lib/node_modules/openclaw/skills/discord/SKILL.md
```

Important: current `tools.profile` is `coding`, and status logs showed it filters out tools including `message`, `nodes`, `tts`, and `gateway`. Discord uses the `message` tool, so Discord setup may require changing tool policy/profile.

Check:

```bash
openclaw config get tools.profile
```

## Security Notes

`openclaw security audit --deep` reported:

```text
0 critical
2 warnings
1 info
```

Warnings:

```text
gateway.trustedProxies missing even though nginx/exe.dev proxying is used
Codex plugin install spec is floating/unpinned
```

Doctor also reported:

```text
no command owner configured
gateway auth token stored plaintext in openclaw.json
Codex OAuth credentials present, outside static SecretRef migration
memory search wants OpenAI API quota
```

Run:

```bash
openclaw doctor
openclaw security audit --deep
```

Do not run this blindly:

```bash
openclaw doctor --fix
```

Inspect its preview first.

## Files Not To Share Or Commit

Do not commit or copy into a shared repo:

```text
~/.openclaw/openclaw.json
~/.openclaw/agents/main/agent/auth-profiles.json
~/.openclaw/agents/main/agent/auth-state.json
~/.openclaw/agents/main/agent/models.json
~/.openclaw/devices/
~/.openclaw/identity/
~/.openclaw/credentials/
~/.openclaw/secrets/
~/.openclaw/agents/main/sessions/
```

These may contain tokens, OAuth state, device pairing state, session logs, or private context.

## Fresh Exploration Advice

For a different idea, prefer creating a new isolated agent instead of overloading the current `main` workspace.

Explore:

```bash
openclaw agents --help
openclaw agents add --help
```

Before changing anything, read:

```bash
openclaw status
openclaw agents list
ls -la ~/.openclaw/workspace
sed -n '1,220p' ~/.openclaw/workspace/AGENTS.md
sed -n '1,220p' ~/.openclaw/workspace/SOUL.md
sed -n '1,220p' ~/.openclaw/workspace/IDENTITY.md
sed -n '1,220p' ~/.openclaw/workspace/USER.md
```
