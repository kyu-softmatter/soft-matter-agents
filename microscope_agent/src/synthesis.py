"""S4: combine what the axes said, per configuration, and choose (4.5.4).

S4 ONLY COMBINES. It makes no new number and asks the librarian nothing --
4.5.4 rule 4, and the reason is in the sentence after it: once the synthesis
stage starts querying, S3's parallel independence stops meaning anything and
one agent is judging everything alone again. If the conclusion is that more
knowledge is needed, the move is back to S3 as a new revision (P9).

So everything here is arithmetic on what is already on disk. The one thing it
produces that was not written by an axis is the operating point, and 4.5.4
rule 2 asks for exactly that -- a point inside the intersection -- which is a
choice among values the axes already permitted, not a new fact.

WHAT IT REFUSES TO DO IS THE INTERESTING HALF. An axis that abstained did not
say "anything goes"; it said it had no grounds (P5, 4.5.2.1). Treating an
abstention as an unbounded interval is the one mistake that would turn seven
honest silences into a plan, so an abstained parameter is carried as
UNBOUNDED and never as a bound with no ends. A parameter the plan needs and
nobody bounded is what stops S5, and it stops it by name.
"""

from __future__ import annotations

import os
import sys

# The same four lines screening.py carries, for the same reason and not by
# preference: running this file as a script puts its own directory at the head
# of sys.path, and this directory holds operator.py. `operator` is a
# standard-library module that `enum` imports during interpreter start-up, so
# the shadow does not wait to be asked for -- `import argparse` below is
# enough to pull our operator.py into the middle of the standard library's own
# import and die there with a circular-import error naming `re`. Measured
# again here on 2026-09-20, which is the third module to pay for one filename.
# plan.md 7 fixes the name and the rename belongs to the design seat.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import json                                                      # noqa: E402
import re                                                        # noqa: E402
import math                                                      # noqa: E402
from datetime import datetime, timezone                          # noqa: E402
from pathlib import Path                                         # noqa: E402

AGENT = Path(__file__).resolve().parent.parent
REPO = AGENT.parent
QUESTIONS = AGENT / "questions"

AXES = ("a1", "a2", "a3", "a4", "a5", "a6", "a7")


class SynthesisError(RuntimeError):
    """S4 cannot combine, and says why rather than combining anyway."""


# --------------------------------------------------------------------------- #
# reading the fan-out
# --------------------------------------------------------------------------- #


def load_fanout(qid: str) -> tuple[dict, dict, dict[str, dict[str, dict]]]:
    """goal, configs and the axis cards, grouped config -> axis -> card.

    Cards are gathered from the question's own directory and grouped by their
    own `config` and `axis`, NOT by the caller_ids configs.json recorded. A
    revision is a re-run (4.5.5) and a re-run may be targeted at one axis, so
    the caller_id on a card can be ahead of the one the fan-out issued --
    a6 is at v4 today against configs.json's v3. Matching on the issued id
    would silently drop exactly the card that was corrected most recently.
    """
    folder = QUESTIONS / qid
    if not folder.exists():
        raise SynthesisError(f"{folder} does not exist; S3.0 has not run for this question")
    goal = json.loads((folder / "goal.json").read_text())
    configs_path = folder / "configs.json"
    if not configs_path.exists():
        raise SynthesisError(
            f"{configs_path} does not exist. S4 combines what S3.0 screened, and without the "
            "screening record there is no list of configurations to combine over (4.5.4)"
        )
    configs = json.loads(configs_path.read_text())

    # THE NEWEST PREFIX SET, NOT EVERY CARD IN THE FOLDER. A re-run of a whole
    # fan-out writes `v2_axis_*` beside `axis_*` rather than over it (4.5.5),
    # and check 58 groups by that prefix because the two are exactly the sets
    # S4 reads separately. Globbing `axis_*` alone would keep reading the
    # superseded set after a re-pin -- the pin moves, the cards are rewritten,
    # and S4 intersects the old ones -- so the highest prefix present wins and
    # the rest stay on disk as the record P9 keeps them for.
    prefixes = sorted({m.group(1) for p in folder.glob("v*_axis_*.json")
                       if (m := re.match(r"(v\d+_)axis_", p.name))},
                      key=lambda s: int(s[1:-1]))
    prefix = prefixes[-1] if prefixes else ""
    by_config: dict[str, dict[str, dict]] = {}
    for path in sorted(folder.glob(f"{prefix}axis_*.json")):
        card = json.loads(path.read_text())
        slot = by_config.setdefault(card["config"], {})
        held = slot.get(card["axis"])
        if held is None or card.get("revision", 1) > held.get("revision", 1):
            card["__path"] = str(path.relative_to(REPO))
            slot[card["axis"]] = card
    if not by_config:
        raise SynthesisError(f"no axis cards under {folder}; S3 has not run")
    return goal, configs, by_config


