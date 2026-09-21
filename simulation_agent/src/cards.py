"""Card assembly shared by this agent's planning modules (plan.md 5.2, 5.3).

Six axis modules and the synthesis emit the same head, so the head is built
here once rather than copied six times, where the copies would drift.

This module reads `contracts/` as data and imports nothing from it, and it
knows nothing about backends or devices (7.2 rule 2). It writes JSON; the
Markdown twin is generated from the JSON, never beside it (P3).

The one rule worth stating: `grade` is derived from `source` and cannot be
passed in. A self-reported grade is a validator failure (check 21), so the
only way to change a number's grade here is to change where it came from.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONTRACTS = REPO / "contracts"
AGENT = REPO / "simulation_agent"

AUTHOR = "simulation_agent"

# The same table the validator derives grades with (5.3). `computed`, `simulated`
# and `kb` are None because none of the three is fixed by the prefix alone: a
# computed value takes the worst of its inputs, a simulated one does the same,
# and a kb value takes the grade the entry carried.
#
# `simulated` grades like `computed` and for the reason one level up. `computed:`
# is E4 at best because the formula is itself an assumption; a run's output is E4
# at best because the model is. What differs is the obligation and not the grade:
# a computed number owes a recomputation (check 17) and a run owes none, because
# there is no formula to re-evaluate -- an integrator emitted it.
#
# It was absent here until 2026-09-20 while the validator already had it, so
# `grade_for("simulated:run-...")` raised on a source the gate accepts. That is
# the 11-11 shape -- one fact in two places -- and this copy is this agent's.
# 5.3's table, and it has to be 5.3's WHOLE table.
#
# This is the second copy -- contracts/validate.py holds the first -- and a
# partial copy of a table is worse than no copy, because `grade_for` raises on
# a kind it has never heard of rather than grading it. `prior_run` and
# `literature` went into the validator on 2026-09-18 (877d652) and never
# arrived here, so for two days `grade_for("prior_run:...")` raised ValueError
# against the 26 store entries that carry that source. Nobody hit it because
# nothing in this agent had cited one yet; the gap was found by counting the
# two tables against each other, not by a failure.
#
# `simulated` was the one that drew attention, because it was new. It was not
# the only one missing, and that is the lesson: what is new gets noticed and
# what went stale does not.
SOURCE_GRADE = {
    "measured": "E1",
    "calibration": "E2",
    "spec": "E3",
    "prior_run": "E3",        # another project ran it; 10.3 rule 1 caps it here
    "literature": "E3",       # published, and not a vendor specification
    "operator_read": "E3",
    "operator_recall": "E5",
    "computed": None,         # max(E4, worst input)
    "simulated": None,        # max(E4, worst input) too -- the model is the assumption
    "assumed": "E5",
    "kb": None,               # inherited from kb_refs
}


def grade_for(source: str, input_grades: list[str] | None = None) -> str:
    """The grade that follows from a source (5.3). Never self-reported."""
    prefix = source.split(":", 1)[0]
    if prefix not in SOURCE_GRADE:
        raise ValueError(f"unknown source kind {prefix!r}")
    fixed = SOURCE_GRADE[prefix]
    if fixed is not None:
        return fixed
    if prefix in ("computed", "simulated"):
        worst = max(input_grades or ["E4"])
        return max("E4", worst)
    raise ValueError("a kb: source takes its grade from the kb_ref, not from here")


def num(name: str, value: float, unit: str, source: str, **kw) -> dict:
    """One number as the four parts P2 requires, plus optional provenance.

    `inputs` and `formula` are required by the validator when the source is
    computed:, and the grade then follows from the inputs' grades -- so they
    are passed as (name, grade) pairs rather than bare names.

    A `simulated:` number takes `inputs` and **no formula**. The grade is
    derived the same way, max(E4, worst input), because a reading is no
    stronger than what was fed to the model that produced it; what it does not
    have is an arithmetic anyone can redo, so check 17 asks nothing of it and
    passing a formula here would invent an obligation the source cannot meet.
    Inputs are optional and omitting them says the reading stands on nothing
    graded, which lands it at E4 -- so an omission reads as a stronger claim
    than the truth, and every caller here names them.
    """
    inputs: list[tuple[str, str]] = kw.pop("inputs", [])
    out = {"name": name, "value": value, "unit": unit, "source": source}
    if source.startswith("computed:"):
        if not inputs or "formula" not in kw:
            raise ValueError(f"{name}: a computed number needs a formula and its inputs")
        out["grade"] = grade_for(source, [g for _, g in inputs])
        out["formula"] = kw.pop("formula")
        out["inputs"] = [n for n, _ in inputs]
    elif source.startswith("simulated:"):
        if "formula" in kw:
            raise ValueError(
                f"{name}: a simulated number has no formula -- an integrator emitted it, and a "
                "formula would promise a recomputation nobody can perform"
            )
        out["grade"] = grade_for(source, [g for _, g in inputs])
        if inputs:
            out["inputs"] = [n for n, _ in inputs]
    else:
        out["grade"] = grade_for(source)
    for key in ("precision", "derived", "symbol", "origin", "note"):
        if key in kw:
            out[key] = kw.pop(key)
    if kw:
        raise ValueError(f"{name}: unexpected fields {sorted(kw)}")
    return out


def head(card: str, cid: str, qid: str, created_at: str, **kw) -> dict:
    """The fields every card carries (5.2). Order follows the schema's."""
    out = {
        "card": card,
        "schema_version": "0.1",
        "id": cid,
        "qid": qid,
        "thread": kw.pop("thread", f"solo-{qid}"),
        "round": kw.pop("round", 0),
        "revision": kw.pop("revision", 1),
        "author": AUTHOR,
        "created_at": created_at,
        "status": kw.pop("status", "VALIDATED"),
    }
    out.update(kw)
    return out


