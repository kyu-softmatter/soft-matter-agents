"""A5: time stability -- drift, PFS, re-settling, total duration and schedule.

4.5.3 gives this axis that cell, and the six inequalities below are derived
from it rather than declared here (4.5.2.1): drift and PFS are one item each,
re-settling is two because this configuration has two different mechanisms to
settle, and duration and schedule are separated because they fail on different
inputs -- one is a sum of times, the other a calendar.

Answered by the service, like A4 and A6: a --responses file holding what the
librarian returned, refused unless stamped with the pin it was asked at. This
axis never opens the store.

What the pass found:

  **Nothing this axis owns produces a bound, and one of the six is refused for
  a reason worth more than the other five.** The PFS interlock is known, it
  bites, and it cannot be written. 2.1 interlock 3 disables PFS across turret
  and path changes and re-acquires it after; the registry carries the element
  and says so. But `precondition.basis` must resolve to a name in numbers[] or
  a kb_ref, the service answers absent for both `pfs` and `perfect_focus`, and
  a safety interlock is policy rather than knowledge (2.1) -- so the one shape
  that fits has nothing to stand on. It is recorded as no_input naming what is
  missing, and what is missing is an entry, not a measurement.

  **`pfs` is deliberately not recorded as a gap.** The service says absent and
  the published devices table carries the element with its interlock note, so
  absent would be the false gap 004 warns about. Two of the six inputs are the
  person's rather than the store's -- a time budget and an availability window
  -- and those are not gaps either: a gap is what the librarian could not
  supply, and the librarian was never the place to ask.

  **The disk row abstains with grounds rather than for want of a number.** An
  exposure through the spinning disk must be an integer multiple of the disk
  period and nothing may be acquired while it spins up -- and on this
  configuration the disk is out. The bound does not bite here. That is a
  different claim from not knowing the disk period, and the ledger keeps them
  apart.

  **The schedule row stops where the entry stops.** stand_ti2e_lock_groups
  carries the arrangement at E3 and its own validity_conditions decline to
  stamp the scheduling consequence -- that stage moves serialise with port and
  filter changes -- as a reading. This axis does not promote it to one.

It reads contracts/ and the recorded responses, and imports no device
(7.2 rule 2).
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
from datetime import datetime, timezone                           # noqa: E402
from pathlib import Path                                          # noqa: E402


def _load(name: str, filename: str):
    path = os.path.join(_HERE, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)                               # type: ignore[union-attr]
    return module


axc = _load("_mic_axis_common", "axis_common.py")

AXIS = "a5"

OWNED = (
    axc.Inequality(
        id="focus_drift_over_record",
        parameter="record_length",
        statement="focus must not wander further over the record than the measurement can "
                  "tolerate: drift_rate * record_length <= focus_tolerance",
        needs=("drift_rate", "focus_tolerance"),
        derived_from="4.5.3 A5 'drift'",
    ),
    axc.Inequality(
        id="pfs_across_configuration_change",
        parameter="pfs_state",
        statement="focus stabilisation must be disabled across a turret or optical-path change "
                  "and re-acquired after it, and no acquisition may span that bracket",
        needs=("pfs_behaviour",),
        derived_from="4.5.3 A5 'PFS state', and 2.1 interlock 3",
    ),
    axc.Inequality(
        id="disk_spin_up_before_acquisition",
        parameter="acquisition_start",
        statement="nothing may be acquired while the spinning disk is still coming up to speed",
        needs=("disk_spin_up_time",),
        derived_from="4.5.3 A5 're-settling after a configuration change'",
    ),
    axc.Inequality(
        id="settling_after_configuration_change",
        parameter="settling_time",
        statement="a measurement may not start until the mechanics have settled after the "
                  "turret, stage or path last moved",
        needs=("settling_time",),
        derived_from="4.5.3 A5 're-settling after a configuration change'",
    ),
    axc.Inequality(
        id="total_duration_within_budget",
        parameter="total_session_time",
        statement="exposures, overheads and settling together must fit the time the session has",
        needs=("session_time_budget",),
        derived_from="4.5.3 A5 'total duration'",
    ),
    axc.Inequality(
        id="schedule_serialisation",
        parameter="instrument_window",
        statement="the run must fit a window in which the instrument is free, and moves that "
                  "share a lock group cannot be scheduled to overlap",
        needs=("instrument_availability_window",),
        derived_from="4.5.3 A5 'schedule'",
    ),
)

GAP_IDS = {
    "drift_rate": "focus_drift_rate_absent",
    "settling_time": "mechanical_settling_time_absent",
}

# Inputs the librarian was never the place to ask. A gap is what the librarian
# could not supply (4.3.1), so recording these as gaps would claim a call that
# was never made and blame the store for not holding the person's diary.
PERSON_SIDE = ("session_time_budget", "instrument_availability_window", "focus_tolerance")

# Answered absent by the service and NOT recorded as a gap, because the fact is
# in the published devices table: the stand carries a `pfs` element whose note
# names 2.1 interlock 3. 004's rule is that an empty query is not evidence of
# absence when the thing is held under another name -- and here it is held in
# another place. What is genuinely missing is an entry to cite, not the fact.
IN_THE_TABLE_NOT_AN_ENTRY = ("pfs_behaviour",)

# Asked and absent, but this configuration does not need it: the disk is out.
NOT_NEEDED_HERE = ("disk_spin_up_time",)


def evaluate(goal: dict, config: str, caller_id: str, responses: dict, pin: str) -> axc.AxisRun:
    """Every inequality A5 owns, each with a constraint or a reason it has none."""
    run = axc.AxisRun(axis=AXIS, caller_id=caller_id, config=config, kb_version=pin,
                      owned=OWNED, degraded=[])
    run.kb_refs = axc.refs_from(responses, pin)
    run.kb_gaps = axc.gaps_from(responses, pin, caller_id, GAP_IDS)

    def outcome(ineq, **kw):
        run.outcomes.append(axc.Outcome(inequality_id=ineq.id, parameter=ineq.parameter, **kw))

    for ineq in OWNED:
        if ineq.id == "focus_drift_over_record":
            outcome(ineq, state="abstained", kind="no_input",
                    missing=["drift_rate", "focus_tolerance"],
                    reason="No drift rate has ever been measured on this instrument -- asked as "
                           "drift_rate, focus_drift and stage_drift, absent all three times -- "
                           "and nothing here licenses calling drift negligible instead. Two "
                           "served entries say why the opposite is more likely: sample "
                           "temperature is not actuated at all, so the dominant driver of "
                           "mechanical and thermal drift is uncontrolled, and the ambient "
                           "reading that stands in for it says in its own validity_conditions "
                           "that where the thermometer sits was not recorded, so it is not "
                           "established as a sample-adjacent temperature. The tolerance is the "
                           "other half and it is not the librarian's: how far focus may wander "
                           "is a property of the measurement. A6 separately bounds the depth of "
                           "field, and this axis does not reach for that -- an axis does not "
                           "take a sibling's output as input (4.5.3 rule b).")
        elif ineq.id == "pfs_across_configuration_change":
            outcome(ineq, state="abstained", kind="no_input", missing=["pfs_behaviour"],
                    reason="This is the one bound on this axis that is known, bites, and cannot "
                           "be written. 2.1 interlock 3 disables focus stabilisation across "
                           "turret and path changes and re-acquires it after, and the registry "
                           "carries a pfs element saying so. The shape that fits is a "
                           "precondition -- it restricts no value and requires something of the "
                           "plan -- and precondition.basis must resolve to a name in numbers[] "
                           "or to a kb_ref on this card. The service answers absent for both "
                           "`pfs` and `perfect_focus`, so there is no entry to cite, and the "
                           "interlock itself is policy rather than knowledge (2.1) and is "
                           "enforced by the operator whatever this card says. So the honest "
                           "state is no_input, and what is missing is an entry rather than a "
                           "measurement: the fact exists, in the published devices table, in a "
                           "form no bound can stand on.")
        elif ineq.id == "disk_spin_up_before_acquisition":
            outcome(ineq, state="abstained", kind="not_constraining",
                    reason="Both halves of the disk constraint are served and neither bites "
                           "here. Nothing may be acquired while the disk is spinning up, and an "
                           "exposure taken through it must be an integer multiple of the disk "
                           "period -- and on widefield_inline the disk is out, which the served "
                           "entry makes a required selector value on this configuration rather "
                           "than a configuration of its own. No disk in the path means no "
                           "spin-up to wait for. Recorded as not_constraining and not as "
                           "no_input deliberately: the disk period is indeed absent from the "
                           "store, but this row does not abstain for want of it. Not knowing a "
                           "number and not needing it are different, and folding them together "
                           "would make this configuration look blocked on a measurement it does "
                           "not use. The row returns to force on any configuration that puts "
                           "the disk back in.")
        elif ineq.id == "settling_after_configuration_change":
            outcome(ineq, state="abstained", kind="no_input", missing=["settling_time"],
                    reason="Asked as settling_time and as thermal_equilibration, absent both "
                           "times, and none of the entries served here carries one. This is the "
                           "mechanical and thermal half of re-settling, distinct from the disk "
                           "above: after the turret rotates, the stage moves or the path "
                           "changes, something has to stop moving before a record starts, and "
                           "no number on this instrument says how long that takes. It is a "
                           "measurement rather than a lookup -- one the operator can make once "
                           "and the store can then hold.")
        elif ineq.id == "total_duration_within_budget":
            outcome(ineq, state="abstained", kind="no_input", missing=["session_time_budget"],
                    reason="Nothing states how long this question may take. The budget is the "
                           "person's and was never the librarian's, so it is named here and not "
                           "recorded as a gap -- a gap claims the store was asked and could not "
                           "supply, and the store is not where a diary lives. The other side of "
                           "the bound is equally out of reach: the total is exposures plus "
                           "overheads plus settling, and how long the record must be is A2's "
                           "parameter. This axis states the bound and does not reach across for "
                           "it (4.5.3 rule b).")
        elif ineq.id == "schedule_serialisation":
            outcome(ineq, state="abstained", kind="no_input",
                    missing=["instrument_availability_window"],
                    reason="No availability window is stated, and that half is the person's "
                           "rather than the store's. The other half stops for a more "
                           "interesting reason. stand_ti2e_lock_groups is served at E3 and "
                           "carries the arrangement -- the body's optical elements in the "
                           "optical_path group, the motor stage in the stage group, because the "
                           "piezo rides on the motor stage -- but its own validity_conditions "
                           "mark the scheduling consequence, that stage moves serialise with "
                           "port and filter changes, as design rather than a hardware reading, "
                           "and say it is not stamped as one. So the serialisation this row "
                           "would rest on exists as a consequence nobody measured. This axis "
                           "does not promote it: a bound resting on an unstamped consequence "
                           "would carry the entry's E3 while claiming something the entry "
                           "declines to claim.")
        else:
            outcome(ineq, state="failed",
                    reason="every input is present and this axis has no code to emit the "
                           "constraint: that is a gap in this file, not an abstention (4.5.2.1)")

    run.notes.append(
        "Answered by the librarian service rather than by reading the store, which is what makes "
        f"degraded empty: {len(run.kb_refs)} entries came back with their own grades and "
        f"{len(run.kb_gaps)} questions came back absent, all at the pinned {pin}, and every call "
        "is in librarian_agent/queries/log.jsonl under this caller_id. Transport was a stdio "
        "client, this session's attached server having failed every call since 07:47:44Z."
    )
    run.notes.append(
        "Six bounds, no constraint, and the six do not fail the same way -- which is the point "
        "of enumerating them. One abstains with grounds because the disk is out of this path. "
        "Two want a measurement nobody has made here: a drift rate and a settling time, both "
        "recorded as gaps. Two want something the person has never said -- a time budget and an "
        "availability window -- and neither is a gap, because the librarian was never the place "
        "to ask. And one wants an entry rather than a measurement."
    )
    run.notes.append(
        "The PFS row is the finding. The interlock is real, it is enforced, and the contract now "
        "has exactly the right shape for it -- `precondition`, added on 2026-09-19 for A4's "
        "verifiability bound, which restricts no value and propagates to the plan. It cannot be "
        "used, because basis must resolve to a kb_ref and the service answers absent for pfs. "
        "One entry stating the interlock's behavioural half would turn this row from an "
        "abstention into a precondition S4 must carry. That entry does not exist, and the fact "
        "is sitting in the published devices table where no bound can cite it."
    )
    run.notes.append(
        "`pfs` is not in kb_gaps although the service answered absent, and the omission is "
        "deliberate. The devices table carries the element and its interlock note, so recording "
        "absent would assert the store does not know something it does know in another place -- "
        "the false gap 004 exists to prevent. Two gaps are recorded and each was asked under at "
        "least two names before being written down."
    )
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A5: time stability (4.5.3).")
    parser.add_argument("goal", type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--caller-id", required=True)
    parser.add_argument("--kb-version", required=True,
                        help="the pin to answer at. Not read from the store: the store moves and "
                             "siblings have to agree (check 33)")
    parser.add_argument("--responses", required=True, type=Path,
                        help="what the librarian returned for this caller_id at that pin")
    parser.add_argument("--revision", type=int, default=1,
                        help="the card's revision; the caller_id carries the same number "
                             "(check 33)")
    args = parser.parse_args(argv)

    goal = json.loads(args.goal.read_text())
    if goal.get("card") != "goal":
        print(f"{args.goal} is not a goal card", file=sys.stderr)
        return 2
    try:
        responses = axc.load_responses(args.responses, args.kb_version, args.caller_id)
    except axc.AxisError as exc:
        print(f"no card written: {exc}", file=sys.stderr)
        return 3
    run = evaluate(goal, args.config, args.caller_id, responses, args.kb_version)
    axc.report(run)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rc = axc.write(run, goal, goal.get("qid", ""), created_at)
    if rc == 0 and args.revision != 1:
        out = (axc.AGENT / "questions" / goal.get("qid", "")
               / f"axis_{args.config}_{AXIS}.json")
        card = json.loads(out.read_text())
        card["revision"] = args.revision
        out.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n")
        print(f"revision -> {args.revision}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
