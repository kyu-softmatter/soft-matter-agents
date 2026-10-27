"""The approval writer -- part of the person's guard (plan.md 6.1 and 15.1; console card 013).

This is the one place the console writes into `microscope_runtime/`: one signed plan approval, into
`<tree>/microscope_runtime/approvals/`, and nothing else. **Any change to this file needs the person's
word, asked through the intake seat and citing `b4f340ee` (Q-20261024-office-01).** It was built on that
word and on no other.

It writes only when every condition holds, in this order, in the same request, and otherwise refuses with
a reason in words and writes nothing:

1. the session's login is the person's login (`person_login` from the console's settings, a plain id).
   That decides the screen and the console's own refusal; the runtime still decides from the person's own
   file and never from those settings;
2. the store is the real tree, not the practice data;
3. the plan's fingerprint, recomputed here from the plan card by the validator's rule, equals the
   fingerprint the screen showed and sent;
4. `microscope_runtime/approvals/` is in the tree. It is never created, and no other place is used;
5. the password was typed again and checked in this request, through the login's throttle;
6. the person's own login file, `microscope_runtime/envelope/console_login.json`, is in place, is valid
   against `contracts/schemas/console_login.schema.json`, and names the session's login byte for byte. The
   runtime would refuse the approval otherwise. This file is read and never written;
7. no approval of that name is there yet. An approval is never rewritten.

(Steps 3 and 4 come before the password, so a plan that changed or a folder that is not there is said
before anyone is asked for a password, and a wrong password is counted only for something that could be
signed. Nothing is ever written before all seven hold.)

What it writes is one `plan_approval` card, built to `plan_approval.schema.json` and validated against the
schema read from the repository before it is written, carrying `signed_through: {via: console, login}`.
It is written whole under a temporary name that does not end in `.json` (the runtime reads every `*.json`
in that folder and must never read half a file), then given its name without ever replacing a file.
No password, and no hash of one, goes anywhere near it.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..agents.schema_lite import SchemaError, Schemas
from ..agents.sma_files import RootNotFoundError, plan_hash, repository_root

#: A login as plan_approval's `signed_through.login` and console_login.json both spell it.
PLAIN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

RUNTIME = "microscope_runtime"
APPROVALS_PARTS = (RUNTIME, "approvals")
LOGIN_FILE_PARTS = (RUNTIME, "envelope", "console_login.json")

NO_APPROVALS_FOLDER = ("Nothing can be signed here: the folder microscope_runtime/approvals/ is not in the tree "
                       "this console reads, and no other place is used. Your approvals folder is not there.")
WRITTEN_MESSAGE = ("Approval written. The runtime reads it from disk now. Commit it yourself when you choose: "
                   "no session may commit a file under approvals/.")

_LOCK = threading.Lock()


class SigningRefused(Exception):
    """Nothing was written, and `message` says why in words. `status` is the HTTP answer for it."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Written:
    file_name: str
    path: Path
    login: str
    qid: str
    plan_id: str
    plan_revision: int
    plan_hash: str
    approved_at: str


def approvals_folder(tree: Path) -> Path:
    return Path(tree).joinpath(*APPROVALS_PARTS)


def _now() -> datetime:
    return datetime.now(UTC)


def _schemas(folder: Path | None) -> Schemas:
    try:
        return Schemas(folder if folder is not None else repository_root() / "contracts" / "schemas")
    except RootNotFoundError as e:
        raise SigningRefused(409, "schema_unavailable",
                             f"The schemas cannot be found, so nothing is written: {e}") from e


def _login_file_refusal(tree: Path, login: str, schemas: Schemas) -> None:
    path = Path(tree).joinpath(*LOGIN_FILE_PARTS)
    if not path.is_file():
        raise SigningRefused(409, "login_file_missing",
                             "Your own login file, placed by hand beside the safety policy, is missing, so "
                             "the runtime would refuse this approval. Nothing was written.")
    try:
        doc = json.loads(path.read_bytes().decode("utf-8-sig"))
        problems = schemas.validate(doc, "console_login.schema.json")
    except (OSError, ValueError) as e:
        problems = [f"it cannot be read: {e}"]
    except SchemaError as e:
        raise SigningRefused(409, "schema_unavailable",
                             f"The login file cannot be checked against its schema, so nothing is written: {e}") from e
    if problems:
        raise SigningRefused(409, "login_file_invalid",
                             "Your own login file, placed by hand beside the safety policy, is not valid, so "
                             f"the runtime would refuse this approval. Nothing was written. ({problems[0]})")
    if doc["login"] != login:
        raise SigningRefused(409, "login_file_other_login",
                             "Your own login file, placed by hand beside the safety policy, names another "
                             "login than this one, so the runtime would refuse this approval. Nothing was written.")


