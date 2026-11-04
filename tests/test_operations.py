import pytest

from approval_guard.approvals import ApprovalStore, TokenInvalid
from approval_guard.operations import (ApprovalRequired, Level, OperationError, OperationLocked, OperationRegistry,
                                       UnknownOperation)


@pytest.fixture
def store(tmp_path):
    return ApprovalStore(tmp_path / "approvals.json")


@pytest.fixture
def registry(store):
    reg = OperationRegistry(store)
    reg.register("save_draft", Level.FREE)
    reg.register("publish", Level.REVIEW)
    reg.register("delete", Level.REVIEW)
    reg.register("pay", Level.LOCKED)
    return reg


def test_free_runs(registry):
    assert registry.run("save_draft", lambda: "saved") == "saved"


def test_locked_never_runs(registry):
    ran = []
    with pytest.raises(OperationLocked, match="only a human does this, by hand"):
        registry.run("pay", lambda: ran.append(1))
    assert ran == []


def test_locked_does_not_run_even_with_a_valid_token(registry, store):
    token = store.resolve(store.ask("pay", "Pay?").id, True, source="button")
    with pytest.raises(OperationLocked):
        registry.run("pay", lambda: None, token=token)


def test_review_without_token_files_an_approval_and_does_not_run(registry, store):
    ran = []
    with pytest.raises(ApprovalRequired) as waiting:
        registry.run("publish", lambda: ran.append(1))
    assert ran == []
    assert [(a.id, a.action) for a in store.pending()] == [(waiting.value.approval_id, "publish")]


def test_review_runs_with_a_button_token(registry, store):
    with pytest.raises(ApprovalRequired) as waiting:
        registry.run("publish", lambda: None)
    token = store.resolve(waiting.value.approval_id, True, source="button")
    assert registry.run("publish", lambda: "published", token=token) == "published"


def test_review_token_runs_once(registry, store):
    token = store.resolve(store.ask("publish", "Publish?").id, True, source="button")
    registry.run("publish", lambda: None, token=token)
    ran = []
    with pytest.raises(TokenInvalid):
        registry.run("publish", lambda: ran.append(1), token=token)
    assert ran == []


def test_publish_token_does_not_run_delete(registry, store):
    token = store.resolve(store.ask("publish", "Publish?").id, True, source="button")
    ran = []
    with pytest.raises(TokenInvalid):
        registry.run("delete", lambda: ran.append(1), token=token)
    assert ran == []


def test_unregistered_operation_is_refused(registry):
    with pytest.raises(UnknownOperation):
        registry.run("format_disk", lambda: None)


def test_a_level_cannot_be_quietly_lowered(registry):
    with pytest.raises(OperationError):
        registry.register("pay", Level.FREE)
    assert registry.level("pay") is Level.LOCKED
