"""A7: driving and motion -- the limits of the side that touches the system.

The other six axes ask what is being looked at. A7 asks what is being done
(4.5.3): the driving quantities, the motion quantities, and the one inequality
that binds them, where drag beats trap force and the bead leaves.

The inequality list below is **derived from 4.5.3, not declared here**
(4.5.2.1). That matters in a way that is easy to lose: if this file chose its
own list it could shorten it, and a list that can shorten itself cannot be
audited against silence. Each entry names the sentence of 4.5.3 or 1b it comes
from, so the derivation is checkable by reading rather than by trust.

What 4.5.2.1 asks of every axis, and the failure it is built against:

  A range or an abstention for **every** inequality on the list. Silence on two
  of seven reads as "this axis does not constrain there", and S4 cannot tell
  that from "this axis could not compute it". One is headroom and the other is
  a missing measurement.

So an abstention here is per inequality and carries its own reason, and the
reasons are not interchangeable. `no_input` means a number this bound needs
does not exist anywhere we may read. `not_constraining` means the bound was
evaluated and does not bite under these conditions. `not_requested` means the
condition the bound is about never arises in this question. Three different
next actions: measure it, use it, or nothing.

This file computes rather than estimates wherever a closed form exists, because
4.5.2.1 puts that split at the axis boundary: code emits what has a closed
form and a sub-agent takes only what does not, and neither recomputes the
other's half. Everything A7 owns has a closed form. There is no sub-agent here.

It reads contracts/ and the knowledge store, and imports no device (7.2 rule
2).
"""

from __future__ import annotations

import os
import sys

# Same shadow screening.py documents: this directory holds operator.py, and
# `operator` is a standard-library module that `enum` imports during
# interpreter start-up. `import json` alone is enough to reach it -- json pulls
# re, re pulls enum, enum pulls operator -- so running any file in src/ as a
# script breaks before its first statement. Dropping this directory from
# sys.path costs nothing here and has to happen before the first import that
# scans the path. Renaming operator.py to system_operator.py would end it for
# every caller instead of each caller repeating this; that rename is the design
# seat's, since plan.md 7 fixes the name.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import json                                                      # noqa: E402
import math                                                      # noqa: E402
from dataclasses import dataclass, field                          # noqa: E402
from datetime import datetime, timezone                           # noqa: E402
from pathlib import Path                                          # noqa: E402

AGENT = Path(__file__).resolve().parent.parent
REPO = AGENT.parent
CONTRACTS = REPO / "contracts"
KB = REPO / "librarian_agent" / "kb"

AXIS = "a7"


class AxisError(RuntimeError):
    """The axis could not run. Not a verdict -- a verdict is an answer."""


# --------------------------------------------------------------------------- #
# the inequalities this axis owns, derived from 4.5.3
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Inequality:
    id: str
    parameter: str
    statement: str
    needs: tuple[str, ...]
    derived_from: str


OWNED = (
    Inequality(
        id="escape_velocity_window",
        parameter="trap_velocity",
        statement="x_min*kappa/gamma <= v <= x_max*kappa/gamma: below the window the "
                  "offset cannot be resolved, above it drag beats the trap and the bead leaves",
        needs=("trap_stiffness", "stokes_drag", "resolvable_offset", "model_limit_offset"),
        derived_from="4.5.3 A7 'coupled limit -- escape', widened to a window by 1b",
    ),
    Inequality(
        id="sampling_above_corner",
        parameter="sampling_rate",
        statement="f_s >= 10*f_c with f_c = kappa/(2*pi*gamma): sampling below ten times the "
                  "corner frequency loses the trap's own response",
        needs=("trap_stiffness", "stokes_drag"),
        derived_from="1b transfer, and rule (a) keeps it here because kappa ties it to the escape bound",
    ),
    Inequality(
        id="resolvable_offset_floor",
        parameter="resolvable_offset",
        statement="x_min = sigma_loc/target_relative_error: the smallest offset worth "
                  "commanding follows from the target, and is not chosen",
        needs=("localisation_error", "target_relative_error"),
        derived_from="1b transfer",
    ),
    Inequality(
        id="settling_before_measurement",
        parameter="settling_time",
        statement="t_settle = ln(1/target)*gamma/kappa: acquisition starts after the trap has "
                  "settled, and this number is an input to A5 rather than a bound of its own",
        needs=("trap_stiffness", "stokes_drag", "target_relative_error"),
        derived_from="4.5.3 A7 'settling time -> A5's input', and 1b",
    ),
    Inequality(
        id="trap_splitting_stiffness",
        parameter="trap_count",
        statement="per-trap power ~ total/N, so per-trap stiffness falls with N; multiplexing "
                  "adds a channel count and an update rate, and traps interfere below a minimum spacing",
        needs=("total_optical_power", "trap_stiffness", "minimum_trap_spacing"),
        derived_from="4.5.3 A7 'driving quantity: trap count N and splitting'",
    ),
    Inequality(
        id="stage_motion_envelope",
        parameter="stage_velocity",
        statement="piezo range, bandwidth and settling, and the motorised stage's speed, "
                  "acceleration, backlash and repeatability, bound commanded motion",
        needs=("piezo_bandwidth", "piezo_settling_time", "stage_max_velocity"),
        derived_from="4.5.3 A7 'motion'",
    ),
    Inequality(
        id="power_within_safety",
        parameter="total_optical_power",
        statement="total power meets P0's limit before it meets the sample's: whatever else "
                  "this axis emits is a subset of the safety envelope",
        needs=("safety_power_limit",),
        derived_from="4.5.3 A7 'safety coupling', and 2.1",
    ),
)


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #


