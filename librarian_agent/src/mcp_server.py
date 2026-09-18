#!/usr/bin/env python3
"""The librarian's read-only MCP server: four tools, and nothing that writes.

Sub-agents query this instead of passing files, which is what makes S3's
fan-out (configuration x axis, up to 21 branches) practical (4.3.1, D9).

The core here is a plain library -- `Store` and four functions -- with the MCP
transport bolted on at the bottom. That split is not tidiness: the matching
rules and the ordering are the part that has to be deterministic, and they are
testable only if answering does not require a running server. `--self-test`
exercises them with no transport at all.

**Four tools, and no fifth.** `kb_group` is separate from `kb_query` because a
formula is looked up by SYMBOL, wants a definition rather than a value, and
takes no condition range. Folding it in would make the return shape depend on
the arguments, and every caller would grow a branch (4.3.1). It serves BOTH
formula-carrying kinds -- a `dimensionless_group`, which asserts a pure number,
and a `derived_quantity`, which keeps a dimension and names it in `unit`. The
tool is keyed on the symbol, not on the kind: a caller asking what `tau_d` means
is asking the same question whichever of the two it turns out to be, and the
answer carries `dimensionless` so nobody has to infer it from a missing field.

**No write tool exists.** External search, distillation, and writing or retiring
entries happen in the librarian session only. A sub-agent that could write to
the KB would make an undistilled value the authority immediately (4.3.1).

## The four rules, and how each is enforced here

1. **Isolation is by `caller_id`, never by `qid`.** This server is *stateless*.
   4.3.1 permits per-`caller_id` state and requires only that the isolation unit
   be right; keeping none is the strongest form of that, because a leak needs a
   place to live. Siblings share a `qid`, which is exactly why the unit may not
   be one.
2. **Determinism.** Same `(query, kb_version)`, same answer, forever. Nothing
   consults call history. `kb_version` is checked rather than assumed: a caller
   pinning a version this store is not at is REFUSED, not quietly answered at
   today's version. The pin exists so a fan-out's siblings read one KB, and
   answering the wrong one silently would defeat it.
3. **The id is issued, not chosen.** `caller_id` must match the contract's
   pattern -- `<qid>:<config>:<axis>`, injected by the fan-out launcher. This
   server can reject a malformed id and cannot verify that the launcher issued
   a well-formed one; that rule lives at the launcher, and saying so here is
   better than implying a check nobody performs.
4. **Global statistics never touch the answer.** Every call is logged through
   `query_log`, which offers no function that reads the log back by caller, by
   observable or by count. There is nothing for answering code to consult.

**Determinism includes ordering.** Entries come back sorted by grade, then by
the rank inside E3 (`peer_reviewed -> textbook -> vendor_spec -> preprint`),
then by `entry_id`. That sort is the only place 4.3's citation preference
actually runs -- until now it was a sentence no code read.

## Matching says whether it covers, never what to do about it

Full containment is `full`; a partial intersection is `partial` with the
uncovered part named; a quantity the query did not mention comes back flagged
rather than assumed satisfied. Nothing is clipped, interpolated, extrapolated or
averaged here -- that judgement belongs to the caller and gets recorded in their
plan (4.3).

An unlogged answer is treated as worse than no answer: if `query_log.record`
fails, the call fails. The log is the only record that the service was asked
something, and a silent hole in it is the failure it exists to prevent.

    python3 librarian_agent/src/mcp_server.py --self-test
    python3 librarian_agent/src/mcp_server.py --serve        # stdio MCP
"""

from __future__ import annotations

import argparse
import functools
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import query_log                                            # noqa: E402

AGENT = Path(__file__).resolve().parent.parent
CONTRACTS = AGENT.parent / "contracts"

GRADE_ORDER = ["E1", "E2", "E3", "E4", "E5", "E6"]
E3_RANK = {"peer_reviewed": 0, "textbook": 1, "vendor_spec": 2, "preprint": 3}
TOOLS = ("kb_query", "kb_get", "kb_conflicts", "kb_group")


class Refused(Exception):
    """A query this server will not answer, with the reason a caller can act on."""


# --------------------------------------------------------------------------- #
# units: the registry is authoritative, and dimensions are not crossed
# --------------------------------------------------------------------------- #

_UNITS = json.loads((CONTRACTS / "units.json").read_text())["units"]


