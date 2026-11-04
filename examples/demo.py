"""A fake agent on a fake publishing site, behind the three layers.

    python examples/demo.py

The agent reads a page (allowed), clicks Publish (it waits for a human), and clicks
Delete (refused). Then the model tries to approve its own Publish (refused), the
human presses the button, and the Publish goes through with a one-time token.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from approval_guard import (ApprovalRefused, ApprovalRequired, ApprovalStore, Level, OperationLocked,  # noqa: E402
                            OperationRegistry, Verdict, classify)

SITE = "https://publisher.example.com/books/draft-42"


def build_registry(store: ApprovalStore) -> OperationRegistry:
    registry = OperationRegistry(store)
    for name in ("read", "navigate", "click"):
        registry.register(name, Level.FREE)
    for name in ("publish", "submit", "send"):
        registry.register(name, Level.REVIEW)
    for name in ("delete", "unpublish", "archive", "payment", "bank", "unknown"):
        registry.register(name, Level.LOCKED)
    return registry


class FakeAgent:
    """Proposes browser actions; every one passes the rules, then the registry."""

    def __init__(self, registry: OperationRegistry, log: list[str]) -> None:
        self.registry = registry
        self.log = log

    def act(self, kind: str, text: str, url: str, token: str | None = None) -> str:
        decision = classify(text, url, kind)
        label = f"{kind} {text!r}" if text else kind
        if decision.verdict is Verdict.FORBIDDEN:
            outcome = f"REFUSED   {label}: {decision.reason}"
        else:
            try:
                self.registry.run(decision.action, lambda: None, token=token, question=f"{label} on {url}")
                outcome = f"DONE      {label}"
            except ApprovalRequired as waiting:
                outcome = f"WAITING   {label}: approval {waiting.approval_id} is pending"
            except OperationLocked as locked:
                outcome = f"REFUSED   {label}: {locked}"
        self.log.append(outcome)
        return outcome


def main(state_dir: Path) -> list[str]:
    store = ApprovalStore(state_dir / "approvals.json")
    log: list[str] = []
    agent = FakeAgent(build_registry(store), log)

    agent.act("read", "", SITE)
    agent.act("click", "Publish", SITE)
    agent.act("click", "Delete title", SITE)

    approval = store.pending()[0]
    try:
        store.resolve(approval.id, True, source="model")
    except ApprovalRefused as refused:
        log.append(f"REFUSED   the model approving its own publish: {refused}")

    token = store.resolve(approval.id, True, source="button")
    log.append("APPROVED  the human pressed the button; a one-time publish token was issued")
    agent.act("click", "Publish", SITE, token=token)
    return log


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        for line in main(Path(tmp)):
            print(line)