def not_run(configs: dict, by_config: dict[str, dict[str, dict]]) -> dict[str, list[str]]:
    """What S3.0 sent out and S4 did not get back, per configuration.

    A CARD THAT IS ABSENT IS NOT A CARD THAT SAID NOTHING, and without this
    the two are the same thing downstream. S3.0's fan_out is the list of
    caller_ids it issued, so it is the only record of what was supposed to
    exist; an axis or a whole configuration that was never run simply does
    not appear in the directory, and S4 grouping by what it finds would
    report the remainder as if that were the whole question.

    This is 4.5.2.1's rule one level up. There it is an axis that says
    nothing about two of its five inequalities and reads as `this axis does
    not constrain there`; here it is a configuration nobody ran and reads as
    a configuration that was never a candidate. Both are silence wearing the
    shape of an answer.

    It matters immediately rather than hypothetically: on 2026-09-20 the
    person narrowed mic-20260920-001 to one of the three configurations S3.0
    screened in, which is a legitimate decision about what to spend, and
    without this the other two would have vanished from the synthesis with
    nothing recording that they were screened in and skipped.
    """
    issued: dict[str, set[str]] = {}
    for row in configs.get("fan_out", []) or []:
        issued.setdefault(row["config"], set()).add(row["axis"])
    missing: dict[str, list[str]] = {}
    for config, axes in sorted(issued.items()):
        have = set(by_config.get(config) or {})
        gap = sorted(axes - have)
        if gap:
            missing[config] = gap
    return missing


def one_store(cards: list[dict]) -> str:
    """Every card of one fan-out reads one store, or the intersection is not one.

    Check 58's rule, enforced here rather than only reported there: an axis
    left at an older pin reports absent for what the newer store holds, and
    downstream that is indistinguishable from a real absence. Intersecting
    across two pins would bake that in.
    """
    pins = sorted({c.get("kb_version") for c in cards})
    if len(pins) != 1:
        raise SynthesisError(
            f"the axis cards cite {len(pins)} kb_versions {pins}. S4 intersects them together, so "
            "one store or none (4.5.2, check 58). Re-derive the stragglers; do not re-pin them "
            "without re-asking"
        )
    return pins[0]


# --------------------------------------------------------------------------- #
# the intersection (4.5.4 rule 1) -- deterministic, no judgement
# --------------------------------------------------------------------------- #


def intersect_intervals(rows: list[tuple[str, dict]]) -> tuple[list[dict], list[dict]]:
    """Per parameter, the tightest min and the loosest max both axes allow.

    Returns (intervals, conflicts). A conflict is an intersection whose min
    has passed its max, and it is reported with the two axes and the two
    numbers that crossed -- 4.5.4 rule 1 asks for which two axes conflict at
    what values, because a refusal without numbers is an opinion (P5).

    Units are not converted here. Two axes bounding one parameter in
    different units is a contract failure upstream, not something to paper
    over with a factor: si() lives in the validator and a silent conversion
    is how a factor of a thousand becomes invisible.
    """
    by_parameter: dict[str, list[tuple[str, dict]]] = {}
    for axis, interval in rows:
        by_parameter.setdefault(interval["parameter"], []).append((axis, interval))

    out: list[dict] = []
    conflicts: list[dict] = []
    for parameter, items in sorted(by_parameter.items()):
        units = sorted({i["unit"] for _, i in items})
        if len(units) != 1:
            raise SynthesisError(
                f"{parameter} is bounded in {units} by different axes. S4 does not convert: a unit "
                "is part of a quantity's identity (quantities.json rule 3), and two units on one "
                "name is a defect to fix upstream"
            )
        lo = hi = None
        lo_axis = hi_axis = None
        basis: list[str] = []
        precision = set()
        for axis, i in items:
            basis += [b for b in i.get("basis", []) if b not in basis]
            if i.get("precision"):
                precision.add(i["precision"])
            if i.get("min") is not None and (lo is None or i["min"] > lo):
                lo, lo_axis = i["min"], axis
            if i.get("max") is not None and (hi is None or i["max"] < hi):
                hi, hi_axis = i["max"], axis
        if lo is not None and hi is not None and lo > hi:
            conflicts.append({
                "axes": [lo_axis, hi_axis],
                "parameter": parameter,
                "statement": (f"{lo_axis} needs {parameter} >= {lo} {units[0]} and {hi_axis} needs "
                              f"it <= {hi} {units[0]}; the two do not overlap"),
            })
            continue
        row = {"parameter": parameter, "unit": units[0], "basis": basis}
        if lo is not None:
            row["min"] = lo
        if hi is not None:
            row["max"] = hi
        # The worst precision any input carried, which is what a combined
        # bound inherits (P15, 5.8). Silence is not an improvement.
        for worst in ("order_of_magnitude", "significant_figures", "exact"):
            if worst in precision:
                row["precision"] = worst
                break
        out.append(row)
    return out, conflicts