def _si(value: float, unit: str) -> tuple[float, tuple]:
    u = _UNITS.get(unit)
    if u is None:
        raise Refused(f"unit {unit!r} is not in contracts/units.json, which is the registry (5.7)")
    if u.get("si_factor") is None:
        raise Refused(f"unit {unit!r} has no plain conversion (it needs a temperature), so it cannot bound a condition")
    return value * u["si_factor"], tuple(sorted(u["dim"].items()))


def _ge(a: float, b: float) -> bool:
    """a >= b, tolerating only what the conversion to SI cost.

    0.17 mm and 170 um are the same length and do not compare equal as floats:
    0.17 * 1e-3 and 170 * 1e-6 differ in the last bit. The tolerance here is a
    float-representation tolerance and NOT a physical one -- it is relative,
    twelve orders below the value, far under any measurement this store holds.
    A physical tolerance would be a judgement about what counts as close
    enough, which is the caller's to make and gets recorded in their plan.
    """
    return a >= b or math.isclose(a, b, rel_tol=1e-12, abs_tol=0.0)


def _interval_si(bound: dict, where: str) -> tuple[float, float, tuple]:
    """One quantity's interval in SI, as (min, max, dimension). Absent side is open."""
    unit = bound.get("unit")
    if not unit:
        raise Refused(f"{where}: an interval without a unit is not an interval (P2)")
    lo = bound.get("min")
    hi = bound.get("max")
    if lo is None and hi is None:
        raise Refused(f"{where}: an interval needs at least one of min or max")
    lo_si, dim = _si(lo if lo is not None else 0.0, unit)
    hi_si, _ = _si(hi if hi is not None else 0.0, unit)
    return (lo_si if lo is not None else float("-inf"),
            hi_si if hi is not None else float("inf"), dim)


# --------------------------------------------------------------------------- #
# the store
# --------------------------------------------------------------------------- #

class Store:
    """Entries and the index, loaded once. Read-only by construction."""

    def __init__(self, kb: Path | None = None, log: Path | None = None):
        self.kb = kb or (AGENT / "kb")
        self.log = log if log is not None else query_log.DEFAULT_LOG
        index_path = self.kb / "index.json"
        if not index_path.exists():
            raise Refused(f"{index_path} is missing; rebuild it with src/kb_index.py")
        self.index = json.loads(index_path.read_text())
        self.kb_version = self.index.get("kb_version")
        self.entries: dict[str, dict] = {}
        for p in sorted((self.kb / "entries").glob("*.json")):
            e = json.loads(p.read_text())
            self.entries[e["entry_id"]] = e
        stale = sorted(set(self.entries) ^ set(self.index.get("entries") or {}))
        if stale:
            raise Refused(f"index.json does not match entries/ ({stale}); rebuild it with src/kb_index.py")

    # -- what an entry is about ------------------------------------------- #

    def subjects(self, e: dict) -> set[str]:
        """The names this entry answers to.

        An entry has no field saying what it is ABOUT -- no observable id, no
        subject -- so the only declared names available are its own id, its
        symbol if it is a group, and the names in `numbers[]`. Matching on those
        is deterministic and explainable, and it is string identity rather than a
        declared relation: `contracts/observables.json` ids such as
        `tracer_diffusivity` live in a different namespace from a number named
        `viscosity`, and nothing links them. That missing field is raised with
        the manager rather than papered over with a text search here.
        """
        names = {e["entry_id"]}
        if e.get("symbol"):
            names.add(e["symbol"])
        for n in e.get("numbers") or []:
            if n.get("name"):
                names.add(n["name"])
        return names

    # -- ordering ---------------------------------------------------------- #

    def sort_key(self, entry_id: str) -> tuple:
        e = self.entries[entry_id]
        grade = e.get("grade", "E6")
        rank = E3_RANK.get(e.get("grade_tag"), len(E3_RANK)) if grade == "E3" else 0
        return (GRADE_ORDER.index(grade) if grade in GRADE_ORDER else len(GRADE_ORDER),
                rank, entry_id)


# --------------------------------------------------------------------------- #
# matching
# --------------------------------------------------------------------------- #

