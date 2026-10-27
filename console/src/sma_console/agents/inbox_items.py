"""A question to the microscope or the simulation, delivered into that agent's inbox (console card 019).

The console's second write outside `console/`, beside the signed approval (plan.md 7.1.1 rule 2): one
`console_question` item, `contracts/schemas/console_inbox_item.schema.json` exactly, written whole into
`<tree>/<agent>_agent/console_inbox/<item_id>.json` and never rewritten, renamed or removed. A
correction is a new item. The console reads the agent's `answers/` back as data to say what became of
an item, and writes nothing there.

* `item_id` is `ci-<UTC yyyymmdd>-<UTC hhmmss>-<four lowercase letters or digits>`.
* `question_id` is `mic-` or `sim-`, the UTC date of `asked_at`, `-c` and three digits: the next
  number after the highest that date already carries in that agent's inbox, from `c001`. The two
  agents count apart. After `c999` nothing is written (`InboxFull`).
* The inbox folder is the agent's. It must already be there; the console never makes it
  (`InboxMissing`). Under the mock store the mock makes it, inside its own write dir.
* The file is written complete under a temporary name in the console's own `requests/outgoing/` (the
  same tree, so a link works), then **linked** to its final name and the temporary name removed. A
  link to a name that exists fails, and another `item_id` is minted, up to five tries. Nothing is
  ever written into an inbox under a temporary name: the checker fails any file there that is not an
  item, an attachment or `.gitkeep`.
* The item is checked against the tree's own schema before it is written; one that fails is refused
  and nothing is written.
* **One console server runs against a tree.** Reading the inbox, minting the `question_id` and
  linking the file happen under one lock in this process; two servers would not see each other's
  lock, and the checker would catch the repeat as a duplicate question id.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .requests import MAX_WORDS, check_asker, random_suffix, utc_now
from .schema_lite import SchemaError, Schemas
from .store import StoreError

#: the agents that have an inbox, and the prefix of each one's question ids
INBOX_AGENTS = {"microscope": "mic", "simulation": "sim"}
ITEM_ID = re.compile(r"ci-[0-9]{8}-[0-9]{6}-[a-z0-9]{4}")
ANSWER_ID = re.compile(r"ca-[0-9]{8}-[0-9]{6}-[a-z0-9]{4}")
ITEM_SCHEMA = "console_inbox_item.schema.json"
ANSWER_SCHEMA = "console_answer.schema.json"
MOST_PER_DAY = 999
TRIES = 5

NOT_ANSWERED = "delivered · not answered yet"
UNREADABLE = "an answer is on disk and cannot be read"

#: scanning, numbering and linking happen under this one lock (see the module docstring)
_LOCK = threading.Lock()


class InboxError(StoreError):
    """An item could not be delivered. `code` and the message are what the person is told."""

    code = "store_error"
    status = 500


class InboxMissing(InboxError):
    code, status = "inbox_missing", 409

    def __init__(self) -> None:
        super().__init__("This agent's inbox is not there, so nothing was sent.")


class InboxFull(InboxError):
    code, status = "inbox_full", 409

    def __init__(self) -> None:
        super().__init__("This agent has had 999 questions from the console today, which is the most a "
                         "day can hold. Ask again after midnight UTC.")


class ItemIdTaken(InboxError):
    code, status = "item_exists", 409

    def __init__(self) -> None:
        super().__init__("An item with that id exists already. Try again.")


def question_id_for(agent: str, when: datetime, number: int) -> str:
    return f"{INBOX_AGENTS[agent]}-{when.strftime('%Y%m%d')}-c{number:03d}"


def build_item(*, agent: str, words: str, login: str, role: str, now: datetime, suffix: str,
               number: int) -> dict[str, Any]:
    """The item as the schema has it, or `RequestError`. `words` is kept exactly as typed."""
    console_role = check_asker(words=words, login=login, role=role)
    return {
        "artifact": "console_question",
        "schema_version": "0.1",
        "item_id": f"ci-{now.strftime('%Y%m%d-%H%M%S')}-{suffix}",
        "question_id": question_id_for(agent, now, number),
        "words": words,
        "asked_by": {"login": login, "console_role": console_role},
        "asked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asker_mark": {"kind": "other_login"},
        "attachments": [],
    }


def _highest_number(inbox: Path, agent: str, when: datetime) -> int:
    """The highest `cNNN` the agent's inbox carries for `when`'s UTC date. A file is read for its
    `question_id`; one that cannot be read is searched for the text of one, so a damaged item still
    holds its number."""
    prefix, day = INBOX_AGENTS[agent], when.strftime("%Y%m%d")
    wanted = re.compile(rf"{prefix}-{day}-c([0-9]{{3}})")
    best = 0
    try:
        names = [p for p in inbox.iterdir() if p.is_file() and p.suffix == ".json"]
    except OSError as e:
        raise InboxError(f"the inbox could not be read: {e}") from e
    for path in names:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, ValueError):
            continue
        found: list[str] = []
        try:
            doc = json.loads(text)
            qid = doc.get("question_id") if isinstance(doc, dict) else None
            found = [qid] if isinstance(qid, str) else []
        except ValueError:
            found = [m.group(0) for m in wanted.finditer(text)]
        for qid in found:
            m = wanted.fullmatch(qid)
            if m:
                best = max(best, int(m.group(1)))
    return best


def deliver(*, agent: str, words: str, login: str, role: str, inbox: Path, outgoing: Path,
            schemas: Schemas | None) -> dict[str, Any]:
    """Write one `console_question` into `inbox` and return it. Raises `RequestError` (the words or
    login cannot be written), `InboxMissing`, `InboxFull`, `ItemIdTaken`, or `InboxError`/`StoreError`
    (the schema cannot be found, the item fails it, or the disk refuses). On any failure the inbox
    holds what it held and `outgoing` holds nothing of this item."""
    if agent not in INBOX_AGENTS:
        raise InboxError(f"{agent!r} has no inbox the console writes into")
    if not inbox.is_dir():
        raise InboxMissing()
    with _LOCK:
        for _ in range(TRIES):
            now = utc_now().astimezone(UTC)
            number = _highest_number(inbox, agent, now) + 1
            if number > MOST_PER_DAY:
                raise InboxFull()
            item = build_item(agent=agent, words=words, login=login, role=role, now=now,
                              suffix=random_suffix(), number=number)
            if schemas is None:
                raise InboxError("the item could not be checked: the tree's schemas were not found")
            try:
                errors = schemas.validate(item, ITEM_SCHEMA)
            except (SchemaError, OSError, ValueError) as e:
                raise InboxError(f"the item could not be checked against its schema: {e}") from e
            if errors:
                raise InboxError("the item does not pass its schema, so nothing was written: "
                                 + "; ".join(str(e) for e in errors[:3]))
            if _link(item, inbox, outgoing):
                return item
        raise ItemIdTaken()


def _link(item: dict[str, Any], inbox: Path, outgoing: Path) -> bool:
    """Write `item` whole under a temporary name in `outgoing`, link it into `inbox`, remove the
    temporary name. False when the final name exists (the caller mints another id)."""
    iid = item["item_id"]
    data = (json.dumps(item, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    tmp = outgoing / f".{iid}.{os.getpid()}.{secrets.token_hex(3)}.tmp"
    try:
        outgoing.mkdir(parents=True, exist_ok=True)
        with open(tmp, "xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp, inbox / f"{iid}.json")  # fails when the name exists: an item is never rewritten
        except FileExistsError:
            return False
        return True
    except OSError as e:
        raise InboxError(f"the item could not be written: {e}") from e
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


# -- reading items and what became of them -------------------------------------------------------


def read_items(inbox: Path, agent: str) -> list[dict[str, Any]]:
    """Every item in `inbox`. A file that is not an item (another artifact, unreadable, a name that is
    not its id, a question id of the other agent) is skipped, never shown."""
    if not inbox.is_dir():
        return []
    prefix = INBOX_AGENTS[agent]
    out: list[dict[str, Any]] = []
    for path in sorted(inbox.glob("ci-*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or doc.get("artifact") != "console_question":
            continue
        iid, qid, words, at, by = (doc.get(k) for k in ("item_id", "question_id", "words", "asked_at", "asked_by"))
        if not (isinstance(iid, str) and ITEM_ID.fullmatch(iid) and path.stem == iid
                and isinstance(qid, str) and re.fullmatch(rf"{prefix}-[0-9]{{8}}-c[0-9]{{3}}", qid)
                and isinstance(words, str) and words != "" and len(words) <= MAX_WORDS
                and isinstance(at, str) and isinstance(by, dict) and isinstance(by.get("login"), str)):
            continue
        out.append(doc)
    return out


def items_newest_first(found: Iterable[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
    """(agent, item) pairs, newest first by `asked_at`, `item_id` breaking a tie. The file name plays
    no part in the order."""
    return sorted(found, key=lambda p: (p[1]["asked_at"], p[1]["item_id"]), reverse=True)


def _read_answers(folders: Iterable[Path], item: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    """The answers on disk that name `item`, and whether any file that names it cannot be read.
    A file that cannot be parsed is attributed to the item only when its text holds the item's id."""
    iid = item["item_id"]
    named: list[dict[str, Any]] = []
    bad = False
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            try:
                text = path.read_text(encoding="utf-8-sig")
            except (OSError, ValueError):
                continue
            try:
                doc = json.loads(text)
            except ValueError:
                bad = bad or iid in text
                continue
            if isinstance(doc, dict) and doc.get("item_id") == iid:
                named.append(doc)
    return named, bad


def state_of(item: dict[str, Any], answers_folders: Iterable[Path], schemas: Schemas | None) -> str:
    """Exactly one of four states for `item`, from the `console_answer` files that name it:
    delivered and not answered; taken up as <question_id>; refused with the reason as written; or
    an answer is on disk and cannot be read. The card does not guess past an answer it cannot read."""
    named, bad = _read_answers(answers_folders, item)
    if bad:
        return UNREADABLE
    if not named:
        return NOT_ANSWERED
    if schemas is None:
        return UNREADABLE
    for doc in named:
        try:
            errors = schemas.validate(doc, ANSWER_SCHEMA)
        except (SchemaError, OSError, ValueError):
            return UNREADABLE
        if errors or doc.get("question_id") != item["question_id"]:
            return UNREADABLE
    latest = max(named, key=lambda d: (d["answered_at"], d["answer_id"]))
    if latest["outcome"] == "taken_up":
        return f"taken up as {item['question_id']}"
    return f"refused · {latest['reason']}"
