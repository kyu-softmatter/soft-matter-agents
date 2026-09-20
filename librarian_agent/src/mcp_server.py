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
uncovered part named; nothing in common at all is `no_overlap`, a value that
carries its own subject so it cannot be read as the FIELD `unconstrained`,
which means something else. A quantity the query did not mention comes back
flagged rather than assumed satisfied. Nothing is clipped, interpolated, extrapolated or
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
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb_index                                             # noqa: E402
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

def _units() -> dict:
    """The unit registry, re-read when the file changes (see query_log._contract)."""
    return query_log._contract("units.json", "units")


def _si(value: float, unit: str) -> tuple[float, tuple]:
    u = _units().get(unit)
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

REPO = AGENT.parent


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, check=True).stdout


def version_history() -> dict[str, str]:
    """Every committed kb_version, mapped to the commit that carried it.

    Built by walking the history of kb/index.json and reading the version out
    of each revision. Derived entirely from content already in git -- it does
    not depend on who called, or on what was asked before, so it is the
    content-addressed cache 4.3.1 rule 2 explicitly permits rather than state
    that could carry anything between callers.
    """
    out: dict[str, str] = {}
    try:
        shas = _git("log", "--format=%H", "--", "librarian_agent/kb/index.json").split()
    except (OSError, subprocess.CalledProcessError):
        return out
    for sha in shas:
        try:
            v = json.loads(_git("show", f"{sha}:librarian_agent/kb/index.json")).get("kb_version")
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        out.setdefault(v, sha)          # the first commit to carry it
    return out


