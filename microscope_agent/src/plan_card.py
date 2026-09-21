"""S5: emit the plan, or say exactly which mandatory field cannot be filled (4.5.5).

S5 writes one card and its generated Markdown, and the JSON is authoritative
(P3): editing the .md changes nothing, which is why it is written from the
JSON here rather than kept beside it.

It invents nothing. Every number on the plan came from S4's operating point,
which came from intersecting what the axes returned; S5's own work is
assembling the shape 5.4 requires and refusing when a required part of that
shape has no source.

THE REFUSAL IS THE NORMAL OUTPUT TODAY AND IT IS NOT A FAILURE. plan.schema
requires conditions, actions and stop_criteria, and each of those points into
numbers[] by name -- a condition never restates a value (5.2). So a plan can
only exist for parameters some axis bounded. With 34 of 37 inequalities
abstaining there is nothing to point at, and the useful output is the list of
which mandatory fields have no source and which axis's silence is behind each.
That list is what a person acts on; a plan assembled around the hole is not.

Why the check is per FIELD and not one verdict: 4.5.6 puts S5's stop at
"validator failure -> stays DRAFT". A card that cannot be built at all never
reaches the validator, so it would stop nowhere and report nothing.
"""

from __future__ import annotations

import os
import sys

# See screening.py: this directory holds operator.py, `operator` is a
# standard-library module, and `enum` imports it during interpreter start-up.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
from datetime import datetime, timezone                          # noqa: E402
from pathlib import Path                                         # noqa: E402

AGENT = Path(_HERE).parent
REPO = AGENT.parent
CONTRACTS = REPO / "contracts"
QUESTIONS = AGENT / "questions"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, Path(_HERE) / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


s4 = _load("_mic_synthesis", "synthesis.py")


class PlanError(RuntimeError):
    """S5 will not write a plan, and names the field rather than the stage."""


# --------------------------------------------------------------------------- #
# the discrete choice S4 cannot make alone
# --------------------------------------------------------------------------- #


def selector_numbers(chosen_pair: str) -> list[dict]:
    """`100x@1x` -> the two numbers a plan can actually carry.

    An allowed_set over objective/zoom pairs is a bound on a SELECTOR, and
    the plan's machinery is numeric: conditions point into numbers[] by name
    and a number's value is a number, so the string `100x@1x` cannot be a
    condition. It decomposes without loss into the two settings the
    instrument actually takes -- the nosepiece POSITION, which is what the
    turret is commanded with and what operator.resolve_limits keys the focus
    floor by, and the intermediate magnification.

    The position is read from the envelope snapshot's own turret row rather
    than counted here, because this turret is indexed from 0 and the table
    says so in an `index_note`: 1-6 would be off by one on every lens.
    """
    snapshot = AGENT / "envelope" / "snapshot.json"
    if not snapshot.exists():
        raise PlanError("envelope/snapshot.json is absent, so a nosepiece position cannot be resolved")
    snap = json.loads(snapshot.read_text())
    devices = json.loads(((snap.get("tables") or {}).get("devices") or {}).get("text") or "{}")
    turret = next((e for c in devices.get("channels", []) or []
                   for e in (c.get("elements") or []) if e.get("id") == "nosepiece"), None)
    if turret is None:
        raise PlanError("the snapshot's device table has no nosepiece element")

    magnification, _, zoom = chosen_pair.partition("@")
    row = next((o for o in turret.get("objectives", [])
                if str(o.get("id", "")).split("-")[0] == magnification), None)
    if row is None:
        raise PlanError(
            f"no objective on this turret answers to {magnification!r}; the set offered "
            f"{chosen_pair!r} and the turret holds "
            f"{[o.get('id') for o in turret.get('objectives', [])]}"
        )
    return [
        {"name": "nosepiece_position", "value": row["position"], "unit": "count",
         "source": f"kb:{row['entry_ref']}", "grade": "E3", "precision": "significant_figures",
         "note": (f"position {row['position']} is the {row['id']} lens ({row['part_number']}). "
                  "The turret is indexed from 0, which the device table states in its own "
                  "index_note; this is read from there and not counted here")},
        {"name": "intermediate_magnification", "value": float(zoom.rstrip("x")), "unit": "1",
         "source": "computed:allowed_set_choice", "grade": "E4",
         "precision": "significant_figures",
         "note": f"the zoom half of the pair {chosen_pair!r} A6's Nyquist bound permits"},
    ]


