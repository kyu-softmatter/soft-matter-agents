"""Pseudonymise one experiment session's records before they leave the microscope PC.

docs/records-privacy.md. Every record goes to soft-matter-agents ``microscope_agent/runs/``,
which is a public repository, so a person may appear there only under a person id. The
mapping (account email -> person id) lives in the local private settings folder, never in
git; this module only takes it as an argument. It is applied at export, not at write time:
the local records keep the account ids and stay usable as they are.

    p = Pseudonyms.from_dict(json.loads(people_json))
    out = redact_session(session_dir, p)      # raises RedactionRefused, or returns copies
    out.files                                 # {"session.json": "...", "records/x.jsonl": ...}
    out.flat_files()                          # {"console.session.json": "...", ...} (runs/ names)

Rules, in order, on every string (dict keys and values alike):

1. a mapped email (any case) becomes its person id;
2. a home folder (``C:\\Users\\<name>``, ``/home/<name>``, ``/Users/<name>``) becomes ``~``;
3. a mapped name or alias (any case, whole words) becomes the person id;
4. the user part of a session id (``YYYYMMDD-HHMM-<user>-<n>``, records.session) becomes the
   person id when it is a mapped person's slug;
5. a mapped host name becomes its label.

Keys in ``DROP_KEYS`` (``user_name``, ``login_id``, ...) are removed, and ``host`` too unless
its value is mapped. Afterwards the result is scanned, and **anything left refuses the whole
session**: an email-like string, a home folder, a mapped name or alias, a session id whose
user part is not a person id, or a person field (``PERSON_KEYS``) whose value is neither a
person id nor an allowed actor. The refusal names the file, the place and the kind, never the
value. Standard library only; nothing here writes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .layout import slug

#: fields whose value names a person (the account id, an approver, a confirmer)
PERSON_KEYS = frozenset({"user_id", "by", "confirmed_by", "approved_by", "account", "holder"})
#: fields that never cross: the display name, the login handle, secrets
DROP_KEYS = frozenset({"user_name", "login_id", "password_hash", "control_grant", "token"})
HOST_KEY = "host"
#: values a person field may hold that are not people
DEFAULT_ACTORS = frozenset({"assistant", "system", "engine"})

#: soft-matter-agents contracts/validate.py: runs/<run_id>/ holds flat names or raw/...
RUNS_FILE = re.compile(r"^([A-Za-z0-9_.-]+|raw/.+)$")
PERSON_ID = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
FLAT_PREFIX = "console."
JSON_SUFFIXES = (".json", ".jsonl")
# records that stay on the microscope PC even when they sit in a session folder: the
# assistant conversation (user decision 2026-10-02, records-privacy.md section 6 item 3)
LOCAL_ONLY = frozenset({"assistant.jsonl"})

_EMAIL = re.compile(r"[\w.%+'-]+[@\uff20][\w-]+(?:\.[\w-]+)*", re.UNICODE)
# an optional drive, then Users / home / Documents and Settings, then the account name
# (also inside /mnt/c/Users/<name> and C:/Users/<name>)
_HOME = re.compile(r"(?i)(?:\b[a-z]:)?[\\/]+(?:users|home|documents and settings)"
                   r"[\\/]+[^\\/\"'\n\r\t]+")
# records.session.new_session_id: <YYYYMMDD-HHMM>-<slug(user)>-<n>
_SESSION_ID = re.compile(r"(?<![0-9A-Za-z])(\d{8}-\d{4})-([a-z0-9][a-z0-9-]*?)-(\d+)"
                         r"(?![0-9A-Za-z-])")


class RedactionRefused(ValueError):
    """Personal information would remain after redaction; nothing may be exported."""

    def __init__(self, findings: list[Finding]):
        self.findings = findings
        shown = "; ".join(str(f) for f in findings[:10])
        more = f" (+{len(findings) - 10} more)" if len(findings) > 10 else ""
        super().__init__(f"{len(findings)} personal-information finding(s): {shown}{more}")


@dataclass(frozen=True)
class Finding:
    file: str     # relative to the session folder ('' for a single record)
    where: str    # JSON path, e.g. "[3].data.by"
    kind: str     # email | home_path | name | session_user | unmapped_person | key

    def __str__(self) -> str:
        return f"{self.file or '<record>'}:{self.where or '$'} {self.kind}"


@dataclass(frozen=True)
class Person:
    person_id: str
    email: str
    name: str = ""
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not PERSON_ID.match(self.person_id):
            raise ValueError("a person id is 2-32 of a-z, 0-9, '-', starting with a letter")
        if not _EMAIL.fullmatch(self.email.strip()):
            raise ValueError(f"person {self.person_id}: email is not an email address")

    @property
    def terms(self) -> list[str]:
        """Words that name this person in free text (the full name and the aliases)."""
        return [t for t in (self.name, *self.aliases) if t and t.strip()]


@dataclass(frozen=True)
class Pseudonyms:
    """The local mapping (``people.json`` in the settings folder, never in git)."""

    persons: tuple[Person, ...]
    hosts: Mapping[str, str] = field(default_factory=dict)  # host name -> public label
    actors: frozenset[str] = DEFAULT_ACTORS

    def __post_init__(self) -> None:
        ids = [p.person_id for p in self.persons]
        emails = [p.email.strip().lower() for p in self.persons]
        if len(set(ids)) != len(ids) or len(set(emails)) != len(emails):
            raise ValueError("person ids and emails must each be unique")
        if set(ids) & set(self.actors):
            raise ValueError("a person id may not be an actor name")
        for label in self.hosts.values():
            if not PERSON_ID.match(label):
                raise ValueError("a host label is 2-32 of a-z, 0-9, '-', starting with a letter")

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Pseudonyms:
        """``{"persons": [{"person_id", "email", "name", "aliases"}], "hosts": {...}}``."""
        persons = tuple(Person(person_id=p["person_id"], email=p["email"],
                               name=p.get("name", ""), aliases=tuple(p.get("aliases", ())))
                        for p in d.get("persons", ()))
        actors = frozenset(d["actors"]) if "actors" in d else DEFAULT_ACTORS
        return cls(persons, dict(d.get("hosts", {})), actors)

    @property
    def person_ids(self) -> frozenset[str]:
        return frozenset(p.person_id for p in self.persons)


class _Rules:
    """The compiled replacements of one mapping."""

    def __init__(self, p: Pseudonyms):
        self.p = p
        self.by_email = {x.email.strip().lower(): x.person_id for x in p.persons}
        self.by_slug = {slug(x.email): x.person_id for x in p.persons}
        terms = sorted(((t, x.person_id) for x in p.persons for t in x.terms),
                       key=lambda tp: -len(tp[0]))
        self.terms = [(_word(t), pid) for t, pid in terms]
        self.hosts = sorted(((h, lab) for h, lab in p.hosts.items() if h),
                            key=lambda hl: -len(hl[0]))
        self.host_res = [(_word(h), lab) for h, lab in self.hosts]
        self.host_of = {h.lower(): lab for h, lab in self.hosts}

    # -- redaction
    def text(self, s: str) -> str:
        s = _EMAIL.sub(lambda m: self.by_email.get(_norm_email(m.group(0)), m.group(0)), s)
        s = _HOME.sub(_home, s)
        for rx, pid in self.terms:
            s = rx.sub(pid, s)
        s = _SESSION_ID.sub(self._session_id, s)
        for rx, label in self.host_res:
            s = rx.sub(label, s)
        return s

    def _session_id(self, m: re.Match[str]) -> str:
        pid = self.by_slug.get(m.group(2))
        return m.group(0) if pid is None else f"{m.group(1)}-{pid}-{m.group(3)}"

    def value(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return self.text(obj)
        if isinstance(obj, list):
            return [self.value(v) for v in obj]
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                if k in DROP_KEYS:
                    continue
                if k == HOST_KEY and isinstance(v, str):
                    label = self.host_of.get(v.strip().lower())
                    if label is None:
                        continue  # an unmapped host name does not cross
                    out[k] = label
                    continue
                out[self.text(k)] = self.value(v)
            return out
        return obj

    # -- the scan after redaction
    def scan(self, obj: Any, file: str = "", where: str = "") -> list[Finding]:
        found: list[Finding] = []
        if isinstance(obj, str):
            found += [Finding(file, where, kind) for kind in self.kinds(obj)]
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                found += self.scan(v, file, f"{where}[{i}]")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                key_kinds = self.kinds(k)
                key = "<key>" if key_kinds else k  # a finding never quotes the value
                here = f"{where}.{key}" if where else key
                found += [Finding(file, here, f"key:{kind}") for kind in key_kinds]
                if k in PERSON_KEYS and not self._is_actor(v):
                    found.append(Finding(file, here, "unmapped_person"))
                found += self.scan(v, file, here)
        return found

    def _is_actor(self, v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, list):
            return all(self._is_actor(x) for x in v)
        return isinstance(v, str) and (v in self.p.person_ids or v in self.p.actors)

    def kinds(self, s: str) -> list[str]:
        kinds = []
        if _EMAIL.search(s):
            kinds.append("email")
        if _HOME.search(s):
            kinds.append("home_path")
        if any(m.group(0).lower() not in self.p.person_ids
               for rx, _ in self.terms for m in rx.finditer(s)):
            kinds.append("name")
        if any(m.group(2) not in self.p.person_ids for m in _SESSION_ID.finditer(s)):
            kinds.append("session_user")
        if any(h.lower() in s.lower() for h, _ in self.hosts):
            kinds.append("host")
        return kinds


def _norm_email(s: str) -> str:
    return s.replace("\uff20", "@").strip().lower()


def _home(m: re.Match[str]) -> str:
    """``C:\\Users\\<name>`` and ``/home/<name>`` -> ``~``; ``/mnt/c/Users/<name>`` ->
    ``/mnt/c/~``."""
    text, at, hit = m.string, m.start(), m.group(0)
    if hit[0] not in "\\/" or at == 0 or not text[at - 1].isalnum():
        return "~"
    return hit[0] + "~"


def _word(term: str) -> re.Pattern[str]:
    """`term` as whole words, any case, any run of spaces between its words."""
    parts = [re.escape(w) for w in term.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)", re.IGNORECASE)


# -- public functions --------------------------------------------------------------------


def redact(obj: Any, p: Pseudonyms) -> Any:
    """The redacted copy of one JSON value (no scan; see `redact_record`)."""
    return _Rules(p).value(obj)


def scan(obj: Any, p: Pseudonyms, file: str = "") -> list[Finding]:
    """What would refuse `obj` as it is (an already redacted value, normally)."""
    return _Rules(p).scan(obj, file)


def redact_record(obj: Any, p: Pseudonyms, file: str = "") -> Any:
    """Redact one JSON value and refuse it if anything personal is left."""
    rules = _Rules(p)
    out = rules.value(obj)
    found = rules.scan(out, file)
    if found:
        raise RedactionRefused(found)
    return out


@dataclass
class RedactedSession:
    session_id: str                  # the local id
    export_id: str                   # the same id with the user part pseudonymised
    files: dict[str, str]            # relative posix path -> redacted text
    left_out: list[str]              # files that are not JSON / JSONL: not copied
    kept_local: list[str] = field(default_factory=list)  # LOCAL_ONLY files: not read

    def flat_files(self, prefix: str = FLAT_PREFIX) -> dict[str, str]:
        """The same files under flat names a runs/<run_id>/ folder accepts:
        ``records/scan_4x.jsonl`` -> ``console.records.scan_4x.jsonl``."""
        out = {}
        for rel, text in self.files.items():
            name = flat_name(rel, prefix)
            if name in out:
                raise ValueError(f"two files flatten to {name}")
            out[name] = text
        return out


def flat_name(rel: str, prefix: str = FLAT_PREFIX) -> str:
    name = prefix + rel.replace("\\", "/").replace("/", ".")
    if not RUNS_FILE.match(name) or "/" in name:
        raise ValueError(f"{rel!r} has no flat runs/ name")
    return name


def redact_session(session_dir: str | Path, p: Pseudonyms) -> RedactedSession:
    """Redacted copies of every JSON and JSONL file of one session folder, or a refusal
    listing every finding across all files. Reads only; the folder is not changed."""
    root = Path(session_dir)
    info_path = root / "session.json"
    if not info_path.is_file():
        raise FileNotFoundError(f"{root} has no session.json")
    rules = _Rules(p)
    files: dict[str, str] = {}
    left_out: list[str] = []
    found: list[Finding] = []
    kept_local: list[str] = []
    for path in sorted(_walk(root)):
        rel = path.relative_to(root).as_posix()
        if path.name in LOCAL_ONLY:
            kept_local.append(rules.text(rel))
            continue
        out_rel = rules.text(rel)
        name_kinds = rules.kinds(out_rel)
        if name_kinds:
            rel = "<file name>"  # a finding never quotes the value
            found += [Finding(rel, "", k) for k in name_kinds]
        if path.suffix not in JSON_SUFFIXES:
            left_out.append(out_rel)
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            value = rules.value(json.loads(text))
            found += rules.scan(value, rel)
            files[out_rel] = json.dumps(value, indent=1, ensure_ascii=False) + "\n"
        else:
            lines = []
            for i, line in enumerate(s for s in text.splitlines() if s.strip()):
                value = rules.value(json.loads(line))
                found += rules.scan(value, rel, f"[{i}]")
                lines.append(json.dumps(value, ensure_ascii=False))
            files[out_rel] = "".join(s + "\n" for s in lines)
    if found:
        raise RedactionRefused(found)
    info = json.loads(info_path.read_text(encoding="utf-8"))
    sid = str(info.get("session_id", ""))
    return RedactedSession(session_id=sid, export_id=rules.text(sid), files=files,
                           left_out=left_out, kept_local=kept_local)


def _walk(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file() and not p.name.endswith(".tmp") and ".git" not in p.parts:
            yield p
