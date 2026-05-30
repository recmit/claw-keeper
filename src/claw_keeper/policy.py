"""Default safe-copy policy for Claw Keeper."""

DEFAULT_BRANCH = "raw-history"

# Include paths are relative to the configured source path. For the default
# OpenClaw layout, source should usually be ~/.openclaw.
DEFAULT_INCLUDE_PATHS = (
    "workspace/",
    "identity/",
    "memory/",
    "agents/",
    "flows/",
    "tasks/",
    "plugin-skills/",
    "skills/",
    "openclaw.json",
)

DEFAULT_EXCLUDE_PATTERNS = (
    ".env",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "*.sqlite",
    "*.db",
    "tokens*",
    "credentials*",
    "auth*",
    "oauth*",
    "sessions/",
    "logs/",
    "browser/",
    "profiles/",
    "provider-credentials/",
    "secrets/",
    "completions/",
    "devices/",
    "npm/",
    "openclaw.json.bak*",
    "openclaw.json.last-good",
    "update-check.json",
    "gateway-supervisor-restart-handoff.json",
    "*api_key*",
    "*API_KEY*",
    "*bot_token*",
    "*access_token*",
    "*refresh_token*",
)

DEFAULT_GITIGNORE_LINES = (
    ".claw-keeper/",
    ".env",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "*.sqlite",
    "*.db",
    "tokens*",
    "credentials*",
    "auth*",
    "oauth*",
    "sessions/",
    "logs/",
    "browser/",
    "profiles/",
    "provider-credentials/",
    "secrets/",
    "completions/",
    "devices/",
    "npm/",
)