def choose_from_set(allowed: dict, goal: dict) -> tuple[str | None, str]:
    """Which value of a discrete bound to spend the plan on.

    4.5.4 rule 2 puts the choice on S4 and gives it a rule: in explore mode a
    difference under 10x is not a difference, and a tie breaks by evidence
    grade, then safety margin, then whichever has been tried less (P16), then
    cost. Four objective/zoom pairs that all satisfy Nyquist are a tie on
    every one of those -- same catalogue grade, no safety margin computed for
    any of them, none tried, no cost model. So there is nothing to break it
    with, and 4.5.4's last clause applies: **if there is no order, S4 does not
    guess**, it goes back to the person through 4.5.1 (c).

    Asking once is cheaper than inventing a discriminator. What would settle
    it is not a preference either -- it is A6's other two bounds, field of
    view and lateral resolution, both of which are abstaining on inputs the
    person holds.
    """
    values = allowed.get("values") or []
    if len(values) == 1:
        return values[0], "one value survived the intersection, so nothing was chosen"
    preference = [p for p in (goal.get("configuration_preference") or []) if p in values]
    if preference:
        return preference[0], (f"the goal card's configuration_preference names {preference[0]!r}, "
                               "which the bound permits; a preference is a tie-break and not "
                               "evidence (preference_is_not_evidence)")
    return None, (
        f"{len(values)} values satisfy this bound and nothing distinguishes them: same evidence "
        "grade, no safety margin computed for any, none tried before, no cost model. 4.5.4 breaks "
        "a tie by grade, then margin, then P16, then cost, and all four are level -- so this goes "
        "to the person (4.5.1 c) rather than being guessed. What would settle it properly is A6's "
        "field_of_view and lateral_resolution bounds, which are abstaining on inputs the person holds"
    )


# --------------------------------------------------------------------------- #
# can the mandatory shape be filled?
# --------------------------------------------------------------------------- #


def mandatory_fields() -> list[str]:
    """Read off plan.schema.json, so this list cannot drift from the contract."""
    schema = json.loads((CONTRACTS / "schemas" / "plan.schema.json").read_text())
    head = json.loads((CONTRACTS / "schemas" / "common.schema.json").read_text())
    return sorted(set(schema.get("required") or []) |
                  set(head["$defs"]["common_head"].get("required") or []))


def assemble(qid: str, revision: int = 1, created_at: str | None = None) -> tuple[dict, list[str]]:
    """Build as much of the plan as the axes support, and list what is unfillable.

    Returns (card, unfillable). `unfillable` names mandatory fields with no
    source and says which silence is behind each, so the next action is a
    person or a measurement rather than a re-read of this file.
    """
    goal, _configs, by_config = s4.load_fanout(qid)
    card4, detail, why = s4.synthesise(qid, revision)
    created_at = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    config = card4.get("chosen_config")
    if config is None:
        raise PlanError(f"S4 chose no configuration: {why}")
    d = detail[config]

    numbers = list(card4.get("numbers") or [])
    conditions = [{"parameter": p["parameter"], "number": p["number"]}
                  for p in card4.get("operating_point") or []]
    unfillable: list[str] = []

    # The discrete bounds, where a value can be chosen without a person.
    for parameter, allowed in sorted(d["allowed_sets"].items()):
        value, reason = choose_from_set(allowed, goal)
        if value is None:
            unfillable.append(f"{parameter}: {reason}")
            continue
        if parameter == "objective_zoom_pair":
            for n in selector_numbers(value):
                numbers.append(n)
                conditions.append({"parameter": n["name"], "number": n["name"],
                                   "device": "nosepiece" if n["name"] == "nosepiece_position"
                                   else "intermediate_magnification"})

    # A goal-side target is carried, never recomputed (5.2, check 52).
    target = next((n for n in goal.get("numbers") or []
                   if n.get("name") == "target_decade_resolution"), None)
    success = []
    if target is not None:
        numbers.append({**{k: v for k, v in target.items() if k != "note"},
                        "origin": "goal.json#target_decade_resolution"})
        success.append({"id": "ok_decade", "metric": "diffusivity_decades_resolved",
                        "comparator": ">=", "number": "target_decade_resolution",
                        "statement": "the diffusivity is placed within one decade"})
    else:
        unfillable.append("success_criteria: the goal card carries no target to compare against")

    if not conditions:
        open_names = sorted({u["parameter"] for u in d["unbounded"] if u.get("kind") == "no_input"})
        unfillable.append(
            "conditions: every parameter is unbounded, so there is nothing to point at. A "
            "condition names a number and never restates a value (5.2), and no axis returned "
            f"one. Open: {', '.join(open_names)}")
    if not any(n["name"] for n in numbers):
        unfillable.append("numbers: nothing was bounded, so the card has no values to carry")
    unfillable.append(
        "actions: no axis bounded an acquisition parameter, so there is no exposure, frame rate "
        "or record length for an acquire action to carry. A1 and A2 own those and both abstain")
    unfillable.append(
        "stop_criteria: a criterion compares a metric against a number in numbers[] (5.4), and "
        "the drift, dose and duration bounds that would supply one are A3's and A5's, which abstain")
    unfillable.append(
        "cost: no duration is bounded, so wall_clock would be a number this stage invented "
        "(4.5.4 rule 4 forbids it one stage earlier and it is no better here)")

    card = {
        "card": "plan",
        "schema_version": "0.1",
        "id": f"plan-{qid}-r{revision}",
        "qid": qid,
        "thread": goal.get("thread", f"solo-{qid}"),
        "round": goal.get("round", 0),
        "revision": revision,
        "author": "microscope_agent",
        "created_at": created_at,
        "status": "DRAFT",
        "goal_id": goal.get("id"),
        "purpose": ("Measure the tracer diffusivity on the configuration S3.0 screened and S4 "
                    "chose, under the conditions the axes bounded."),
        "intent": goal.get("intent", "explore"),
        "observable": {"name": (goal.get("observable") or {}).get("name")},
        "system_configuration": {"config": config, "optical_path": None, "devices": [], "model": None},
        "conditions": conditions,
        "actions": [],
        "envelope_check": {"checked_against": [], "status": "unavailable",
                           "note": "no condition is bounded, so nothing was compared"},
        "cost": {"wall_clock": "", "numbers": []},
        "stop_criteria": [],
        "success_criteria": success,
        "open_risks": [],
        "numbers": numbers,
        "degraded": [],
    }
    return card, unfillable


