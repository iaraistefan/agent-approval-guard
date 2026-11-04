# agent-approval-guard

Code-level guards that stop an AI agent from publishing, deleting or paying without a human's approval.

Extracted and simplified from Fabrica, my private AI agent, where the same rules guard Amazon KDP publishing.

## The problem

An agent that drives a browser can click anything a human can: **Publish**, **Delete**, **Pay now**.
Telling the model "always ask first" in a prompt is not a guarantee. Prompts get ignored,
misread, or overridden by text on the page itself. If a mistake is irreversible (a book goes
live, a title is deleted, money leaves the account), the check has to live in code that the model
cannot talk its way past.

## Three layers

```
 agent proposes an action
          |
          v
 1. rules.py        classify(text, url, kind)  ->  ALLOW | NEEDS_APPROVAL | FORBIDDEN
          |
          v
 2. operations.py   registry.run(name, fn, token)   FREE runs, REVIEW needs a token, LOCKED never runs
          |
          v
 3. approvals.py    ask() -> pending (on disk) -> human presses the button -> one-time token
```

1. **Rules** (`approval_guard/rules.py`) read the proposed browser action: the words on the control
   and the page URL. Delete, unpublish, archive, payments and bank details are `FORBIDDEN`, and so is
   any write on a payment or bank page. Publish, submit and send are `NEEDS_APPROVAL`. The most
   dangerous rule wins ("Delete and publish" is forbidden), text is folded (case and accents do not
   matter), and anything the guard cannot identify (no words, bad URL, unknown kind) is refused.
2. **Operations** (`approval_guard/operations.py`) give every side effect a level. `FREE` runs.
   `REVIEW` runs only with an approval token for that exact operation; without one it files a pending
   approval and raises `ApprovalRequired`. `LOCKED` raises `OperationLocked`: *only a human does this,
   by hand*. An operation nobody registered is refused.
3. **Approvals** (`approval_guard/approvals.py`) are written to a JSON file before anything waits, so
   a restart does not lose them. Only `source="button"` can answer: an answer from the API or from
   the model is refused, even a "no". An accepted approval yields a **one-time token** bound to one
   action: it works once (also across restarts), a `publish` token never unlocks `delete`, and only
   its SHA-256 hash is stored.

## Demo

```
$ python examples/demo.py
DONE      read
WAITING   click 'Publish': approval 8215d36dbaa3 is pending
REFUSED   click 'Delete title': 'Delete title' is a delete action; only a human does it
REFUSED   the model approving its own publish: approvals are given only by a human, with the button (not from 'model')
APPROVED  the human pressed the button; a one-time publish token was issued
DONE      click 'Publish'
```

## Usage

```python
from approval_guard import ApprovalStore, ApprovalRequired, Level, OperationRegistry, Verdict, classify

store = ApprovalStore("state/approvals.json")
ops = OperationRegistry(store)
ops.register("publish", Level.REVIEW)
ops.register("delete", Level.LOCKED)

decision = classify("Publish", "https://publisher.example.com/books/42")
if decision.verdict is Verdict.FORBIDDEN:
    raise SystemExit(decision.reason)
try:
    ops.run(decision.action, do_the_click)            # no token yet
except ApprovalRequired as waiting:
    notify_human(waiting.approval_id)                 # your Telegram / Slack / UI button

# later, in the button's handler (and only there):
token = store.resolve(waiting.approval_id, True, source="button")
ops.run("publish", do_the_click, token=token)         # runs once
```

## Running the tests

Python 3.11+ and pytest, nothing else.

```
python -m pip install pytest
python -m pytest -q
```

CI runs the suite and the demo on Python 3.11, 3.12 and 3.13 on every push.

## License

MIT, see [LICENSE](LICENSE).