class Store:
    """Entries and the index, loaded once. Read-only by construction."""

    def __init__(self, kb: Path | None = None, log: Path | None = None,
                 _index: dict | None = None, _entries: dict | None = None,
                 _commit: str | None = None):
        self.kb = kb or (AGENT / "kb")
        self.log = log if log is not None else query_log.DEFAULT_LOG
        self.commit = _commit                       # None means the working tree
        self.index_stale = False
        if _index is not None:
            self.index, self.entries = _index, (_entries or {})
            self.kb_version = self.index.get("kb_version")
            return
        # The entries are the authority and index.json is their index -- the
        # index file says so itself. This used to read the index and REFUSE
        # when the two disagreed, which took the service down for every
        # session in the shared working copy for as long as it took one seat
        # to write entries and rebuild. _serve() builds a Store at startup, so
        # a new server could not start at all during that window; a caller saw
        # a bare tool error and the launcher logged the connection healthy.
        # One symptom, two failures -- an attached process failing every call,
        # and a new process unable to start -- and only the first is cured by
        # restarting, which is why it was misdiagnosed for hours.
        #
        # Deriving the version from the entries removes the window rather than
        # asking every writer to close it quickly. Discipline does not scale;
        # this seat wrote that in task 006 and then shipped a window anyway.
        self.entries: dict[str, dict] = {}
        for p in sorted((self.kb / "entries").glob("*.json")):
            e = json.loads(p.read_text())
            self.entries[e["entry_id"]] = e
        fresh = kb_index.build(self.kb)
        self.index = fresh
        self.kb_version = fresh["kb_version"]
        index_path = self.kb / "index.json"
        written = json.loads(index_path.read_text()) if index_path.exists() else {}
        self.index_stale = written.get("kb_version") != self.kb_version

    # -- serving the version that was pinned, not the one we happen to be at -- #

    def at(self, kb_version: str) -> "Store":
        """The store as it was at `kb_version`.

        4.3.1 asks that the same (query, kb_version) always give the same
        answer. Serving that version is what satisfies it; refusing gives
        neither the same answer nor any answer, and turns a guarantee about
        reproducibility into a lock on the store -- every version move would
        stop whatever fan-out was in flight, held back only by discipline,
        and discipline does not scale.
        """
        if kb_version == self.kb_version:
            return self
        if not isinstance(kb_version, str) or not re.fullmatch(r"kbv-[0-9a-f]{12}", kb_version or ""):
            raise Refused(f"kb_version {kb_version!r} is not the shape a version takes "
                          "(kbv- and twelve hex digits). Malformed, not merely old.")
        sha = version_history().get(kb_version)
        if sha is None:
            raise Refused(
                f"kb_version {kb_version} is well formed and is not in this repository's history, "
                f"so nothing can be read at it. This store is at {self.kb_version}. A version that "
                "was never committed is not servable and that is deliberate: it hashes a working "
                "tree nobody else can reproduce, and answering from HEAD instead would answer a "
                "different question under the pinned name."
            )
        index = json.loads(_git("show", f"{sha}:librarian_agent/kb/index.json"))
        entries = {}
        for line in _git("ls-tree", "--name-only", sha, "librarian_agent/kb/entries/").splitlines():
            if not line.endswith(".json"):
                continue
            e = json.loads(_git("show", f"{sha}:{line}"))
            entries[e["entry_id"]] = e
        return Store(kb=self.kb, log=self.log, _index=index, _entries=entries, _commit=sha)

    @property
    def reproducible(self) -> bool:
        """False when this version exists only in an uncommitted working tree."""
        return self.commit is not None or self.kb_version in version_history()

    # -- what an entry is about ------------------------------------------- #

    def subjects(self, e: dict) -> set[str]:
        """The names this entry answers to.

        Four handles, and `subject` is the only one that is a declared relation
        rather than a by-product. The other three are what an entry happens to
        contain: its own id, its symbol if it carries a formula, and the names
        in `numbers[]`. Those leave a whole genre unreachable -- a device fact
        has no number and no symbol, so before `subject` existed 14 of 25
        entries answered only to an id the caller had to learn by reading the
        staging table first.

        A subject names its registry rather than being a bare string:
        `{"kind": "device", "id": "csuw1_port"}`. Two entries calling one thing
        by different words would make matching a coincidence, which is the
        defect `subject` exists to remove, so a free list of strings would only
        have moved it one level. Four registries, all of which already exist --
        device (channel, element, or RETIRED row), configuration, observable,
        and quantity, which is the weakest because it is a de facto registry of
        names used in numbers[] rather than a declared one.

        What is matched here is the `id`. The `kind` says where that id is
        checkable, and nothing checks it yet: the check that every subject
        resolves is declared in section 8 and does not exist, so filling this
        field is useful and unverified, and saying so is cheaper than finding
        out in six months that it drifted.

        The fifth handle is the values of `identifiers` whose key is in the
        schema's `addressable` list -- the part number on the barrel, the model
        on the camera. Before it, the string an operator would actually type
        found nothing, while `na` returned six objectives no argument could
        tell apart. Membership is decided by one question the schema asks:
        does reconfiguring the instrument change this value? A part number
        survives a lens swap; a slot number is falsified by one, and nothing in
        the store records that somebody turned the nosepiece, so an addressable
        placement would hand back a stale answer at full confidence.

        The set is a union, not a replacement: an entry without `subject` still
        answers to everything it answered to before, which is what makes
        filling the field additive rather than a migration.
        """
        names = {e["entry_id"]}
        if e.get("symbol"):
            names.add(e["symbol"])
        for n in e.get("numbers") or []:
            if n.get("name"):
                names.add(n["name"])
        names.update(s["id"] for s in (e.get("subject") or []) if s.get("id"))
        ids = e.get("identifiers") or {}
        names.update(str(v) for k, v in ids.items() if k in addressable() and v)
        return names

    def answers_to(self, e: dict, name: str) -> bool:
        """Does this entry answer to `name`? Case-insensitively, see _fold."""
        return _fold(name) in {_fold(n) for n in self.subjects(e)}

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

    if not validity:
        # The entry declares no conditions at all, which is not the same claim
        # as declaring some that happen to miss. "Compared and it covers" and
        # "there was nothing to compare" are different answers, and entry rule
        # 2 says a claim without conditions is not reusable -- so the caller
        # has to be able to see which one it got.
        return {"overlap": "unstated", "uncovered": {},
                "unconstrained": unconstrained, "unasked": unasked}

    if not shared:
        return {"overlap": "no_overlap", "uncovered": {},
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
        # The uncovered part is a CLOSED piece of the asked interval, not a
        # one-sided bound. `{min: 280}` would say everything above 280 is
        # uncovered, which includes the 288-298 the entry does cover -- an
        # overstatement in a store whose discipline is not overstating. So the
        # entry's own bound is carried, converted into the unit the caller
        # asked in, and becomes the other end of the piece.
        unit = query[q]["unit"]
        factor, _ = _si(1.0, unit)
        out: dict[str, Any] = {"unit": unit}
        if not _ge(q_lo, e_lo) and e_lo != float("-inf"):
            out["below_min"] = query[q].get("min")
            out["covered_from"] = min(e_lo, q_hi) / factor
        if not _ge(e_hi, q_hi) and e_hi != float("inf"):
            out["above_max"] = query[q].get("max")
            out["covered_to"] = max(e_hi, q_lo) / factor
        if e_hi < q_lo or q_hi < e_lo:
            out["disjoint"] = True
        uncovered[q] = out

    return {"overlap": "full" if not uncovered else "partial",
            "uncovered": uncovered,
            "unconstrained": unconstrained, "unasked": unasked}


def uncovered_ranges(row: dict) -> list[dict]:
    """The uncovered part, as condition_ranges the contract can carry.

    The row's own `uncovered` says which side missed and by how much, in a
    shape this module invented. `kb_gap.nearest[].uncovered` is a
    condition_range -- quantity to {min?, max?, unit} -- and a condition_range
    cannot hold a union, so a query that overhangs an entry on BOTH sides is
    two pieces and comes back as two `nearest` items for one entry.

    Two items for one entry reads oddly and is the honest option. The
    alternative is one item covering the whole asked interval, which would
    report the middle -- the part the entry does cover -- as uncovered. This
    store's discipline is not overstating; a slightly awkward list is cheaper
    than a gap that claims more is missing than is.
    """
    pieces: list[dict] = []
    for quantity, miss in (row.get("uncovered") or {}).items():
        unit = miss.get("unit")
        if miss.get("below_min") is not None:
            pieces.append({quantity: {"min": miss["below_min"],
                                      "max": miss["covered_from"], "unit": unit}})
        if miss.get("above_max") is not None:
            pieces.append({quantity: {"min": miss["covered_to"],
                                      "max": miss["above_max"], "unit": unit}})
    return pieces


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

# Every registry below is a function, not a constant, for one reason: a
# constant is read once per PROCESS, and this server is long-running. Reading
# at import is indistinguishable from reading live when you are looking at the
# source, and on 2026-09-19 it refused a legitimate bridge caller for ten
# minutes after the pattern had been fixed, with the message that had already
# been replaced.
def caller_id_pattern() -> str:
    return query_log.caller_id_pattern()


def purposes() -> tuple[str, ...]:
    return query_log.purposes()
def addressable() -> tuple[str, ...]:
    """Which `identifiers` keys a caller may address an entry BY.

    Closed, and the default is not-addressable, so a key invented next month
    does not silently become a query surface.
    """
    try:
        return tuple(query_log._contract("schemas/kb_entry.schema.json",
                                         "addressable_identifiers", "addressable"))
    except (KeyError, TypeError):
        return ()


def _fold(name: str) -> str:
    """Case, and nothing beyond case.

    Every caller-supplied name is matched case-insensitively, uniformly across
    all five handles. Four of them -- entry_id, symbol, subject ids and
    numbers[].name -- are `^[a-z][a-z0-9_]*$` by schema, so folding is a no-op
    there and the rule costs nothing to make uniform; it bites only on
    identifier values, which are free strings: `MRD71670` is upper and
    `Kinetix 22` has a capital and a space.

    Whitespace and punctuation are deliberately NOT normalised. Case has one
    obvious mapping and reversing it invents nothing; stripping spaces or
    hyphens is a guess about which of several strings the caller meant, and
    every extra normalisation makes two different strings answer to one name --
    which is the collision this handle widens the surface for. An operator who
    types `Kinetix22` gets nothing, and nothing is the honest answer.
    """
    return name.casefold() if isinstance(name, str) else name


def _preflight(store: Store, caller_id: str, kb_version: str, tool: str) -> Store:
    """Check the caller, then return the store AS OF the pinned version."""
    if tool not in TOOLS:
        raise Refused(f"{tool!r} is not one of the four read-only tools {TOOLS}")
    if not isinstance(caller_id, str) or not re.match(caller_id_pattern(), caller_id):
        # Name every form the pattern takes. This said "<qid>:<config>:<axis>"
        # while the pattern accepted four, so a bridge caller -- whose id looks
        # nothing like that one -- was told its id was the wrong shape and had
        # no way to see which shapes were right. It guessed correctly that the
        # message was abridged rather than the pattern narrow, and had to
        # escalate to find out, because reading this file would have crossed a
        # seat boundary. Same defect as 008: the string a caller reads drifting
        # from what the code does, and here the string was the only thing it
        # could see.
        raise Refused(
            f"caller_id {caller_id!r} is not one the launcher issues. Four forms: "
            "<qid>:v<N>:<config>:<axis>, <qid>:v<N>:s2, <qid>:v<N>:operator, and "
            "bridge:<thread>:r<N>, where <qid> is (mic|sim)-YYYYMMDD-NNN. The revision "
            "is part of the id; the form without v<N> is accepted while cards migrate. "
            "A sub-agent may not choose its own id (4.3.1 rule 3) -- a malformed one is "
            "refused here, and that an issued-looking one really came from the launcher "
            "is enforced at the launcher, not here."
        )
    return store.at(kb_version)


def _log(store: Store, **rec) -> None:
    """An unlogged answer is worse than no answer, so a log failure fails the call."""
    query_log.record(store.log, server_session=SERVER_SESSION, **rec)


AGENT_OF = {"mic": "microscope_agent", "sim": "simulation_agent", "bridge": "bridge"}


def _agent_of(caller_id: str) -> str | None:
    """Which agent is asking, from the id the launcher issued.

    Four id forms, and the bridge's does not look like the other three: it is
    `bridge:<thread>:r<N>` rather than `<qid>:v<N>:...`, so splitting on the
    first hyphen -- which worked while every caller was mic or sim -- returns
    the whole string for it.
    """
    if caller_id.startswith("bridge:"):
        return AGENT_OF["bridge"]
    return AGENT_OF.get(caller_id.split("-", 1)[0])


def _gap_id(observable: str, kind: str) -> str:
    """A stable id for a gap, so the same question names the same gap.

    `^[a-z][a-z0-9_]*$` by contract, and an observable may be a part number
    with digits and capitals, so it is folded and non-conforming characters
    become underscores. Derived, never random: an assumption points at a gap
    by id (check 39), and an id that changed per call would break that link on
    the next run of the same question.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", observable.casefold()).strip("_") or "unnamed"
    if not slug[0].isalpha():
        slug = "q_" + slug
    return f"{slug}_{kind}"


def published_table_for(store: Store, caller_id: str, name: str) -> dict | None:
    """Where a name lives, when it lives in a published table rather than an entry.

    On 2026-09-19 five of the first seven kb_query calls came back `absent`,
    and every one of the five named something the librarian itself publishes:
    the device registry, a control channel, a read-back column, the optical
    path table, and `automatable_condition` -- a field this seat wrote into
    the dmd row four commits earlier. Telling a caller a thing does not exist
    when it exists in another shape sends them looking outside for something
    already on their disk.

    Where the thing lives is the same fact for every caller, and the first
    version of this did not treat it that way: it looked only in the asker's
    own snapshot, so `device_registry` came back `in_published_table` to the
    microscope and `absent` to the simulation. `absent` means no claim exists,
    which was false -- the table exists, the simulation simply was not
    published a copy. The determinism witness in the query log caught it
    inside the self-test: one query, one kb_version, two answers.

    So the table, its sha256 and the kind are identical for everyone. Only
    `snapshot` is caller-dependent, and it is present exactly when that
    agent's own snapshot carries the table -- which is a statement about the
    caller's copy, not about the fact.
    """
    # The snapshot is read AT THE PINNED VERSION, not from the working tree.
    # It was read from the tree until 2026-09-19, so a caller pinned to an
    # older version was handed the sha256 of the table as published NOW --
    # which does not match the copy in its own envelope. The next action this
    # gap kind prescribes is "read tables.<table> and confirm it is the
    # version the store published", and that sent the one caller who followed
    # it to a mismatch. Serving the pinned version has to reach the packaging
    # too, not only the entries.
    snapshots: dict[str, str] = {}
    if store.commit:
        try:
            listing = _git("ls-tree", "--name-only", store.commit,
                           "librarian_agent/kb/exports/").splitlines()
        except (OSError, subprocess.CalledProcessError):
            listing = []
        for path in sorted(listing):
            if Path(path).name.startswith("snapshot_") and path.endswith(".json"):
                try:
                    snapshots[Path(path).name] = _git("show", f"{store.commit}:{path}")
                except (OSError, subprocess.CalledProcessError):
                    continue
    else:
        published = store.kb / "exports"
        if published.exists():
            for snap_path in sorted(published.glob("snapshot_*.json")):
                snapshots[snap_path.name] = snap_path.read_text()
    if not snapshots:
        return None

    folded = _fold(name)
    hits: dict[str, dict] = {}
    mine: set[str] = set()
    agent = _agent_of(caller_id)
    for snap_name in sorted(snapshots):                           # sorted: determinism
        try:
            tables = (json.loads(snapshots[snap_name]).get("tables") or {})
        except json.JSONDecodeError:
            continue
        for table in sorted(tables):
            meta = tables[table]
            by_name = folded in {_fold(n) for n in (meta.get("names") or {})}
            by_column = folded in {_fold(c) for c in (meta.get("columns") or [])}
            if not (by_name or by_column):
                continue
            hits.setdefault(table, {"table": table, "sha256": meta.get("sha256"),
                                    **({"column": name} if by_column and not by_name else {})})
            if agent and snap_name == f"snapshot_{agent}.json":
                mine.add(table)
    if not hits:
        return None
    table = sorted(hits)[0]
    found = dict(hits[table])
    if table in mine:
        found["snapshot"] = f"kb/exports/snapshot_{agent}.json"
    return found


SERVER_SESSION = f"srv-{os.getpid()}-{int(time.time())}"


NEAR_MIN_SHARED = 4
NEAR_LIMIT = 8


def near_names(store: Store, asked: str) -> list[str]:
    """Names the store DOES answer to that are close to `asked`.

    Suggesting is not matching. Nothing here returns an entry -- a name in
    this list makes the caller ask again -- so a wrong suggestion costs one
    query, while a missing one costs the fact. That is why this is not the
    move refused for whitespace: folding a guess into the MATCHER makes a
    wrong string authoritative, and folding it into a suggestion cannot.

    Two exact predicates, not a score. A score has a threshold, a threshold
    is a dial, and a dial gets widened until the report cries at everything
    -- which this seat wrote down in 009 and would rather not demonstrate.

    1. CONTAINMENT, either direction, case-folded, with the shorter side at
       least four characters. Catches `objective` -> `objective_mrd70040` and
       `magnification` -> `nominal_magnification`. The minimum length is the
       guard: without it `na` is inside `nanoparticle` and every short handle
       becomes a suggestion for everything that happens to spell it.

    2. INITIALISM: the handle is exactly the first letters of the asked
       name's underscore-separated words. This exists for one case that no
       containment rule can reach -- `numerical_aperture` -> `na`, which is
       what six objectives carry and what the service answered `absent` to on
       its first day. `na` is not a substring of `numerical_aperture`; it is
       an abbreviation of it, and no amount of widening rule 1 finds it while
       every widening makes rule 1 noisier. Narrow by construction: it
       proposes at most one string per asked name, and only if the store
       already answers to it.

    3. A SINGLE TRAILING S dropped from the asked name, then rule 1 again.
       The case is in the log: a caller asked `objectives`, got nothing, and
       asked `objective` forty-three seconds later. `objective` is inside
       `objective_mrd70040` and `objectives` is not, so the plural found the
       neighbourhood empty while the singular found seven. This is the third
       exact rule and not a loosening of the first -- it drops one character
       in one position and re-runs the same predicate, so what it can propose
       is still bounded by containment.

    Deliberately NOT here: edit distance, token overlap, and general
    stemming. Each is a dial with a threshold, and a threshold gets widened
    until the report cries at everything. When a real miss turns up that none
    of these reaches, the honest answer is a fourth exact rule with its case
    written beside it, the way rule 3 got here.
    """
    handles = {h for e in store.entries.values() for h in store.subjects(e)}
    a = _fold(asked)
    words = [w for w in re.split(r"[^a-z0-9]+", a) if w]
    initials = "".join(w[0] for w in words) if len(words) > 1 else None

    forms = {a}
    if a.endswith("s") and len(a) - 1 >= NEAR_MIN_SHARED:
        forms.add(a[:-1])

    out = set()
    for h in handles:
        f = _fold(h)
        if f == a:
            continue                                  # it answered; this is not a near miss
        if initials and f == initials:
            out.add(h)
            continue
        for form in forms:
            short, long = sorted((f, form), key=len)
            if len(short) >= NEAR_MIN_SHARED and short in long:
                out.add(h)
                break
    return sorted(out)[:NEAR_LIMIT]


def _provenance(store: Store) -> dict:
    """Which version answered, and whether anyone could reproduce it."""
    # Resolve the commit even when the answer came from the working tree. It
    # said `commit: null, reproducible: true` -- not contradictory, since the
    # version is in history, but it told a consumer it could pin and then did
    # not say what to pin to, leaving it to search the history itself. The map
    # is already built.
    commit = store.commit or version_history().get(store.kb_version)
    return {
        "kb_version": store.kb_version,
        "commit": commit,
        "reproducible": store.reproducible,
        "index_written": not store.index_stale,
        "note": ("read from the working tree at a version that is not committed, so this exact "
                 "answer cannot be reproduced later -- record it as such" if not store.reproducible
                 else "the answer came from this version, not from whatever the store is at now"),
    }


def _recording_refusals(fn):
    """Record a refusal before re-raising it.

    Every refusal path goes through here rather than through each tool,
    because the ones that were invisible were the ones raised somewhere other
    than where the logging happened -- preflight, a dimension mismatch inside
    matching, a symbol defined twice. A wrapper cannot miss a path the way a
    call site can.

    A failure to record a refusal fails the call, the same way a failure to
    record an answer does, and the original refusal is chained so the caller
    still sees why it was turned away.
    """
    @functools.wraps(fn)
    def guard(store, caller_id=None, kb_version=None, *a, **kw):
        try:
            return fn(store, caller_id, kb_version, *a, **kw)
        except Refused as exc:
            query_log.record_refusal(
                store.log, tool=fn.__name__, reason=str(exc),
                server_session=SERVER_SESSION,
                caller_id=caller_id, kb_version=kb_version,
                arguments={k: v for k, v in kw.items()} or None,
            )
            raise
    return guard


@_recording_refusals
def kb_query(store: Store, caller_id: str, kb_version: str, observable: str,
             condition_range: dict | None = None, purpose: str = "screen") -> dict:
    store = _preflight(store, caller_id, kb_version, "kb_query")
    if purpose not in purposes():
        raise Refused(f"purpose {purpose!r} is not in contracts/schemas/goal.schema.json")

    hits = sorted((eid for eid, e in store.entries.items() if store.answers_to(e, observable)),
                  key=store.sort_key)
    returned, compared_and_short = [], []
    for eid in hits:
        e = store.entries[eid]
        m = match(e, condition_range)
        row = {"entry_id": eid, "grade": e["grade"], "grade_tag": e.get("grade_tag"),
               "claim": e["claim"], "numbers": e.get("numbers") or [],
               "validity": e.get("validity"), "validity_conditions": e["validity_conditions"],
               "identifiers": e.get("identifiers"), "source": e.get("source"),
               "source_ref": e["source_ref"],
               # Rules 7 and 8 keep a contradicted or superseded entry rather
               # than removing it, so the MARK is the whole of the protection
               # -- and until 2026-09-19 this projection dropped both, while
               # kb_get kept them. A screening fan-out calls kb_query, so the
               # store answered a disputed number with its grade, its source
               # and no sign that another entry contradicts it. validate.py's
               # CLAIM_FIELDS says exactly why these two belong to a citing
               # card: an entry gaining a contradiction is something the card
               # has to know. Found when a vendor emission peak the person had
               # measured differently came back clean at E3 -- a real
               # citation, a passing gate, and the wrong number.
               "conflict_with": e.get("conflict_with") or [],
               "supersedes": e.get("supersedes"), **m}
        returned.append(row)
        for piece in uncovered_ranges(m):
            compared_and_short.append({"entry_id": eid, "overlap": "partial",
                                       "uncovered": piece})

    # A gap needs something to be missing. Until 2026-09-19 this read
    # `absent if nothing returned else condition_mismatch`, which called every
    # not-full overlap a mismatch without asking whether anything had been
    # compared -- so a query with no condition_range against an entry with no
    # validity produced `condition_mismatch`, telling a caller its conditions
    # were not covered when neither side had stated any. The next action that
    # kind prescribes, find literature at other conditions, was nonsense.
    #
    # Two cases produce a gap and a third deliberately does not:
    #   nothing answers to the name                     -> absent
    #   a comparison happened and fell short            -> condition_mismatch
    #   entries came back and no comparison was possible-> no gap; the rows say
    #     why, in `overlap` (`unstated` when the entry declares no conditions,
    #     `no_overlap` when it declares others) and in `unconstrained`.
    # The third case wants a fifth kind more than it wants one of these four,
    # and inventing kinds is not this seat's to do, so it is reported on the
    # row and raised rather than forced into a word that means something else.
    gaps = []
    covered = [r for r in returned if r["overlap"] == "full"]
    if not returned or (condition_range and compared_and_short and not covered):
        published = published_table_for(store, caller_id, observable) if not returned else None
        kind = ("in_published_table" if published else
                "absent" if not returned else "condition_mismatch")
        gap = {
            # Required by the contract, and derived rather than invented so the
            # same question yields the same id. Until 2026-09-19 this server
            # emitted gaps with no gap_id and with a `note` the schema does not
            # allow -- kb_gap sets additionalProperties false -- so a caller
            # pasting one into a card would have failed check 1. Nothing caught
            # it because no card had copied a gap yet. The note is no loss: what
            # it said is now carried by `kind` and `published_in`, which is the
            # whole argument for moving the kind rather than adding guidance.
            "gap_id": _gap_id(observable, kind),
            "observable": observable,
            "kind": kind,
            "searched": ["kb/entries"] + (["kb/exports"] if not returned else []),
            "nearest": compared_and_short,
            "kb_version": store.kb_version,
            "asked_by": caller_id,
            "asked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        # Omitted rather than emitted empty: a condition_range has
        # minProperties 1, and `{}` is not "no conditions were asked", it is an
        # invalid range. The server was emitting it on every gap.
        if condition_range:
            gap["condition_range"] = condition_range
        if published:
            gap["published_in"] = published
        if gap["kind"] in ("absent", "in_published_table"):
            # Always present on these two, empty included. An empty array says
            # the neighbourhood was searched and nothing was near; the key
            # missing says the search never ran, and then the gap may only
            # claim "not found under this name" rather than "it does not
            # exist". Same distinction `searched` draws one level up.
            #
            # On in_published_table as well as absent, because pointing at a
            # table is not the whole answer when entries are also near:
            # `objectives` is a column of the device table AND the subject of
            # six entries, and a gap that named only the table would send a
            # caller to read a row when six graded claims were a re-ask away.
            # Not on condition_mismatch -- there the name matched, and what
            # fell short is in `nearest`.
            gap["near_names"] = near_names(store, observable)
        gaps.append(gap)

    answer = {"entries": returned, "gaps": gaps,
              "grade_summary": grade_summary(store, [r["entry_id"] for r in returned]),
              "kb_version": store.kb_version,
              "answered_from": _provenance(store)}
    _log(store, caller_id=caller_id, kb_version=kb_version, tool="kb_query", purpose=purpose,
         observable=observable, condition_range=condition_range,
         returned=[{"entry_id": r["entry_id"], "grade": r["grade"]} for r in returned],
         gaps=[g["kind"] for g in gaps],
         coverage={r["entry_id"]: r["overlap"] for r in returned})
    return answer


@_recording_refusals
def kb_get(store: Store, caller_id: str, kb_version: str, entry_id: str,
           purpose: str = "screen") -> dict:
    store = _preflight(store, caller_id, kb_version, "kb_get")
    e = store.entries.get(entry_id)
    _log(store, caller_id=caller_id, kb_version=kb_version, tool="kb_get", purpose=purpose,
         observable=entry_id,
         returned=[{"entry_id": entry_id, "grade": e["grade"]}] if e else [],
         gaps=[] if e else ["absent"], coverage={})
    if e is None:
        raise Refused(f"no entry {entry_id!r} at {store.kb_version}")
    return {"entry": e, "sha256": (store.index.get("entries") or {}).get(entry_id, {}).get("sha256"),
            "kb_version": store.kb_version, "answered_from": _provenance(store)}


@_recording_refusals
def kb_conflicts(store: Store, caller_id: str, kb_version: str, topic: str = "",
                 purpose: str = "troubleshoot") -> dict:
    store = _preflight(store, caller_id, kb_version, "kb_conflicts")
    pairs, seen = [], set()
    for eid in sorted(store.entries, key=store.sort_key):
        e = store.entries[eid]
        for other in e.get("conflict_with") or []:
            key = tuple(sorted((eid, other)))
            if key in seen:
                continue
            seen.add(key)
            o = store.entries.get(other)
            if topic and not (store.answers_to(e, topic) or (o and store.answers_to(o, topic))):
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
    return {"pairs": pairs, "kb_version": store.kb_version, "answered_from": _provenance(store),
            "note": "both sides of a conflict are kept and neither is merged away (4.3 rule 6); "
                    "which one applies is decided by the conditions, by the caller"}


@_recording_refusals
def kb_group(store: Store, caller_id: str, kb_version: str, symbol: str,
             purpose: str = "screen") -> dict:
    store = _preflight(store, caller_id, kb_version, "kb_group")
    formula_kinds = ("dimensionless_group", "derived_quantity")
    hits = sorted((eid for eid, e in store.entries.items()
                   if e.get("kind") in formula_kinds and _fold(e.get("symbol") or "") == _fold(symbol)),
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
            "kb_version": store.kb_version, "answered_from": _provenance(store),
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

        # The shared log must be untouchable from here. A test writes under
        # ids that look exactly like a live seat's, and a line in the real log
        # is attributed by nothing but that id -- so a test that reached it
        # would put a call no seat made under a caller_id that identifies one.
        # Checked by the bytes rather than by reading the code, because every
        # Store() built without an explicit log defaults to the real one and a
        # single such call is enough.
        shared = query_log.DEFAULT_LOG
        cid = "mic-20260917-001:v1:transmitted:a2"
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

        # 2b. a gap needs something to be missing. The case that produced a
        # false `condition_mismatch` for a day: nobody stated a condition on
        # either side, and the caller was told its conditions were not covered.
        for label, cr in [("no conditions asked", None),
                          ("conditions asked", {"temperature": {"min": 290, "max": 295, "unit": "K"}})]:
            a = kb_query(store, cid, v, "stand_ti2e_lock_groups", cr)
            if a["gaps"]:
                bad(f"{label}: an entry that states no conditions produced {a['gaps'][0]['kind']}")
            if a["entries"][0]["overlap"] != "unstated":
                bad(f"{label}: an entry with no validity reported {a['entries'][0]['overlap']}")
        # states conditions, none of them the asked one: not a mismatch either
        a = kb_query(store, cid, v, "viscosity", {"bead_diameter": {"min": 1, "max": 2, "unit": "um"}})
        if a["gaps"] or a["entries"][0]["overlap"] != "no_overlap":
            bad(f"an entry constraining another quantity gave {a['gaps']} / {a['entries'][0]['overlap']}")
        # and the two that must still be gaps
        if [g["kind"] for g in kb_query(store, cid, v, "nothing_answers_to_this", None)["gaps"]] != ["absent"]:
            bad("a name nothing answers to stopped producing absent")

        # 2c. a name that is published in a table is not absent. All five that
        # came back absent on the first day of real use, plus the two cases
        # that must not become this kind.
        expect = {"device_registry": ("devices", None), "control_channel": ("devices", None),
                  "optical_path_valid_tuples": ("optical_paths", None),
                  "read_back": ("devices", "read_back"),
                  "automatable_condition": ("devices", "automatable_condition")}
        for q, (table, column) in expect.items():
            g = kb_query(store, cid, v, q, None)["gaps"][0]
            if g["kind"] != "in_published_table":
                bad(f"{q!r} is published in {table} and came back {g['kind']}")
                continue
            pi = g.get("published_in")
            if not pi:
                bad(f"{q!r}: in_published_table with no published_in, which names the shelf not the book")
            elif pi.get("table") != table or pi.get("column") != column:
                bad(f"{q!r}: published_in says {pi.get('table')}/{pi.get('column')}")
            elif not re.fullmatch(r"[0-9a-f]{64}", pi.get("sha256") or ""):
                bad(f"{q!r}: published_in carries no usable sha256, so the next action is advisory")
        if kb_query(store, cid, v, "genuinely_absent_name", None)["gaps"][0]["kind"] != "absent":
            bad("a name that is nowhere stopped being absent")

        # where a thing lives is one fact. Only whether THIS caller holds a
        # copy may vary, and it varies in `snapshot` alone.
        mic = kb_query(store, cid, v, "device_registry", None)["gaps"][0]["published_in"]
        sim = kb_query(store, "sim-20260917-001:v1:bd_overdamped:a1", v,
                       "device_registry", None)["gaps"][0]["published_in"]
        if (mic["table"], mic["sha256"]) != (sim["table"], sim["sha256"]):
            bad(f"the table differs by who asked: {mic} vs {sim}")
        if "snapshot" not in mic or "snapshot" in sim:
            bad(f"`snapshot` should be present only for the agent that holds it: {mic} / {sim}")

        # the uncovered piece is a closed part of the asked interval. The
        # entry covers 288-298 K, so none of these may report the middle.
        overhangs = {
            (280, 320): [{"min": 280, "max": 288.0}, {"min": 298.0, "max": 320}],
            (280, 295): [{"min": 280, "max": 288.0}],
            (291, 320): [{"min": 298.0, "max": 320}],
            (330, 340): [{"min": 330.0, "max": 340}],
        }
        for (lo, hi), want in overhangs.items():
            g = kb_query(store, cid, v, "viscosity",
                         {"temperature": {"min": lo, "max": hi, "unit": "K"}})["gaps"][0]
            got = [n["uncovered"]["temperature"] for n in g["nearest"]]
            if got != [{**w, "unit": "K"} for w in want]:
                bad(f"{lo}-{hi} K reported uncovered {got}, expected {want}")

        # every gap this server emits has to be pasteable into a card
        try:
            import jsonschema
            from referencing import Registry, Resource
        except ImportError:
            print("note: jsonschema not installed, so gap shape was not checked against the contract")
        else:
            res = {f.name: Resource.from_contents(json.loads(f.read_text()))
                   for f in (CONTRACTS / "schemas").glob("*.json")}
            gap_schema = json.loads((CONTRACTS / "schemas" / "common.schema.json").read_text())
            gv = jsonschema.Draft202012Validator(
                {"$ref": "common.schema.json#/$defs/kb_gap", "$defs": gap_schema.get("$defs", {})},
                registry=Registry().with_resources(res.items()))
            for probe, cr in [("device_registry", None), ("read_back", None),
                              ("genuinely_absent_name", None),
                              ("viscosity", {"temperature": {"min": 280, "max": 320, "unit": "K"}})]:
                for g in kb_query(store, cid, v, probe, cr)["gaps"]:
                    errs = [f"{'/'.join(str(x) for x in e.path) or '(root)'}: {e.message}"
                            for e in gv.iter_errors(g)]
                    if errs:
                        bad(f"the gap for {probe!r} is not a kb_gap: {errs}")

        # 2d. the contract registries follow the FILE, not the process. A
        # constant read at import looks the same as a live read from inside
        # the source, and is not: this server refused a legitimate bridge
        # caller for ten minutes after the pattern was fixed, because the
        # running process still held the pattern it had loaded at start.
        # Asserted through the cache rather than by editing contracts/ --
        # that file belongs to another seat and a crash mid-test would leave
        # it modified.
        for accessor in (caller_id_pattern, purposes, addressable, _units):
            if not callable(accessor):
                bad(f"{accessor} is a constant again, so it is read once per process")
        _units()
        stamp = query_log._REGISTRY_CACHE.get(("units.json", ("units",)))
        if not stamp or stamp[0] != (CONTRACTS / "units.json").stat().st_mtime_ns:
            bad("the registry cache is not keyed on the file's mtime, so an edit will not be seen")

        # 2e. near_names: suggest without matching. The key is present on
        # absent and in_published_table, empty included, because an empty
        # array and a missing key are different claims.
        flagship = kb_query(store, cid, v, "numerical_aperture", None)["gaps"][0]
        if flagship["kind"] != "absent" or flagship.get("near_names") != ["na"]:
            bad(f"numerical_aperture should suggest na: {flagship.get('near_names')}")
        objective = kb_query(store, cid, v, "objective", None)["gaps"][0]
        if "objective_mrd70040" not in (objective.get("near_names") or []):
            bad(f"`objective` should reach the objective entries: {objective.get('near_names')}")
        # `pixel_size` was the one honest absent on the service's first day and
        # is answered now, by the operator's twelve calibrations. Asserted as an
        # answer rather than deleted: a gap that closes because the fact arrived
        # is worth a test, and this one closed for the right reason.
        px = kb_query(store, cid, v, "pixel_size", None)
        if not px["entries"] or px["gaps"]:
            bad(f"pixel_size should answer now: {len(px['entries'])} entries, {px['gaps']}")
        for q in ("refractive_index", "pinhole_diameter"):
            g = kb_query(store, cid, v, q, None)["gaps"][0]
            if g.get("near_names") != []:
                bad(f"{q} has nothing near it and should say so with an empty list, got "
                    f"{g.get('near_names')}")
        # the plural is the case rule 3 exists for: this caller asked
        # `objectives`, got nothing, and asked `objective` 43 seconds later
        tbl = kb_query(store, cid, v, "objectives", None)["gaps"][0]
        if tbl["kind"] != "in_published_table" or "near_names" not in tbl:
            bad(f"a published-table answer should still say what is near: {sorted(tbl)}")
        elif "objective_mrd70040" not in tbl["near_names"]:
            bad(f"the plural found an empty neighbourhood: {tbl['near_names']}")
        # a suggestion must never be a match: the store answers to `na`, so a
        # query for it returns entries rather than suggesting anything
        if not kb_query(store, cid, v, "na", None)["entries"]:
            bad("suggesting leaked into matching: `na` stopped answering")
        # and a short handle must not be suggested for anything that spells it
        noisy = kb_query(store, cid, v, "nanoparticle_count", None)["gaps"][0]
        if "na" in (noisy.get("near_names") or []):
            bad("a two-letter handle was suggested by containment; the length guard is gone")

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
        if e0["overlap"] != "no_overlap" or "bead_diameter" not in e0["unconstrained"]:
            bad(f"an entry with no opinion on bead_diameter should say so: {e0['overlap']}, {e0['unconstrained']}")
        if "temperature" not in e0["unasked"]:
            bad(f"the temperature the entry constrains and the query skipped should be flagged: {e0['unasked']}")

        # 4b. `subject` is a handle, and it is additive -- an entry keeps every
        # handle it had. Asserted on the function rather than through the store
        # so it holds before any entry carries the field.
        probe = {"entry_id": "e", "numbers": [{"name": "n"}], "symbol": "s",
                 "subject": [{"kind": "device", "id": "csuw1_port"},
                             {"kind": "observable", "id": "tracer_diffusivity"}]}
        if store.subjects(probe) != {"e", "n", "s", "csuw1_port", "tracer_diffusivity"}:
            bad(f"subject is not a handle, or it replaced the others: {store.subjects(probe)}")
        if store.subjects({"entry_id": "e"}) != {"e"}:
            bad("an entry with no subject stopped answering to its own id")
        # the shape is an object and was a bare string for one commit; a list
        # of strings must not silently half-work by iterating characters
        if store.subjects({"entry_id": "e", "subject": [{"kind": "device"}]}) != {"e"}:
            bad("a subject with no id contributed something")

        # 4c. the fifth handle: an addressable identifier value. The three
        # probes that motivated it, and the keys that must stay out.
        # Membership, not counts. `Kinetix 22` returned one entry when this
        # was written and returns two now that a second entry carries the same
        # model, which is correct and would have failed a count -- the same
        # reason this repository tells you to read counts off the run.
        probes = {q: {e["entry_id"] for e in kb_query(store, cid, v, q, {})["entries"]}
                  for q in ("MRD71670", "Kinetix 22", "na")}
        for q, must in [("MRD71670", {"objective_mrd71670"}),
                        ("Kinetix 22", {"cameras_both_kinetix22"}),
                        ("na", {f"objective_mrd{n}" for n in
                                ("70040", "70170", "70270", "71670", "71970", "77400")})]:
            if not must <= probes[q]:
                bad(f"{q!r} did not reach {sorted(must - probes[q])}")
        if not addressable():
            bad("the addressable list is empty; it is read from the schema and something moved")
        for shut in ("position_0", "fitted_slot", "position_index_base", "0", "1", "3"):
            if kb_query(store, cid, v, shut, {})["entries"]:
                bad(f"{shut!r} is not addressable and found something anyway -- the default is closed")

        # case folds, and only case
        for lower, upper in [("mrd71670", "MRD71670"), ("kinetix 22", "Kinetix 22")]:
            a = [e["entry_id"] for e in kb_query(store, cid, v, lower, {})["entries"]]
            b = [e["entry_id"] for e in kb_query(store, cid, v, upper, {})["entries"]]
            if a != b or not a:
                bad(f"{lower!r} and {upper!r} answered differently: {a} vs {b}")
        if kb_query(store, cid, v, "Kinetix22", {})["entries"]:
            bad("whitespace was normalised; only case is folded, and nothing is the honest answer")

        # a new handle must not reorder anything
        na = [e["entry_id"] for e in kb_query(store, cid, v, "na", {})["entries"]]
        if na != sorted(na):
            bad(f"the objectives stopped coming back in entry_id order: {na}")

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
        b = kb_query(store, "mic-20260917-001:v1:confocal:a3", v,
                     "viscosity", {"temperature": {"min": 291, "max": 295, "unit": "K"}})
        strip = lambda x: json.dumps({k: x[k] for k in ("entries", "grade_summary")}, sort_keys=True)
        if strip(a) != strip(b):
            bad("two callers got different answers to one query at one kb_version")

        # 7. an old pin is SERVED, not refused, and it answers as it was then.
        # The fixture is the repository's own history -- no store move needed.
        history = version_history()
        if len(history) < 2:
            print("note: fewer than two committed versions, so the old-pin case was not exercised")
        else:
            oldest = min(history, key=lambda v: len(Store(log=log).at(v).entries))
            then = Store(log=log).at(oldest)
            a = kb_query(store, cid, oldest, "viscosity", {})
            if a["kb_version"] != oldest or a["answered_from"]["commit"] is None:
                bad(f"a pinned old version did not answer from itself: {a['answered_from']}")
            if not a["entries"]:
                bad("the old version had the viscosity entry and did not return it")

            # the sharpest case: one entry_id, two versions, two answers
            now_kind = kb_get(store, cid, v, "tau_d")["entry"]["kind"]
            then_kind = kb_get(store, cid, oldest, "tau_d")["entry"]["kind"]
            if now_kind == then_kind:
                print(f"note: tau_d reads the same at both versions ({now_kind}); "
                      "the re-filing may have been squashed out of history")
            elif (then_kind, now_kind) != ("dimensionless_group", "derived_quantity"):
                bad(f"tau_d went {then_kind} -> {now_kind}, which is not the re-filing that happened")

            # an entry that did not exist then must not appear from HEAD
            if len(then.entries) < len(store.entries):
                gone = sorted(set(store.entries) - set(then.entries))[0]
                try:
                    kb_get(store, cid, oldest, gone)
                    bad(f"{gone} did not exist at {oldest} and was served anyway -- HEAD leaked in")
                except Refused:
                    pass
                if kb_query(store, cid, oldest, "na", {})["entries"]:
                    bad("the objectives did not exist at the oldest version and were returned")

        # 7c. a published-table answer is read at the PINNED version, so the
        # sha256 it hands out is one the caller's own copy can match. It used
        # to come from the working tree, which sent a caller pinned to an
        # older version to a table whose bytes it does not have.
        if len(history) >= 2:
            for pin in sorted(history):
                g = kb_query(store, cid, pin, "immersion", None)["gaps"][0]
                pi = g.get("published_in")
                if not pi:
                    continue        # that version published no table index; absent is honest
                # The sha belongs to the commit the SNAPSHOT was built from,
                # which is usually earlier than the commit the entries are at
                # -- publishing follows writing. That is what
                # `built_from_commit` is for, and comparing against the wrong
                # commit is how this assertion first failed.
                try:
                    snap = json.loads(_git(
                        "show", f"{history[pin]}:{pi['snapshot']}"))
                    blob = _git("show", f"{snap['built_from_commit']}:"
                                        "librarian_agent/kb/staging/devices.v0.json")
                except Exception:
                    continue
                import hashlib as _h
                if _h.sha256(blob.encode()).hexdigest() != pi.get("sha256"):
                    bad(f"pin {pin}: the table sha is not the one its own snapshot was built from")

        # 7b. unresolvable is still refused, and says which kind
        for pin, word in [("kbv-000000000000", "history"), ("not-a-version", "Malformed"),
                          ("kbv-XYZ", "Malformed")]:
            try:
                kb_query(store, cid, pin, "viscosity", {})
                bad(f"served an unresolvable pin {pin!r}")
            except Refused as exc:
                if word not in str(exc):
                    bad(f"{pin!r} was refused without saying which kind: {exc}")

        # 8. a caller may not choose its own id
        # the bridge's id is a different shape: bridge:<thread>:r<N>, with no
        # hyphen where the others have one. Splitting on the first hyphen was
        # correct while every caller was mic or sim.
        b = kb_query(store, "bridge:thr-mic-sim-001:r1", v, "device_registry", None)
        if b["gaps"][0]["kind"] != "in_published_table":
            bad(f"a bridge caller could not reach a published table: {b['gaps'][0]['kind']}")

        for wrong in ("librarian", "mic-20260917-001", "mic-20260917-001:v1:transmitted:a9"):
            try:
                kb_query(store, wrong, v, "viscosity", {})
                bad(f"accepted caller_id {wrong!r}")
            except Refused:
                pass

        # 8b. a contradiction reaches the tool a screen actually uses.
        # Rules 7 and 8 do not remove a disputed or superseded entry, so the
        # mark IS the protection; a projection that drops it hands out a
        # contested number that looks uncontested. kb_get kept both fields and
        # kb_query dropped them, and a screening fan-out calls kb_query.
        marked = [e for e in store.entries.values() if e.get("conflict_with")]
        if not marked:
            bad("no entry carries conflict_with, so this property is untested "
                "rather than passing -- rule 7 says conflicts are kept and marked")
        for e in marked:
            obs = (e.get("numbers") or [{}])[0].get("name") or e["entry_id"]
            rows = kb_query(store, "selftest:conflict-mark", v, obs, None)["entries"]
            row = next((r for r in rows if r["entry_id"] == e["entry_id"]), None)
            if row is None:
                bad(f"{e['entry_id']} carries a conflict and does not answer to {obs!r}")
            elif sorted(row.get("conflict_with") or []) != sorted(e["conflict_with"]):
                bad(f"kb_query dropped the conflict mark on {e['entry_id']}: "
                    f"{row.get('conflict_with')!r} for {e['conflict_with']!r}")
            elif "supersedes" not in row:
                bad(f"kb_query dropped supersedes on {e['entry_id']}")

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

        # 11. conflicts: the shape holds, including one side not yet filed.
        # This asserted zero pairs until 2026-09-19, which was true when
        # written and stopped being true the moment rule 7 was first used in
        # anger -- the fourth assertion here to go stale for a good reason.
        # "Nothing has happened yet" is not a property; what is checked now is
        # the shape, and `dangling` in particular, because a contradiction
        # whose other side cannot be entered yet is a real state and not an
        # error: the person's measured value waits on a cal_id and a validity
        # that only they can supply, and inventing either to make the pair
        # resolve is the failure this leaves room for.
        c = kb_conflicts(store, cid, v)
        for pair in c["pairs"]:
            if len(pair["pair"]) != 2:
                bad(f"a conflict pair is not a pair: {pair}")
            if pair["dangling"] and pair["dangling"] in store.entries:
                bad(f"{pair['dangling']} is called dangling and is in the store")
            if not pair["dangling"] and len(pair["grades"]) != 2:
                bad(f"a resolved pair reports {len(pair['grades'])} grades: {pair}")

        # 12. no write tool is exposed
        import types
        exported = {n for n, val in globals().items()
                    if n.startswith("kb_") and not isinstance(val, types.ModuleType)}
        if exported != set(TOOLS):
            bad(f"the module exposes {sorted(exported)}; only the four read-only tools may exist")

        # 13. every call was logged, and the log audits clean
        problems = query_log.verify(log)
        if problems:
            bad(f"the query log did not audit clean: {problems}")
        lines = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
        if {x["tool"] for x in lines} != set(TOOLS):
            bad(f"not every tool reached the log: {sorted({x['tool'] for x in lines})}")

        # A refused call is recorded too, and the shape is the point. Until
        # 2026-09-19 the log held answers only, so how often the service
        # refused was written nowhere. What a refusal must not do is write a
        # caller_id the launcher never issued into the field that means one.
        before = len(lines)
        # Earlier cases refuse too -- a bad dimension, three bad ids, an
        # unresolvable pin -- so what is asserted here is the delta.
        for attempt in [lambda: kb_query(store, "librarian", v, "viscosity", {}),
                        lambda: kb_query(store, cid, "kbv-000000000000", "viscosity", {})]:
            try:
                attempt()
            except Refused:
                pass
        after = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
        if len(after) != before + 2:
            bad(f"two refusals produced {len(after) - before} records")
        refusals = [r for r in after[before:] if r.get("outcome") == "refused"]
        if len(refusals) != 2:
            bad(f"{len(refusals)} refusals recorded for two refused calls")
        for r in refusals:
            if "caller_id" in r or "kb_version" in r:
                bad(f"a refusal asserted what the server rejected: {sorted(r)}")
            if not r.get("reason") or not isinstance(r.get("claimed"), dict):
                bad(f"a refusal recorded that something failed and not what: {r}")
        if not any(r["claimed"].get("caller_id") == "librarian" for r in refusals):
            bad("the claimed id was not kept; a refusal nobody can attribute is still evidence")
        if any(r.get("claimed", {}).get("caller_id") == r.get("caller_id") for r in refusals):
            bad("a claimed id leaked into the validated field")
        if query_log.verify(log):
            bad(f"refusal records do not audit clean: {query_log.verify(log)}")

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
            # The instructions string is the only part of the design most
            # callers ever see, and on 2026-09-18 it still said a stale pin was
            # refused for one commit after that stopped being true. This pins
            # the positive claim, tied to case 7 which verifies the behaviour;
            # it does not and cannot check descriptions for drift in general.
            if "version it names" not in (app.instructions or ""):
                bad("the instructions no longer say a pin is answered from the version it names")
            listed = asyncio.run(app.list_tools())
            names = {t.name for t in listed}
            if names != set(TOOLS):
                bad(f"the transport registered {sorted(names)}")
            for t_ in listed:
                schema = getattr(t_, "input_schema", None) or getattr(t_, "inputSchema", None) or {}
                props = set(schema.get("properties") or {})
                if not {"caller_id", "kb_version"} <= props:
                    bad(f"tool {t_.name} exposes {sorted(props)}; caller_id and kb_version are the wire contract")

        # Look for THIS process's session id rather than comparing bytes.
        # Four other sessions call the live server, so the shared log changes
        # under a passing test, and a guard that reads any change as a write
        # by the test is a guard that cries at other people's work. The
        # session stamp makes the question exact: did anything I did land
        # there.
        if shared.exists() and SERVER_SESSION in shared.read_text():
            bad(f"the self-test wrote to {shared}, the log real callers are attributed by")

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
        "fan-out launcher and pins which question, configuration and axis is asking. "
        "kb_version is honoured: a pin is answered from the version it names, not from "
        "whatever the store is at now, and every response says in `answered_from` which "
        "version and commit replied. The one pin that cannot be served is a version that "
        "was never committed -- it hashes a working tree, so there is nowhere to read it "
        "back from. Matching reports whether an entry's validity covers the asked "
        "conditions and never decides what to do about a gap."))
    app.add_tool(tool_kb_query, name="kb_query",
                 description=("entries for a name and condition range, plus gaps and a grade summary. "
                              "`observable` is the name asked about and takes more than an observable id: "
                              "a device or configuration id, a quantity name, an entry id, or an addressable "
                              "identifier such as a part number or a camera model. Matching ignores case and "
                              "nothing else. A name that fits a class -- an immersion, a product line -- "
                              "returns the whole class, so read `identifiers` on each row to tell them apart"))
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