def tail(numbers: list[dict], **kw) -> dict:
    """The evidence fields. `degraded` is mandatory, not a default (3.1).

    kb_refs empty with the librarian in `degraded` says it was never reached;
    kb_refs empty with `degraded` empty would claim it answered and had
    nothing, which is a different fact (4.3.1).
    """
    out: dict = {"numbers": numbers}
    for key in ("assumptions", "kb_refs", "kb_gaps"):
        out[key] = kw.pop(key, [])
    out["degraded"] = kw.pop("degraded", [])
    if kw:
        raise ValueError(f"unexpected fields {sorted(kw)}")
    return out


def question_dir(qid: str) -> Path:
    return AGENT / "questions" / qid


def goal_path(qid: str, revision: int | None = None) -> Path:
    """Where a question's goal for a given revision lives.

    **A question has one goal PER REVISION, not one goal.** 4.5.5 gives every
    revision its own files and `artifact_name` names them; the goal was the one
    card exempted from that, by a special case in `plan_card` and `synthesis`
    reading `goal.json` whatever the revision. The exemption was known -- the
    comment beside it called putting the revisions back on disk "a separate
    repair" -- and this is that repair.

    **What the exemption cost is that two revisions cannot coexist.** Check 12
    resolves a carried number's `origin` by FILENAME and reads no revision
    (validate.py:1284), so while every revision's cards cite `goal.json#x`,
    they all resolve to whichever revision that file currently holds. Bumping
    the goal to revision 2 therefore broke all six revision-1 axis cards at
    once -- 46 failures, none of them about anything being wrong. The rule that
    revision 1 stays on disk and the rule that the goal moves were not both
    satisfiable.

    With no revision given this returns the LATEST on disk, which is what
    `question_revision` asks for and what a caller who has not chosen a
    revision means.
    """
    directory = question_dir(qid)
    if revision is not None:
        return directory / artifact_name("goal.json", revision)
    found = [(1, directory / "goal.json")] if (directory / "goal.json").exists() else []
    for path in directory.glob("v*_goal.json"):
        m = re.fullmatch(r"v(\d+)_goal\.json", path.name)
        if m:
            found.append((int(m.group(1)), path))
    if not found:
        return directory / "goal.json"          # so the caller's error names the plain name
    return max(found)[1]


def load_goal(qid: str, revision: int | None = None) -> dict:
    return json.loads(goal_path(qid, revision).read_text())


def pick(card: dict, *names: str) -> dict[str, dict]:
    """Numbers of a card by name, so a module can carry its inputs forward."""
    by_name = {n["name"]: n for n in card.get("numbers", [])}
    missing = [n for n in names if n not in by_name]
    if missing:
        raise KeyError(f"{card.get('id')} has no number named {missing}")
    return {n: by_name[n] for n in names}


