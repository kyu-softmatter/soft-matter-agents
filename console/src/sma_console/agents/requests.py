"""The question request: what the console's question window writes (console card 010, plan.md 4.5).

A request is `contracts/schemas/question_request.schema.json`: the asker's words exactly as typed,
the asking login and that login's console role, the time (UTC) and the agent addressed. It is
written into the console's own folder, `console/requests/questions/<id>.json`, and **nothing reaches
an agent**: nothing reads a request until the agents' new inbox opens, which is designed on its own
and approved by the person (Q-20261022-office-04). So this module writes a file in one place and
reads that place back for the cards and for autocomplete, and does nothing else.

* The id is `qr-<UTC yyyymmdd>-<UTC hhmmss>-<four random lowercase letters or digits>`, and the file
  is `<id>.json`.
* The file is written complete to a temporary name in the same folder and then **linked** to its
  final name, so it appears whole or not at all, and a link to a name that exists fails: a request
  is **never rewritten**, an existing id is refused (`RequestIdTaken`).
* There is no key the schema does not name, and no claim that the asker is the person's own: that
  claim counts only with a proof no session can forge (plan.md 4.5, 6.2), which is not built.
* Autocomplete offers only strings already on disk: the `words` of earlier requests and the quantity
  names in `contracts/quantities.json`. Never a model's completion, never the store's contents.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import string
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..auth.accounts import AccountError, check_login
from .store import StoreError

ADDRESSEES = ("agents_decide", "microscope", "simulation", "librarian")
#: the agents a console role may name, in the schema's order
AGENTS_ASKABLE = ("microscope", "simulation", "librarian")
MAX_WORDS = 4000
FOLDER_PARTS = ("console", "requests", "questions")
ID_PATTERN = re.compile(r"qr-[0-9]{8}-[0-9]{6}-[a-z0-9]{4}")
SUGGESTION_KINDS = ("earlier question", "registered name")
NOT_PICKED_UP = "request written · not picked up yet"
_ALPHABET = string.ascii_lowercase + string.digits


class RequestError(ValueError):
    """What was asked cannot be written as a request (the message says why)."""


class RequestIdTaken(StoreError):
    """A request with this id is already on disk. It is never rewritten."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def random_suffix() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(4))


def request_id(now: datetime, suffix: str) -> str:
    return f"qr-{now.strftime('%Y%m%d-%H%M%S')}-{suffix}"


def console_role_for(role: str) -> dict[str, Any] | None:
    """What a login may do inside the console, derived from today's role until the admin card brings
    console-side roles: an admin or an operator may ask, draft, address every agent and ask for a
    model run; a viewer may do none of it (None: such a login cannot send)."""
    if role in ("admin", "operator"):
        return {"may_ask": True, "may_draft": True, "agents": list(AGENTS_ASKABLE),
                "may_ask_model_run": True}
    return None


def build_request(*, words: str, login: str, role: str, addressed_to: str, now: datetime,
                  suffix: str) -> dict[str, Any]:
    """The request as the schema has it, or `RequestError`. `words` is kept exactly: not trimmed,
    not rewritten. Only a question that is blank or cannot be written is refused."""
    if not isinstance(words, str) or words.strip() == "":
        raise RequestError("a question needs words")
    if len(words) > MAX_WORDS:
        raise RequestError(f"a question is at most {MAX_WORDS} characters")
    try:
        words.encode("utf-8")
    except UnicodeEncodeError as e:
        raise RequestError("the words contain a character that cannot be written") from e
    if addressed_to not in ADDRESSEES:
        raise RequestError(f"addressed_to is one of {', '.join(ADDRESSEES)}")
    try:
        check_login(login)
    except AccountError as e:
        raise RequestError(str(e)) from e
    console_role = console_role_for(role)
    if console_role is None:
        raise RequestError("this login may not ask a question")
    when = now.astimezone(UTC)
    return {
        "artifact": "question_request",
        "schema_version": "0.1",
        "id": request_id(when, suffix),
        "words": words,
        "asked_by": {"login": login, "console_role": console_role},
        "asked_at": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "addressed_to": addressed_to,
    }


def write_request(folder: Path, request: dict[str, Any]) -> Path:
    """Write `request` as `<folder>/<id>.json`, whole or not at all, and never over a file that is
    there. Raises `RequestIdTaken` when the id exists, `StoreError` when the disk refuses."""
    rid = request["id"]
    if ID_PATTERN.fullmatch(rid) is None:
        raise StoreError(f"not a request id: {rid!r}")
    final = folder / f"{rid}.json"
    data = (json.dumps(request, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    tmp = folder / f".{rid}.{os.getpid()}.{secrets.token_hex(3)}.tmp"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with open(tmp, "xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp, final)  # fails when the name exists: a request is never rewritten
        except FileExistsError as e:
            raise RequestIdTaken(f"a request {rid} already exists") from e
    except RequestIdTaken:
        raise
    except OSError as e:
        raise StoreError(f"the request could not be written: {e}") from e
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    return final


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