def intersect_sets(rows: list[tuple[str, dict]]) -> tuple[dict[str, dict], list[dict]]:
    """Per parameter, the values every axis that spoke about it permits.

    A discrete bound intersects by set intersection, and an empty result is
    the same failure an empty interval is: two axes that permit nothing in
    common.
    """
    by_parameter: dict[str, list[tuple[str, dict]]] = {}
    for axis, allowed in rows:
        by_parameter.setdefault(allowed["parameter"], []).append((axis, allowed))

    out: dict[str, dict] = {}
    conflicts: list[dict] = []
    for parameter, items in sorted(by_parameter.items()):
        keep: set[str] | None = None
        basis: list[str] = []
        axes = []
        for axis, allowed in items:
            axes.append(axis)
            basis += [b for b in allowed.get("basis", []) if b not in basis]
            values = set(allowed.get("values") or [])
            keep = values if keep is None else (keep & values)
        if not keep:
            conflicts.append({
                "axes": [axes[0], axes[-1] if len(axes) > 1 else axes[0]],
                "parameter": parameter,
                "statement": (f"the axes bounding {parameter} permit no value in common: "
                              + "; ".join(f"{a} allows {sorted(i.get('values') or [])}"
                                          for a, i in items)),
            })
            continue
        out[parameter] = {"parameter": parameter, "values": sorted(keep), "basis": basis,
                          "from_axes": axes}
    return out, conflicts


# --------------------------------------------------------------------------- #
# what nobody bounded
# --------------------------------------------------------------------------- #


def unbounded_of(cards: dict[str, dict]) -> list[dict]:
    """Every parameter an axis owns and did not bound, with why and what is missing.

    This is the field the synthesis card needs most and the one the contract
    does not declare yet. Without it a card holding three bounds out of
    thirty-seven reads as a configuration that is nearly decided, which is
    the reading 4.5.2.1 was written to prevent -- silence on a bound looks
    downstream like that bound not applying.

    `not_constraining` is kept apart from `no_input` here for the same
    reason the axis keeps them apart: one of them is closed and the other is
    waiting on somebody.
    """
    out = []
    for axis in sorted(cards):
        for row in cards[axis].get("inequalities", []) or []:
            if row.get("state") == "returned":
                continue
            out.append({
                "axis": axis,
                "inequality": row.get("inequality"),
                "parameter": row.get("parameter"),
                "state": row.get("state"),
                "kind": row.get("kind"),
                "missing": row.get("missing") or [],
            })
    return out


# --------------------------------------------------------------------------- #
# choosing (4.5.4 rule 2)
# --------------------------------------------------------------------------- #


def geometric_middle(row: dict) -> float | None:
    """The point inside a two-sided interval, chosen the same way every time.

    Geometric rather than arithmetic because these bounds are stated in
    decades (P15): halfway between 1 ms and 1 s is 31 ms, not 500 ms, and the
    arithmetic middle of a decade-wide interval sits against its top end.

    A one-sided interval has no middle and gets none. Picking the bound
    itself would be operating exactly at a limit, and inventing an opposite
    end would be S4 making a number (4.5.4 rule 4).
    """
    lo, hi = row.get("min"), row.get("max")
    if lo is None or hi is None:
        return None
    if lo <= 0 or hi <= 0:
        return (lo + hi) / 2
    return math.sqrt(lo * hi)


