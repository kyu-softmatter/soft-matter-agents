"""S4 -- synthesis and trade-offs (plan.md 4.5.4).

Two jobs with a line between them, and the line is what this file is for:

* **The intersection is deterministic.** Per configuration, per parameter, the
  allowed intervals from every axis are intersected: the highest floor and the
  lowest ceiling win. An empty intersection drops the configuration and says
  which two axes collided at which numbers. All configurations empty is a
  refusal, not a best effort (P5).

* **The operating point is a judgement.** Which point inside the intersection
  to run is not derivable from the intervals, so it is passed in rather than
  computed here, and every component of it has to resolve to a number the card
  already carries. S4 introduces no new facts and looks nothing up (4.5.4
  rule 4): a number in this card is either carried from an axis card or the
  goal with an `origin`, or computed from numbers that are.

Nothing here imports a backend or a device (7.2 rule 2). It reads cards.
"""

from __future__ import annotations

import json
import sys

from . import cards

AXES = ("a1", "a2", "a3", "a4", "a5", "a7")


def axis_cards(qid: str, config: str, revision: int = 1) -> list[tuple[str, dict]]:
    """Every axis card of one configuration, as (filename, card).

    All six are read, including the ones that abstained. An abstention carries
    no interval, but leaving it out of the record would lose the fact that the
    axis was asked (P1).
    """
    out = []
    for axis in AXES:
        path = cards.question_dir(qid) / cards.artifact_name(
            f"axis_{config}_{axis}.json", revision
        )
        if not path.exists():
            raise FileNotFoundError(f"{path.name} is missing; every axis leaves a card (4.5.3)")
        out.append((path.name, json.loads(path.read_text())))
    return out


def intersect(cards_of_config: list[tuple[str, dict]]) -> tuple[list[dict], dict | None]:
    """Intersect the intervals of one configuration, parameter by parameter.

    Returns (intersection, conflict). `conflict` is None unless some parameter
    came out empty, in which case it names the two axes and the parameter --
    which is the whole point of intersecting in code rather than in prose.
    """
    bounds: dict[str, dict] = {}
    for fname, card in cards_of_config:
        axis = card["axis"]
        for iv in card.get("constraints", []) or []:
            slot = bounds.setdefault(
                iv["parameter"],
                {"unit": iv["unit"], "min": None, "max": None, "basis": [], "from": {}},
            )
            if iv["unit"] != slot["unit"]:
                raise ValueError(
                    f"{iv['parameter']}: {axis} states {iv['unit']} against {slot['unit']}; "
                    "cards are authoritative in physical units (D7)"
                )
            for end in ("min", "max"):
                if end not in iv:
                    continue
                keep = (
                    slot[end] is None
                    or (end == "min" and iv[end] > slot[end])
                    or (end == "max" and iv[end] < slot[end])
                )
                if keep:
                    slot[end] = iv[end]
                    slot["from"][end] = axis
                    slot["basis"] = [b for b in iv.get("basis", [])]

    intersection, conflict = [], None
    for parameter, slot in sorted(bounds.items()):
        if slot["min"] is not None and slot["max"] is not None and slot["min"] > slot["max"]:
            conflict = {
                "axes": [slot["from"]["min"], slot["from"]["max"]],
                "parameter": parameter,
                "statement": (
                    f"{slot['from']['min']} needs {parameter} at or above {slot['min']} "
                    f"{slot['unit']} while {slot['from']['max']} holds it at or below "
                    f"{slot['max']} {slot['unit']}"
                ),
            }
            continue
        iv = {"parameter": parameter, "unit": slot["unit"], "basis": slot["basis"]}
        for end in ("min", "max"):
            if slot[end] is not None:
                iv[end] = slot[end]
        iv["precision"] = "order_of_magnitude"
        intersection.append(iv)
    return intersection, conflict


def carry_from(qid: str, config: str, wanted: list[tuple[str, str]]) -> list[dict]:
    """Numbers pulled into this card from where they were produced.

    `wanted` is a list of (filename, number name). The value, unit and grade
    come along unchanged and `origin` records where from, so check 12 can
    compare them against the card that made them rather than re-deriving.
    """
    out = []
    for fname, name in wanted:
        path = cards.question_dir(qid) / fname
        src = json.loads(path.read_text())
        num = next((n for n in src.get("numbers", []) if n["name"] == name), None)
        if num is None:
            raise KeyError(f"{fname} has no number named {name!r}")
        carried = {
            "name": name,
            "value": num["value"],
            "unit": num["unit"],
            "source": num["source"],
            "grade": num["grade"],
            "origin": f"{fname}#{name}",
        }
        if "precision" in num:
            carried["precision"] = num["precision"]
        if "note" in num:
            carried["note"] = num["note"]
        out.append(carried)
    return out


