"""Basic local risk scanning for copied snapshot content."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple


HIGH_MARKERS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "BEGIN PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
)

MEDIUM_MARKERS = (
    "access_token",
    "refresh_token",
    "oauth",
    "credentials",
    "id_ed25519",
    "id_rsa",
    "bot token",
)


@dataclass(frozen=True)
class RiskFinding:
    level: str
    path: str
    marker: str


def scan_tree(root: Path, skip_prefixes: Tuple[str, ...] = ()) -> List[RiskFinding]:
    findings = []
    for path in sorted(
        item for item in root.rglob("*") if item.is_file() and not item.is_symlink()
    ):
        relative = path.relative_to(root).as_posix()
        if any(
            relative == prefix.rstrip("/")
            or relative.startswith(prefix.rstrip("/") + "/")
            for prefix in skip_prefixes
        ):
            continue
        findings.extend(scan_file(root, path))
    return findings


def scan_file(root: Path, path: Path) -> List[RiskFinding]:
    relative = path.relative_to(root).as_posix()
    try:
        data = path.read_bytes()
    except OSError:
        return []
    if b"\x00" in data[:4096]:
        return []
    text = data[: 1024 * 1024].decode("utf-8", errors="ignore")
    lowered = text.lower()

    findings = []
    for marker in HIGH_MARKERS:
        if marker in text:
            findings.append(RiskFinding("HIGH", relative, marker))
    for marker in MEDIUM_MARKERS:
        if marker.lower() in lowered:
            findings.append(RiskFinding("MEDIUM", relative, marker))
    return findings


def has_high_risk(findings: Sequence[RiskFinding]) -> bool:
    return any(finding.level == "HIGH" for finding in findings)


def summarize_findings(findings: Sequence[RiskFinding]) -> str:
    if not findings:
        return "No credential-like markers found."
    counts = {}
    for finding in findings:
        counts[finding.level] = counts.get(finding.level, 0) + 1
    return ", ".join(
        "{0}: {1}".format(level, counts[level]) for level in sorted(counts)
    )


def render_report(findings: Sequence[RiskFinding]) -> str:
    lines = ["# Claw Keeper Risk Scan", "", summarize_findings(findings), ""]
    if findings:
        lines.append("Findings:")
        for finding in findings:
            lines.append(
                "- {0}: {1} matched {2}".format(
                    finding.level, finding.path, finding.marker
                )
            )
        lines.append("")
    return "\n".join(lines)
