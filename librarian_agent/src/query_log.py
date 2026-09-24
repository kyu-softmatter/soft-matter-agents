#!/usr/bin/env python3
"""Append-only record of who asked the store for what, and why.

The two questions this answers are already arguments of the contract, not new
ideas: `kb_query(caller_id, kb_version, observable, condition_range, purpose)`
carries the asker in `caller_id` and the reason in `purpose` (4.3.1). Today
they arrive, shape the answer and vanish. A `kb_gap` keeps `asked_by` and
`asked_at`, so a question that FAILED is already attributable; a question that
succeeded is not. This module closes that asymmetry.

Why it is worth keeping:

* `caller_id` is `<qid>:<config>:<axis>`, issued by the fan-out launcher and
  never chosen by the sub-agent (4.3.1). So the asker is not a name an agent
  claims -- it names which question, which configuration and which axis the
  query came from, and the log inherits that trustworthiness. It also inherits
  its limit: this module records the id it was handed and cannot check that the
  launcher issued it. A self-chosen id would make every line a fiction, which
  is why the rule lives at the launcher and not here.
* `purpose` is an enum read live from `contracts/schemas/goal.schema.json`, not
  copied. Prose reasons cannot be counted; an enum can.
* Recording the ANSWER next to the query makes the log a determinism witness.
  4.3.1 requires the same `(query, kb_version)` to give the same answer
  forever. Nothing enforces that at present. Two lines here with one query and
  one kb_version but different returns is that violation, caught after the
  fact by `verify`, without which the guarantee is a promise nobody checks.

**The one rule that keeps this safe.** 4.3.1: global statistics never touch the
answer. A store that notices what callers ask about starts answering with what
is popular, and two things break at once -- determinism, and caller isolation,
because a sibling's query would then be visible in another sibling's answer.
The enforcement is structural rather than a comment: this module offers `record`
(write) and `verify` (offline audit) and NO function that reads the log by
caller, observable or count. There is nothing here for answering code to call.

**Where it sits, and why not in the store.** `librarian_agent/queries/`, beside
`kb/` rather than inside it. 4.3.2 sorts material into three genres -- knowledge,
records, policy -- and a query log is a record, the same genre as
`microscope_agent/runs/`. The mechanical reason is sharper than the taxonomy:
`kb_version` hashes the entries and a card cites the store with `kb:<entry_id>`,
so everything inside `kb/` is either citable or noise in the hash. A log can be
neither cited nor hashed, and putting it there would blur the boundary that
`kb_version` exists to draw.

    python3 librarian_agent/src/query_log.py --verify
    python3 librarian_agent/src/query_log.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

AGENT = Path(__file__).resolve().parent.parent
CONTRACTS = AGENT.parent / "contracts"
DEFAULT_LOG = AGENT / "queries" / "log.jsonl"

TOOLS = ("kb_query", "kb_get", "kb_conflicts", "kb_group")
FIELDS = ("asked_at", "caller_id", "kb_version", "tool", "purpose",
          "observable", "condition_range", "returned", "gaps", "coverage",
          "outcome", "reason", "claimed", "server_session", "unusable")

# `unusable` is the entry ids that answered to the name and could not be
# compared, so the server skipped them and served the rest (task 025). It is
# written only when there were some. It belongs in the log and not only in
# the answer for the same reason `outcome: refused` does: an event that
# happens to one caller and is reported only to that caller is one nobody can
# count afterwards, and "did this ever bite?" is the question this repository
# keeps having to settle from disk rather than from memory.

# `caller_id` is the argument a caller passed, and the server cannot check
# that the process on the other end is the seat that id names. On 2026-09-19
# three lines one second apart carried three different seats' ids, and
# settling whose they were took a grep across six commits -- the log could not
# say, because nothing in it distinguishes three seats calling from one
# process iterating over three ids.
#
# `server_session` is the one thing the server does observe: which of its own
# runs answered. It does not identify the caller and must not be read as
# doing so. What it gives is that lines sharing it were served by one process,
# which is exactly the distinction that was missing. Recorded, never consulted
# when answering (4.3.1 rule 4).

# A refused call is a record too. Until 2026-09-19 the log held answers only,
# so how often the service refused was written nowhere -- "nine of ten queries
# came back empty" was countable because empty is an answer, and refusals were
# not. It also left the check 0.3-4 will want unable to tell a card that never
# called from one that called and was turned away. Those are different claims,
# the same way `searched` separates not-looked-for from not-there.
#
# The trap, and the shape exists for it: a refusal may be OF a caller_id that
# the launcher never issued. Writing that string into `caller_id` would put an
# invented id into the audit trail -- the reason this seat refused to fabricate
# the log's first line. So a refusal records nothing as validated: every
# argument as given goes under `claimed`, whose name says what it is, and no
# field asserts a property the server just rejected.
REFUSAL_FIELDS = ("asked_at", "tool", "outcome", "reason", "claimed", "server_session")


_REGISTRY_CACHE: dict = {}


def _contract(path: str, *keys):
    """Read a registry out of contracts/ rather than restating it here (P3).

    Cached on the file's mtime, not for the life of the process. Reading a
    registry once at import looks identical to reading it live from inside the
    code, and is not: the MCP server is long-running, so on 2026-09-19 it
    refused a legitimate bridge caller for the ten minutes between the commit
    that fixed the pattern and the next restart -- with the old message, which
    sent that seat to escalate something already fixed. From in here the code
    plainly reads the current file; only a caller could see otherwise.

    The mtime key rather than no cache at all because units.json is read once
    per bound per quantity, and because a re-read that happens to catch
    another seat mid-write should not take the service down.
    """
    full = CONTRACTS / path
    stamp = full.stat().st_mtime_ns
    key = (path, keys)
    hit = _REGISTRY_CACHE.get(key)
    if hit is not None and hit[0] == stamp:
        return hit[1]
    node = json.loads(full.read_text(encoding="utf-8"))
    for k in keys:
        node = node[k]
    _REGISTRY_CACHE[key] = (stamp, node)
    return node


def contract_first(*candidates: tuple[str, tuple[str, ...]]):
    """The first of several places a definition may live, or a clear refusal.

    On 2026-09-19 `caller_id` moved from axis.schema.json's own properties into
    common.schema.json's $defs. Both this module and the server read the old
    place with a bare subscript at import time, so the contract moved and the
    service did not degrade -- it failed to start, twice, in one run. Reading
    a registry instead of restating it is right; doing it without saying what
    happens when it moves is what cost the outage. One implementation, because
    two copies of the fallback drift the same way the registry would.
    """
    for path, keys in candidates:
        try:
            node = _contract(path, *keys)
        except (KeyError, TypeError, FileNotFoundError):
            continue
        if node is not None:
            return node
    raise Rejected(f"none of {[c[0] for c in candidates]} carries that definition; "
                   "the contract moved again and this reads it rather than restating it")


def gap_kinds() -> tuple[str, ...]:
    """The gap kinds, from the contract rather than retyped.

    Validated here because a wrong kind is the defect this log has already
    surfaced once: `condition_mismatch` was reported for a query where nothing
    had been compared, and only the record made it visible. A kind the contract
    does not have would be a worse version of the same thing, recorded as
    though it were fine.
    """
    return tuple(_contract("schemas/common.schema.json", "$defs", "kb_gap",
                           "properties", "kind", "enum"))


def purposes() -> tuple[str, ...]:
    return tuple(_contract("schemas/goal.schema.json", "properties", "purpose", "enum"))


def overlap_values() -> tuple[str, ...]:
    """The overlap verdicts a `coverage` entry may carry, read from the contract.

    This was a hardcoded tuple until 2026-09-19 and it broke twice the same
    way: `coverage` verdicts are validated against it and a rejected record
    FAILS THE CALL, so an overlap value that reaches the server and not this
    list stops every query that produces it. `unstated` did it once, found by
    a test. `disjoint` did it again within the day, found by the first run
    after the change -- and that time the value had been agreed in the schema
    first, so the copy here was already stale when it was written.

    Two lists in two files that have to agree is one list too many. This reads
    `kb_gap.nearest[].overlap` and adds the two verdicts that exist on a row
    and cannot reach `nearest`, which the contract's own description names:
    `full`, nothing uncovered, and `unstated`, the entry declares no
    conditions at all. Those two stay written here rather than derived because
    they have no home in the schema -- the row shape belongs to this module
    and the gap shape to the contract -- and saying so is better than leaving
    a silent second source of truth.

    `unconstrained` is gone without an edit here. It was this enum's name for
    `no_overlap`, kept while cards migrated; manager-librarian verified that
    no card on disk still carries it and dropped it in 5908649, closing an
    expand-migrate-contract that had been open since 2026-09-18. Deriving is
    what makes the contract step land here for free.
    """
    nearest = contract_first(
        ("schemas/common.schema.json",
         ("$defs", "kb_gap", "properties", "nearest", "items", "properties", "overlap", "enum")),
        ("schemas/common.schema.json", ("$defs", "overlap", "enum")),
    )
    return tuple(nearest) + ("full", "unstated")


def caller_id_pattern() -> str:
    return contract_first(
        ("schemas/common.schema.json", ("$defs", "caller_id", "pattern")),
        ("schemas/axis.schema.json", ("properties", "caller_id", "pattern")),
    )


class Rejected(ValueError):
    """A record that would have made the log unreadable or untrue."""


def check(rec: dict, *, writing: bool = False) -> dict:
    """Validate one record. A log that accepts anything documents nothing.

    `writing` separates what a NEW line must carry from what an old one may
    lack. `server_session` arrived on 2026-09-19 with sixty-one lines already
    on disk, and requiring it of those would have made verify() report the
    whole history as malformed -- expand, migrate, contract, which this seat
    has invoked at three other seats and broke here on its own first field.
    """
    unknown = sorted(set(rec) - set(FIELDS))
    if unknown:
        raise Rejected(f"unknown fields {unknown}; the record shape is fixed so the log stays countable")

    if rec.get("outcome") == "refused":
        expected = set(REFUSAL_FIELDS) if writing else set(REFUSAL_FIELDS) - {"server_session"}
        missing = sorted(expected - set(rec))
        if missing:
            raise Rejected(f"a refusal is missing {missing}")
        asserted = sorted(set(rec) - set(REFUSAL_FIELDS))
        if asserted:
            raise Rejected(
                f"a refusal carries {asserted}, which assert what the server refused to accept. "
                "Everything as given goes under `claimed`, so a caller_id the launcher never "
                "issued is never recorded as one that it did."
            )
        if not isinstance(rec.get("claimed"), dict):
            raise Rejected("`claimed` is the arguments as given and has to be an object")
        if not str(rec.get("reason") or "").strip():
            raise Rejected("a refusal without a reason records that something failed and not what")
        return rec
    needed = ["asked_at", "caller_id", "kb_version", "tool", "purpose"]
    if writing:
        needed.append("server_session")
    for f in needed:
        if not rec.get(f):
            raise Rejected(f"{f} is required: a line without it cannot be attributed or replayed")
    if rec["tool"] not in TOOLS:
        raise Rejected(f"tool {rec['tool']!r} is not one of the four read-only tools {TOOLS}")
    if not re.match(caller_id_pattern(), rec["caller_id"]):
        raise Rejected(f"caller_id {rec['caller_id']!r} is not <qid>:<config>:<axis> as the launcher issues it (4.3.1)")
    if rec["purpose"] not in purposes():
        raise Rejected(f"purpose {rec['purpose']!r} is not in contracts/schemas/goal.schema.json")
    kinds = gap_kinds()
    for g in rec.get("gaps") or []:
        if g not in kinds:
            raise Rejected(f"gap kind {g!r} is not in contracts/schemas/common.schema.json ({kinds})")
    for r in rec.get("returned") or []:
        if r.get("grade") == "E6":
            raise Rejected(f"entry {r.get('entry_id')!r} logged as E6; E6 is in no entry, so a line claiming one is wrong (5.3)")
    for quantity, verdict in (rec.get("coverage") or {}).items():
        allowed = overlap_values()
        if verdict not in allowed:
            raise Rejected(f"coverage of {quantity!r} is {verdict!r}, not one of {allowed}: matching says whether it covers, never what to do (4.3.1)")
    return rec


def record_refusal(log: Path, tool: str, reason: str, server_session: str = "", **claimed) -> dict:
    """Append a refusal. Nothing in `claimed` is validated, and its name says so."""
    return record(log, tool=tool, outcome="refused", reason=reason,
                  server_session=server_session,
                  claimed={k: v for k, v in claimed.items() if v is not None})


def record(log: Path = DEFAULT_LOG, **rec) -> dict:
    """Append one line. Returns the record as written."""
    rec.setdefault("asked_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    check(rec, writing=True)
    if not log.parent.exists():
        raise Rejected(
            f"{log.parent} does not exist, and this module will not create it. "
            "librarian_agent/queries/ is a declared path (check 13 in "
            "contracts/validate.py) and is kept in git by its README; a "
            "directory missing here means something removed it, and writing to "
            "a path the repository does not admit fails the repository rather "
            "than recording anything."
        )
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
    return rec


def _query_key(rec: dict) -> str:
    """What the answer may depend on, and nothing else.

    The tool, the pinned version and the question -- plus the caller's AGENT,
    which is the prefix of the caller_id and not the whole of it. 4.3.1 rule 1
    isolates by caller_id and permits per-caller context; rule 2 forbids the
    answer depending on call history. An agent is neither: it is an argument,
    and one answer legitimately varies with it -- a gap pointing into a
    published table names the asker's own snapshot only when that agent holds
    a copy, while the table and its sha256 are the same fact for everyone.

    Keying on the whole caller_id would make this witness useless, because
    every axis of every fan-out has its own id and no two lines would ever be
    compared. Keying on none of it called a legitimate difference a violation:
    that is how the first version of the published-table lookup was caught,
    which answered `absent` to a simulation and `in_published_table` to a
    microscope for one question -- a real defect. Two axes of one agent asking
    one question at one version must still agree, and that is the property a
    fan-out depends on.
    """
    agent = str(rec.get("caller_id", "")).split("-", 1)[0]
    return json.dumps([rec["tool"], rec["kb_version"], agent, rec.get("observable"),
                       rec.get("condition_range")], sort_keys=True)


def _answer_key(rec: dict) -> str:
    return json.dumps([rec.get("returned"), rec.get("gaps"), rec.get("coverage")], sort_keys=True)


def verify(log: Path = DEFAULT_LOG) -> list[str]:
    """Audit the log offline. Returns one line per problem; empty means clean."""
    if not log.exists():
        return []      # an absent log is not a corrupt one; main() says so separately
    problems: list[str] = []
    seen: dict[str, tuple[int, str, str]] = {}
    last = ""
    for n, line in enumerate(log.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = check(json.loads(line))
        except (json.JSONDecodeError, Rejected) as exc:
            problems.append(f"line {n}: {exc}")
            continue
        if rec["asked_at"] < last:
            problems.append(f"line {n}: asked_at {rec['asked_at']} precedes line above; an append-only log does not go backwards")
        last = rec["asked_at"]
        if rec.get("outcome") == "refused":
            continue      # nothing was answered, so there is no answer to compare
        qk, ak = _query_key(rec), _answer_key(rec)
        if qk in seen and seen[qk][1] != ak:
            # Name the query and both answers. A violation that says only
            # "line 7 and line 13 differ" makes the reader reconstruct which
            # question it was, and this report exists to be acted on.
            problems.append(
                f"line {n}: same query at the same kb_version as line {seen[qk][0]} returned something "
                f"different. query={qk}; then={seen[qk][1]}; now={ak}. "
                "4.3.1 requires one answer per (query, kb_version); this is that guarantee failing"
            )
        elif qk not in seen:
            seen[qk] = (n, ak, rec["caller_id"])
    return problems


_AXIS_RE = re.compile(r"^a[1-7]$")
_REV_RE = re.compile(r"^v[0-9]+$")


def _fanout_of(caller_id: str) -> tuple[tuple[str, str, str] | None, str | None]:
    """Split an axis caller_id into its fan-out and its axis.

    Returns ((qid, revision, config), axis) for the config-axis form, and
    (None, None) for everything else -- s2, operator, bridge and selftest are
    not siblings of anything, so they have no fan-out to disagree within.

    The un-versioned axis form gets (None, None) too, and that is the point
    rather than an omission. `mic-20260918-001:widefield_inline:a4` names no
    revision, so it cannot be told from the a4 of a re-plan, and grouping it
    with v1 would be a guess written into a finding. common.schema.json accepts
    that form only "while the cards that predate a6dca6a migrate"; until the
    migration finishes those calls are simply outside this witness, which
    `retired_caller_form` reports so the absence is visible rather than silent.
    """
    parts = caller_id.split(":")
    if len(parts) < 3 or parts[0] in ("bridge", "selftest"):
        return None, None
    qid, rest = parts[0], parts[1:]
    if not _REV_RE.match(rest[0]):
        return None, None
    rev, rest = rest[0], rest[1:]
    if len(rest) == 2 and _AXIS_RE.match(rest[1]):
        return (qid, rev, rest[0]), rest[1]
    return None, None


def fanout_pins(log: Path = DEFAULT_LOG) -> list[str]:
    """Siblings of one fan-out that read different stores.

    A separate property from the one `verify` witnesses, and invisible to it
    on purpose: `_query_key` folds the caller down to its AGENT, so two axes of
    one fan-out are the same key there and their pins are never compared. The
    rule this checks is stated in librarian_agent/CLAUDE.md -- pin kb_version
    for the whole fan-out and do not move the store mid-flight -- and until now
    nothing tested it. It is worth a witness because no caller can see it: an
    axis knows its own pin and never its siblings', and the server is the only
    place both appear.

    Why this reports rather than fails. The pin is chosen by the fan-out
    launcher, which is not this seat; a check that fails for something the
    reader cannot fix gets suppressed, and then the determinism witness beside
    it gets suppressed with it. `--strict` promotes it, the same way
    contracts/validate.py promotes undecided.
    """
    if not log.exists():
        return []
    pins: dict[tuple[str, str, str], dict[str, list[str]]] = {}
    when: dict[tuple[tuple[str, str, str], str], list[str]] = {}
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue          # verify() owns malformed lines; do not report twice
        if rec.get("outcome") == "refused" or not rec.get("kb_version"):
            continue
        fan, axis = _fanout_of(str(rec.get("caller_id", "")))
        if fan is None:
            continue
        pins.setdefault(fan, {}).setdefault(rec["kb_version"], [])
        if axis not in pins[fan][rec["kb_version"]]:
            pins[fan][rec["kb_version"]].append(axis)
        when.setdefault((fan, rec["kb_version"]), []).append(rec["asked_at"])
    problems = []
    for fan, versions in sorted(pins.items()):
        if len(versions) < 2:
            continue
        qid, rev, config = fan
        detail = "; ".join(
            f"{v} read by {sorted(axes)} ({min(when[(fan, v)])} to {max(when[(fan, v)])})"
            for v, axes in sorted(versions.items())
        )
        problems.append(
            f"fan-out {qid}:{rev}:{config} read {len(versions)} stores: {detail}. "
            "Siblings pinned to different kb_versions did not see the same knowledge, "
            "so the fan-out's axes are not comparable and the difference is itself a "
            "channel between them"
        )
    return problems


def retired_caller_form(log: Path = DEFAULT_LOG) -> list[str]:
    """Axis calls still arriving without a revision, and when they last did.

    common.schema.json accepts `<qid>:<config>:<axis>` only while cards that
    predate a6dca6a migrate, and says it stops being accepted after. Whoever
    tightens that pattern needs to know the migration is finished, and this log
    is the only place that is observable. Reports the latest use, because a
    form last seen yesterday and one still being issued this hour are different
    decisions.
    """
    if not log.exists():
        return []
    latest: dict[str, str] = {}
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        cid = str(rec.get("caller_id", ""))
        parts = cid.split(":")
        if len(parts) == 3 and not _REV_RE.match(parts[1]) and _AXIS_RE.match(parts[2]):
            latest[cid] = max(latest.get(cid, ""), rec.get("asked_at", ""))
    return [f"{cid} carries no revision; last used {ts}" for cid, ts in sorted(latest.items())]


def _self_test() -> int:
    """Exercise the module without writing into the store."""
    import tempfile

    ok = True
    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "log.jsonl"
        base = dict(caller_id="mic-20260917-001:v1:transmitted:a2", kb_version="kbv-c6aab372060a",
                    server_session="srv-selftest-0",
                    tool="kb_query", purpose="screen", observable="tracer_diffusivity",
                    condition_range={"temperature": {"min": 288, "max": 298, "unit": "K"}},
                    returned=[{"entry_id": "water_viscosity_293k", "grade": "E3"}],
                    gaps=[], coverage={"temperature": "full"})
        record(log, **base)
        record(log, **dict(base, asked_at="2099-01-01T00:00:00+00:00"))
        if verify(log):
            print("FAIL: a clean log reported problems:", verify(log)); ok = False

        for bad, why in [
            (dict(base, caller_id="librarian"), "a caller_id the launcher would not issue"),
            (dict(base, purpose="curiosity"), "a purpose outside the enum"),
            (dict(base, returned=[{"entry_id": "x", "grade": "E6"}]), "an E6 entry"),
            (dict(base, coverage={"temperature": "close enough"}), "a coverage verdict that is advice"),
            (dict(base, note="extra"), "a field the shape does not have"),
        ]:
            try:
                record(log, **bad)
                print(f"FAIL: accepted {why}"); ok = False
            except Rejected:
                pass

        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(base, asked_at="2099-01-02T00:00:00+00:00",
                                     returned=[{"entry_id": "tau_d", "grade": "E4"}]), sort_keys=True) + "\n")
        found = verify(log)
        if not any("returned something different" in p for p in found):
            print("FAIL: a determinism violation went unnoticed:", found); ok = False

        # The fan-out pin witness, on a log of its own so the determinism
        # fixture above does not have to stay pin-clean as well.
        fan = Path(d) / "fanout.jsonl"
        sib = dict(base, observable="tracer_diffusivity")
        for axis, ver in [("a1", "kbv-aaaaaaaaaaaa"), ("a2", "kbv-aaaaaaaaaaaa"),
                          ("a3", "kbv-bbbbbbbbbbbb")]:
            record(fan, **dict(sib, caller_id=f"mic-20260917-001:v1:transmitted:{axis}",
                               kb_version=ver))
        split = fanout_pins(fan)
        if len(split) != 1 or "a3" not in split[0] or "kbv-bbbbbbbbbbbb" not in split[0]:
            print("FAIL: a fan-out reading two stores was not reported:", split); ok = False
        if any("v2" in x for x in split):
            print("FAIL: reported a fan-out that does not exist:", split); ok = False

        # A different REVISION of the same question is a different fan-out and
        # may legitimately repin -- that is what v<N> is for. Regression: an
        # earlier draft keyed on (qid, config) and called every re-plan a split.
        agree = Path(d) / "agree.jsonl"
        for cid, ver in [("mic-20260917-001:v1:transmitted:a1", "kbv-aaaaaaaaaaaa"),
                         ("mic-20260917-001:v2:transmitted:a1", "kbv-bbbbbbbbbbbb"),
                         ("mic-20260917-001:v1:confocal:a1", "kbv-cccccccccccc"),
                         ("mic-20260917-001:v1:s2", "kbv-dddddddddddd"),
                         ("mic-20260917-001:v1:operator", "kbv-eeeeeeeeeeee"),
                         ("bridge:thr-mic-sim-001:r1", "kbv-ffffffffffff"),
                         ("selftest:pins", "kbv-000000000000")]:
            record(agree, **dict(sib, caller_id=cid, kb_version=ver))
        if fanout_pins(agree):
            print("FAIL: called a repin, another config, or a non-axis caller a split:",
                  fanout_pins(agree)); ok = False

        # The un-versioned form is reported as unattributable, never folded in.
        # Two of these with different pins must NOT become a fan-out finding:
        # which revision each belonged to is exactly what is not on record.
        oldform = Path(d) / "oldform.jsonl"
        for cid, ver in [("mic-20260917-001:transmitted:a1", "kbv-aaaaaaaaaaaa"),
                         ("mic-20260917-001:transmitted:a2", "kbv-bbbbbbbbbbbb")]:
            record(oldform, **dict(sib, caller_id=cid, kb_version=ver))
        if fanout_pins(oldform):
            print("FAIL: guessed a revision for an id that carries none:",
                  fanout_pins(oldform)); ok = False
        if len(retired_caller_form(oldform)) != 2:
            print("FAIL: the retired form went unreported:",
                  retired_caller_form(oldform)); ok = False
        if retired_caller_form(agree):
            print("FAIL: reported a current-form id as retired:",
                  retired_caller_form(agree)); ok = False

        missing = Path(d) / "undeclared" / "log.jsonl"
        try:
            record(missing, **base)
            print("FAIL: created an undeclared directory"); ok = False
        except Rejected:
            pass

    print("self-test: ok" if ok else "self-test: FAILED")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", type=Path, default=DEFAULT_LOG)
    ap.add_argument("--verify", action="store_true", help="audit the log: shape, ordering, and one answer per (query, kb_version)")
    ap.add_argument("--self-test", action="store_true", help="exercise record and verify in a temporary directory")
    ap.add_argument("--strict", action="store_true",
                    help="count fan-out pin splits as failures, not reports (they are another seat's to fix)")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    if args.verify:
        if not args.path.exists():
            print(f"{args.path} has not been created yet: nothing to audit")
            return 0
        problems = verify(args.path)
        for p in problems:
            print(p)
        print(f"{args.path}: {len(problems)} problems" if problems else f"{args.path}: clean")

        # Reported below the verdict, never folded into it. These two are the
        # launcher's and the contract's to act on; printing them as failures
        # here would make this command fail for something its reader cannot
        # fix, and a check like that gets silenced along with the one above it.
        splits = fanout_pins(args.path)
        for s_ in splits:
            print(f"REPORT {s_}")
        for s_ in retired_caller_form(args.path):
            print(f"REPORT {s_}")
        return 1 if problems or (splits and args.strict) else 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
