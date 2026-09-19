"""What every axis card needs, and no axis's reasoning.

Seven axes emit one kind of card, so the card's plumbing is shared and each
axis holds only the inequalities 4.5.3 gives it. This file is deliberately not
an axis: it owns the ledger shape, the store reads, the grade discipline and
the refusal to write a card that cannot hold what 4.5.2.1 requires.

Two alternatives were worse. Importing this from one axis into another would
put A1 inside A7's file, and rule (b) of 4.5.3 says no axis takes another's
output -- code shaped like that dependency is worth avoiding even where it is
only code. Copying the plumbing into seven files would drift, and the copy that
goes stale says something false without erroring (0.4-6).

plan.md 7 fixes the src/ file list and this name is not on it, which is a
deviation to say out loud rather than bury: that list names the seven axes,
synthesis, operator and orchestrator, and screening.py is already outside it.
The name belongs to the design seat if it wants a different one.

It reads contracts/ and the store, and imports no device (7.2 rule 2).
"""

from __future__ import annotations

import os
import sys

# The shadow screening.py and operator.py both document: this directory holds
# operator.py, `operator` is a standard-library module that `enum` imports at
# interpreter start-up, and `import json` reaches it through re and enum. Any
# file here run as a script breaks before its first statement without this.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
from dataclasses import dataclass, field                          # noqa: E402
from pathlib import Path                                          # noqa: E402

AGENT = Path(_HERE).parent
REPO = AGENT.parent
CONTRACTS = REPO / "contracts"
KB = REPO / "librarian_agent" / "kb"

LEDGER_FIELD = "inequalities"


def load_sibling(module_name: str, filename: str):
    """Import a file from this directory by path, never by name.

    By name would need src/ back on sys.path, which is the shadow above.
    operator.py resolves its own dependencies the same way.
    """
    path = os.path.join(_HERE, filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)                               # type: ignore[union-attr]
    return module


class AxisError(RuntimeError):
    """The axis could not run. Not a verdict -- a verdict is an answer."""


def kb_entry(entry_id: str) -> dict | None:
    """One entry, read straight off the store.

    This is the degraded path and a card that uses it has to say so (4.3.2):
    no service means no gap detection, no conflict detection and no external
    search, so what was missed is unknown rather than nothing.
    """
    path = KB / "entries" / f"{entry_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def kb_version() -> str | None:
    path = KB / "index.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text()).get("kb_version")
    except json.JSONDecodeError:
        return None


def kb_ref(entry_id: str, version: str | None) -> dict:
    """A reference carries the grade the store gave it and never a better one.

    Read out of the entry rather than restated, so a card cannot quietly
    promote what it cites (check 21).
    """
    entry = kb_entry(entry_id) or {}
    return {"entry_id": entry_id, "grade": entry.get("grade"),
            "kb_version": version, "claim": (entry.get("claim") or "")[:200]}


def load_responses(path: Path, pin: str, caller_id: str) -> dict:
    """What the librarian returned, and a refusal if any of it answered elsewhere.

    The normal path (4.3.2). kb_entry() above is the degraded one: it opens the
    store's files, and reading the files is not the service answering (0.3), so
    an axis that uses it cannot honestly write an empty `degraded` whatever it
    puts in the field. An axis that uses this one can.

    Three refusals, and each is a claim the card would otherwise make silently.
    A pin mismatch means the answer is to a different question and check 33
    exists to catch the mixture. A caller_id mismatch means another axis's
    answers, and isolation is by caller_id (4.3.1). Both stop here, where the
    reason is legible, rather than in a card someone has to unpick.
    """
    data = json.loads(path.read_text())
    if data.get("pin") != pin:
        raise AxisError(
            f"the responses were obtained at {data.get('pin')!r} and this axis is answering at "
            f"{pin!r}; re-ask rather than re-label"
        )
    if data.get("caller_id") != caller_id:
        raise AxisError(
            f"the responses were asked by {data.get('caller_id')!r}, not {caller_id!r}. Isolation "
            "is by caller_id (4.3.1), so another caller's answers are not this axis's input"
        )
    for eid, rec in (data.get("entries") or {}).items():
        got = (rec.get("answered_from") or {}).get("kb_version")
        if got != pin:
            raise AxisError(f"{eid} was answered from {got!r}, not the pinned {pin!r}")
    for gap in data.get("gaps") or []:
        got = (gap.get("answered_from") or {}).get("kb_version")
        if got != pin:
            raise AxisError(
                f"the gap on {gap.get('observable')!r} was answered from {got!r}, not {pin!r}"
            )
    return data


