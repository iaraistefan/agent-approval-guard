"""Layer 1: classify a browser action an AI agent proposes, before it reaches the page.

The agent says "I want to click the button that says X on page Y". This module
answers with one of three verdicts:

    ALLOW           reading, scrolling, ordinary clicks
    NEEDS_APPROVAL  the click makes something public or sends it out (publish, submit, send)
    FORBIDDEN       the click destroys something or touches money (delete, unpublish,
                    archive, payments, bank details); no approval opens these

Rules are checked from the most dangerous down, so "Delete and publish" is FORBIDDEN,
not NEEDS_APPROVAL. Text is folded first (lower case, no accents), so "Șterge",
"DELETE" and "delete" are read the same way. An action the guard cannot identify
(an empty button, a broken URL) is refused: when in doubt, the agent does not click.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    FORBIDDEN = "FORBIDDEN"


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    #: The action family the verdict is about ("publish", "delete", "payment", ...).
    #: An approval token is bound to exactly one of these.
    action: str
    reason: str


#: Actions that never reach a control on the page.
READ_KINDS = ("read", "scroll", "wait", "screenshot")
#: Actions that do something to the page.
WRITE_KINDS = ("click", "type", "select", "upload")

#: Words on a control that destroy something. Order matters only for the reported action.
FORBIDDEN_WORDS: dict[str, re.Pattern[str]] = {
    "delete": re.compile(r"\bdelete|\bsterge"),
    "unpublish": re.compile(r"\bunpublish|\bdepublica"),
    "archive": re.compile(r"\barchive|\barhiveaza"),
    "payment": re.compile(r"\bpay\b|\bpayment|\bpayout|\bcheckout|\bbuy now|\bpurchase|\bbilling|\bcredit card"),
    "bank": re.compile(r"\bbank|\biban\b|\bswift\b|\brouting number|\baccount number"),
}
#: URL paths where nothing is a draft: money and bank details. Every write there is refused.
FORBIDDEN_PATHS = re.compile(r"/(payments?|payouts?|bank|billing|checkout|cart|wallet)(/|$)")
#: Words on a control that make something public or send it to someone.
APPROVAL_WORDS: dict[str, re.Pattern[str]] = {
    "publish": re.compile(r"\bpublish|\bpublica"),
    "submit": re.compile(r"\bsubmit|\btrimite"),
    "send": re.compile(r"\bsend\b"),
}


def fold(text: str) -> str:
    """Lower case without accents, whitespace collapsed: "Șterge  Titlul" -> "sterge titlul"."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    plain = "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
    return " ".join(plain.split())


def _path(url: str) -> str | None:
    """The URL's path in lower case, or None when the URL cannot be parsed or has no host."""
    try:
        parsed = urlparse(url or "")
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return (parsed.path or "/").lower()


def classify(text: str, url: str, kind: str = "click") -> Decision:
    """The verdict for one proposed action: `kind` of action, on the control that says `text`,
    on the page at `url`."""
    path = _path(url)
    if path is None:
        return Decision(Verdict.FORBIDDEN, "unknown", f"cannot read the page address {url!r}; not touching it")
    forbidden_page = bool(FORBIDDEN_PATHS.search(path))

    if kind in READ_KINDS:
        return Decision(Verdict.ALLOW, "read", "reading changes nothing")
    if kind == "navigate":
        if forbidden_page:
            return Decision(Verdict.FORBIDDEN, "payment", "payment and bank pages are opened by a human only")
        return Decision(Verdict.ALLOW, "navigate", "opening a page changes nothing")
    if kind not in WRITE_KINDS:
        return Decision(Verdict.FORBIDDEN, "unknown", f"unknown action kind {kind!r}; not doing it")

    words = fold(text)
    if not words:
        return Decision(Verdict.FORBIDDEN, "unknown", "the control has no words; cannot tell what it does")
    if forbidden_page:
        return Decision(Verdict.FORBIDDEN, "payment", "nothing is clicked or typed on payment and bank pages")
    for action, pattern in FORBIDDEN_WORDS.items():
        if pattern.search(words):
            return Decision(Verdict.FORBIDDEN, action, f"{text!r} is a {action} action; only a human does it")
    for action, pattern in APPROVAL_WORDS.items():
        if pattern.search(words):
            return Decision(Verdict.NEEDS_APPROVAL, action, f"{text!r} is a {action} action; it needs approval")
    return Decision(Verdict.ALLOW, "click", "an ordinary control")