def match(entry: dict, condition_range: dict | None) -> dict:
    """How an entry's validity stands against a query's conditions.

    Returns overlap plus what is NOT covered and what was not compared. It never
    says what to do about any of it.
    """
    validity = entry.get("validity") or {}
    query = condition_range or {}
    shared = sorted(set(validity) & set(query))
    unconstrained = sorted(set(query) - set(validity))   # the entry has no opinion
    unasked = sorted(set(validity) - set(query))         # the query was silent

    if not shared:
        return {"overlap": "unconstrained", "uncovered": {},
                "unconstrained": unconstrained, "unasked": unasked}

    uncovered: dict[str, dict] = {}
    for q in shared:
        e_lo, e_hi, e_dim = _interval_si(validity[q], f"entry {entry['entry_id']}, {q}")
        q_lo, q_hi, q_dim = _interval_si(query[q], f"query, {q}")
        if e_dim != q_dim:
            raise Refused(
                f"{q}: the entry bounds it in a {dict(e_dim)} unit and the query in a "
                f"{dict(q_dim)} one. Units convert only within one dimension; across "
                f"dimensions the query is refused rather than coerced (4.3.1 rule 4)"
            )
        if _ge(q_lo, e_lo) and _ge(e_hi, q_hi):
            continue
        out: dict[str, Any] = {"unit": query[q]["unit"]}
        if not _ge(q_lo, e_lo):
            out["below_min"] = query[q].get("min")
        if not _ge(e_hi, q_hi):
            out["above_max"] = query[q].get("max")
        if e_hi < q_lo or q_hi < e_lo:
            out["disjoint"] = True
        uncovered[q] = out

    return {"overlap": "full" if not uncovered else "partial",
            "uncovered": uncovered,
            "unconstrained": unconstrained, "unasked": unasked}


def grade_summary(store: Store, ids: list[str]) -> dict:
    counts: dict[str, int] = {}
    for i in ids:
        g = store.entries[i].get("grade", "E6")
        counts[g] = counts.get(g, 0) + 1
    worst = max((store.entries[i].get("grade", "E6") for i in ids),
                key=lambda g: GRADE_ORDER.index(g) if g in GRADE_ORDER else 99) if ids else None
    return {"counts": {g: counts[g] for g in GRADE_ORDER if g in counts},
            "worst": worst,
            "note": "a convenience only. The authority is each entry's own grade, and a card "
                    "cites entries rather than this summary -- citing a summary loses which "
                    "number carried which grade (4.3.1)"}


# --------------------------------------------------------------------------- #
# the four tools
# --------------------------------------------------------------------------- #

CALLER_ID = json.loads((CONTRACTS / "schemas" / "axis.schema.json").read_text(
))["properties"]["caller_id"]["pattern"]
PURPOSES = tuple(json.loads((CONTRACTS / "schemas" / "goal.schema.json").read_text(
))["properties"]["purpose"]["enum"])


def _preflight(store: Store, caller_id: str, kb_version: str, tool: str) -> None:
    if tool not in TOOLS:
        raise Refused(f"{tool!r} is not one of the four read-only tools {TOOLS}")
    if not isinstance(caller_id, str) or not re.match(CALLER_ID, caller_id):
        raise Refused(
            f"caller_id {caller_id!r} is not <qid>:<config>:<axis>. The launcher issues it and a "
            "sub-agent may not choose it (4.3.1 rule 3); a malformed one is refused here, and "
            "that an issued-looking id really came from the launcher is enforced there, not here"
        )
    if kb_version != store.kb_version:
        raise Refused(
            f"this store is at {store.kb_version} and the call pins {kb_version!r}. Refused rather "
            "than answered at today's version: the pin exists so a fan-out's siblings read one KB "
            "(4.3.1 rule 2), and an older version is confirmable only from the store's git history"
        )


def _log(store: Store, **rec) -> None:
    """An unlogged answer is worse than no answer, so a log failure fails the call."""
    query_log.record(store.log, **rec)


