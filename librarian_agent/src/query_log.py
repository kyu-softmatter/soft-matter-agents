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
# Expand, migrate, contract -- the same transition the schema is in. The
# overlap value `unconstrained` became `no_overlap` because one word was
# naming both a value and a field; a card belonging to another seat still
# carries the old one, so both are accepted until the last holder moves.
# This tuple is not cosmetic: `coverage` verdicts are checked against it and
# a rejected record fails the call, so renaming the server without renaming
# here would have stopped every query that found no overlap.
OVERLAP = ("full", "partial", "no_overlap", "unstated", "unconstrained")
# `unstated` joined on 2026-09-19: the entry declares no conditions at all,
# which is a different answer from declaring some that miss. This tuple has
# now caught the same coupling twice -- it validates `coverage`, and a
# rejected record fails the call, so a new overlap value that lands in the
# server and not here stops every query that produces it. The first time it
# was found by a test; this time by the first run after the change.
FIELDS = ("asked_at", "caller_id", "kb_version", "tool", "purpose",
          "observable", "condition_range", "returned", "gaps", "coverage")


def _contract(path: str, *keys):
    """Read a registry out of contracts/ rather than restating it here (P3)."""
    node = json.loads((CONTRACTS / path).read_text())
    for k in keys:
        node = node[k]
    return node


def purposes() -> tuple[str, ...]:
    return tuple(_contract("schemas/goal.schema.json", "properties", "purpose", "enum"))


def caller_id_pattern() -> str:
    return _contract("schemas/axis.schema.json", "properties", "caller_id", "pattern")


class Rejected(ValueError):
    """A record that would have made the log unreadable or untrue."""


def check(rec: dict) -> dict:
    """Validate one record. A log that accepts anything documents nothing."""
    unknown = sorted(set(rec) - set(FIELDS))
    if unknown:
        raise Rejected(f"unknown fields {unknown}; the record shape is fixed so the log stays countable")
    for f in ("asked_at", "caller_id", "kb_version", "tool", "purpose"):
        if not rec.get(f):
            raise Rejected(f"{f} is required: a line without it cannot be attributed or replayed")
    if rec["tool"] not in TOOLS:
        raise Rejected(f"tool {rec['tool']!r} is not one of the four read-only tools {TOOLS}")
    if not re.match(caller_id_pattern(), rec["caller_id"]):
        raise Rejected(f"caller_id {rec['caller_id']!r} is not <qid>:<config>:<axis> as the launcher issues it (4.3.1)")
    if rec["purpose"] not in purposes():
        raise Rejected(f"purpose {rec['purpose']!r} is not in contracts/schemas/goal.schema.json")
    for r in rec.get("returned") or []:
        if r.get("grade") == "E6":
            raise Rejected(f"entry {r.get('entry_id')!r} logged as E6; E6 is in no entry, so a line claiming one is wrong (5.3)")
    for quantity, verdict in (rec.get("coverage") or {}).items():
        if verdict not in OVERLAP:
            raise Rejected(f"coverage of {quantity!r} is {verdict!r}, not one of {OVERLAP}: matching says whether it covers, never what to do (4.3.1)")
    return rec


def record(log: Path = DEFAULT_LOG, **rec) -> dict:
    """Append one line. Returns the record as written."""
    rec.setdefault("asked_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    check(rec)
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
    """What 4.3.1 says must determine the answer, and nothing else."""
    return json.dumps([rec["tool"], rec["kb_version"], rec.get("observable"),
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
        qk, ak = _query_key(rec), _answer_key(rec)
        if qk in seen and seen[qk][1] != ak:
            problems.append(
                f"line {n}: same query at the same kb_version as line {seen[qk][0]} returned something different. "
                "4.3.1 requires one answer per (query, kb_version); this is that guarantee failing"
            )
        elif qk not in seen:
            seen[qk] = (n, ak, rec["caller_id"])
    return problems


def _self_test() -> int:
    """Exercise the module without writing into the store."""
    import tempfile

    ok = True
    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "log.jsonl"
        base = dict(caller_id="mic-20260917-001:transmitted:a2", kb_version="kbv-c6aab372060a",
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
        return 1 if problems else 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