def choose_config(survivors: list[str], goal: dict) -> tuple[str | None, str, list[str], str]:
    """Which configuration to spend the plan on, and by whose order.

    One survivor is not a choice and is not recorded as one. Several is a
    choice, and 4.5.4 settles who makes it: the concession order comes in on
    the goal card, written before any axis produced a number so that it
    cannot be the order that justifies a configuration already picked. IF
    THE CARD CARRIES NO ORDER, S4 DOES NOT GUESS -- it escalates through
    4.5.1 (c), and choosing to have no default was intended to produce
    exactly that.
    """
    priority = list(goal.get("priority") or [])
    source = "goal_card" if priority else "default_policy"
    if not survivors:
        return None, "no configuration survived the intersection", priority, source
    if len(survivors) == 1:
        return survivors[0], "one configuration survived, so nothing was traded off", priority, source
    if not priority:
        return None, (
            "several configurations survived and the goal card carries no priority order, so S4 "
            "does not choose. 4.5.4: where things are close and there is no order, it goes back "
            "to the person (4.5.1 c). Asking once is cheaper than inventing an order"
        ), priority, source
    return None, (
        f"{len(survivors)} configurations survived and comparing them is the LLM half of 4.5.4 "
        "rule 2, which this module does not do. The deterministic half -- the intersection and "
        "the conflicts -- is complete and is on this card"
    ), priority, source


# --------------------------------------------------------------------------- #
# the card
# --------------------------------------------------------------------------- #


def synthesise(qid: str, revision: int = 1, created_at: str | None = None) -> dict:
    goal, configs, by_config = load_fanout(qid)
    created_at = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    pin = one_store([c for cards in by_config.values() for c in cards.values()])
    skipped = not_run(configs, by_config)

    per_config = []
    detail: dict[str, dict] = {}
    for config in sorted(set(by_config) | set(skipped)):
        if config not in by_config:
            # Screened in and not run at all. It gets a row so the card cannot
            # read as if S3.0 had never offered it, and `empty` is false
            # because an empty intersection is a finding and this is not one.
            per_config.append({"config": config, "empty": False, "axis_files": ["(not run)"]})
            detail[config] = {"allowed_sets": {}, "preconditions": [], "conflicts": [],
                              "unbounded": [], "origins": {}}
            continue
        cards = by_config[config]
        intervals, sets, preconditions = [], [], []
        origins: dict[str, list[str]] = {}
        for axis in sorted(cards):
            for row in cards[axis].get("inequalities", []) or []:
                if row.get("state") != "returned":
                    continue
                if row.get("interval"):
                    intervals.append((axis, row["interval"]))
                if row.get("allowed_set"):
                    sets.append((axis, row["allowed_set"]))
                    origins.setdefault(row["allowed_set"]["parameter"], []).append(
                        f"{Path(cards[axis]['__path']).name}#{row['inequality']}")
                if row.get("precondition"):
                    preconditions.append({
                        "axis": axis,
                        "origin": f"{Path(cards[axis]['__path']).name}#{row['inequality']}",
                        "bound": row["precondition"]})
        merged, conflicts = intersect_intervals(intervals)
        chosen_sets, set_conflicts = intersect_sets(sets)
        conflicts += set_conflicts

        row: dict = {
            "config": config,
            "empty": bool(conflicts),
            "axis_files": [cards[a]["__path"] for a in sorted(cards)],
        }
        if merged:
            row["intersection"] = merged
        if conflicts:
            # The contract carries one conflict per configuration. The rest are
            # not dropped: they are on this module's stderr and in `detail`,
            # and a second conflict is a second refusal, not a footnote.
            row["conflict"] = conflicts[0]
        per_config.append(row)
        detail[config] = {"allowed_sets": chosen_sets, "preconditions": preconditions,
                          "conflicts": conflicts, "unbounded": unbounded_of(cards),
                          "origins": origins}

    # A configuration whose axes did not all run is NOT a survivor. It has not
    # been intersected, so calling it one would make "nothing contradicted it"
    # mean "nothing looked".
    survivors = [r["config"] for r in per_config if not r["empty"] and r["config"] not in skipped]
    chosen, why, priority, source = choose_config(survivors, goal)
    if skipped:
        why += (". Not intersected, because S3.0 screened them in and not every axis ran: "
                + "; ".join(f"{c} is missing {', '.join(a)}" for c, a in sorted(skipped.items()))
                + ". They are not empty and they are not survivors -- nothing looked")

    numbers: list[dict] = []
    operating_point: list[dict] = []
    if chosen is not None:
        for row in next(r for r in per_config if r["config"] == chosen).get("intersection", []):
            middle = geometric_middle(row)
            if middle is None:
                continue
            numbers.append({
                "name": row["parameter"],
                "value": middle,
                "unit": row["unit"],
                "source": "computed:geometric_middle",
                "grade": "E4",
                "precision": row.get("precision", "order_of_magnitude"),
                "note": (f"the geometric middle of the intersected interval "
                         f"{row.get('min')} to {row.get('max')} {row['unit']}; a decade-wide "
                         "interval has no arithmetic middle worth the name (5.8)"),
            })
            operating_point.append({"parameter": row["parameter"], "number": row["parameter"]})

    card = {
        "card": "synthesis",
        "schema_version": "0.1",
        "id": f"synthesis-{qid}-r{revision}",
        "qid": qid,
        "thread": goal.get("thread", f"solo-{qid}"),
        "round": goal.get("round", 0),
        "revision": revision,
        "author": "microscope_agent",
        "created_at": created_at,
        "status": "DRAFT",
        "configs_screened": sorted(by_config),
        "per_config": per_config,
        "chosen_config": chosen,
        "priority_used": priority,
        "priority_source": source,
        "numbers": numbers,
        "kb_refs": [],
        "degraded": [],
    }
    if operating_point:
        card["operating_point"] = operating_point

    rejected = [{
        "what": r["config"], "kind": "configuration",
        "reason": r["conflict"]["statement"],
        "grounds": [r["conflict"]["parameter"]],
    } for r in per_config if r["empty"]]
    if rejected:
        card["rejected"] = rejected
    carry(card, detail)
    return card, detail, why