def kb_entry(entry_id: str) -> dict | None:
    """Read one entry straight off the store.

    This is the degraded path and the card has to say so (4.3.2): no service
    means no gap detection, no conflict detection and no external search, so
    what we missed is unknown rather than nothing.
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


def goal_number(goal: dict, name: str) -> dict | None:
    return next((n for n in goal.get("numbers", []) if n.get("name") == name), None)


def driving_requested(goal: dict, config: str) -> bool:
    """Does this question ask for anything to be driven?

    Read off contracts/ rather than guessed: the observable is produced by this
    configuration either on its own or only in composition with a perturbation,
    and it is the second case that puts a trap in the question. A goal that
    names no driving leaves this axis with nothing to bound, and 4.5.3 is
    explicit that it abstains and stays on the list rather than being cut --
    cutting it would record nothing about the constraint that went unexamined
    (P1).
    """
    caps = json.loads((CONTRACTS / "capabilities" / "microscope.json").read_text())
    by_id = {c["config"]: c for c in caps.get("configurations", [])}
    observable = (goal.get("observable") or {}).get("name", "")
    for produced in by_id.get(config, {}).get("produces", []) or []:
        if isinstance(produced, str):
            if produced == observable:
                return False               # produced alone: nothing is driven
        elif produced.get("id") == observable:
            return bool(produced.get("requires_composition"))
    raise AxisError(
        f"configuration {config!r} does not produce {observable!r}; S3.0 should not have "
        "fanned out over it (4.5.1)"
    )


def stokes_drag(viscosity_pa_s: float, radius_m: float) -> float:
    """gamma = 6*pi*eta*a, unbounded medium (1b transfer, A7 slot).

    The unbounded value is the one this formula gives and the one the card
    reports. Near a wall the true drag is larger, which biases anything divided
    by gamma upward and anything multiplied by it downward; the card states that
    with a number rather than a warning.
    """
    return 6.0 * math.pi * viscosity_pa_s * radius_m


def wall_correction(radius_m: float, height_m: float) -> float:
    """Faxen, parallel to a wall: gamma/gamma_0 = 1/(1 - 9a/16h + ...).

    First order is what 1b carried across. The next terms are kept here because
    the ratio decides whether truncating is honest: at a/h = 1/4 the series
    gives 16.2% against the first term's 16.4%, so the first term is good to
    about two tenths of a point and the difference is far inside one
    significant figure. At a larger ratio it would not be.
    """
    r = radius_m / height_m
    series = 1 - (9 / 16) * r + (1 / 8) * r ** 3 - (45 / 256) * r ** 4 - (1 / 16) * r ** 5
    return 1 / series


# --------------------------------------------------------------------------- #
# outcomes
# --------------------------------------------------------------------------- #


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
    caller_id: str
    config: str
    kb_version: str | None
    outcomes: list[Outcome]
    numbers: list[dict] = field(default_factory=list)
    kb_refs: list[str] = field(default_factory=list)
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

        4.5.2.1 refuses the axis's output when this is non-empty, and refuses it
        here rather than downstream: an axis that reports six of seven has
        already lost the fact that the seventh was never asked.
        """
        spoke = {o.inequality_id for o in self.outcomes}
        return [i.id for i in OWNED if i.id not in spoke]


