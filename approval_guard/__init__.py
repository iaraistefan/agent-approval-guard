"""Approval guards for AI agents: classify, gate, and approve by hand."""
from approval_guard.approvals import (ApprovalError, ApprovalRefused, ApprovalStore, TokenInvalid,
                                      UnknownApproval)
from approval_guard.operations import (ApprovalRequired, Level, OperationLocked, OperationRegistry,
                                       UnknownOperation)
from approval_guard.rules import Decision, Verdict, classify

__all__ = [
    "ApprovalError", "ApprovalRefused", "ApprovalRequired", "ApprovalStore", "Decision", "Level",
    "OperationLocked", "OperationRegistry", "TokenInvalid", "UnknownApproval", "UnknownOperation",
    "Verdict", "classify",
]