def refs_from(responses: dict, pin: str) -> list[dict]:
    """Refs carrying the grade the service returned, never a restated one (check 21)."""
    served = responses["entries"]
    return [{"entry_id": eid, "grade": served[eid]["grade"], "kb_version": pin,
             "claim": served[eid]["claim"][:200]}
            for eid in sorted(served)]


def gaps_from(responses: dict, pin: str, caller_id: str, gap_ids: dict[str, str]) -> list[dict]:
    """Gaps that name the call that came back empty, not a directory that was listed.

    `searched` held directory paths while there was no service to ask. Now it
    holds the call, because asked-and-absent and nobody-checked are different
    claims (4.3.1) and only the first one is available once the librarian
    answers.
    """
    out = []
    for gap in sorted(responses["gaps"], key=lambda g: g["observable"]):
        observable = gap["observable"]
        out.append({
            "gap_id": gap_ids[observable],
            "observable": observable,
            "kind": gap["kind"],
            "searched": [f"{gap['tool']}(observable={observable}, caller_id={caller_id}, "
                         f"kb_version={pin}) -> {gap['kind']}, searched {gap['searched']}"],
            "kb_version": pin,
            "asked_by": caller_id,
            "asked_at": gap["asked_at"],
        })
    return out


def goal_number(goal: dict, name: str) -> dict | None:
    return next((n for n in goal.get("numbers", []) if n.get("name") == name), None)


def capabilities() -> dict:
    return json.loads((CONTRACTS / "capabilities" / "microscope.json").read_text())


def configuration(config: str) -> dict:
    by_id = {c["config"]: c for c in capabilities().get("configurations", [])}
    if config not in by_id:
        raise AxisError(f"{config!r} is not a configuration in the capability table")
    return by_id[config]


@dataclass(frozen=True)
class Inequality:
    id: str
    parameter: str
    statement: str
    needs: tuple[str, ...]
    derived_from: str


@dataclass
class Outcome:
    """One inequality's result. Never absent, which is the whole point."""
    inequality_id: str
    parameter: str
    state: str                      # returned | abstained | not_run | failed
    kind: str | None = None         # no_input | not_constraining | not_requested
    reason: str = ""
    missing: list[str] = field(default_factory=list)
    interval: dict | None = None

    def as_dict(self) -> dict:
        out = {"inequality": self.inequality_id, "parameter": self.parameter,
               "state": self.state}
        if self.kind:
            out["kind"] = self.kind
        if self.reason:
            out["reason"] = self.reason
        if self.missing:
            out["missing"] = self.missing
        if self.interval is not None:
            out["interval"] = self.interval
        return out


@dataclass
class AxisRun:
    axis: str
    caller_id: str
    config: str
    kb_version: str | None
    owned: tuple[Inequality, ...]
    outcomes: list[Outcome] = field(default_factory=list)
    numbers: list[dict] = field(default_factory=list)
    kb_refs: list[dict] = field(default_factory=list)
    kb_gaps: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    degraded: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if any(o.state == "failed" for o in self.outcomes):
            raise AxisError("an inequality failed; a failed axis has no verdict (4.5.2.1)")
        if any(o.state == "returned" for o in self.outcomes):
            return "feasible"
        return "abstain"

    def silent(self) -> list[str]:
        """Inequalities on the list with neither a range nor an abstention.

        Refused here rather than downstream: an axis that reports six of seven
        has already lost the fact that the seventh was never asked (4.5.2.1).
        """
        spoke = {o.inequality_id for o in self.outcomes}
        return [i.id for i in self.owned if i.id not in spoke]

    def gap(self, gap_id: str, observable: str, searched: list[str],
            nearest: list[dict] | None = None) -> None:
        entry = {"gap_id": gap_id, "observable": observable, "kind": "absent",
                 "searched": searched, "kb_version": self.kb_version,
                 "asked_by": self.caller_id}
        if nearest:
            entry["nearest"] = nearest
        self.kb_gaps.append(entry)


def ledger_has_a_home() -> bool:
    """Whether an axis card can carry the per-inequality ledger at all.

    False until axis.schema.json declares the field, and then the refusal
    clears itself. Folding several outcomes into one abstain_reason string
    makes prose, and prose is what 4.5.2.1 replaced.
    """
    schema = json.loads((CONTRACTS / "schemas" / "axis.schema.json").read_text())
    return LEDGER_FIELD in (schema.get("properties") or {})


