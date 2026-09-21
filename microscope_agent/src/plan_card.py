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
from fractions import Fraction                                   # noqa: E402
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


def _turret() -> dict:
    """The nosepiece row of the published device table, read from this agent's envelope.

    One reader, because there are now two directions through this table --
    a chosen pair down to a position, and a position the goal card names back
    up to a pair -- and two mappings between a lens and a turret position is
    one mapping too many. The position is the turret's own, indexed from 0,
    which the table states in an `index_note`.
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
    return turret


def pair_from_goal(goal: dict) -> tuple[str | None, str]:
    """The pair the person already chose, assembled from the parts the goal card names.

    A6 returns ONE name -- `objective_zoom_pair` -- and a goal card answers in
    the two settings the instrument actually takes: a turret position and an
    intermediate magnification. S5 looked for a number called
    objective_zoom_pair, found none, and reported an unresolved tie over a
    choice that had been made hours earlier. The choice was never missing; it
    was spelled in two names.

    This is selector_numbers() run backwards and through the same turret row.
    It returns the pair and never a verdict: whether the pair is permitted is
    the axis's to say, and the caller checks it against the set.
    """
    numbers = {n.get("name"): n for n in goal.get("numbers") or []}
    position, zoom = numbers.get("nosepiece_position"), numbers.get("intermediate_magnification")
    if position is None or zoom is None:
        missing = [n for n, v in (("nosepiece_position", position),
                                  ("intermediate_magnification", zoom)) if v is None]
        return None, f"the goal card names no {' and no '.join(missing)}"
    row = next((o for o in _turret().get("objectives", [])
                if o.get("position") == position.get("value")), None)
    if row is None:
        held = [o.get("position") for o in _turret().get("objectives", [])]
        return None, (f"the goal card names nosepiece_position {position.get('value')!r} and this "
                      f"turret holds positions {held}; the table is indexed from 0")
    magnification = str(row.get("id", "")).split("-")[0]
    return (f"{magnification}@{zoom.get('value'):g}x",
            f"position {position.get('value')} is the {row.get('id')} lens ({row.get('part_number')})")


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
    turret = _turret()
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

    # The answer may already be on the goal card under other names. Read it
    # before calling this a tie -- 4.5.1 (c) sends a question to the person,
    # and asking one that has been answered is the same defect as guessing.
    # A refusal here is deliberate and is NOT a tie: a person's choice does
    # not override an axis, so a goal naming a pair the axis excluded is an
    # error in the goal, named as one.
    if allowed.get("parameter") == "objective_zoom_pair":
        pair, how = pair_from_goal(goal)
        if pair is not None and pair in values:
            return pair, (f"the goal card chose this, in parts: {how}, at intermediate "
                          f"magnification {pair.split('@')[1]}. The pair is one of the "
                          f"{len(values)} this bound permits, so nothing was guessed and nobody "
                          "is asked again. A person's setting is a setting and not evidence: it "
                          "raises no grade and supports no other number")
        if pair is not None:
            return None, (f"the goal card chooses {pair!r} ({how}) and this bound does not permit "
                          f"it: A6 admitted {sorted(values)} on Nyquist grounds and excluded the "
                          "rest. A person's choice does not override an axis, so this is an error "
                          "in the goal card rather than an instruction to this stage, and S2 "
                          "owns it. Fix the goal or re-derive A6; do not widen the set here")

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


def carried_from_goal(goal: dict, bounded: set[str]) -> list[dict]:
    """The operator's own numbers, carried onto the plan with where they came from.

    NOT A WAY ROUND THE AXES, and the distinction is the whole of it. S4
    chooses a point inside an intersection; there are questions where no
    intersection can exist, because the parameter the axes would bound is
    the very quantity the run exists to measure. A pre-measurement for
    tracer_brightness is one: A1 bounds an exposure from a brightness, and
    the brightness is this question's observable. The axes are not failing
    there, they are correct, and the operating point has to come from the
    person or the question cannot be asked at all.

    The mechanism is the contract's and not a new one. `origin` is
    `<file>#<name>` and check 12 already compares a carried number against
    the card it names, the same way it compares S4's carried numbers today.
    So a number that came from the person is traceable to the goal card that
    recorded their words, and a reader can tell it from one an axis derived
    by looking at where it points.

    WHAT IS NOT CARRIED. A number an axis DID bound -- S4 chose a point
    inside it and that point wins, because it rests on evidence and this
    does not. And a number a target names, which is a decision about the
    answer rather than a setting for the run.
    """
    # BOTH TARGET FORMS. The old one names a numbers[] entry; the new one is
    # inline and names its own metric (5.3.1). Reading only `number` made a
    # correctly written target invisible here, the same way it did in A6.
    named_by_target = {t.get("number") for t in goal.get("targets", []) or []}
    named_by_target |= {t.get("metric") for t in goal.get("targets", []) or []}
    named_by_target.discard(None)
    out = []
    for number in goal.get("numbers", []) or []:
        name = number.get("name")
        if name in bounded or name in named_by_target:
            continue
        out.append({**{k: v for k, v in number.items() if k != "note"},
                    "origin": f"goal.json#{name}",
                    "note": ("carried from the goal card unchanged. No axis bounded it and none "
                             "could: " + str(number.get("note", ""))[:400])})
    return out


def axc_elements() -> set[str]:
    """Every element id in the registry, from this agent's own snapshot."""
    snapshot = AGENT / "envelope" / "snapshot.json"
    if not snapshot.exists():
        return set()
    snap = json.loads(snapshot.read_text())
    text = ((snap.get("tables") or {}).get("devices") or {}).get("text")
    if not text:
        return set()
    return {e["id"] for ch in json.loads(text).get("channels", []) or []
            for e in ch.get("elements") or [] if e.get("id")}