def kb_query(store: Store, caller_id: str, kb_version: str, observable: str,
             condition_range: dict | None = None, purpose: str = "screen") -> dict:
    _preflight(store, caller_id, kb_version, "kb_query")
    if purpose not in PURPOSES:
        raise Refused(f"purpose {purpose!r} is not in contracts/schemas/goal.schema.json")

    hits = sorted((eid for eid, e in store.entries.items() if observable in store.subjects(e)),
                  key=store.sort_key)
    returned, nearest = [], []
    for eid in hits:
        e = store.entries[eid]
        m = match(e, condition_range)
        row = {"entry_id": eid, "grade": e["grade"], "grade_tag": e.get("grade_tag"),
               "claim": e["claim"], "numbers": e.get("numbers") or [],
               "validity": e.get("validity"), "validity_conditions": e["validity_conditions"],
               "identifiers": e.get("identifiers"), "source": e.get("source"),
               "source_ref": e["source_ref"], **m}
        returned.append(row)
        if m["overlap"] != "full":
            nearest.append({"entry_id": eid, "overlap": "partial" if m["uncovered"] else "unconstrained",
                             **({"uncovered": m["uncovered"]} if m["uncovered"] else {})})

    gaps = []
    covered = [r for r in returned if r["overlap"] == "full"]
    if not covered:
        gaps.append({
            "observable": observable,
            "condition_range": condition_range or {},
            "kind": "absent" if not returned else "condition_mismatch",
            "searched": ["kb/entries"],
            "nearest": nearest,
            "kb_version": store.kb_version,
            "asked_by": caller_id,
            "asked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note": "searched kb/entries only. This server does not search outside the store; "
                    "external search happens in the librarian session (4.3.1)",
        })

    answer = {"entries": returned, "gaps": gaps,
              "grade_summary": grade_summary(store, [r["entry_id"] for r in returned]),
              "kb_version": store.kb_version}
    _log(store, caller_id=caller_id, kb_version=kb_version, tool="kb_query", purpose=purpose,
         observable=observable, condition_range=condition_range,
         returned=[{"entry_id": r["entry_id"], "grade": r["grade"]} for r in returned],
         gaps=[g["kind"] for g in gaps],
         coverage={r["entry_id"]: r["overlap"] for r in returned})
    return answer


def kb_get(store: Store, caller_id: str, kb_version: str, entry_id: str,
           purpose: str = "screen") -> dict:
    _preflight(store, caller_id, kb_version, "kb_get")
    e = store.entries.get(entry_id)
    _log(store, caller_id=caller_id, kb_version=kb_version, tool="kb_get", purpose=purpose,
         observable=entry_id,
         returned=[{"entry_id": entry_id, "grade": e["grade"]}] if e else [],
         gaps=[] if e else ["absent"], coverage={})
    if e is None:
        raise Refused(f"no entry {entry_id!r} at {store.kb_version}")
    return {"entry": e, "sha256": (store.index.get("entries") or {}).get(entry_id, {}).get("sha256"),
            "kb_version": store.kb_version}


def kb_conflicts(store: Store, caller_id: str, kb_version: str, topic: str = "",
                 purpose: str = "troubleshoot") -> dict:
    _preflight(store, caller_id, kb_version, "kb_conflicts")
    pairs, seen = [], set()
    for eid in sorted(store.entries, key=store.sort_key):
        e = store.entries[eid]
        for other in e.get("conflict_with") or []:
            key = tuple(sorted((eid, other)))
            if key in seen:
                continue
            seen.add(key)
            o = store.entries.get(other)
            if topic and not (topic in store.subjects(e) or (o and topic in store.subjects(o))):
                continue
            pairs.append({
                "pair": list(key),
                "grades": {eid: e["grade"], **({other: o["grade"]} if o else {})},
                "dangling": None if o else other,
                "conditions": {eid: e.get("validity_conditions"),
                               **({other: o.get("validity_conditions")} if o else {})},
            })
    _log(store, caller_id=caller_id, kb_version=kb_version, tool="kb_conflicts", purpose=purpose,
         observable=topic or None, returned=[], gaps=[], coverage={})
    return {"pairs": pairs, "kb_version": store.kb_version,
            "note": "both sides of a conflict are kept and neither is merged away (4.3 rule 6); "
                    "which one applies is decided by the conditions, by the caller"}


