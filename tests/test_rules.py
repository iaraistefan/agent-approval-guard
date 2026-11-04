import pytest

from approval_guard.rules import Verdict, classify, fold

PAGE = "https://publisher.example.com/books/draft-42"


@pytest.mark.parametrize("text", ["Delete", "Delete title", "DELETE", "Șterge cartea"])
def test_delete_is_forbidden(text):
    decision = classify(text, PAGE)
    assert decision.verdict is Verdict.FORBIDDEN
    assert decision.action == "delete"


@pytest.mark.parametrize("text", ["Unpublish", "Unpublish this book"])
def test_unpublish_is_forbidden_not_a_publish(text):
    decision = classify(text, PAGE)
    assert decision.verdict is Verdict.FORBIDDEN
    assert decision.action == "unpublish"


def test_archive_is_forbidden():
    assert classify("Archive title", PAGE).verdict is Verdict.FORBIDDEN


@pytest.mark.parametrize("text", ["Pay now", "Add payment method", "Buy now", "Checkout", "Update billing"])
def test_payments_are_forbidden(text):
    assert classify(text, PAGE).verdict is Verdict.FORBIDDEN


@pytest.mark.parametrize("text", ["Add bank account", "IBAN", "Routing number"])
def test_bank_details_are_forbidden(text):
    assert classify(text, PAGE).verdict is Verdict.FORBIDDEN


@pytest.mark.parametrize("url", ["https://publisher.example.com/payments",
                                 "https://publisher.example.com/account/bank/edit",
                                 "https://publisher.example.com/checkout/"])
def test_every_write_on_a_money_page_is_forbidden(url):
    assert classify("Save", url).verdict is Verdict.FORBIDDEN
    assert classify("Save", url, kind="type").verdict is Verdict.FORBIDDEN


def test_navigating_to_a_money_page_is_forbidden():
    assert classify("", "https://publisher.example.com/billing", kind="navigate").verdict is Verdict.FORBIDDEN


@pytest.mark.parametrize("text,action", [("Publish", "publish"), ("Publish your book", "publish"),
                                         ("Submit for review", "submit"), ("Send", "send"),
                                         ("Send message", "send")])
def test_publish_submit_send_need_approval(text, action):
    decision = classify(text, PAGE)
    assert decision.verdict is Verdict.NEEDS_APPROVAL
    assert decision.action == action


def test_forbidden_wins_over_approval():
    assert classify("Delete and publish", PAGE).verdict is Verdict.FORBIDDEN


@pytest.mark.parametrize("text", ["Save as draft", "Next", "Preview", "Edit description"])
def test_ordinary_clicks_are_allowed(text):
    assert classify(text, PAGE).verdict is Verdict.ALLOW


@pytest.mark.parametrize("kind", ["read", "scroll", "wait", "screenshot"])
def test_reading_is_allowed(kind):
    assert classify("", PAGE, kind=kind).verdict is Verdict.ALLOW


def test_word_boundaries_avoid_false_matches():
    assert classify("Sender details", PAGE).verdict is Verdict.ALLOW
    assert classify("Display settings", PAGE).verdict is Verdict.ALLOW


@pytest.mark.parametrize("text,url,kind", [("", PAGE, "click"),
                                           ("Save", "not a url", "click"),
                                           ("Save", "javascript:alert(1)", "click"),
                                           ("Save", PAGE, "drag")])
def test_what_cannot_be_identified_is_refused(text, url, kind):
    assert classify(text, url, kind).verdict is Verdict.FORBIDDEN


def test_fold_removes_case_accents_and_extra_spaces():
    assert fold("  Șterge   TITLUL ") == "sterge titlul"
