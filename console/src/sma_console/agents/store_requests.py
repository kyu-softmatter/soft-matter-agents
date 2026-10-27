"""A request to the librarian, delivered into its inbox, and the answers read back (console card 020).

The console's third write outside `console/`, beside the signed approval and a question's item
(plan.md 7.1.1 rules 2 and 4): one `console_store_request` item, `contracts/schemas/console_store_request.schema.json`
exactly, written whole into `<tree>/librarian_agent/console_inbox/<item_id>.json`, with at most one attached
file beside it as `<item_id>--<name>`. Neither is rewritten, renamed or removed afterwards, except that a
file this call linked is taken out again when the item that names it could not be linked. The console
writes nothing else into the librarian's tree, and reads `librarian_agent/answers/` back as data.

* The asker's words are sent once, as `words`, and are kept as typed. The one field of the request that
  holds the words in the form's own sense (`WORDS_FIELD`) is set here to `words.strip()`; a request that
  already carries it is refused.
* The attached file travels inside the request as base64. It is checked before anything is written (not
  empty, at most 20 MB, not a JSON object: the store's checks would read that as a card), then linked
  into the inbox first and the item last, under the same lock card 019's items are written under.
* The file's bytes are never opened, served or read back after they are written.
* Answers are read by exact name, and one is readable only when its item is in the inbox and it matches
  that item's bytes. An answer that cannot be read is listed as such and never guessed past.
"""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from . import inbox_items
from .inbox_items import ANSWER_ID, ITEM_ID, TRIES, InboxError, ItemIdTaken
from .requests import MAX_WORDS, RequestError, check_asker
from .schema_lite import SchemaError, Schemas

ITEM_SCHEMA = "console_store_request.schema.json"
ANSWER_SCHEMA = "store_answer.schema.json"
KINDS = ("enter_document", "withdraw_value", "offer_result", "ask")
#: the field of each kind's request that holds what the asker typed
WORDS_FIELD = {"enter_document": "fact_wanted", "withdraw_value": "reason",
               "offer_result": "fact_in_words", "ask": "question"}
KIND_WORDS = {"enter_document": "Enter a document or a value", "withdraw_value": "Withdraw a value",
              "offer_result": "Offer a result", "ask": "Ask a question"}
MOST_BYTES = 20 * 1024 * 1024
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

#: the Library screen's words for an outcome (web/src/features/library/answers.tsx's OUTCOME_WORDS; a test
#: holds the two together)
OUTCOME_WORDS = {
    "entered": "Entered",
    "waiting_for_a_name": "Waiting for a name",
    "refuted": "Refuted",
    "in_conflict": "In conflict",
    "superseded": "Superseded",
    "kept": "Kept",
    "no_entry_of_that_name": "No entry of that name",
    "answered": "Answered",
    "not_in_the_store": "Not in the store",
}
NOT_ANSWERED = inbox_items.NOT_ANSWERED
UNREADABLE = inbox_items.UNREADABLE

TOO_BIG = "This file is larger than 20 MB, which the inbox does not take. Send a smaller copy, or the pages that hold the value."
LOOKS_LIKE_DATA = ("This file reads as data with named fields, which the inbox cannot carry, because the store's "
                   "checks would read it as a card. Attach it as CSV, text or PDF instead.")
EMPTY = "This file is empty."


class StoreInboxMissing(InboxError):
    code, status = "inbox_missing", 409

    def __init__(self) -> None:
        super().__init__("The librarian's inbox is not there, so nothing was sent.")


class FileRefused(InboxError):
    """The attached file cannot be carried. The message says why, in words for the asker."""

    code, status = "file_refused", 422


@dataclass(frozen=True)
class Attached:
    """The one file of a request: its plain name and its bytes, as they arrived."""

    name: str
    data: bytes


def decode_attached(name: Any, content_base64: Any) -> Attached:
    """The file as it arrived, or `RequestError` (the name or the encoding is not one) or `FileRefused`
    (the bytes are not ones the inbox carries). Nothing is written."""
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise RequestError("This file's name cannot be kept: use letters, digits, dots, dashes and underscores, "
                           "starting with a letter or a digit, at most 128 characters.")
    if not isinstance(content_base64, str):
        raise RequestError("The file did not arrive whole.")
    if len(content_base64) > MOST_BYTES * 4 // 3 + 16:
        raise FileRefused(TOO_BIG)
    try:
        data = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise RequestError("The file did not arrive whole.") from e
    if len(data) > MOST_BYTES:
        raise FileRefused(TOO_BIG)
    if len(data) == 0:
        raise FileRefused(EMPTY)
    if _holds_an_object(data):
        raise FileRefused(LOOKS_LIKE_DATA)
    return Attached(name, data)