def evaluate(goal: dict, config: str, caller_id: str) -> AxisRun:
    """Every inequality A7 owns, each with a range or a reason it has none."""
    run = AxisRun(caller_id=caller_id, config=config, kb_version=kb_version(),
                  outcomes=[], degraded=["librarian_agent"])

    driven = driving_requested(goal, config)

    # gamma is the one input this axis can produce today, and producing it
    # changes what the abstentions say: they name one missing measurement
    # instead of two.
    viscosity = kb_entry("water_viscosity_293k")
    ambient = kb_entry("lab_ambient_temperature")
    diameter = goal_number(goal, "tracer_diameter")
    gamma = None
    if viscosity and diameter:
        eta = next((n["value"] for n in viscosity.get("numbers", [])
                    if n.get("name") == "viscosity"), None)
        radius_m = diameter["value"] * 1e-6 / 2
        if eta is not None:
            gamma = stokes_drag(eta, radius_m)
            run.kb_refs.append("kb:water_viscosity_293k")
            window = (viscosity.get("validity") or {}).get("temperature") or {}
            if ambient:
                run.kb_refs.append("kb:lab_ambient_temperature")
                run.kb_refs.append("kb:sample_temperature_not_actuated")
                run.notes.append(
                    f"The viscosity holds between {window.get('min')} and {window.get('max')} "
                    f"{window.get('unit')} and the laboratory reads 293 K, so the value is used "
                    "inside its window rather than carried past it. Sample temperature is not "
                    "actuated here, so the ambient reading is the best statement of it, and that "
                    "is a claim about the room rather than about the sample."
                )
            run.notes.append(
                f"Stokes drag, unbounded medium: 6*pi*eta*a = {gamma:.2e} N*s/m "
                f"({gamma * 1e6:.3f} pN*s/um), one significant figure at 5e-8 N*s/m. It is in "
                "prose and not in numbers[] because units.json registers no unit of drag -- "
                "neither N*s/m nor pN*s/um -- and a number's unit has to be in that registry. "
                "Requested from the seat that owns contracts/."
            )
            run.notes.append(
                "That drag is the unbounded-medium value and it is biased low near the "
                "coverslip. Faxen parallel to a wall gives +16.4% at a = 2.5 um and h = 10 um "
                "(+16.2% carrying the series past first order), against +12.7% for the 4 um "
                "bead the prior project cited. The bias is real and it is smaller than one "
                "significant figure, so it does not move an order-of-magnitude answer -- which "
                "is also why correcting by formula buys little next to a calibration in situ, "
                "where a measured corner frequency returns kappa and the wall-corrected drag "
                "together. h is not stated anywhere, so +16.4% stands on h = 10 um and nothing "
                "else."
            )

    absent = {
        "trap_stiffness": "no trap stiffness exists: the tweezers calibration is GUI-only and "
                          "the store holds no kappa",
        "localisation_error": "no localisation error exists: the camera entry enters no sensor "
                              "number, so sigma_loc has nothing to come from",
        "model_limit_offset": "x_max is where the ray-optics model stops being defined, and that "
                              "model was deliberately not taken across (1b)",
        "minimum_trap_spacing": "no measured trap-trap interference spacing exists",
        "piezo_bandwidth": "the piezo constants from the prior project are measured numbers that "
                           "go through the librarian at E3, not into code (1b downgrade)",
        "piezo_settling_time": "same measurement, same route",
        "stage_max_velocity": "no stage velocity has been measured here",
        "safety_power_limit": "envelope/safety.json does not exist; it is policy a person writes "
                              "after confirming it physically (2.1 rule 7)",
        "total_optical_power": "no power is requested by this goal and none has been measured",
        "target_relative_error": "the goal states a decade of resolution and a signal-to-noise "
                                 "target, and neither is a relative error on a trap offset: an "
                                 "SNR is about detecting the bead and x_min is about resolving "
                                 "how far it was pushed. Reading one as the other would put a "
                                 "number into a bound it does not belong to",
    }
    # Only gamma. snr_target was read as target_relative_error in an earlier
    # pass here, which overstated what was available: an SNR target and a
    # relative-error target are different quantities and the floor needs the
    # second one.
    have = {"stokes_drag"} if gamma is not None else set()

    for ineq in OWNED:
        missing = [n for n in ineq.needs if n not in have and n in absent]
        if not driven:
            run.outcomes.append(Outcome(
                inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
                kind="not_requested",
                reason=("this goal drives nothing: it asks for "
                        f"{(goal.get('observable') or {}).get('name')!r} on an imaging "
                        "configuration with no perturbation composed in, so there is no "
                        "commanded motion or power for this bound to be about. The missing "
                        "inputs are listed anyway -- they are what would have to be measured "
                        "before a driven plan could be made"),
                missing=missing,
            ))
            continue
        if missing:
            run.outcomes.append(Outcome(
                inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
                kind="no_input", missing=missing,
                reason="; ".join(absent[m] for m in missing),
            ))
            continue
        run.outcomes.append(Outcome(
            inequality_id=ineq.id, parameter=ineq.parameter, state="failed",
            reason="every input is present and this axis has no code to emit the range: "
                   "that is a gap in this file, not an abstention (4.5.2.1)",
        ))

    for gap_id, observable, why in (
        ("trap_stiffness", "trap_stiffness", absent["trap_stiffness"]),
        ("localisation_error", "localisation_error", absent["localisation_error"]),
        ("working_height", "working_height_above_coverslip",
         "no working height is stated anywhere, and the wall correction scales directly with it"),
    ):
        run.kb_gaps.append({
            "gap_id": gap_id, "observable": observable, "kind": "absent",
            "searched": ["librarian_agent/kb/entries/", "librarian_agent/kb/staging/",
                         "contracts/capabilities/microscope.json"],
            "kb_version": run.kb_version, "asked_by": caller_id,
        })
    return run