def write(path: Path, card: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n")
    return path


def carry(goal: dict, names: list[str]) -> tuple[list[dict], list[dict]]:
    """Goal numbers an axis needs as inputs, with the assumptions that explain them.

    An assumed number must be explained in the card that holds it (check 4),
    so the rationale travels with the number instead of being left behind in
    the goal. The rationale's `numbers` list is narrowed to what actually came
    along -- an assumption pointing at a number this card does not hold would
    claim to explain something that is not here.
    """
    picked = pick(goal, *names)
    numbers = []
    for n in picked.values():
        carried = dict(n)
        # `origin` says where the number was made, and that is what lets a
        # carried value be checked by comparison with its source (check 12)
        # instead of being re-derived here. Without it a carried `computed:`
        # number would have to bring its own inputs along -- A1 would end up
        # holding a temperature it has no use for, and the axis card would
        # grow a copy of the whole derivation chain.
        # The filename comes off the goal's own revision rather than being
        # spelled here. A carried number has to resolve to the goal it was
        # actually carried from, and check 12 matches on the filename alone.
        carried["origin"] = f"{artifact_name('goal.json', int(goal['revision']))}#{n['name']}"
        numbers.append(carried)
    wanted = set(names)
    assumptions = []
    for a in goal.get("assumptions", []) or []:
        overlap = [n for n in a.get("numbers", []) if n in wanted]
        if overlap:
            assumptions.append({**a, "numbers": overlap})
    return numbers, assumptions


# --------------------------------------------------------------------------- #
# librarian evidence
# --------------------------------------------------------------------------- #

SERVED_BY = "librarian_mcp"


def evidence(kb_result: dict | None, fallback_refs: list[dict] | None = None) -> dict:
    """The three evidence fields, from a served answer or from its absence.

    **The default is degraded, and undegraded requires proof.** A session whose
    librarian tools are not loaded does not fail loudly when it "calls" them --
    it simply proceeds on the degraded path (0.3-4). So the dangerous card is
    not the one that says `degraded: ["librarian_agent"]` while the service is
    down; that one is true. It is the card that says `degraded: []` because
    whoever wrote it believed a call happened.

    So `served_by` has to be present and has to say the service answered. A
    `None` result, or a result that cannot name its server, is treated as the
    service having been unreachable -- which is what it was.

    `fallback_refs` are entries read straight off the store files, which 4.3.0
    permits and which stay legitimate. They go in `kb_refs` either way: what
    changes with the service is not the values but **the discovery of what is
    missing**, and that is why `degraded` is about gaps rather than about
    citations.

    **"Either way" is what this said and not what it did until 2026-09-20.**
    The served branch returned the served entries alone and dropped the
    fallbacks, so a card that carried a `kb:` number and then reached the
    service lost the citation for it -- check 25 caught three of them the first
    time revision 2 ran with the librarian on. The two lists answer different
    questions, which is why neither replaces the other: the served entries are
    what this axis asked, and the fallbacks are what its carried numbers
    already stand on. Merged by `entry_id`, served winning, because the served
    copy is the one whose pin was checked on this call.
    """
    fallbacks = list(fallback_refs or [])
    if not kb_result or kb_result.get("served_by") != SERVED_BY:
        return {
            "kb_refs": fallbacks,
            "kb_gaps": [],
            "degraded": ["librarian_agent"],
        }
    merged = {r.get("entry_id"): r for r in fallbacks}
    merged.update({r.get("entry_id"): r for r in (kb_result.get("entries") or [])})
    return {
        "kb_refs": [merged[k] for k in sorted(merged)],
        "kb_gaps": list(kb_result.get("gaps") or []),
        "degraded": [],
    }


def carried_kb_refs(goal: dict, numbers: list[dict]) -> list[dict]:
    """The goal's citations for whichever `kb:` numbers were carried here.

    A number sourced `kb:<entry>` is a citation, and check 25 asks the card
    holding it to carry the record of what was cited. `carry` brings the number
    and the goal keeps the reference, so without this the two separate the
    moment a number leaves the goal -- which is what happened to
    `bead_diameter` in three axis cards as soon as it stopped being `assumed:`
    and became a citation of the store.

    Only the entries actually cited by these numbers, not the goal's whole
    list: a card that cites the reference it did not use is as wrong as one
    that omits the reference it did.
    """
    wanted = {str(n.get("source", ""))[3:] for n in numbers
              if str(n.get("source", "")).startswith("kb:")}
    return [dict(r) for r in (goal.get("kb_refs") or []) if r.get("entry_id") in wanted]


def observable(name: str) -> dict:
    """The observable as a card states it: the name, and nothing else.

    **A card does not carry the definition.** `contracts/observables.json`
    defines an observable, and a transport that restates the definition holds a
    second copy of the same thing -- which then drifts. Eight cards had drifted
    from the vocabulary by 2026-09-18, and this one among them had written an
    *estimator* into the definition field, which is the category error the
    two-field split exists to prevent. The name resolves to the entry; the
    entry is the definition.

    The name is checked against the vocabulary here, so a card cannot name an
    observable nobody has defined.

    The generated Markdown reads the vocabulary and prints both the definition
    and the estimator (P3: the JSON is authoritative, the prose is generated).
    That matters for the estimator in particular -- no card can carry one
    today, `comparable` is gated on both sides having run the same one, and
    until a contract can carry it the rendered text is the only record of
    which one a plan meant.
    """
    definition_entry(name)          # refuses a name the vocabulary lacks
    return {"name": name}


def definition_entry(name: str) -> dict:
    vocabulary = json.loads((CONTRACTS / "observables.json").read_text())
    for entry in vocabulary["observables"]:
        if entry["id"] == name:
            return entry
    raise KeyError(
        f"{name!r} is not in contracts/observables.json. An entry is added when a question "
        "needs one; a card may not define an observable the vocabulary has not."
    )


# --------------------------------------------------------------------------- #
# revisions
# --------------------------------------------------------------------------- #


def artifact_name(base: str, revision: int) -> str:
    """A card's filename for a given revision (4.5.5, 7.1 rule 3).

    Revision 1 keeps the bare name and every later revision takes a `v<N>_`
    prefix, so the revisions of one question sit side by side in one flat
    folder rather than replacing each other.

    **`v` and not `r`, because check 13 reads the two letters as two fields.**
    `r<N>_` is a ROUND and `v<N>_` is a REVISION (7.1 rule 3), and the check
    compares the number in the prefix against whichever field the letter names.
    This function returned `r<N>_` until 2026-09-20, after a6ab72b split the
    two: every card of this question carries `round: 0`, so the first
    revision-2 artifact generated would have been named `r2_` and failed check
    13 against a round of 0 -- the exact failure a6ab72b's own comment
    describes, still reachable because the validator moved and this did not.
    Found before generating revision 2 rather than by it.

    **This is the mechanism that removes a question nobody could answer.** A
    re-run that rewrote revision 1 in place had to decide, each time, which
    store version to stamp on a card that had already read one -- and there is
    no right answer to that, which is why this agent's pin moved four times in
    one evening. A new run is a new revision: revision 1 keeps what it read,
    and the new revision records what it read. Nothing has to be chosen.
    """
    if revision < 1:
        raise ValueError(f"revision {revision} is not a revision")
    return base if revision == 1 else f"v{revision}_{base}"


def question_revision(qid: str) -> int:
    """The revision the question is currently on: the latest goal on disk.

    Not "what goal.json says" any more -- that file is revision 1's and stays
    revision 1's. `goal_path` with no revision picks the highest `v<N>_goal`
    present, so raising a question's revision is writing its new goal rather
    than editing the old one in place.
    """
    return int(load_goal(qid)["revision"])


def canon_sha(card: dict) -> str:
    """The card's identity as the bridge computes it: sorted keys, no spaces.

    Deliberately the same form as the validator's, because that is what a
    bridge ledger records as `(card_id, revision, hash)`. Raw bytes cannot be
    the identity -- the bridge re-serialises the card inside the envelope --
    so semantic equality is what "not a character changed" means.
    """
    blob = json.dumps(card, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def content_sha(card: dict) -> str:
    """`canon_sha` with `status` removed: the card's content, not its state.

    A card's status advances along the state machine on the same file --
    DRAFT to VALIDATED to APPROVED (5.5) -- so a hash that includes it changes
    when nothing about the plan has. `plan_hash` already excludes status for
    exactly this reason: hashing it "would void an approval at the instant it
    was granted". The same argument applies to any check that asks whether the
    content moved.
    """
    return canon_sha({k: v for k, v in card.items() if k != "status"})


def refuse_overwrite(path: Path, revision: int, card: dict | None = None) -> None:
    """Stop rather than replace a card, on either of two grounds.

    **Another revision.** Previous output is not deleted (4.5.5); the repair
    for a changed question is a new revision, not a steadier hand.

    **The same revision with different content.** This is the one that cost
    something. Revision 1 of this agent's first plan held seven different
    contents in one evening, and a bridge seat computing its hash a day apart
    got two answers. Once a card has crossed into a round, a ledger records
    `(card_id, revision, hash)`; content moving under a fixed revision then
    stops the round, and the contract forbids repairing it (4.4). Refusing
    here is what makes "the revision is stable" a fact rather than an
    intention.

    Regeneration that reproduces the same card byte-for-byte is fine: that is
    a rebuild, not a change.
    """
    if not path.exists():
        return
    existing = json.loads(path.read_text())
    was = existing.get("revision")
    if was is not None and int(was) != revision:
        raise FileExistsError(
            f"{path.name} is revision {was} and this run is revision {revision}. "
            "A re-run raises the revision and writes beside the old output rather than over "
            f"it (4.5.5): the file for this one is {artifact_name(path.name, revision)!r}."
        )
    if card is not None and content_sha(existing) != content_sha(card):
        raise FileExistsError(
            f"{path.name} already exists at revision {revision} with different content.\n"
            f"  on disk: {content_sha(existing)}\n"
            f"  new    : {content_sha(card)}\n"
            "A fixed revision has one content. Changing it means raising the revision "
            f"({artifact_name(path.name, revision + 1)!r}), because a round that carried the old "
            "hash cannot be repaired once it has moved (4.4, 4.5.5)."
        )
