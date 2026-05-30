"""Default safe-copy policy for Claw Keeper."""

DEFAULT_BRANCH = "raw-history"

DEFAULT_INCLUDE_PATHS = (
    "skills/",
    "memory/",
    "config/",
    "workspace/",
    "AGENTS.md",
    "SOUL.md",
    "IDENTITY.md",
    "USER.md",
    "TOOLS.md",
    "HEARTBEAT.md",
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
)
