import json

import pytest

from approval_guard.approvals import (APPROVED, DENIED, PENDING, ApprovalRefused, ApprovalStore, TokenInvalid,
                                      UnknownApproval)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "approvals.json"


def test_ask_creates_a_pending_approval_on_disk(path):
    store = ApprovalStore(path)
    approval = store.ask("publish", "Publish draft 42?")
    assert approval.status == PENDING
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert [r["id"] for r in rows] == [approval.id]


def test_pending_approval_survives_a_restart(path):
    approval = ApprovalStore(path).ask("publish", "Publish draft 42?")
    restarted = ApprovalStore(path)  # a new object on the same file: the process restarted
    assert [a.id for a in restarted.pending()] == [approval.id]
    assert restarted.resolve(approval.id, True, source="button") is not None


@pytest.mark.parametrize("source", ["api", "model", "", "Button"])
def test_only_the_button_can_accept(path, source):
    store = ApprovalStore(path)
    approval = store.ask("publish", "Publish?")
    with pytest.raises(ApprovalRefused):
        store.resolve(approval.id, True, source=source)
    assert store.get(approval.id).status == PENDING


def test_the_model_cannot_even_deny(path):
    store = ApprovalStore(path)
    approval = store.ask("publish", "Publish?")
    with pytest.raises(ApprovalRefused):
        store.resolve(approval.id, False, source="model")
    assert store.get(approval.id).status == PENDING


def test_button_accept_returns_a_token_that_is_not_stored_in_clear(path):
    store = ApprovalStore(path)
    approval = store.ask("publish", "Publish?")
    token = store.resolve(approval.id, True, source="button")
    assert token and len(token) >= 32
    assert store.get(approval.id).status == APPROVED
    assert token not in path.read_text(encoding="utf-8")


def test_button_deny_returns_no_token(path):
    store = ApprovalStore(path)
    approval = store.ask("publish", "Publish?")
    assert store.resolve(approval.id, False, source="button") is None
    assert store.get(approval.id).status == DENIED


def test_an_approval_is_answered_once(path):
    store = ApprovalStore(path)
    approval = store.ask("publish", "Publish?")
    store.resolve(approval.id, True, source="button")
    with pytest.raises(UnknownApproval):
        store.resolve(approval.id, True, source="button")


def test_unknown_approval_is_refused(path):
    with pytest.raises(UnknownApproval):
        ApprovalStore(path).resolve("nope", True, source="button")


def test_token_works_once(path):
    store = ApprovalStore(path)
    approval = store.ask("publish", "Publish?")
    token = store.resolve(approval.id, True, source="button")
    store.consume(token, "publish")
    with pytest.raises(TokenInvalid):
        store.consume(token, "publish")


def test_spent_token_stays_spent_after_a_restart(path):
    store = ApprovalStore(path)
    token = store.resolve(store.ask("publish", "Publish?").id, True, source="button")
    store.consume(token, "publish")
    with pytest.raises(TokenInvalid):
        ApprovalStore(path).consume(token, "publish")


def test_publish_token_does_not_unlock_delete(path):
    store = ApprovalStore(path)
    token = store.resolve(store.ask("publish", "Publish?").id, True, source="button")
    with pytest.raises(TokenInvalid):
        store.consume(token, "delete")
    store.consume(token, "publish")  # a wrong try does not spend it for its own action


@pytest.mark.parametrize("token", ["", "made-up-token", None])
def test_unknown_tokens_are_refused(path, token):
    store = ApprovalStore(path)
    store.ask("publish", "Publish?")
    with pytest.raises(TokenInvalid):
        store.consume(token, "publish")