def assumptions_for(qid: str, carried: list[dict]) -> list[dict]:
    """The rationales that explain the carried estimates.

    An assumed number has to be explained in the card that holds it (check 4),
    and carrying the value without its rationale would leave an estimate here
    with no reason attached. Each rationale is narrowed to the numbers that
    actually came along.
    """
    by_file: dict[str, list[str]] = {}
    for n in carried:
        if not str(n.get("source", "")).startswith("assumed:"):
            continue
        fname = str(n["origin"]).split("#", 1)[0]
        by_file.setdefault(fname, []).append(n["name"])

    out: list[dict] = []
    seen: set[str] = set()
    for fname, names in by_file.items():
        src = json.loads((cards.question_dir(qid) / fname).read_text())
        for a in src.get("assumptions", []) or []:
            overlap = [n for n in a.get("numbers", []) if n in names]
            if overlap and a["rationale_id"] not in seen:
                seen.add(a["rationale_id"])
                out.append({**a, "numbers": overlap})
    return out


def kb_refs_for(qid: str, carried: list[dict]) -> list[dict]:
    """The librarian records behind the carried values.

    A number whose source is `kb:<entry_id>` needs that entry recorded in the
    same card (check 25): a citation whose record stayed in another file is a
    claim this card cannot back. Collected by entry id, so an entry cited from
    two places is recorded once.
    """
    out: dict[str, dict] = {}
    for n in carried:
        if not str(n.get("source", "")).startswith("kb:"):
            continue
        fname = str(n["origin"]).split("#", 1)[0]
        src = json.loads((cards.question_dir(qid) / fname).read_text())
        for ref in src.get("kb_refs", []) or []:
            out.setdefault(ref["entry_id"], ref)
    return list(out.values())


def kb_gaps_for(qid: str) -> list[dict]:
    """The gaps the question was posed against, carried down the pipeline.

    A gap is a fact about the question, not about one number: what was looked
    for and was not in the store. It has to travel with the plan, because the
    plan is what a person reads before spending anything, and an estimate whose
    absence went unrecorded looks exactly like one nobody checked (4.3.1).
    """
    return [dict(g) for g in (cards.load_goal(qid).get("kb_gaps") or [])]


# The judgement half of S4. Which point inside the intersection to run cannot
# be read off the intervals, so it is written here as a table rather than
# derived -- and every entry has to resolve to a number this card carries.
OPERATING_POINT = {
    "bd_overdamped": {
        "carry": [
            ("goal.json", "bead_diameter"),
            ("goal.json", "temperature"),
            ("goal.json", "viscosity"),
            ("goal.json", "diffusivity"),
            ("goal.json", "max_lag_time"),
            ("goal.json", "tau_d"),
            ("goal.json", "n_particles"),
            ("axis_bd_overdamped_a1.json", "integration_timestep_max"),
            ("axis_bd_overdamped_a2.json", "total_simulated_time_min"),
            ("axis_bd_overdamped_a2.json", "lag_to_record_ratio_max"),
            ("axis_bd_overdamped_a3.json", "box_length_min_images"),
            ("axis_bd_overdamped_a3.json", "box_length_min_dilution"),
            ("axis_bd_overdamped_a4.json", "save_interval_max"),
        ],
        "computed": [
            {
                "name": "integration_timestep_point",
                "value": 0.3,
                "unit": "s",
                "source": "computed:thousandth_of_a_diffusive_time",
                "formula": "tau_d / 1000",
                "inputs": ["tau_d"],
                "note": "the person's standing default, a thousandth of the diffusive time. S4 no longer picks this inside A1's interval -- 0.3 s sits an order of magnitude under A1's 3 s ceiling, but the value comes from the default rather than from the choice. The thousandth is a decision and carries no grade; what it multiplies is kb:tau_d, so the seconds inherit E4",
            },
            {
                "name": "total_simulated_time_point",
                "value": 3000,
                "unit": "s",
                "source": "computed:ten_diffusive_times",
                "formula": "10 * tau_d",
                "inputs": ["tau_d"],
                "note": "the person's standing default, ten diffusive times. It replaces two decades above A2's statistical floor, which was S4 choosing: the floor is 3 s and this is a thousand times it, so the statistical bound is satisfied by a wide margin rather than by construction. The ten is a decision and carries no grade; the seconds inherit E4 from kb:tau_d, which is the ceiling a wall-clock duration can never beat",
            },
        ],
        "ratio": {
            "name": "lag_to_record_ratio",
            "value": 0.01,
            "unit": "1",
            "formula": "max_lag_time / total_simulated_time_point",
            "inputs": ["max_lag_time", "total_simulated_time_point"],
            "note": "the window as a share of the record. The vocabulary requires the window to satisfy a statistical bound as well as the physical one, and this is the number that shows it",
        },
        "point": [
            ("integration_timestep", "integration_timestep_point"),
            ("total_simulated_time", "total_simulated_time_point"),
            ("save_interval", "save_interval_max"),
            ("box_length", "box_length_min_dilution"),
            ("max_lag_time", "max_lag_time"),
            ("n_particles", "n_particles"),
        ],
        "rejected": [
            {
                "what": "integration_timestep at A1's ceiling",
                "kind": "operating_point",
                "reason": "A1 allows a far coarser step, set from the diffusive time, but a saved frame would then fall between steps; the step is set a decade below the save interval instead",
                "grounds": ["integration_timestep_max", "save_interval_max"],
            },
            {
                "what": "box_length at the periodic-image bound",
                "kind": "operating_point",
                "reason": "the image bound is cleared by a much smaller box, but that box puts a thousand tracers about a diameter apart, which is not the dilute limit the observable is defined in; the dilution bound binds instead",
                "grounds": ["box_length_min_images", "box_length_min_dilution"],
            },
        ],
    }
}