def kb_group(store: Store, caller_id: str, kb_version: str, symbol: str,
             purpose: str = "screen") -> dict:
    _preflight(store, caller_id, kb_version, "kb_group")
    formula_kinds = ("dimensionless_group", "derived_quantity")
    hits = sorted((eid for eid, e in store.entries.items()
                   if e.get("kind") in formula_kinds and e.get("symbol") == symbol),
                  key=store.sort_key)
    _log(store, caller_id=caller_id, kb_version=kb_version, tool="kb_group", purpose=purpose,
         observable=symbol,
         returned=[{"entry_id": i, "grade": store.entries[i]["grade"]} for i in hits],
         gaps=[] if hits else ["absent"], coverage={})
    if not hits:
        raise Refused(f"no formula carries the symbol {symbol!r} at {store.kb_version}")
    if len(hits) > 1:
        raise Refused(f"symbol {symbol!r} is defined by {hits}; a symbol defining two formulas is "
                      "a collision the store must resolve, not a choice for a caller (5.7, check 36)")
    e = store.entries[hits[0]]
    return {"entry_id": e["entry_id"], "symbol": e["symbol"], "formula": e.get("formula"),
            "inputs": e.get("inputs") or [], "grade": e["grade"],
            "kind": e["kind"],
            "dimensionless": e["kind"] == "dimensionless_group",
            "unit": e.get("unit"),
            "validity_conditions": e["validity_conditions"], "validity": e.get("validity"),
            "kb_version": store.kb_version,
            "note": "a definition, not a value: it carries a formula and takes no condition "
                    "range (4.3.1). `dimensionless` is stated rather than left to be inferred "
                    "from a missing unit -- absent and pure-number are different claims, and "
                    "tau_d spent its first day filed as the second while being the first"}


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

