"""systemd user service generation."""

from __future__ import annotations

from pathlib import Path

SERVICE_NAME = "claw-keeper-watch.service"


def service_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / SERVICE_NAME


def render_service(
    config_path: Path, debounce: int = 60, interval: int = 5, push: bool = False
) -> str:
    args = [
        "%h/.local/bin/claw-keeper",
        "watch",
        "--config",
        str(config_path),
        "--debounce",
        str(debounce),
        "--interval",
        str(interval),
    ]
    if push:
        args.append("--push")
    return """[Unit]
Description=Claw Keeper watcher
After=network-online.target

[Service]
Type=simple
WorkingDirectory=%h
ExecStart={exec_start}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
""".format(exec_start=" ".join(args))


def install_service(
    config_path: Path, debounce: int = 60, interval: int = 5, push: bool = False
) -> Path:
    path = service_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_service(config_path, debounce=debounce, interval=interval, push=push),
        encoding="utf-8",
    )
    return path