def build_approval(*, login: str, plan_card: dict[str, Any], approved_at: str) -> dict[str, Any]:
    """The approval card for `plan_card`: the schema's own fields and `signed_through`, nothing else."""
    plan_id, revision = plan_card.get("id"), plan_card.get("revision")
    qid = plan_card.get("qid")
    return {
        "card": "plan_approval",
        "schema_version": "0.1",
        "id": f"appr-{qid}-r{revision}",
        "qid": qid,
        "thread": plan_card.get("thread"),
        "round": 0,
        "revision": 1,
        "author": "human",
        "created_at": approved_at,
        "status": "APPROVED",
        "plan_id": plan_id,
        "plan_revision": revision,
        "plan_hash": plan_hash(plan_card),
        "approved_by": login,
        "approved_at": approved_at,
        "numbers": [],
        "degraded": [],
        "signed_through": {"via": "console", "login": login},
    }


def _put(folder: Path, name: str, doc: dict[str, Any]) -> None:
    """Whole, under a name that does not end in .json, then given its name without replacing anything."""
    tmp = folder / f".{name}.{secrets.token_hex(6)}.part"
    final = folder / name
    data = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        with open(tmp, "xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp, final)  # fails if the name is taken: a file is never replaced
        except FileExistsError as e:
            raise SigningRefused(409, "already_approved", "This plan revision is already approved.") from e
        except OSError:  # a file system without hard links: rename refuses an existing name on Windows
            if final.exists():
                raise SigningRefused(409, "already_approved", "This plan revision is already approved.") from None
            os.rename(tmp, final)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def write_approval(*, tree: Path, practice: bool, session_login: str | None, person_login: str | None,
                   qid: str, shown_plan_hash: str, plan_card: dict[str, Any] | None,
                   check_password: Callable[[], bool], schemas_folder: Path | None = None,
                   now: Callable[[], datetime] = _now) -> Written:
    """Write the approval, or raise `SigningRefused` with nothing written. `check_password` is called
    once, at its place in the order, and returns whether the password was right; it raises
    `TooManyAttempts` when the login's throttle says wait, which this does not catch."""
    if person_login is None or not PLAIN_ID.match(person_login):
        raise SigningRefused(403, "person_not_named", "The person's login is not named yet, so no one can sign.")
    if session_login is None or not PLAIN_ID.match(session_login) or session_login != person_login:
        raise SigningRefused(403, "not_person", "Only the person's own login signs.")
    if practice:
        raise SigningRefused(409, "practice", "This is practice data: nothing real is written.")
    if plan_card is None or plan_hash(plan_card) != shown_plan_hash or plan_card.get("qid") != qid:
        raise SigningRefused(409, "plan_changed", "The plan changed; review it again.")
    folder = approvals_folder(tree)
    if not folder.is_dir():
        raise SigningRefused(409, "no_approvals_folder", NO_APPROVALS_FOLDER)
    if not check_password():
        raise SigningRefused(401, "bad_credentials", "Wrong password.")
    schemas = _schemas(schemas_folder)
    _login_file_refusal(tree, session_login, schemas)
    stamp = now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_approval(login=session_login, plan_card=plan_card, approved_at=stamp)
    try:
        problems = schemas.validate(doc, "plan_approval.schema.json")
    except SchemaError as e:
        raise SigningRefused(409, "schema_unavailable",
                             f"The approval cannot be checked against its schema, so nothing is written: {e}") from e
    if problems:
        raise SigningRefused(409, "approval_invalid",
                             f"The plan cannot be signed as it stands, so nothing is written. ({problems[0]})")
    name = f"{doc['id']}.json"  # the schema fixes qid to <agent>-<date>-<n> and the revision to an integer
    with _LOCK:
        if (folder / name).exists():
            raise SigningRefused(409, "already_approved", "This plan revision is already approved.")
        _put(folder, name, doc)
    return Written(file_name=name, path=folder / name, login=session_login, qid=doc["qid"], plan_id=doc["plan_id"],
                   plan_revision=doc["plan_revision"], plan_hash=doc["plan_hash"], approved_at=stamp)