def _self_test() -> int:                                    # noqa: C901
    import tempfile

    ok = True

    def bad(why: str) -> None:
        nonlocal ok
        print(f"FAIL: {why}")
        ok = False

    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "log.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        store = Store(log=log)
        cid = "mic-20260917-001:transmitted:a2"
        v = store.kb_version

        # 1. a covering condition comes back full
        r = kb_query(store, cid, v, "viscosity", {"temperature": {"min": 291, "max": 295, "unit": "K"}})
        got = [e["entry_id"] for e in r["entries"]]
        if got != ["water_viscosity_293k"]:
            bad(f"expected the viscosity entry, got {got}")
        elif r["entries"][0]["overlap"] != "full":
            bad(f"291-295 K inside 288-298 K should be full, got {r['entries'][0]['overlap']}")
        elif r["gaps"]:
            bad("a fully covered query produced a gap")

        # 2. a wider condition is partial, names what is uncovered, and opens a gap
        r = kb_query(store, cid, v, "viscosity", {"temperature": {"min": 280, "max": 320, "unit": "K"}})
        e0 = r["entries"][0]
        if e0["overlap"] != "partial":
            bad(f"280-320 K should be partial, got {e0['overlap']}")
        if e0["uncovered"].get("temperature", {}).get("below_min") != 280:
            bad(f"uncovered should name 280 below the minimum: {e0['uncovered']}")
        if not r["gaps"] or r["gaps"][0]["kind"] != "condition_mismatch":
            bad(f"a partial-only answer is a condition_mismatch gap, got {r['gaps']}")
        if r["gaps"] and not r["gaps"][0]["searched"]:
            bad("a gap with an empty searched is not a gap")

        # 3. units convert inside a dimension and are refused across one
        r = kb_query(store, cid, v, "coverslip_thickness", {"coverslip_um": {"min": 0.17, "max": 0.17, "unit": "mm"}})
        if not r["entries"] or r["entries"][0]["overlap"] != "full":
            bad(f"0.17 mm is 170 um and should cover: {[(e['entry_id'], e['overlap']) for e in r['entries']]}")
        try:
            kb_query(store, cid, v, "viscosity", {"temperature": {"min": 1, "max": 2, "unit": "mm"}})
            bad("compared a temperature against a length")
        except Refused:
            pass

        # 4. silence is reported, never read as satisfaction
        r = kb_query(store, cid, v, "viscosity", {"bead_diameter": {"min": 1, "max": 2, "unit": "um"}})
        e0 = r["entries"][0]
        if e0["overlap"] != "unconstrained" or "bead_diameter" not in e0["unconstrained"]:
            bad(f"an entry with no opinion on bead_diameter should say so: {e0['overlap']}, {e0['unconstrained']}")
        if "temperature" not in e0["unasked"]:
            bad(f"the temperature the entry constrains and the query skipped should be flagged: {e0['unasked']}")

        # 5. ordering is grade, then the rank inside E3, then entry_id
        r = kb_query(store, cid, v, "na", {})
        got = [e["entry_id"] for e in r["entries"]]
        if got != sorted(got):
            bad(f"six vendor_spec E3 entries should fall back to entry_id order: {got}")
        keys = [store.sort_key(i) for i in store.entries]
        if keys != sorted(keys) and sorted(store.entries, key=store.sort_key) != [
                i for _, i in sorted((store.sort_key(i), i) for i in store.entries)]:
            bad("sort_key is not a total order")

        # 6. determinism: same query, same answer
        a = kb_query(store, cid, v, "viscosity", {"temperature": {"min": 291, "max": 295, "unit": "K"}})
        b = kb_query(store, "mic-20260917-001:confocal:a3", v,
                     "viscosity", {"temperature": {"min": 291, "max": 295, "unit": "K"}})
        strip = lambda x: json.dumps({k: x[k] for k in ("entries", "grade_summary")}, sort_keys=True)
        if strip(a) != strip(b):
            bad("two callers got different answers to one query at one kb_version")

        # 7. the pin is checked, not assumed
        try:
            kb_query(store, cid, "kbv-000000000000", "viscosity", {})
            bad("answered a call pinning a version this store is not at")
        except Refused:
            pass

        # 8. a caller may not choose its own id
        for wrong in ("librarian", "mic-20260917-001", "mic-20260917-001:transmitted:a9"):
            try:
                kb_query(store, wrong, v, "viscosity", {})
                bad(f"accepted caller_id {wrong!r}")
            except Refused:
                pass

        # 9. a symbol returns a definition, and says whether it is dimensionless.
        # tau_d is a derived_quantity, not a group: kb_group keys on the symbol
        # and must serve both formula-carrying kinds, or re-filing an entry
        # silently removes it from the only tool that looks formulas up.
        g = kb_group(store, cid, v, "tau_d")
        if g["formula"] != "bead_diameter**2/diffusivity" or g["grade"] != "E4":
            bad(f"kb_group returned {g}")
        if g["kind"] != "derived_quantity" or g["dimensionless"] or g["unit"] != "s":
            bad(f"a length squared over a diffusivity is a time: {g['kind']}, {g['unit']}")
        if any(e.get("kind") == "dimensionless_group" and e.get("unit") for e in store.entries.values()):
            bad("a dimensionless_group carries a unit, which contradicts its kind")
        try:
            kb_group(store, cid, v, "not_a_symbol")
            bad("invented a group")
        except Refused:
            pass

        # 10. kb_get is verbatim, and a miss is a refusal rather than an empty answer
        e = kb_get(store, cid, v, "tau_d")
        if e["entry"] != store.entries["tau_d"] or not e["sha256"]:
            bad("kb_get did not return the entry verbatim with its digest")
        try:
            kb_get(store, cid, v, "nope")
            bad("kb_get invented an entry")
        except Refused:
            pass

        # 11. conflicts: none recorded yet, and the shape holds
        c = kb_conflicts(store, cid, v)
        if c["pairs"]:
            bad(f"no entry names a conflict yet, so there are no pairs: {c['pairs']}")

        # 12. no write tool is exposed
        exported = {n for n in globals() if n.startswith("kb_")}
        if exported != set(TOOLS):
            bad(f"the module exposes {sorted(exported)}; only the four read-only tools may exist")

        # 13. every call was logged, and the log audits clean
        problems = query_log.verify(log)
        if problems:
            bad(f"the query log did not audit clean: {problems}")
        lines = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
        if {x["tool"] for x in lines} != set(TOOLS):
            bad(f"not every tool reached the log: {sorted({x['tool'] for x in lines})}")

        # The log counts ANSWERS, not attempts. A call refused in preflight
        # leaves no line, and for the malformed-id case it cannot leave one:
        # every record needs an attributable caller_id, and an unattributable
        # attempt has none. Asserting it here keeps the behaviour deliberate
        # rather than incidental -- if attempts need recording, that is a
        # different record with a different shape.
        before = len(lines)
        for attempt in [lambda: kb_query(store, "librarian", v, "viscosity", {}),
                        lambda: kb_query(store, cid, "kbv-000000000000", "viscosity", {})]:
            try:
                attempt()
            except Refused:
                pass
        after = len([x for x in log.read_text().splitlines() if x.strip()])
        if after != before:
            bad(f"a refused call left {after - before} lines; the log records answers, not attempts")

        # 14. an unlogged answer fails rather than returning quietly
        broken = Store(log=Path(d) / "gone" / "log.jsonl")
        try:
            kb_query(broken, cid, broken.kb_version, "viscosity", {})
            bad("answered without being able to log it")
        except query_log.Rejected:
            pass

        # 15. the transport registers the four tools WITH their arguments.
        # A wrapper taking **kwargs registers cleanly and tells a client the
        # tool takes nothing, which is why this asserts the parameters too.
        try:
            app = _build_app(store)
        except ImportError:
            print("note: no usable mcp package, so the transport was not exercised")
        else:
            import asyncio
            listed = asyncio.run(app.list_tools())
            names = {t.name for t in listed}
            if names != set(TOOLS):
                bad(f"the transport registered {sorted(names)}")
            for t_ in listed:
                schema = getattr(t_, "input_schema", None) or getattr(t_, "inputSchema", None) or {}
                props = set(schema.get("properties") or {})
                if not {"caller_id", "kb_version"} <= props:
                    bad(f"tool {t_.name} exposes {sorted(props)}; caller_id and kb_version are the wire contract")

    print("self-test: ok" if ok else "self-test: FAILED")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# transport