def axc_required_selectors(config: str) -> dict:
    """The selectors this configuration requires, as the path table states them."""
    snapshot = AGENT / "envelope" / "snapshot.json"
    if not snapshot.exists():
        return {}
    snap = json.loads(snapshot.read_text())
    text = ((snap.get("tables") or {}).get("optical_paths") or {}).get("text")
    if not text:
        return {}
    row = next((c for c in json.loads(text).get("configurations", []) or []
                if c.get("id") == config), None)
    return dict((row or {}).get("required_selectors") or {})


def axc_detectors(config: str) -> list[str]:
    """The detectors the optical-path table declares for a configuration.

    Read from this agent's own snapshot, which is where the published table
    lives for us (P14). Two for widefield_inline, which is the whole reason
    the acquire action cannot be written without a choice.
    """
    snapshot = AGENT / "envelope" / "snapshot.json"
    if not snapshot.exists():
        return []
    snap = json.loads(snapshot.read_text())
    text = ((snap.get("tables") or {}).get("optical_paths") or {}).get("text")
    if not text:
        return []
    row = next((c for c in json.loads(text).get("configurations", []) or []
                if c.get("id") == config), None)
    return list((row or {}).get("detectors") or [])


def mandatory_fields() -> list[str]:
    """Read off plan.schema.json, so this list cannot drift from the contract."""
    schema = json.loads((CONTRACTS / "schemas" / "plan.schema.json").read_text())
    head = json.loads((CONTRACTS / "schemas" / "common.schema.json").read_text())
    return sorted(set(schema.get("required") or []) |
                  set(head["$defs"]["common_head"].get("required") or []))


