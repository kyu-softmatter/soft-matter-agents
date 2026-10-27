"""The earlier question request, read back (console card 010, plan.md 4.5; no longer written, card 022).

A request is `contracts/schemas/question_request.schema.json`: the asker's words exactly as typed,
the asking login and that login's console role, the time (UTC) and the agent addressed. A console of
before wrote one into its own folder, `console/requests/questions/<id>.json`, for a question left to the
agents, which no agent has an inbox for. **A request in that folder is not delivered**, and nothing writes
one any more: a question to the microscope or the simulation goes into that agent's inbox as an item
(`inbox_items.py`, card 019), and one to the librarian as an `ask` request (`store_requests.py`, card 020).
This module only reads the old files back, for the cards and for autocomplete, and checks who may ask.

* The id is `qr-<UTC yyyymmdd>-<UTC hhmmss>-<four random lowercase letters or digits>`, and the file
  is `<id>.json`.
* The reader accepts every addressee the schema allows, `agents_decide` included, so an old request is
  shown and never refused; the console just no longer offers that choice.
* Autocomplete offers only strings already on disk: the `words` of earlier requests and the quantity
  names in `contracts/quantities.json`. Never a model's completion, never the store's contents.
"""

from __future__ import annotations

import json
import re
import secrets
import string
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..auth.accounts import AccountError, check_login

#: every addressee the request schema allows: what the reader accepts. The console offers only the last three.
ADDRESSEES = ("agents_decide", "microscope", "simulation", "librarian")
#: the agents a console role may name, in the schema's order
AGENTS_ASKABLE = ("microscope", "simulation", "librarian")
MAX_WORDS = 4000
FOLDER_PARTS = ("console", "requests", "questions")
ID_PATTERN = re.compile(r"qr-[0-9]{8}-[0-9]{6}-[a-z0-9]{4}")
SUGGESTION_KINDS = ("earlier question", "registered name")
NOT_DELIVERED = "written in the console · not delivered"
_ALPHABET = string.ascii_lowercase + string.digits


class RequestError(ValueError):
    """What was asked cannot be written as a request (the message says why)."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def random_suffix() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(4))


def console_role_for(role: str) -> dict[str, Any] | None:
    """What a login may do inside the console, derived from today's role until the admin card brings
    console-side roles: an admin or an operator may ask, draft, address every agent and ask for a
    model run; a viewer may do none of it (None: such a login cannot send)."""
    if role in ("admin", "operator"):
        return {"may_ask": True, "may_draft": True, "agents": list(AGENTS_ASKABLE),
                "may_ask_model_run": True}
    return None


def check_asker(*, words: str, login: str, role: str) -> dict[str, Any]:
    """The asker's console role, or `RequestError` when the words or the login cannot be written.
    `words` is kept exactly as typed: only a question that is blank or cannot be written is refused."""
    if not isinstance(words, str) or words.strip() == "":
        raise RequestError("a question needs words")
    if len(words) > MAX_WORDS:
        raise RequestError(f"a question is at most {MAX_WORDS} characters")
    try:
        words.encode("utf-8")
    except UnicodeEncodeError as e:
        raise RequestError("the words contain a character that cannot be written") from e
    try:
        check_login(login)
    except AccountError as e:
        raise RequestError(str(e)) from e
    console_role = console_role_for(role)
    if console_role is None:
        raise RequestError("this login may not ask a question")
    return console_role


def read_requests(folders: Iterable[Path]) -> list[dict[str, Any]]:
    """Every request on disk in `folders`, newest first. A file that is not a request (another
    artifact, unreadable, a name that is not its id) is skipped, never offered or shown. A request
    in an earlier folder is kept over one of the same id in a later one."""
    found: dict[str, dict[str, Any]] = {}
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            doc = _read_request(path)
            if doc is not None and doc["id"] not in found:
                found[doc["id"]] = doc
    return sorted(found.values(), key=lambda d: (d["asked_at"], d["id"]), reverse=True)


def _read_request(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("artifact") != "question_request":
        return None
    rid, words, at, to, by = (doc.get(k) for k in ("id", "words", "asked_at", "addressed_to", "asked_by"))
    if not (isinstance(rid, str) and ID_PATTERN.fullmatch(rid) and path.stem == rid
            and isinstance(words, str) and words != "" and isinstance(at, str)
            and to in ADDRESSEES and isinstance(by, dict) and isinstance(by.get("login"), str)):
        return None
    return doc


def quantity_names(root: Path | None) -> list[str]:
    """The ids in `<root>/contracts/quantities.json`, in the file's order; none when it is not
    there. A name registered there is a string on disk and nothing more."""
    if root is None:
        return []
    try:
        data = json.loads((root / "contracts" / "quantities.json").read_text(encoding="utf-8-sig"))
        rows = data["quantities"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    out: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        name = row.get("id") if isinstance(row, dict) else None
        if isinstance(name, str) and name not in out:
            out.append(name)
    return out


def suggestions(requests: list[dict[str, Any]], names: list[str]) -> list[dict[str, str]]:
    """The words of earlier requests (newest first, each once), then the registered names, each
    labelled. Nothing else is ever offered."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for r in requests:
        if r["words"] not in seen:
            seen.add(r["words"])
            out.append({"text": r["words"], "kind": "earlier question"})
    out.extend({"text": n, "kind": "registered name"} for n in names)
    return out
