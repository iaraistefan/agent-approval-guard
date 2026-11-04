"""Layer 3: a human's "yes", given by hand, used once.

`ask()` writes a pending approval to a JSON file before anything waits on it, so a
restart of the agent does not lose the question: a new `ApprovalStore` on the same
file sees it again.

Only one source can accept: `source="button"`, the human pressing the button under
the question. An answer that arrives from the API or from the model itself is
refused, whatever it says. A model that can approve its own actions has no guard.

An accepted approval returns a one-time token, bound to the single action family it
was asked for. Only a hash of the token is stored; the token itself is shown once.
Spending it (`consume`) marks it used on disk, so it does not work a second time,
not even after a restart, and a "publish" token never opens a "delete".
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

#: The one source that may accept an approval.
HUMAN_SOURCE = "button"

PENDING = "pending"
APPROVED = "approved"
DENIED = "denied"


class ApprovalError(RuntimeError):
    pass


class ApprovalRefused(ApprovalError):
    """The answer came from somewhere other than the human's button."""


class UnknownApproval(ApprovalError):
    """No pending approval with this id."""


class TokenInvalid(ApprovalError):
    """The token is unknown, already spent, or for a different action."""


@dataclass
class Approval:
    id: str
    action: str
    question: str
    status: str = PENDING
    asked_at: str = ""
    answered_at: str | None = None
    #: sha256 of the one-time token; the token itself is never written down.
    token_hash: str | None = None
    token_used: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ApprovalStore:
    """Every read goes to the file, so two objects on the same file (before and after
    a restart) always agree."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    # ------------------------------------------------------------------ #
    def _load(self) -> dict[str, Approval]:
        if not self.path.exists():
            return {}
        rows = json.loads(self.path.read_text(encoding="utf-8"))
        return {row["id"]: Approval(**row) for row in rows}

    def _save(self, approvals: dict[str, Approval]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps([asdict(a) for a in approvals.values()], indent=1), encoding="utf-8")
        tmp.replace(self.path)  # atomic: a crash leaves the old file or the new one, never half

    # ------------------------------------------------------------------ #
    def ask(self, action: str, question: str) -> Approval:
        """Write down a pending approval for `action` and return it."""
        approvals = self._load()
        approval = Approval(id=uuid.uuid4().hex[:12], action=action, question=question, asked_at=_now())
        approvals[approval.id] = approval
        self._save(approvals)
        return approval

    def get(self, approval_id: str) -> Approval | None:
        return self._load().get(approval_id)

    def pending(self) -> list[Approval]:
        return [a for a in self._load().values() if a.status == PENDING]

    def resolve(self, approval_id: str, accept: bool, *, source: str) -> str | None:
        """The human's answer. Returns the one-time token when accepted, None when denied.

        Raises ApprovalRefused for any source other than the button, before anything is
        read or written: the API and the model cannot answer, not even with "no"."""
        if source != HUMAN_SOURCE:
            raise ApprovalRefused(f"approvals are given only by a human, with the button (not from {source!r})")
        approvals = self._load()
        approval = approvals.get(approval_id)
        if approval is None or approval.status != PENDING:
            raise UnknownApproval(f"no pending approval {approval_id!r}")
        approval.answered_at = _now()
        if not accept:
            approval.status = DENIED
            self._save(approvals)
            return None
        token = secrets.token_urlsafe(32)
        approval.status = APPROVED
        approval.token_hash = _hash(token)
        self._save(approvals)
        return token

    def consume(self, token: str, action: str) -> Approval:
        """Spend `token` on `action`. Works once, and only for the action it was given for."""
        approvals = self._load()
        digest = _hash(token or "")
        approval = next((a for a in approvals.values()
                         if a.token_hash is not None and secrets.compare_digest(a.token_hash, digest)), None)
        if approval is None or approval.status != APPROVED:
            raise TokenInvalid("unknown token")
        if approval.token_used:
            raise TokenInvalid("this token was already used")
        if approval.action != action:
            raise TokenInvalid(f"this token approves {approval.action!r}, not {action!r}")
        approval.token_used = True
        self._save(approvals)
        return approval