def assemble(qid: str, revision: int = 1,
             created_at: str | None = None) -> tuple[dict, list[str], list[dict]]:
    """Build as much of the plan as the axes support, and list what is unfillable.

    Returns (card, unfillable, preconditions). `unfillable` names mandatory
    fields with no source and says which silence is behind each, so the next
    action is a person or a measurement rather than a re-read of this file.

    The third is returned as well as carried. `preconditions` landed in
    plan.schema.json on 2026-09-21 and this stage was discarding A4's two
    until then -- silently, because `conditions` points into numbers[] by
    name and a requirement on the plan's FORM is not a number. They are now
    written into the card AND reported, because a plan that drops one an
    axis returned is missing a requirement and nothing downstream shows it.
    """
    goal, _configs, by_config = s4.load_fanout(qid)
    card4, detail, why = s4.synthesise(qid, revision)
    created_at = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    config = card4.get("chosen_config")
    if config is None:
        raise PlanError(f"S4 chose no configuration: {why}")
    d = detail[config]
    preconditions = list(d.get("preconditions") or [])

    # CARRIED UNCHANGED, AND `requires` IS NOT PARAPHRASED. The schema says
    # why: restating it in the planner's words would put one rule in two
    # wordings, and the next revision would make it two rules (P3).
    carried_pre = []
    for pre in preconditions:
        bound = pre.get("bound") or {}
        row = {"parameter": bound.get("parameter", ""),
               "requires": bound.get("requires", ""),
               "from_axis": pre.get("axis", "")}
        if bound.get("basis"):
            row["basis"] = list(bound["basis"])
        carried_pre.append(row)

    cited = {b[3:] for pre in carried_pre for b in pre.get("basis") or []
             if isinstance(b, str) and b.startswith("kb:")}
    carried_refs, seen = [], set()
    for axis_card in (by_config.get(config) or {}).values():
        for ref in axis_card.get("kb_refs") or []:
            entry = ref.get("entry_id")
            if entry in cited and entry not in seen:
                seen.add(entry)
                carried_refs.append(ref)

    numbers = list(card4.get("numbers") or [])
    carried_assumptions: list[dict] = []
    conditions = [{"parameter": p["parameter"], "number": p["number"]}
                  for p in card4.get("operating_point") or []]
    unfillable: list[str] = []

    # The operator's own settings, where no axis bounded the parameter.
    bounded = {n["name"] for n in numbers}
    for number in carried_from_goal(goal, bounded):
        numbers.append(number)
        conditions.append({"parameter": number["name"], "number": number["name"]})

    # The discrete bounds, where a value can be chosen without a person.
    for parameter, allowed in sorted(d["allowed_sets"].items()):
        value, reason = choose_from_set(allowed, goal)
        if value is None:
            unfillable.append(f"{parameter}: {reason}")
            continue
        if parameter == "objective_zoom_pair":
            # When the pair came off the goal card, its two parts are already
            # here -- carried_from_goal put them in above -- and adding them
            # again would put one quantity in two places at two grades, which
            # is the drift check 9 exists against. The condition gains the
            # device it belongs to instead, which is the part that was missing.
            present = {n["name"] for n in numbers}
            for n in selector_numbers(value):
                device = ("nosepiece" if n["name"] == "nosepiece_position"
                          else "intermediate_magnification")
                if n["name"] in present:
                    for c in conditions:
                        if c["parameter"] == n["name"]:
                            c["device"] = device
                    continue
                numbers.append(n)
                conditions.append({"parameter": n["name"], "number": n["name"],
                                   "device": device})

    # ONE CRITERION PER TARGET, BUILT FROM THE TARGET.
    #
    # Until 2026-09-21 this read `goal["numbers"]` for the literal name
    # `target_decade_resolution` and never looked at `goal["targets"]` at
    # all, so it reported "the goal card carries no target" about a card
    # carrying two. The contract moved and the reader did not: a target is
    # INLINE now, because it is a decision and a decision is correct by
    # being made, so it carries no source and no grade -- and inline is what
    # makes a grade inexpressible rather than merely absent (5.3.1).
    #
    # And the criterion was hardcoded to one question: metric, statement and
    # threshold were all mic-20260918-001's diffusivity. A shape fix alone
    # would have left this run emitting a criterion about a quantity it does
    # not measure -- AND IT WOULD HAVE PASSED CHECK 6, which recomputes a
    # verdict against the criterion a card states and never asks whether the
    # criterion is about the right thing.
    #
    # The target is carried and NOT copied into numbers[]: `criterion.target`
    # exists for exactly this, added when the target left numbers[] and the
    # criterion had nothing to point at. Copying it back would make a grade
    # expressible on something that must not have one.
    success, carried_targets = [], []
    for spec in goal.get("targets", []) or []:
        metric, kind = spec.get("metric"), spec.get("kind")
        if not metric or not kind:
            continue
        if "number" in spec:                    # the superseded by-reference form
            unfillable.append(
                f"success_criteria[{metric}]: this target names numbers[{spec['number']}] rather "
                "than carrying its value, which is the form 5.3.1 superseded. Migrating it is "
                "the goal card's owner's, not this stage's")
            continue
        shape = {
            "decade_resolution": (f"{metric}_decades_resolved", ">=",
                                  f"{metric} is placed within {spec['value']} decade"
                                  + ("s" if spec["value"] != 1 else "")),
            "uncertainty": (f"{metric}_relative_error", "<=",
                            f"{metric} is known to within {spec['value']} {spec['unit']}"),
            "detection": (metric, "<=",
                          f"{metric} reaches {spec['value']} {spec['unit']}"),
        }.get(kind)
        if shape is None:
            unfillable.append(
                f"success_criteria[{metric}]: target kind {kind!r} has no criterion shape in this "
                "stage. Inventing one would be this stage deciding what the person's target means")
            continue
        criterion_metric, comparator, statement = shape
        carried_targets.append({k: v for k, v in spec.items() if k != "note"})
        success.append({"id": f"ok_{metric}", "metric": criterion_metric,
                        "comparator": comparator, "target": metric, "statement": statement})
    if not success and not any(u.startswith("success_criteria") for u in unfillable):
        unfillable.append("success_criteria: the goal card states no target to compare against")

    # The window a window_required observable depends on (5.7, check 40).
    # NOT DEFAULTED, and that is deliberate. A window says WHICH PART of the
    # record the estimator ran over, and a short-lag and a long-lag answer
    # land in one column under one name without it. No axis produces one and
    # the person did not state one, so it is named as open rather than filled
    # with a plausible range -- a window this stage invents is a measurement
    # nobody chose.
    observable = (goal.get("observable") or {}).get("name")
    vocab = {o["id"]: o for o in
             json.loads((CONTRACTS / "observables.json").read_text()).get("observables", [])}
    spec = vocab.get(observable) or {}
    if spec.get("window_required"):
        want = spec.get("window_parameter")
        if want and want not in {c["parameter"] for c in conditions}:
            unfillable.append(
                f"conditions[{want}]: {observable!r} is window_required and nothing states the "
                f"window. Check 40 rejects the plan without it, and it is not a default: the "
                f"window is which part of the record the estimator ran over, and a short-lag "
                f"and a long-lag answer land in one column under one name without it. The "
                f"estimator says what the window means and not what it should be: "
                f"{str(spec.get('estimator', ''))[:180]}")

    if not conditions:
        open_names = sorted({u["parameter"] for u in d["unbounded"] if u.get("kind") == "no_input"})
        unfillable.append(
            "conditions: every parameter is unbounded, so there is nothing to point at. A "
            "condition names a number and never restates a value (5.2), and no axis returned "
            f"one. Open: {', '.join(open_names)}")
    if not any(n["name"] for n in numbers):
        unfillable.append("numbers: nothing was bounded, so the card has no values to carry")
    have = {n["name"] for n in numbers}
    actions: list[dict] = []

    # THE FRAME COUNT IS AN INTEGER OR THERE IS NONE. Dividing in binary
    # floats is the same trap as summing in them: 60/0.1 lands on 600 and
    # 0.3/0.1 lands on 2.9999999999999996, and which happens depends on
    # values S4 chose. Fraction over the decimal text divides exactly, so a
    # record that is not a whole number of exposures is REFUSED rather than
    # rounded -- rounding it would move a number the person set.
    #
    # An integer count is also what the operator must derive its elapsed time
    # from. frames x exposure rounds once; a running sum rounds once per
    # frame and reports a finished run as unfinished.
    record_length = next((n["value"] for n in numbers if n["name"] == "record_length"), None)
    exposure_time = next((n["value"] for n in numbers if n["name"] == "exposure_time"), None)
    frame_count = None
    if record_length is not None and exposure_time:
        ratio = Fraction(str(record_length)) / Fraction(str(exposure_time))
        if ratio.denominator == 1:
            frame_count = int(ratio)
            numbers.append({
                # UNIT `1` AND NOT `count`, WHICH LOOKS WRONG AND IS RIGHT.
                # `count` carries dimension N, and record_length /
                # exposure_time is s/s, which is dimensionless. The reason is
                # that exposure_time is seconds PER FRAME and units.json has
                # no way to say "per frame", so the N cancels where nothing
                # can see it. Writing `count` would make the card claim a
                # dimension its own formula does not produce; check 17 caught
                # exactly that.
                "name": "frame_count", "value": frame_count, "unit": "1",
                "source": "computed:record_length_over_exposure_time", "grade": "E5",
                "precision": "significant_figures",
                "formula": "record_length / exposure_time",
                # Without these the grade rule sees a value computed from
                # constants, which is E4, and refuses an E5 as over-modest
                # in the wrong direction -- max(E4, worst input) is only
                # E5 once the inputs are named. Both are the person's
                # starting point, so E5 is what it inherits.
                "inputs": ["record_length", "exposure_time"],
                "note": ("the frame period equals the exposure on this camera -- readout is "
                         "pipelined and the interval setting is ignored -- so the frames cover "
                         f"the record with no dead time and {frame_count} x {exposure_time:g} s "
                         f"is {record_length:g} s exactly, not approximately. It counts FRAMES "
                         "despite the dimensionless unit: the exposure is seconds per frame and "
                         "units.json cannot say per-frame, so the amount cancels silently. E5 "
                         "because both "
                         "inputs are the person's starting point and a computed value inherits "
                         "the worst of them")})
            have.add("frame_count")

    # A CONDITION BECOMES A SET ACTION WHEN THE REGISTRY NAMES ITS ELEMENT,
    # and not otherwise. The match is by name and nothing here guesses: an
    # element id exactly, or an element id with `_position` after it, which
    # is how a selector's parameter is written. `intermediate_magnification`
    # is an element and matches the first way; `nosepiece_position` matches
    # the second. Check 38 takes an element as a plan device name, so
    # naming the element rather than stand_ti2e is the right grain -- that
    # channel carries nine of them and naming the channel loses which.
    #
    # What does NOT match gets no action and is named in the refusal. An
    # exposure belongs to a camera and there are two; a window is an
    # instruction to the estimator and no device does it at all.
    elements = axc_elements()
    unplaced: list[str] = []
    for condition in conditions:
        parameter = condition["parameter"]
        device = condition.get("device") or (
            parameter if parameter in elements else
            parameter[:-len("_position")] if parameter.endswith("_position")
            and parameter[:-len("_position")] in elements else None)
        if device is None:
            unplaced.append(parameter)
            continue
        condition["device"] = device
        actions.append({"id": f"act_set_{parameter}", "device": device,
                        "action": f"set_{parameter}", "reversible": True,
                        "parameters": [parameter], "tier": 1})

    # AND ONE ACQUIRE, IF THE CONFIGURATION NAMES ONE DETECTOR.
    #
    # It names two. widefield_inline declares camera_red and camera_blue, and
    # which one collects depends on the band -- a fact this question's goal
    # states in prose, with real evidence behind it, and which no field on any
    # card can carry: a detector is a SELECTOR, a string naming a channel, and
    # conditions[] point into numbers[] where a value is a number. That is the
    # same wall as the camera mode and the objective, and the objective only
    # escaped it because the turret publishes a POSITION.
    #
    # So the choice is named rather than taken. Reading it out of the goal's
    # prose would be this stage deciding which arm the light goes down on the
    # strength of a sentence nothing checks.
    # SELECTORS. Two kinds, and only one of them is this stage's to derive.
    #
    # The optical-path table states some required_selectors as a VALUE the
    # device keys on -- csuw1_disk_position `out`, lapp_branch `inline` --
    # and those are read straight across. It states others as a description:
    # light_path_port `the imaging port`, filter_turret_1 `the multiband
    # cube`. A description is not a label, and $defs/selector says why an
    # index must not be invented to fill the gap: "a numeric encoding a seat
    # invents is not one the instrument answers to". Those are commanded and
    # unrecorded until somebody reads the labels.
    #
    # The port that picks the camera is neither -- it is the person's
    # decision, and it enters on the goal card. `selectors` is not a field
    # goal.schema.json declares, so this reads what is there and refuses
    # when it is not, rather than guessing from the store: the chain to
    # camera_red ends at an E5 recall carrying the word `probably`, and the
    # store declines to promote it.
    literal = {"csuw1_disk_position", "lapp_branch"}
    selectors = [{"element": e, "value": v, "selects": [],
                  "note": "stated as a value by the optical-path table and read across unchanged"}
                 for e, v in sorted((axc_required_selectors(config) or {}).items())
                 if e in literal and isinstance(v, str)]
    from_goal = [s for s in (goal.get("selectors") or []) if isinstance(s, dict)]
    selectors = from_goal + [s for s in selectors
                             if s["element"] not in {g.get("element") for g in from_goal}]

    detectors = [d for d in (axc_detectors(config) or []) if d]
    # A selector that names a detector in `selects` IS the choice, made where
    # a decision belongs. Nothing here reads prose and nothing infers.
    decided_by = next(((s, d) for s in selectors for d in (s.get("selects") or [])
                       if d in detectors), None)
    chosen_detector = decided_by[1] if decided_by else None
    if chosen_detector is not None:
        detectors = [chosen_detector]

    # A DETECTOR CHOSEN BY DECISION RATHER THAN BOUNDED BY AN AXIS IS A RISK,
    # and the run is its falsifier. Written here rather than as a success
    # criterion because it is not what this run measures: criteria carry a
    # comparator and a threshold, and "the light arrived on the arm we
    # pointed it at" has neither. A reader a month from now needs to know
    # WHY a run went ahead on a decision, and this is the field that says so.
    open_risks: list[str] = []
    if decided_by is not None:
        selector, detector = decided_by
        open_risks.append(
            f"The detector is {detector}, selected by setting {selector['element']} to "
            f"{selector['value']!r}. That is the person's DECISION and not a bound any axis "
            "returned -- the store's chain to this arm ends at an E5 recall carrying the word "
            "`probably`, and the store declines to promote it. THIS RUN ADJUDICATES IT: if no "
            "particles appear on this arm, the recalled emission-wheel-to-camera mapping is "
            "inverted, and that is a RESULT rather than a failure -- the result card carries "
            "the correction to the librarian. It costs nothing to find out this way, because "
            "bare particles are not the mount and the one mount is not spent. The reading that "
            "would have settled it beforehand is one visit to the emission wheel, which also "
            "closes light_path_port and filter_turret_1; it is on card 018 and comes before the "
            "measurement this run unblocks, not before this run.")
    if "record_length" not in have or "exposure_time" not in have:
        unfillable.append(
            "actions: an acquire action needs a record length and an exposure, and the plan "
            "carries " + (", ".join(sorted(have & {"record_length", "exposure_time"})) or "neither"))
    elif frame_count is None:
        unfillable.append(
            f"actions[acquire]: {record_length:g} s of record is not a whole number of "
            f"{exposure_time:g} s exposures, so the acquire action has no frame count. Rounding "
            "one out would move the record length, and the record length came from the person")
    elif len(detectors) != 1:
        unfillable.append(
            "actions[acquire]: the person confirmed the red arm on 2026-09-21 and no field "
            "carries it. goal.schema.json declares no `selectors` and check 1 refuses one; "
            "plan.schema.json gained system_configuration.selectors the same day -- so the "
            "slot exists where a selector is EMITTED and not where the decision ENTERS. "
            "Deriving camera_red from the store instead is refused here on purpose: the chain "
            "ends at emission_wheel_camera_mapping, E5, with the word `probably`, and "
            "red_path_605_is_the_ff01_595_31_filter declines to name the device for that exact "
            "reason. Raised with manager-microscope. "
            f"{config!r} declares {len(detectors)} detectors ({', '.join(detectors)}) and "
            "the device table settles that the cameras cannot break the tie themselves: both "
            "are Kinetix 22, and 'the 561 dichroic in the port is the only thing making the "
            "arms differ'. Everything else the acquire needs is here -- "
            f"{frame_count} frames of {exposure_time:g} s. Only the device is missing")
    else:
        actions.append({"id": "act_acquire", "device": detectors[0], "action": "acquire_series",
                        "reversible": True,
                        "parameters": ["exposure_time", "frame_count"], "tier": 1})
    if unplaced:
        print(f"  {len(unplaced)} condition(s) got no set action, because no registry element "
              f"carries the name: {', '.join(unplaced)}. Three kinds, and only one is a gap. "
              "record_length and exposure_time are the ACQUIRE action's parameters and want no "
              "set of their own. The two windows are instructions to the estimator and no "
              "device performs them at all. Only the line intensity is a real gap: it belongs "
              "to an engine the path table declines to confirm (lapp_branch_assignment).",
              file=sys.stderr)

    carried_assumptions[:] = [a for a in goal.get("assumptions") or []
                              if {n for n in a.get("numbers") or []} & have]

    # THE STOP CRITERION IS THE PLANNED END, and `on_met` says so: `complete`
    # rather than `continue`, because reaching the record length is the run
    # finishing and not a guard being violated.
    stop_criteria: list[dict] = []
    if frame_count is not None:
        stop_criteria.append({
            "id": "sc_frame_count", "metric": "frames_acquired", "comparator": ">=",
            "number": "frame_count", "on_met": "complete",
            "statement": (f"the acquisition stops at {frame_count} frames, which is the planned "
                          f"end and not a guard. It counts FRAMES and not seconds on purpose: an "
                          "elapsed time accumulated a step at a time lands a hair off the "
                          "boundary and reports a finished run as unfinished, and the direction "
                          "of the error moves with the exposure. A frame count is an integer and "
                          "compares exactly. No tolerance is added -- the limit came from the "
                          "person and an operator that widens it is changing an approved number")})
    else:
        unfillable.append(
            "stop_criteria: a criterion compares a metric against a number in numbers[] (5.4) "
            "and no frame count could be derived")

    # COST IS ARITHMETIC OVER THE PLAN, and says what it does not cover.
    if frame_count is not None:
        cost = {"wall_clock": (f"{frame_count} frames x {exposure_time:g} s = "
                               f"{record_length:g} s of acquisition. That is a FLOOR and not an "
                               "estimate: setup, focusing and settling are not bounded -- A5 "
                               "abstains on the settling time and nothing bounds the session "
                               "budget -- so the only part of the wall clock this plan can do "
                               "arithmetic on is the record itself"),
                "numbers": ["frame_count", "exposure_time", "record_length"]}
    else:
        cost = {"wall_clock": "", "numbers": []}
        unfillable.append("cost: no duration is on the card, so wall_clock would be invented here")

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
        # Carried from the goal, both of them. `purpose` is an enum and held a
        # SENTENCE -- and the sentence said "measure the tracer diffusivity",
        # which is mic-20260918-001's question and not this one's. Two faults
        # in one field: the wrong type, and a claim about what this run
        # measures that was wrong. A free-text purpose is not a thing the
        # plan contract has, and it should not be: the goal decides what the
        # question is for and the plan carries it.
        "purpose": goal["purpose"],
        "intent": goal.get("intent", "explore"),
        "observable": {"name": (goal.get("observable") or {}).get("name")},
        "system_configuration": {
            "config": config, "optical_path": config, "model": None,
            # Every element and channel this plan touches, deduplicated and
            # ordered -- the actions' devices plus the selectors' elements.
            # minItems 1, so an empty one is a schema failure and not a
            # blank to be filled later.
            "devices": sorted({a["device"] for a in actions}
                              | {s["element"] for s in selectors}),
            "selectors": selectors},
        "preconditions": carried_pre,
        "conditions": conditions,
        "actions": actions,
        "envelope_check": {"checked_against": [], "status": "unavailable",
                           "note": "no condition is bounded, so nothing was compared"},
        "cost": cost,
        "stop_criteria": stop_criteria,
        "success_criteria": success,
        "targets": carried_targets,
        "open_risks": open_risks,
        "numbers": numbers,
        # An assumed: number is meaningless without the assumption that
        # explains it, so the two travel together. Carried unchanged for the
        # same reason a precondition is: rewording a falsifier makes it a
        # second falsifier by the next revision (P3).
        "assumptions": carried_assumptions,
        # WHAT THE CARRIED PRECONDITIONS REST ON. A precondition's `basis`
        # names `kb:<entry_id>`, and check 54 is right to refuse a card that
        # rests a bound on an entry it never cites: a plan carrying A4's
        # requirement without A4's evidence looks grounded and is not.
        # Filtered to what is actually cited rather than copying every
        # kb_ref in the fan-out -- citing more than the card rests on is the
        # same defect pointing the other way.
        "kb_refs": carried_refs,
        # An assumption names the gap it stands on, so the gap has to be
        # here too or the naming points at nothing -- looked-for-and-absent
        # and nobody-checked are the distinction check 39 exists to keep,
        # and it collapses if the card carries the claim without the gap.
        "kb_gaps": [g for g in goal.get("kb_gaps") or []
                    if g.get("gap_id") in {a.get("gap_ref") for a in carried_assumptions}],
        "degraded": [],
    }
    return card, unfillable, preconditions


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
            # Exactly one of `number` and `target`, and they are rendered
            # apart because they are not the same kind of thing: a number is
            # a graded claim about the world and a target is a decision the
            # person made. Reading `number` unconditionally crashed the
            # moment S5 started carrying targets, which is the shape of the
            # mistake -- one field assumed where the contract says two.
            lines += [
                f"- **{c['id']}**: {c.get('statement','')} (`{c['metric']}` {c['comparator']} "
                + (f"`numbers[{c['number']}]`)" if c.get("number") is not None
                   else f"`targets[{c['target']}]`, a decision and not a graded value)")
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
        card, unfillable, preconditions = assemble(args.qid, args.revision)
    except (PlanError, s4.SynthesisError) as exc:
        print(f"S5 refused: {exc}", file=sys.stderr)
        return 2

    print(f"S5 {args.qid}: configuration {card['system_configuration']['config']}, "
          f"{len(card['numbers'])} number(s), {len(card['conditions'])} condition(s)")
    for n in card["numbers"]:
        print(f"  number  {n['name']:28} {n['value']} {n['unit']:6} {n['grade']}  {n['source']}")
    # Said in both directions -- before a refusal and before a write -- because
    # the write is the dangerous one: a plan that omits a precondition an axis
    # returned is a plan missing a requirement, and nothing downstream would
    # show it. This stage does not invent a field to put them in; the contract
    # is manager-microscope's and the gap is reported there.
    if preconditions:
        print(f"\n  {len(preconditions)} precondition(s) reached this stage and are carried into "
              "the plan's `preconditions` (slot added 2026-09-21):", file=sys.stderr)
        for pre in preconditions:
            bound = pre.get("bound") or {}
            print(f"    {bound.get('parameter', '?')} <- {pre.get('axis', '?')}: "
                  f"{str(bound.get('requires', ''))[:160]}", file=sys.stderr)
        print("    Until that slot existed this stage dropped them without saying so, because "
              "a\n    precondition names no number and `conditions` points into numbers[] by "
              "name.\n    Nothing yet compares the plan's list against the axis cards' -- the "
              "schema\n    says that check is owed, and it is not this file's to write.",
              file=sys.stderr)

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
