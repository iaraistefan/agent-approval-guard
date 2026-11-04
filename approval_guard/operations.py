"""Layer 2: every operation with side effects is registered with a level.

    FREE    runs without asking (reading, drafting, saving a draft)
    REVIEW  runs only with a one-time approval token for this operation
    LOCKED  never runs from code: only a human does it, by hand

An operation that was never registered is refused: the default for something
nobody thought about is "no", not "yes". A REVIEW operation without a token does
not run; it files a pending approval and raises ApprovalRequired with its id, so the
agent can stop and tell the human what it is waiting for.
"""
from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import TypeVar

from approval_guard.approvals import ApprovalStore

T = TypeVar("T")


class Level(str, Enum):
    FREE = "FREE"
    REVIEW = "REVIEW"
    LOCKED = "LOCKED"


class OperationError(RuntimeError):
    pass


class OperationLocked(OperationError):
    """The code may not do this. A human does it."""


class UnknownOperation(OperationError):
    """Not registered, so not allowed."""


class ApprovalRequired(OperationError):
    """A REVIEW operation was called without a token; a pending approval was filed."""

    def __init__(self, operation: str, approval_id: str) -> None:
        super().__init__(f"{operation!r} needs approval; waiting for approval {approval_id}")
        self.operation = operation
        self.approval_id = approval_id


class OperationRegistry:
    def __init__(self, approvals: ApprovalStore) -> None:
        self.approvals = approvals
        self._levels: dict[str, Level] = {}

    def register(self, name: str, level: Level) -> None:
        if name in self._levels and self._levels[name] != level:
            raise OperationError(f"{name!r} is already registered as {self._levels[name].value}")
        self._levels[name] = Level(level)

    def level(self, name: str) -> Level:
        if name not in self._levels:
            raise UnknownOperation(f"{name!r} is not a registered operation; refusing it")
        return self._levels[name]

    def run(self, name: str, action: Callable[[], T], *, token: str | None = None,
            question: str | None = None) -> T:
        """Run `action` as operation `name`, if its level allows it."""
        level = self.level(name)
        if level is Level.LOCKED:
            raise OperationLocked(f"{name!r}: only a human does this, by hand")
        if level is Level.REVIEW:
            if token is None:
                approval = self.approvals.ask(name, question or f"Allow the agent to {name}?")
                raise ApprovalRequired(name, approval.id)
            self.approvals.consume(token, name)  # raises TokenInvalid: spent, unknown or another action's
        return action()