# --------------------------------------------------------------------------- #
# the card
# --------------------------------------------------------------------------- #


LEDGER_FIELD = "inequalities"


def ledger_has_a_home() -> bool:
    """Whether an axis card can carry the per-inequality ledger at all.

    4.5.2.1 requires the enumeration, and axis.schema.json offers `constraints`
    (intervals), `counterexample` (for infeasible), one `abstain_reason` string
    and one `note` string, with unevaluatedProperties false. Seven outcomes,
    each with its own kind and its own missing inputs, do not fit in one string
    except as prose -- and prose is what the section exists to replace, since
    nothing can check it and a missing line in it looks like no line at all.

    An interval with neither min nor max is not a way out. That is exactly the
    silence 4.5.2.1 forbids being read as headroom.

    So this returns False today and the card is refused rather than written
    wrong. It clears itself the moment the field exists.
    """
    schema = json.loads((CONTRACTS / "schemas" / "axis.schema.json").read_text())
    return LEDGER_FIELD in (schema.get("properties") or {})


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
            "outcomes 4.5.2.1 requires. Writing them into abstain_reason as prose would "
            "reproduce the failure that section is against. Requested from the seat that owns "
            "contracts/; the ledger is printed instead so the work is not lost"
        )
    card = {
        "card": "axis",
        "schema_version": "0.1",
        "id": f"axis-{qid}-{run.config}-{AXIS}",
        "qid": qid,
        "thread": goal.get("thread", f"solo-{qid}"),
        "round": goal.get("round", 0),
        "revision": 1,
        "author": "microscope_agent",
        "created_at": created_at,
        "status": "DRAFT",
        "caller_id": run.caller_id,
        "config": run.config,
        "axis": AXIS,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A7: driving and motion (4.5.3).")
    parser.add_argument("goal", type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--caller-id", required=True)
    args = parser.parse_args(argv)

    goal = json.loads(args.goal.read_text())
    if goal.get("card") != "goal":
        print(f"{args.goal} is not a goal card", file=sys.stderr)
        return 2
    qid = goal.get("qid", "")
    run = evaluate(goal, args.config, args.caller_id)

    print(f"A7 {args.config}: verdict {run.verdict}, {len(run.outcomes)} inequalities, "
          f"kb_version {run.kb_version}, degraded {run.degraded}")
    for o in run.outcomes:
        line = f"  {o.inequality_id:28} {o.state:10}"
        if o.kind:
            line += f" {o.kind:17}"
        if o.missing:
            line += f" missing={','.join(o.missing)}"
        print(line)
    for note in run.notes:
        print(f"  note: {note}")

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        card = to_card(run, goal, qid, created_at)
    except AxisError as exc:
        print(f"\nno card written: {exc}", file=sys.stderr)
        print("\nledger, in full:")
        print(json.dumps([o.as_dict() for o in run.outcomes], ensure_ascii=False, indent=2))
        return 3
    out = AGENT / "questions" / qid / f"axis_{run.config}_{AXIS}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