def carry(card: dict, detail: dict) -> None:
    """Write the three carried fields, but only into a contract that has them.

    Lifting the refusal and leaving the card silent would be worse than the
    refusal: `homeless` keys on the field NAMES, so the day they are declared
    it stops refusing, and without this the card would then be written
    missing exactly the rows the refusal existed to protect. The two have to
    move together, so they are in one file and this comment is the reason.

    Shape, measured rather than assumed. `config` and `origin` sit BESIDE the
    bound and not inside it, because common.schema.json's `interval`,
    `allowed_set` and `precondition` are all `additionalProperties: false` --
    so `allOf: [{$ref: allowed_set}, {properties: {config, origin}}]` is
    REJECTED, which this seat proposed to architecture before checking and
    had to withdraw. Nesting costs one level and needs no change to
    common.schema.json at all.

    `origin` is `<file>#<inequality>`, the form check 12 already reads for a
    carried number, pointing at the axis card that asked. That is what makes
    a carried `kb:` basis resolvable: not an exemption from check 54 but the
    right card to resolve against, because that card is the one that asked
    (architecture's ruling, 061ee6d).

    If the declared shape differs from this one, check 1 fails on the written
    card. That is the intended outcome -- a loud mismatch beats a card that
    validates by leaving things out.
    """
    schema = json.loads((REPO / "contracts" / "schemas" / "synthesis.schema.json").read_text())
    declared = set(schema.get("properties") or {})
    for config, d in sorted(detail.items()):
        if "allowed_sets" in declared:
            for parameter, allowed in sorted(d["allowed_sets"].items()):
                bound = {k: v for k, v in allowed.items() if k not in ("from_axes",)}
                card.setdefault("allowed_sets", []).append({
                    "config": config,
                    "origin": d["origins"].get(parameter, [""])[0],
                    "bound": bound})
        if "preconditions" in declared:
            for pre in d["preconditions"]:
                card.setdefault("preconditions", []).append({
                    "config": config, "origin": pre["origin"], "bound": pre["bound"]})
        if "unbounded" in declared:
            for row in d["unbounded"]:
                card.setdefault("unbounded", []).append({"config": config, **row})


# --------------------------------------------------------------------------- #
# what the contract has no room for
# --------------------------------------------------------------------------- #