def _holds_an_object(data: bytes) -> bool:
    """True when the bytes parse as JSON and the value is, or holds anywhere, an object. A bare number or
    string, or a list of them, is taken. Text too deeply nested to parse is refused as data."""
    try:
        value = json.loads(data)
    except RecursionError:
        return True
    except ValueError:  # includes UnicodeDecodeError: not JSON
        return False
    stack = [value]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            return True
        if isinstance(x, list):
            stack.extend(x)
    return False


def _document_holder(request: dict[str, Any]) -> dict[str, Any] | None:
    """The dict of the request where its one `document` lives, whether or not it is set: the request for
    `enter_document`, the evidence for a withdrawal whose evidence takes a file, else none."""
    kind = request.get("kind")
    if kind == "enter_document":
        return request
    if kind == "withdraw_value":
        evidence = request.get("evidence")
        if isinstance(evidence, dict) and evidence.get("kind") in ("reading", "document"):
            return evidence
    return None


def _check_request(words: str, request: Any, attached: Attached | None) -> str | None:
    """The request's name for the file it names (or None), or `RequestError`: nothing is judged but
    whether the request and the file say the same thing."""
    if not isinstance(request, dict) or request.get("kind") not in KINDS:
        raise RequestError("The request is not one of the four the librarian takes.")
    kind = request["kind"]
    if WORDS_FIELD[kind] in request:
        raise RequestError(f"The request already carries its {WORDS_FIELD[kind]}: the words are sent once, as the words.")
    holder = _document_holder(request)
    named = None if holder is None else holder.get("document")
    if holder is None:
        if attached is not None:
            raise RequestError("This kind of request takes no file.")
        return None
    if named is not None and not isinstance(named, str):
        raise RequestError("The file the request names is not a name.")
    if named is None and attached is not None:
        raise RequestError("A file came that the request does not name.")
    if named is not None and attached is None:
        raise RequestError("The request names a file, but no file came with it.")
    if named is not None and attached is not None and named != attached.name:
        raise RequestError("The request names one file and another came with it.")
    return named


def deliver(*, words: str, request: Any, attached: Attached | None, login: str, role: str, inbox: Path,
            outgoing: Path, schemas: Schemas | None) -> dict[str, Any]:
    """Write one `console_store_request` (and its attachment, if any) into `inbox` and return the item.

    Raises `RequestError` (the words, the request or the file cannot be written, or the item does not
    pass its schema), `FileRefused`, `StoreInboxMissing`, `ItemIdTaken`, or `InboxError` (the schemas
    were not found, or the disk refused). On any failure the inbox holds what it held, and `outgoing`
    holds nothing of this call."""
    console_role = check_asker(words=words, login=login, role=role)
    _check_request(words, request, attached)
    if not inbox.is_dir():
        raise StoreInboxMissing()
    if schemas is None:
        raise InboxError("the request could not be checked: the tree's schemas were not found")
    with inbox_items._LOCK:
        for _ in range(TRIES):
            now = inbox_items.utc_now().astimezone(UTC)
            iid = f"ci-{now.strftime('%Y%m%d-%H%M%S')}-{inbox_items.random_suffix()}"
            body = copy.deepcopy(request)
            body[WORDS_FIELD[body["kind"]]] = words.strip()
            file_name: str | None = None
            if attached is not None:
                file_name = f"{iid}--{attached.name}"
                holder = _document_holder(body)
                assert holder is not None
                holder["document"] = file_name
            item = {
                "artifact": "console_store_request",
                "schema_version": "0.1",
                "item_id": iid,
                "words": words,
                "asked_by": {"login": login, "console_role": console_role},
                "asked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "asker_mark": {"kind": "other_login"},
                "attachments": [] if attached is None else [
                    {"file": file_name, "sha256": hashlib.sha256(attached.data).hexdigest()}],
                "request": body,
            }
            try:
                errors = schemas.validate(item, ITEM_SCHEMA)
            except (SchemaError, OSError, ValueError) as e:
                raise InboxError(f"the request could not be checked against its schema: {e}") from e
            if errors:
                raise RequestError("The request does not pass the librarian's form, so nothing was sent: "
                                   + "; ".join(str(e) for e in errors[:3]))
            if _link(item, file_name, attached, inbox, outgoing):
                return item
        raise ItemIdTaken()


