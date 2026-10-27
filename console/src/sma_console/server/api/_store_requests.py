"""What the Library's routes and the Questions screen's routes share about the librarian's inbox (console card 020).

Underscore-prefixed, so the router discovery skips it: it holds models and helpers, no route. The delivery
itself is `agents/store_requests.py`; this is the part that speaks HTTP -- who may ask, how a failure is said, the
audit line (the item id, the kind and whether a file came, never the words and never the file's name) and the
shapes that go out.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ...agents import MockStore, StoreError
from ...agents import requests as question_requests
from ...agents import store_requests
from ...agents.inbox_items import InboxError
from ...agents.schema_lite import Schemas
from ...agents.sma_files import RootNotFoundError, repository_root
from ...auth import AuditKind
from . import Refusal, server_action_why

READ_ONLY_MESSAGE = "Submitting to soft-matter-agents is not connected yet (read-only)"
READ_ONLY = Refusal(409, "read_only_store", READ_ONLY_MESSAGE)
REMOTE_ASK = ("Questions can be asked from the microscope computer only. This browser is "
              "viewing from another computer.")
VIEWER_ASK = "This login can only look: it cannot ask a question. An administrator can give it more."
NO_REQUESTS = "No requests yet."


def ask_refusal(me: Any) -> Refusal | None:
    """`server_action_why` for asking, with the refusal said in words for the person."""
    why = server_action_why(me, "submit_question")
    if why is None:
        return None
    if why.code == "remote_view":
        return Refusal(403, "remote_view", REMOTE_ASK)
    if why.code == "role":
        return Refusal(403, "role", VIEWER_ASK)
    return why


def schemas_of(store: Any) -> Schemas:
    """The tree's own schemas, found as the instrument routes find them."""
    root = store.runtime_root() if hasattr(store, "runtime_root") else None
    if root is None:
        try:
            root = repository_root()
        except RootNotFoundError:
            root = None
    return Schemas(root / "contracts" / "schemas" if root is not None else "contracts/schemas")


def has_inbox(store: Any) -> bool:
    return all(hasattr(store, n) for n in ("inbox_write_folder", "inbox_folders", "answers_folders",
                                           "outgoing_folder"))


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


# -- the answers, as the Library and the Questions screen show one --------------------------------------


class NumberOut(_Out):
    name: str
    value: float | int | str
    unit: str
    entry_id: str
    grade: str
    source: str
    covers_conditions: str


class GapOut(_Out):
    asked_for: str
    looked_in: str


class AnswerOut(_Out):
    answer_id: str
    item_id: str
    answered_by: str
    answered_at: str
    outcome: str
    reason: str
    kb_version: str | None
    answer: str | None
    entries_cited: list[str]
    numbers: list[NumberOut]
    gaps: list[GapOut]
    entries_marked: list[str]
    other_side: list[str]
    quantity_name: str | None
    entries_made: list[str]
    example: bool


def _str_list(x: Any) -> list[str]:
    return [s for s in x if isinstance(s, str)] if isinstance(x, list) else []


def answer_out(doc: dict[str, Any], example: bool) -> AnswerOut:
    numbers = [NumberOut(**{k: n.get(k) for k in NumberOut.model_fields})
               for n in doc.get("numbers", []) if isinstance(n, dict)]
    gaps = [GapOut(asked_for=str(g.get("asked_for", "")), looked_in=str(g.get("looked_in", "")))
            for g in doc.get("gaps", []) if isinstance(g, dict)]
    return AnswerOut(
        answer_id=str(doc.get("answer_id", "")), item_id=str(doc.get("item_id", "")),
        answered_by=str(doc.get("answered_by", "")), answered_at=str(doc.get("answered_at", "")),
        outcome=str(doc.get("outcome", "")), reason=str(doc.get("reason", "")),
        kb_version=doc.get("kb_version") if isinstance(doc.get("kb_version"), str) else None,
        answer=doc.get("answer") if isinstance(doc.get("answer"), str) else None,
        entries_cited=_str_list(doc.get("entries_cited")), numbers=numbers, gaps=gaps,
        entries_marked=_str_list(doc.get("entries_marked")), other_side=_str_list(doc.get("other_side")),
        quantity_name=doc.get("quantity_name") if isinstance(doc.get("quantity_name"), str) else None,
        entries_made=_str_list(doc.get("entries_made")), example=example)