def to_markdown(card: dict) -> str:
    """The human-readable face of the card, generated and never authored (P3).

    Every number here is rendered from `numbers[]`, so a value that appears in
    both places cannot disagree -- and if someone edits this file the system
    does not read it. That is the whole of 5.6: one authoritative copy, and a
    second one that is visibly derived.
    """
    lines = [f"# plan {card['id']}", "",
             f"*Generated from {card['id']}.json. Editing this file changes nothing (P3, 5.6).*",
             "", f"- question: `{card['qid']}`  ·  thread `{card['thread']}`  ·  revision "
             f"{card['revision']}  ·  status **{card['status']}**",
             f"- observable: `{card['observable']['name']}`  ·  intent: {card['intent']}",
             f"- configuration: `{card['system_configuration']['config']}`", "",
             "## Purpose", "", card["purpose"], ""]
    if card.get("numbers"):
        lines += ["## Numbers", "", "| name | value | unit | grade | source |",
                  "|---|---|---|---|---|"]
        lines += [f"| `{n['name']}` | {n['value']} | {n.get('unit','')} | {n.get('grade','')} | "
                  f"`{n.get('source','')}` |" for n in card["numbers"]]
        lines.append("")
    if card.get("conditions"):
        lines += ["## Conditions", ""]
        lines += [f"- `{c['parameter']}` = `numbers[{c['number']}]`"
                  + (f" on `{c['device']}`" if c.get("device") else "") for c in card["conditions"]]
        lines.append("")
    if card.get("actions"):
        lines += ["## Actions", ""]
        lines += [f"- **{a['id']}** `{a['action']}` on `{a['device']}` "
                  f"(tier {a['tier']}, {'reversible' if a['reversible'] else '**irreversible**'})"
                  for a in card["actions"]]
        lines.append("")
    for field, heading in (("stop_criteria", "Stop criteria"),
                           ("success_criteria", "Success criteria")):
        if card.get(field):
            lines += [f"## {heading}", ""]
            lines += [f"- **{c['id']}**: {c.get('statement','')} "
                      f"(`{c['metric']}` {c['comparator']} `numbers[{c['number']}]`)"
                      for c in card[field]]
            lines.append("")
    if card.get("open_risks"):
        lines += ["## Open risks", ""] + [f"- {r}" for r in card["open_risks"]] + [""]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S5: emit the plan card (4.5.5)")
    parser.add_argument("--qid", required=True)
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    try:
        card, unfillable = assemble(args.qid, args.revision)
    except (PlanError, s4.SynthesisError) as exc:
        print(f"S5 refused: {exc}", file=sys.stderr)
        return 2

    print(f"S5 {args.qid}: configuration {card['system_configuration']['config']}, "
          f"{len(card['numbers'])} number(s), {len(card['conditions'])} condition(s)")
    for n in card["numbers"]:
        print(f"  number  {n['name']:28} {n['value']} {n['unit']:6} {n['grade']}  {n['source']}")
    if not unfillable:
        if args.write:
            out = QUESTIONS / args.qid / f"plan_microscope_{args.qid}.json"
            out.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n")
            out.with_suffix(".md").write_text(to_markdown(card))
            print(f"  wrote {out.relative_to(REPO)} and its generated .md")
        return 0

    print(f"\nS5 will not write a plan: {len(unfillable)} mandatory field(s) have no source.",
          file=sys.stderr)
    for line in unfillable:
        print(f"  {line}", file=sys.stderr)
    print("  These are not defects in this stage. Each one is an axis that abstained for a\n"
          "  reason it recorded, and the next action is on its kb_gap or on the person --\n"
          "  run src/synthesis.py for the full list of 34.", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
