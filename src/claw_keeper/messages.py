"""Commit-message provider interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class CommitMessage:
    subject: str
    body: List[str]

    def as_text(self) -> str:
        if not self.body:
            return self.subject + "\n"
        return self.subject + "\n\n" + "\n".join(self.body).rstrip() + "\n"


class CommitMessageProvider:
    def generate(self, changed_files: Iterable[str], reason: Optional[str] = None) -> CommitMessage:
        raise NotImplementedError


class FallbackCommitMessageProvider(CommitMessageProvider):
    def generate(self, changed_files: Iterable[str], reason: Optional[str] = None) -> CommitMessage:
        files = list(changed_files)
        subject = "chore(agent-state): snapshot OpenClaw state"
        body = []
        if reason:
            body.append("Snapshot reason: {0}".format(reason))
            body.append("")
        if files:
            body.append("Changed files:")
            body.extend("- {0}".format(path) for path in files)
        return CommitMessage(subject=subject, body=body)


class LLMCommitMessageProvider(CommitMessageProvider):
    def generate(self, changed_files: Iterable[str], reason: Optional[str] = None) -> CommitMessage:
        raise NotImplementedError("LLM commit-message generation is not implemented in this slice")