def returned_needs_numeric_interval() -> bool:
    """Whether the contract makes `returned` require an interval it can only state numerically.

    Read off the schema rather than assumed, so that the refusal below clears
    itself the day a slot for a discrete constraint exists -- the same shape as
    ledger_has_a_home().

    A4 is where this bites. The three axis states are a numeric range, an
    abstention with a kind, or a failure, and a bound that has grounds and
    constrains something other than a number is none of the three: `interval`
    requires {parameter, unit, basis} with numeric min/max, `basis` names
    entries in numbers[], and both the interval and the ledger item forbid
    additional properties. So the contract cannot hold "this configuration's
    selectors are readable but not verifiable" in any shape, well or badly.
    """
    schema = json.loads((CONTRACTS / "schemas" / "axis.schema.json").read_text())
    item = ((schema.get("properties") or {}).get("inequalities") or {}).get("items") or {}
    for rule in item.get("allOf") or []:
        if (((rule.get("if") or {}).get("properties") or {}).get("state") or {}).get("const") == "returned":
            if "interval" in ((rule.get("then") or {}).get("required") or []):
                return True
    return False


def to_card(run: AxisRun, goal: dict, qid: str, created_at: str) -> dict:
    silent = run.silent()
    if silent:
        raise AxisError(
            f"{len(silent)} inequalities said nothing: {', '.join(silent)}. The axis's output is "
            "refused, because silence on a bound reads downstream as that bound not applying "
            "(4.5.2.1)"
        )
    if not ledger_has_a_home():
        raise AxisError(
            f"axis.schema.json declares no {LEDGER_FIELD!r} and is closed to additional "
            f"properties, so this card cannot carry the {len(run.outcomes)} per-inequality "
            "outcomes 4.5.2.1 requires"
        )
    discrete = [o.inequality_id for o in run.outcomes
                if o.state == "returned" and o.interval is None]
    if discrete and returned_needs_numeric_interval():
        raise AxisError(
            f"{len(discrete)} bounds have grounds and constrain something that is not a number: "
            f"{', '.join(discrete)}. axis.schema.json makes `interval` required when state is "
            "`returned`, and interval requires {parameter, unit, basis} with numeric min/max -- "
            "so the card cannot say it. The three ways out are all worse than stopping: a made-up "
            "interval would be a fabricated bound resting on an empty `basis`, and each of the "
            "three abstention kinds is false here -- the inputs were present (not no_input), the "
            "bound does bite (not not_constraining), and it was asked for (not not_requested). "
            "A discrete constraint needs a slot in the contract, which is the manager's (6.2)"
        )
    card = {
        "card": "axis",
        "schema_version": "0.1",
        "id": f"axis-{qid}-{run.config}-{run.axis}",
        "qid": qid,
        "thread": goal.get("thread", f"solo-{qid}"),
        "round": goal.get("round", 0),
        "revision": 1,
        "author": "microscope_agent",
        "created_at": created_at,
        "status": "DRAFT",
        "caller_id": run.caller_id,
        "config": run.config,
        "axis": run.axis,
        "kb_version": run.kb_version,
        "method": "deterministic",
        "verdict": run.verdict,
        "constraints": [o.interval for o in run.outcomes if o.interval is not None],
        LEDGER_FIELD: [o.as_dict() for o in run.outcomes],
        "numbers": run.numbers,
        "kb_refs": run.kb_refs,
        "kb_gaps": run.kb_gaps,
        "degraded": run.degraded,
        "note": " ".join(run.notes),
    }
    if card["verdict"] == "abstain":
        card["abstain_reason"] = (
            "Every inequality this axis owns abstained, each for its own reason; the ledger "
            "carries them one by one rather than collapsing them into this sentence."
        )
    return card


def report(run: AxisRun) -> None:
    print(f"{run.axis.upper()} {run.config}: verdict {run.verdict}, "
          f"{len(run.outcomes)} inequalities, kb_version {run.kb_version}, "
          f"degraded {run.degraded}")
    for o in run.outcomes:
        line = f"  {o.inequality_id:30} {o.state:10}"
        if o.kind:
            line += f" {o.kind:17}"
        if o.missing:
            line += f" missing={','.join(o.missing)}"
        print(line)
    for note in run.notes:
        print(f"  note: {note}")


def write(run: AxisRun, goal: dict, qid: str, created_at: str) -> int:
    """Write the card, or refuse and print the ledger so the work is not lost."""
    try:
        card = to_card(run, goal, qid, created_at)
    except AxisError as exc:
        print(f"\nno card written: {exc}", file=sys.stderr)
        print("\nledger, in full:")
        print(json.dumps([o.as_dict() for o in run.outcomes], ensure_ascii=False, indent=2))
        return 3
    out = AGENT / "questions" / qid / f"axis_{run.config}_{run.axis}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {out.relative_to(REPO)}")
    return 0