def homeless(detail: dict) -> list[str]:
    """Results this fan-out produced that synthesis.schema.json cannot hold.

    Read off the schema rather than listed here, so this refusal disappears
    by itself the day the contract grows the fields -- axis_common's
    `ledger_has_a_home` does the same thing for the same reason.

    THE THREE, AND WHY EACH MATTERS RIGHT NOW.

    `allowed_set` and `precondition` were added to the AXIS contract on
    2026-09-19 (5.3.2) and not to this one, whose `intersection` takes
    intervals and nothing else and is closed to additional properties. Today
    every bound this fan-out produced is one of those two shapes -- A4's
    lock_group and verified_selectors, A6's objective_zoom_pair -- so a
    synthesis card written without them says a configuration survived with
    nothing bounding it, while three bounds sit on the axis cards beside it.

    `unbounded` is the same argument at larger scale. 34 of 37 inequalities
    said nothing, and a card carrying only the three that spoke reads as a
    configuration nearly decided. 4.5.2.1 wrote the rule against exactly
    that: silence on a bound reads downstream as that bound not applying.

    So this does not write a card that would be true only by omission. The
    way out is a shape in the contract, not a wrong field here -- which is
    axis_common's sentence, and it applies one stage later unchanged.
    """
    schema = json.loads((REPO / "contracts" / "schemas" / "synthesis.schema.json").read_text())
    if schema.get("unevaluatedProperties") is not False and \
       schema.get("additionalProperties") is not False:
        return []                       # open contract: nothing is homeless
    head = json.loads((REPO / "contracts" / "schemas" / "common.schema.json").read_text())
    allowed = set(schema.get("properties") or {})
    allowed |= set((head["$defs"]["common_head"].get("properties") or {}))

    wants = {
        "allowed_sets": sum(len(d["allowed_sets"]) for d in detail.values()),
        "preconditions": sum(len(d["preconditions"]) for d in detail.values()),
        "unbounded": sum(len(d["unbounded"]) for d in detail.values()),
    }
    return [f"{n} {field} (synthesis.schema.json declares no {field!r})"
            for field, n in sorted(wants.items()) if n and field not in allowed]


def report(card: dict, detail: dict, why: str) -> None:
    print(f"S4 {card['qid']}: {len(card['configs_screened'])} configuration(s), "
          f"chosen {card['chosen_config']!r}")
    for row in card["per_config"]:
        n = len(row.get("intersection") or [])
        sets = detail[row["config"]]["allowed_sets"]
        unb = detail[row["config"]]["unbounded"]
        print(f"  {row['config']:20} empty={row['empty']}  intervals={n}  "
              f"allowed_sets={len(sets)}  preconditions={len(detail[row['config']]['preconditions'])}"
              f"  unbounded={len(unb)}")
        for c in detail[row["config"]]["conflicts"]:
            print(f"    CONFLICT {c['parameter']}: {c['statement']}")
        for p, s in sets.items():
            print(f"    set  {p}: {s['values']}")
        for u in unb:
            miss = ",".join(u["missing"]) or "-"
            print(f"    open {u['axis']} {u['inequality']:24} {str(u['kind']):17} missing={miss}")
    print(f"  {why}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S4: intersect the axis cards and choose (4.5.4)")
    parser.add_argument("--qid", required=True)
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--write", action="store_true",
                        help="write questions/<qid>/synthesis.json; without it nothing is written")
    args = parser.parse_args(argv)
    try:
        card, detail, why = synthesise(args.qid, args.revision)
    except SynthesisError as exc:
        print(f"S4 refused: {exc}", file=sys.stderr)
        return 2
    report(card, detail, why)
    stranded = homeless(detail)
    if stranded:
        print("\nS4 will not write a card the contract cannot make true:", file=sys.stderr)
        for line in stranded:
            print(f"  no home for {line}", file=sys.stderr)
        print("  The intersection above is complete and correct; what is missing is somewhere to\n"
              "  put it. A bound with grounds and no shape to put them in is the silence 4.5.2.1\n"
              "  refuses, and the way out is a shape in the contract, not a wrong field here.\n"
              "  Raised with manager-microscope, who owns contracts/schemas/.", file=sys.stderr)
        return 3
    if args.write:
        out = QUESTIONS / args.qid / "synthesis.json"
        out.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n")
        print(f"  wrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
