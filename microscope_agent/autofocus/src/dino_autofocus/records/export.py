"""Export one closed experiment session for soft-matter-agents' public runs/ folder.

docs/records-privacy.md section 5, with the user's answers to section 6 (2026-10-02):

1. a person appears under the short id they chose (the handle of their SMA approval cards,
   e.g. ``kyuhwan``); an account without one gets a random ``p-xxxxxx`` once, kept in the
   local ``people.json`` (settings folder, never in git): ``assign_person_ids``;
2. free text (close note, manual-step notes, flag names, notes) goes out after the scan;
3. the assistant conversation stays local: ``assistant.jsonl`` is never read
   (``redact.LOCAL_ONLY``);
4. the files go next to the ``log.json`` of the SMA run the session belongs to
   (``session.json`` ``sma_run_id``), as ``console.*`` flat names.

This repository never writes into soft-matter-agents (PLAN section 5): ``export_session``
writes ``<out_dir>/<run_id>/console.*`` in a local staging folder, laid out like SMA's
``runs/<run_id>/``, and the SMA side copies them in. Nothing is written when the redaction
refuses, and an existing file is never overwritten.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .redact import FLAT_PREFIX, Pseudonyms, redact_session

PEOPLE_FILE = "people.json"  # in the settings folder, beside accounts.json
EXPORT_FILE = FLAT_PREFIX + "export.json"
#: A soft-matter-agents ``runs/<run_id>/`` folder name: its validator (contracts/validate.py,
#: ALLOWED_PATHS) admits ``runs/[a-z0-9-]+/`` only, so upper case, ``_`` and ``.`` are refused
#: here before anything is written (R-03). `tests/records/test_records_export.py` compares
#: this rule with that validator's when a soft-matter-agents checkout is present.
RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
#: Top-level keys that would make a console.* file read as a soft-matter-agents card or
#: artifact (its check 1 validates those against the card schemas); never written.
CARD_KEYS = ("card", "artifact")


class ExportRefused(ValueError):
    """The session may not be exported (open, not on the bench, no SMA run, target taken)."""


@dataclass(frozen=True)
class Exported:
    run_id: str
    folder: Path                  # <out_dir>/<run_id>
    export_id: str                # the session id with its user part pseudonymised
    files: dict[str, str]         # flat name -> sha256 of what was written
    left_out: list[str]           # attachments that are not JSON / JSONL (not copied)
    kept_local: list[str]         # local-only records that were not read

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["folder"] = self.folder.as_posix()
        return d


# -- people.json -------------------------------------------------------------------------


def load_people(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {"persons": [], "hosts": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def assign_person_ids(path: str | Path, emails: Iterable[str], *,
                      token: Callable[[], str] = lambda: secrets.token_hex(3)) -> Pseudonyms:
    """Give every account in `emails` that has no person yet a random ``p-xxxxxx`` id and
    save ``people.json`` (atomically). A chosen handle is set by editing the file; an id
    already given is never changed. Returns the mapping."""
    data = load_people(path)
    persons = data.setdefault("persons", [])
    known = {str(p["email"]).strip().lower() for p in persons}
    taken = {p["person_id"] for p in persons}
    added = False
    for email in emails:
        if email.strip().lower() in known:
            continue
        pid = f"p-{token()}"
        while pid in taken:
            pid = f"p-{token()}"
        persons.append({"person_id": pid, "email": email.strip()})
        known.add(email.strip().lower())
        taken.add(pid)
        added = True
    mapping = Pseudonyms.from_dict(data)  # validates before anything is saved
    if added:
        _write_atomic(Path(path), json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return mapping


# -- one session -------------------------------------------------------------------------


def export_session(session_dir: str | Path, people: Pseudonyms, out_dir: str | Path, *,
                   run_id: str | None = None,
                   now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> Exported:
    """Redact `session_dir` and write its records as ``<out_dir>/<run_id>/console.*``.
    `run_id` defaults to the session's ``sma_run_id``. Raises ``ExportRefused`` or
    ``redact.RedactionRefused`` and then writes nothing."""
    root = Path(session_dir)
    info = json.loads((root / "session.json").read_text(encoding="utf-8"))
    if info.get("status") != "closed":
        raise ExportRefused("only a closed session is exported")
    if info.get("bench") is not True:  # T-106b: a mock or simulated backend, or not recorded
        raise ExportRefused("a session without the real microscope is not exported "
                            "(session.json bench is not True)")
    run_id = run_id or info.get("sma_run_id")
    if not run_id:
        raise ExportRefused("the session has no sma_run_id: console files go next to the "
                            "log.json of the SMA run they belong to")
    if not RUN_ID.match(str(run_id)):
        raise ExportRefused(f"run id {run_id!r} is not a soft-matter-agents runs/ folder name "
                            "(lower-case letters, digits and '-', at most 64)")

    red = redact_session(root, people)  # RedactionRefused: nothing written
    flat = red.flat_files()
    for name, text in flat.items():
        for key in _top_level_keys(name, text):
            if key in CARD_KEYS:
                raise ExportRefused(f"{name} carries a top-level {key!r} key: a console file "
                                    "must not read as a soft-matter-agents card")
    folder = Path(out_dir) / str(run_id)
    names = [*flat, EXPORT_FILE]
    taken = [n for n in names if (folder / n).exists()]
    if taken:
        raise ExportRefused(f"{len(taken)} console file(s) already in {folder.name}; "
                            "an export never overwrites")
    folder.mkdir(parents=True, exist_ok=True)
    digests = {}
    for name, text in sorted(flat.items()):
        _write_atomic(folder / name, text)
        digests[name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    done = Exported(str(run_id), folder, red.export_id, digests, red.left_out, red.kept_local)
    summary = {"export_id": red.export_id, "run_id": str(run_id),
               "exported_at": now().isoformat(timespec="seconds"),
               "files": digests, "left_out": red.left_out, "kept_local": red.kept_local}
    _write_atomic(folder / EXPORT_FILE, json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    return done


def _top_level_keys(name: str, text: str) -> set[str]:
    """Top-level object keys of a console.* JSON file, or of every line of a JSONL file."""
    keys: set[str] = set()
    if name.endswith(".jsonl"):
        docs = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif name.endswith(".json"):
        docs = [json.loads(text)]
    else:
        return keys
    for d in docs:
        if isinstance(d, dict):
            keys |= set(d)
    return keys


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)