# -- the item that was written ---------------------------------------------------------------------------


class AttachmentOut(_Out):
    file: str
    sha256: str


class StoreRequestOut(_Out):
    """`contracts/schemas/console_store_request.schema.json`, exactly: the item that was written."""

    artifact: Literal["console_store_request"]
    schema_version: Literal["0.1"]
    item_id: str
    words: str
    asked_by: dict[str, Any]
    asked_at: str
    asker_mark: dict[str, Any]
    attachments: list[AttachmentOut]
    request: dict[str, Any]


class FileIn(_Out):
    """The one file of a request, inside the JSON body."""

    name: str
    content_base64: str


def deliver_store_request(store: Any, me: Any, seat: Any, *, words: str, request: Any,
                          file: FileIn | None) -> StoreRequestOut:
    """Check who may ask, then write the request (and its file) into the librarian's inbox. Every failure is
    a refusal with a code and words for the asker, and nothing is written."""
    if why := ask_refusal(me):
        raise why.http()
    if not getattr(store, "writable", False) or not has_inbox(store):
        raise READ_ONLY.http()
    try:
        attached = None if file is None else store_requests.decode_attached(file.name, file.content_base64)
        item = store_requests.deliver(
            words=words, request=request, attached=attached, login=me.info.user_id, role=str(me.info.role),
            inbox=store.inbox_write_folder("librarian"), outgoing=store.outgoing_folder(),
            schemas=schemas_of(store))
    except question_requests.RequestError as e:
        raise Refusal(422, "invalid", str(e)).http() from e
    except InboxError as e:
        raise Refusal(e.status, e.code, str(e)).http() from e
    except StoreError as e:
        raise Refusal(500, "store_error", str(e)).http() from e
    if seat.audit is not None:  # the item, the kind and whether a file came: never the words, never the name
        seat.audit.append(AuditKind.QUESTION_SUBMITTED, me.user_id, origin="console", target="librarian",
                          item_id=item["item_id"], request_kind=item["request"]["kind"],
                          attached=bool(item["attachments"]))
    return StoreRequestOut.model_validate(item)


# -- the requests as the Library lists them --------------------------------------------------------------


class UnreadableOut(_Out):
    file: str
    reason: str


class RequestViewOut(_Out):
    item_id: str
    kind: str
    kind_words: str
    words: str
    login: str
    asked_at: str
    file: str | None
    example: bool
    state: str
    answers: list[AnswerOut]
    unreadable: list[UnreadableOut]


def _under_sample(store: Any, path: Path) -> bool:
    """True for a file of the mock's shipped sample (an example), false for one the practice wrote."""
    return isinstance(store, MockStore) and store.library_root() in path.parents


def request_views(store: Any) -> tuple[list[RequestViewOut], list[UnreadableOut]]:
    """Every request in the librarian's inbox, newest first, each with the answers that name it, and the
    answers on disk that name no request. Reads only."""
    if not has_inbox(store):
        return [], []
    inbox, answers = store.inbox_folders("librarian"), store.answers_folders("librarian")
    readable, unreadable = store_requests.read_answers(answers, inbox, schemas_of(store))
    views, orphans = store_requests.view_requests(store_requests.read_items(inbox), readable, unreadable)
    out: list[RequestViewOut] = []
    for v in views:
        doc = v.item.doc
        attachments = doc.get("attachments")
        files = [a.get("file") for a in attachments if isinstance(a, dict) and isinstance(a.get("file"), str)] \
            if isinstance(attachments, list) else []
        kind = doc["request"]["kind"]
        out.append(RequestViewOut(
            item_id=doc["item_id"], kind=kind, kind_words=store_requests.KIND_WORDS[kind], words=doc["words"],
            login=doc["asked_by"]["login"], asked_at=doc["asked_at"], file=files[0] if files else None,
            example=_under_sample(store, v.item.path), state=v.state,
            answers=[answer_out(a.doc, _under_sample(store, a.path)) for a in v.answers],
            unreadable=[UnreadableOut(file=u.file, reason=u.reason) for u in v.unreadable]))
    return out, [UnreadableOut(file=u.file, reason=u.reason) for u in orphans]