# --------------------------------------------------------------------------- #

def _build_app(store: Store):
    """Register the four tools on an MCP server, without running it.

    The adapters below exist for one reason: a wrapper taking `**kwargs` has no
    parameter schema, so a client would be told the tool takes nothing. The
    signatures here ARE the wire contract, which is why they are spelled out
    instead of forwarded.

    A refusal comes back as `{"refused": "..."}` rather than as a transport
    error. It is a legitimate answer -- this server will not answer that query,
    and here is the reason -- and the caller records the reason in their card.
    An exception would carry less and read as a broken server.
    """
    try:
        from mcp.server.mcpserver import MCPServer as _Server      # mcp 2.x
    except ImportError:                                            # pragma: no cover
        from mcp.server.fastmcp import FastMCP as _Server          # mcp 1.x

    def refusing(fn):
        # functools.wraps is load-bearing, not decoration: inspect.signature
        # follows __wrapped__, and without it the server publishes a tool whose
        # arguments are (*a, **kw) -- registered, callable, and undocumented.
        # The self-test asserts the parameters for exactly this reason.
        @functools.wraps(fn)
        def guard(*a, **kw):
            try:
                return fn(*a, **kw)
            except (Refused, query_log.Rejected) as exc:
                return {"refused": str(exc)}
        return guard

    @refusing
    def tool_kb_query(caller_id: str, kb_version: str, observable: str,
                      condition_range: dict | None = None, purpose: str = "screen") -> dict:
        return kb_query(store, caller_id, kb_version, observable, condition_range, purpose)

    @refusing
    def tool_kb_get(caller_id: str, kb_version: str, entry_id: str,
                    purpose: str = "screen") -> dict:
        return kb_get(store, caller_id, kb_version, entry_id, purpose)

    @refusing
    def tool_kb_conflicts(caller_id: str, kb_version: str, topic: str = "",
                          purpose: str = "troubleshoot") -> dict:
        return kb_conflicts(store, caller_id, kb_version, topic, purpose)

    @refusing
    def tool_kb_group(caller_id: str, kb_version: str, symbol: str,
                      purpose: str = "screen") -> dict:
        return kb_group(store, caller_id, kb_version, symbol, purpose)

    app = _Server(name="librarian", instructions=(
        "Read-only knowledge store. Four tools and no writes. caller_id is issued by the "
        "fan-out launcher and pins which question, configuration and axis is asking; "
        "kb_version pins the store version and a mismatch is refused rather than answered "
        "at another version. Matching reports whether an entry's validity covers the asked "
        "conditions and never decides what to do about a gap."))
    app.add_tool(tool_kb_query, name="kb_query",
                 description="entries for an observable and condition range, plus gaps and a grade summary")
    app.add_tool(tool_kb_get, name="kb_get", description="one entry verbatim, with its digest")
    app.add_tool(tool_kb_conflicts, name="kb_conflicts", description="pairs of entries that disagree")
    app.add_tool(tool_kb_group, name="kb_group",
                 description="one symbol's definition: formula, inputs, unit, validity")
    return app


def _serve() -> int:
    """MCP over stdio. Transport only: the answers come from the functions above."""
    try:
        app = _build_app(Store())
    except ImportError:
        print("no usable mcp package; the core still runs under --self-test", file=sys.stderr)
        return 1
    app.run(transport="stdio")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true", help="exercise the matching rules with no transport")
    ap.add_argument("--serve", action="store_true", help="run as an MCP server over stdio")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    if args.serve:
        return _serve()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