def build(qid: str, configs: list[str], created_at: str, revision: int = 1) -> dict:
    per_config, chosen = [], None
    for config in configs:
        group = axis_cards(qid, config, revision)
        intersection, conflict = intersect(group)
        entry = {
            "config": config,
            "empty": conflict is not None,
            "axis_files": [fname for fname, _ in group],
        }
        if conflict is not None:
            entry["conflict"] = conflict
        else:
            entry["intersection"] = intersection
            chosen = chosen or config
        per_config.append(entry)

    if chosen is None:
        raise SystemExit(
            "every configuration came out empty; S4 ends in a refusal card, not a plan (P5)"
        )

    goal = cards.load_goal(qid, revision)
    spec = OPERATING_POINT[chosen]
    # The table names revision-1 files. Resolve each to this revision's name,
    # so `origin` points at the card that actually produced the number rather
    # than at whatever a previous revision left on disk.
    resolved = [(cards.artifact_name(f, revision), n) for f, n in spec["carry"]]
    numbers = carry_from(qid, chosen, resolved)
    assumptions = assumptions_for(qid, numbers)
    grades = {n["name"]: n["grade"] for n in numbers}
    # The ratio reads a number computed a line earlier, so the grade table
    # grows as the loop runs: a computed value takes the worst grade among its
    # inputs, and an input that is itself computed has to be in the table by
    # the time it is read.
    for c in spec["computed"] + [spec["ratio"]]:
        number = cards.num(
            c["name"],
            c["value"],
            c["unit"],
            # Per entry, with the configuration's own prefix as the default.
            # Two of these stopped being S4 choosing a point inside an interval
            # and became the person's standing defaults applied to kb:tau_d, so
            # a source claiming the choice would claim something that no longer
            # happens (9 M2, 2026-09-22).
            c.get("source") or f"computed:operating_point_of_{chosen}",
            formula=c["formula"],
            inputs=[(i, grades[i]) for i in c["inputs"]],
            precision="order_of_magnitude",
            note=c["note"],
        )
        numbers.append(number)
        grades[number["name"]] = number["grade"]

    priority = goal.get("priority") or [
        "physical_feasibility",
        "target_accuracy",
        "evidence_grade",
        "cost",
    ]
    card = cards.head(
        "synthesis",
        f"synthesis-{qid}" + ("" if revision == 1 else f"-r{revision}"),
        qid,
        created_at,
        revision=revision,
        configs_screened=configs,
        per_config=per_config,
        chosen_config=chosen,
        operating_point=[{"parameter": p, "number": n} for p, n in spec["point"]],
        priority_used=priority,
        priority_source="goal_card" if goal.get("priority") else "default_policy",
        rejected=spec["rejected"],
    )
    card.update(cards.tail(
        numbers,
        assumptions=assumptions,
        kb_refs=kb_refs_for(qid, numbers),
        kb_gaps=kb_gaps_for(qid),
        degraded=["librarian_agent"],
    ))
    # The synthesis schema carries no free note field, deliberately: an
    # observation about the result belongs to the plan's open_risks, where a
    # person reads it before approving, rather than in a card nobody gates on.
    return card


if __name__ == "__main__":
    # The configuration list comes from the same screening the fan-out ran, so
    # there is one source of it rather than a copy here that can drift. The
    # import is at the entry point and not at module scope: S4 intersects
    # cards and has no business importing the axis modules that made them
    # (7.2 rule 2).
    from . import fanout

    qid = sys.argv[1] if len(sys.argv) > 1 else "sim-20260917-001"
    created_at = sys.argv[2] if len(sys.argv) > 2 else "2026-09-18T10:10:00Z"
    configs = fanout.screen(cards.load_goal(qid)["observable"]["name"])
    revision = cards.question_revision(qid)
    target = cards.question_dir(qid) / cards.artifact_name("synthesis.json", revision)
    card = build(qid, configs, created_at, revision)
    cards.refuse_overwrite(target, revision, card)
    print(cards.write(target, card).relative_to(cards.REPO))
