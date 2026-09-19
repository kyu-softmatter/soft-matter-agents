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

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONTRACTS = REPO / "contracts"
AGENT = REPO / "simulation_agent"

AUTHOR = "simulation_agent"

# The same table the validator derives grades with (5.3). `computed` and `kb`
# are None because neither is fixed by the prefix alone: a computed value takes
# the worst of its inputs, and a kb value takes the grade the entry carried.
SOURCE_GRADE = {
    "measured": "E1",
    "calibration": "E2",
    "spec": "E3",
    "operator_read": "E3",
    "operator_recall": "E5",
    "computed": None,
    "assumed": "E5",
    "kb": None,
}


def grade_for(source: str, input_grades: list[str] | None = None) -> str:
    """The grade that follows from a source (5.3). Never self-reported."""
    prefix = source.split(":", 1)[0]
    if prefix not in SOURCE_GRADE:
        raise ValueError(f"unknown source kind {prefix!r}")
    fixed = SOURCE_GRADE[prefix]
    if fixed is not None:
        return fixed
    if prefix == "computed":
        worst = max(input_grades or ["E4"])
        return max("E4", worst)
    raise ValueError("a kb: source takes its grade from the kb_ref, not from here")


def num(name: str, value: float, unit: str, source: str, **kw) -> dict:
    """One number as the four parts P2 requires, plus optional provenance.

    `inputs` and `formula` are required by the validator when the source is
    computed:, and the grade then follows from the inputs' grades -- so they
    are passed as (name, grade) pairs rather than bare names.
    """
    inputs: list[tuple[str, str]] = kw.pop("inputs", [])
    out = {"name": name, "value": value, "unit": unit, "source": source}
    if source.startswith("computed:"):
        if not inputs or "formula" not in kw:
            raise ValueError(f"{name}: a computed number needs a formula and its inputs")
        out["grade"] = grade_for(source, [g for _, g in inputs])
        out["formula"] = kw.pop("formula")
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


def load_goal(qid: str) -> dict:
    return json.loads((question_dir(qid) / "goal.json").read_text())


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
        carried["origin"] = f"goal.json#{n['name']}"
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
    """
    if not kb_result or kb_result.get("served_by") != SERVED_BY:
        return {
            "kb_refs": list(fallback_refs or []),
            "kb_gaps": [],
            "degraded": ["librarian_agent"],
        }
    return {
        "kb_refs": list(kb_result.get("entries") or []),
        "kb_gaps": list(kb_result.get("gaps") or []),
        "degraded": [],
    }


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