def _link(item: dict[str, Any], file_name: str | None, attached: Attached | None, inbox: Path,
          outgoing: Path) -> bool:
    """Write the file (if any) and the item whole under temporary names in `outgoing`, link the file into
    `inbox`, then the item. False when either final name exists (the caller mints another id). When the
    item cannot be linked after the file was, only the file this call linked is removed."""
    iid = item["item_id"]
    item_bytes = (json.dumps(item, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    tag = f"{os.getpid()}.{secrets.token_hex(3)}"
    tmps: list[Path] = []
    linked: Path | None = None
    try:
        outgoing.mkdir(parents=True, exist_ok=True)
        pending: list[tuple[Path, bytes, Path]] = []
        if attached is not None and file_name is not None:
            pending.append((outgoing / f".{iid}.file.{tag}.tmp", attached.data, inbox / file_name))
        pending.append((outgoing / f".{iid}.{tag}.tmp", item_bytes, inbox / f"{iid}.json"))
        for tmp, data, _ in pending:
            tmps.append(tmp)
            with open(tmp, "xb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
        for tmp, _, final in pending:
            try:
                os.link(tmp, final)  # fails when the name exists: nothing here is ever rewritten
            except FileExistsError:
                _unlink(linked)
                return False
            except OSError:
                _unlink(linked)
                raise
            if final.name != f"{iid}.json":
                linked = final
        return True
    except OSError as e:
        raise InboxError(f"the request could not be written: {e}") from e
    finally:
        for tmp in tmps:
            _unlink(tmp)


def _unlink(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink()
    except OSError:
        pass


# -- reading the requests and what became of them -------------------------------------------------------


@dataclass(frozen=True)
class Read:
    """A document read from a file, and the file."""

    doc: dict[str, Any]
    path: Path


@dataclass(frozen=True)
class Unreadable:
    """An answer on disk that cannot be read: its file, why in words, and the request it names when that
    could be told."""

    file: str
    reason: str
    item_id: str | None
    path: Path


@dataclass
class RequestView:
    item: Read
    answers: list[Read] = field(default_factory=list)
    unreadable: list[Unreadable] = field(default_factory=list)

    @property
    def state(self) -> str:
        return state_of([a.doc for a in self.answers], bool(self.unreadable))


def schemas_in(root: Path | None) -> Schemas | None:
    """The schemas of the tree rooted at `root`, or none when no tree is known."""
    return None if root is None else Schemas(root / "contracts" / "schemas")


def _parse(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8-sig"))


def read_items(folders: list[Path]) -> list[Read]:
    """Every `console_store_request` in `folders`, by exact item name, newest first by `asked_at` (`item_id`
    breaking a tie). A file that is not one (another name, another artifact, unreadable, malformed) is
    skipped. A folder named earlier keeps its item over a later one's."""
    seen: dict[str, Read] = {}
    for folder in folders:
        if not folder.is_dir():
            continue
        try:
            names = sorted(p for p in folder.iterdir() if p.suffix == ".json" and ITEM_ID.fullmatch(p.stem))
        except OSError:
            continue
        for path in names:
            if path.stem in seen or not path.is_file():
                continue
            try:
                doc = _parse(path.read_bytes())
            except (OSError, ValueError):
                continue
            if _is_request(doc, path.stem):
                seen[path.stem] = Read(doc, path)
    return sorted(seen.values(), key=lambda r: (r.doc["asked_at"], r.doc["item_id"]), reverse=True)


def _is_request(doc: Any, stem: str) -> bool:
    if not isinstance(doc, dict) or doc.get("artifact") != "console_store_request" or doc.get("item_id") != stem:
        return False
    words, at, by, req = (doc.get(k) for k in ("words", "asked_at", "asked_by", "request"))
    return (isinstance(words, str) and words != "" and len(words) <= MAX_WORDS and isinstance(at, str)
            and isinstance(by, dict) and isinstance(by.get("login"), str)
            and isinstance(req, dict) and req.get("kind") in KINDS)


def _named_in(raw: bytes, known: set[str]) -> str | None:
    """The one known item id the bytes hold, when exactly one is there."""
    text = raw.decode("latin-1")
    found = {m for m in ITEM_ID.findall(text) if m in known}
    return next(iter(found)) if len(found) == 1 else None


def read_answers(answers_folders: list[Path], inbox_folders: list[Path], schemas: Schemas | None
                 ) -> tuple[list[Read], list[Unreadable]]:
    """The librarian's answers: those readable, newest first by `answered_at` (`answer_id` breaking a tie), and
    those on disk that are not, each with why. An answer is taken by exact name `ca-<...>.json`, whose
    stem is its `answer_id`. It is readable only when it passes `store_answer.schema.json`, its item is in
    the inbox, its `request_sha256` is the sha256 of that item file's bytes, and, when it follows another,
    that one is there and answers the same item. A missing folder holds no answers."""
    files: dict[str, Path] = {}
    for folder in answers_folders:
        if not folder.is_dir():
            continue
        try:
            for p in sorted(folder.iterdir()):
                if p.suffix == ".json" and ANSWER_ID.fullmatch(p.stem) and p.is_file():
                    files.setdefault(p.stem, p)
        except OSError:
            continue
    inbox: dict[str, Path] = {}
    for folder in inbox_folders:
        if folder.is_dir():
            for p in sorted(folder.glob("ci-*.json")):
                if ITEM_ID.fullmatch(p.stem) and p.is_file():
                    inbox.setdefault(p.stem, p)
    known = {r.doc["item_id"] for r in read_items(inbox_folders)}
    docs: dict[str, dict[str, Any] | None] = {}
    raws: dict[str, bytes] = {}
    for stem, path in files.items():
        try:
            raws[stem] = path.read_bytes()
        except OSError:
            raws[stem] = b""
            docs[stem] = None
            continue
        try:
            doc = _parse(raws[stem])
            docs[stem] = doc if isinstance(doc, dict) else None
        except ValueError:
            docs[stem] = None
    readable: list[Read] = []
    unreadable: list[Unreadable] = []
    for stem, path in files.items():
        doc, raw = docs[stem], raws[stem]
        item_id = doc.get("item_id") if doc is not None and isinstance(doc.get("item_id"), str) else None
        if item_id is None or not ITEM_ID.fullmatch(item_id):
            item_id = _named_in(raw, known)
        why = _why_unreadable(stem, doc, files, docs, inbox, schemas)
        if why is None:
            assert doc is not None
            readable.append(Read(doc, path))
        else:
            unreadable.append(Unreadable(path.name, why, item_id if item_id in known else None, path))
    readable.sort(key=lambda r: (str(r.doc.get("answered_at", "")), str(r.doc.get("answer_id", ""))), reverse=True)
    unreadable.sort(key=lambda u: u.file, reverse=True)
    return readable, unreadable


def _why_unreadable(stem: str, doc: dict[str, Any] | None, files: dict[str, Path],
                    docs: dict[str, dict[str, Any] | None], inbox: dict[str, Path],
                    schemas: Schemas | None) -> str | None:
    if doc is None:
        return "it is not text the console can read as an answer"
    if schemas is None:
        return "the console could not find the form an answer takes, so it cannot check it"
    try:
        errors = schemas.validate(doc, ANSWER_SCHEMA)
    except (SchemaError, OSError, ValueError):
        return "the console could not check it against the form an answer takes"
    if errors:
        return "it does not follow the form an answer takes"
    if doc["answer_id"] != stem:
        return "its name and its answer id differ"
    item = inbox.get(doc["item_id"])
    if item is None:
        return "it names a request that is not in the inbox"
    try:
        item_bytes = item.read_bytes()
        shown = _parse(item_bytes)
    except (OSError, ValueError):
        return "it names a request that is not in the inbox"
    if not _is_request(shown, item.stem):
        return "it names a request that is not in the inbox"
    if hashlib.sha256(item_bytes).hexdigest() != doc["request_sha256"]:
        return "it does not match the request it names"
    follows = doc.get("follows")
    if follows is not None:
        earlier = str(follows).rsplit("/", 1)[-1][: -len(".json")]
        before = docs.get(earlier)
        if earlier not in files:
            return "it follows an answer that is not there"
        if before is None or before.get("item_id") != doc["item_id"]:
            return "it follows an answer that does not name the same request"
    return None


def view_requests(items: list[Read], readable: list[Read], unreadable: list[Unreadable]
                  ) -> tuple[list[RequestView], list[Unreadable]]:
    """Each request with the answers that name it (newest first) and the unreadable ones that name it, and
    the unreadable answers that name no request in the inbox."""
    views = {r.doc["item_id"]: RequestView(r) for r in items}
    for a in readable:
        views[a.doc["item_id"]].answers.append(a)
    orphans: list[Unreadable] = []
    for u in unreadable:
        if u.item_id in views:
            views[u.item_id].unreadable.append(u)
        else:
            orphans.append(u)
    return [views[r.doc["item_id"]] for r in items], orphans


def state_of(answers: list[dict[str, Any]], unreadable: bool) -> str:
    """One state for a request: an answer that cannot be read beats everything; no answer is "delivered ·
    not answered yet"; else the latest answer's outcome, a waiting one with the name it waits for."""
    if unreadable:
        return UNREADABLE
    if not answers:
        return NOT_ANSWERED
    latest = answers[0]
    outcome = str(latest.get("outcome", ""))
    if outcome == "waiting_for_a_name":
        return f"waiting for a name · {latest.get('quantity_name', '')}"
    return OUTCOME_WORDS.get(outcome, outcome)

