"""A7: driving and motion -- the limits of the side that touches the system.

The other six axes ask what is being looked at. A7 asks what is being done
(4.5.3): the driving quantities, the motion quantities, and the one inequality
that binds them, where drag beats trap force and the bead leaves.

The inequality list below is **derived from 4.5.3 and 1b, not declared here**
(4.5.2.1). If this file chose its own list it could shorten it, and a list that
can shorten itself cannot be audited against silence -- so each entry names the
sentence it comes from.

Everything A7 owns has a closed form, so there is no sub-agent here: 4.5.2.1
puts that split at the axis boundary, code emits what has a closed form and a
sub-agent takes only what does not, and neither recomputes the other's half.

It reads contracts/ and the store, and imports no device (7.2 rule 2).
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
import math                                                      # noqa: E402
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

AXIS = "a7"
GAP_IDS = {
    "trap_stiffness": "trap_stiffness",
    "localisation_error": "localisation_error",
    "working_height_above_coverslip": "working_height",
}

OWNED = (
    axc.Inequality(
        id="escape_velocity_window",
        parameter="trap_velocity",
        statement="x_min*kappa/gamma <= v <= x_max*kappa/gamma: below the window the offset "
                  "cannot be resolved, above it drag beats the trap and the bead leaves",
        needs=("trap_stiffness", "stokes_drag", "resolvable_offset", "model_limit_offset"),
        derived_from="4.5.3 A7 'coupled limit -- escape', widened to a window by 1b",
    ),
    axc.Inequality(
        id="sampling_above_corner",
        parameter="sampling_rate",
        statement="f_s >= 10*f_c with f_c = kappa/(2*pi*gamma): sampling below ten times the "
                  "corner frequency loses the trap's own response",
        needs=("trap_stiffness", "stokes_drag"),
        derived_from="1b transfer; rule (a) keeps it here because kappa ties it to the escape bound",
    ),
    axc.Inequality(
        id="resolvable_offset_floor",
        parameter="resolvable_offset",
        statement="x_min = sigma_loc/target_relative_error: the smallest offset worth commanding "
                  "follows from the target, and is not chosen",
        needs=("localisation_error", "target_relative_error"),
        derived_from="1b transfer",
    ),
    axc.Inequality(
        id="settling_before_measurement",
        parameter="settling_time",
        statement="t_settle = ln(1/target)*gamma/kappa: acquisition starts after the trap has "
                  "settled, and this number is an input to A5 rather than a bound of its own",
        needs=("trap_stiffness", "stokes_drag", "target_relative_error"),
        derived_from="4.5.3 A7 'settling time -> A5's input', and 1b",
    ),
    axc.Inequality(
        id="trap_splitting_stiffness",
        parameter="trap_count",
        statement="per-trap power ~ total/N, so per-trap stiffness falls with N; multiplexing "
                  "adds a channel count and an update rate, and traps interfere below a minimum "
                  "spacing",
        needs=("total_optical_power", "trap_stiffness", "minimum_trap_spacing"),
        derived_from="4.5.3 A7 'driving quantity: trap count N and splitting'",
    ),
    axc.Inequality(
        id="stage_motion_envelope",
        parameter="stage_velocity",
        statement="piezo range, bandwidth and settling, and the motorised stage's speed, "
                  "acceleration, backlash and repeatability, bound commanded motion",
        needs=("piezo_bandwidth", "piezo_settling_time", "stage_max_velocity"),
        derived_from="4.5.3 A7 'motion'",
    ),
    axc.Inequality(
        id="power_within_safety",
        parameter="total_optical_power",
        statement="total power meets P0's limit before it meets the sample's: whatever else this "
                  "axis emits is a subset of the safety envelope",
        needs=("safety_power_limit",),
        derived_from="4.5.3 A7 'safety coupling', and 2.1",
    ),
)

ABSENT = {
    "trap_stiffness": "no trap stiffness exists: the tweezers calibration is GUI-only and the "
                      "store holds no kappa",
    "localisation_error": "no localisation error exists: the camera entry enters no sensor "
                          "number, so sigma_loc has nothing to come from",
    "model_limit_offset": "x_max is where the ray-optics model stops being defined, and that "
                          "model was deliberately not taken across (1b)",
    "minimum_trap_spacing": "no measured trap-trap interference spacing exists",
    "piezo_bandwidth": "the piezo constants from the prior project are measured numbers that go "
                       "through the librarian at E3, not into code (1b downgrade)",
    "piezo_settling_time": "same measurement, same route",
    "stage_max_velocity": "no stage velocity has been measured here",
    "safety_power_limit": "envelope/safety.json does not exist; it is policy a person writes "
                          "after confirming it physically (2.1 rule 7)",
    "total_optical_power": "no power is requested by this goal and none has been measured",
    "target_relative_error": "the goal states a decade of resolution and a signal-to-noise "
                             "target, and neither is a relative error on a trap offset: an SNR "
                             "is about detecting the bead and x_min is about resolving how far "
                             "it was pushed. Reading one as the other would put a number into a "
                             "bound it does not belong to",
}


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
    observable = (goal.get("observable") or {}).get("name", "")
    for produced in axc.configuration(config).get("produces", []) or []:
        if isinstance(produced, str):
            if produced == observable:
                return False               # produced alone: nothing is driven
        elif produced.get("id") == observable:
            return bool(produced.get("requires_composition"))
    raise axc.AxisError(
        f"configuration {config!r} does not produce {observable!r}; S3.0 should not have fanned "
        "out over it (4.5.1)"
    )


def stokes_drag(viscosity_pa_s: float, radius_m: float) -> float:
    """gamma = 6*pi*eta*a, unbounded medium (1b transfer, A7 slot).

    The unbounded value is what this formula gives and what the card reports.
    Near a wall the true drag is larger, which biases anything divided by gamma
    upward and anything multiplied by it downward; the card states that with a
    number rather than a warning.
    """
    return 6.0 * math.pi * viscosity_pa_s * radius_m


def wall_correction(radius_m: float, height_m: float) -> float:
    """Faxen, parallel to a wall: gamma/gamma_0 = 1/(1 - 9a/16h + ...).

    First order is what 1b carried across. The next terms are kept because the
    ratio decides whether truncating is honest: at a/h = 1/4 the series gives
    16.2% against the first term's 16.4%, so the first term is good to about
    two tenths of a point and the difference is far inside one significant
    figure. At a larger ratio it would not be.
    """
    r = radius_m / height_m
    series = 1 - (9 / 16) * r + (1 / 8) * r ** 3 - (45 / 256) * r ** 4 - (1 / 16) * r ** 5
    return 1 / series


def evaluate(goal: dict, config: str, caller_id: str, responses: dict, pin: str) -> axc.AxisRun:
    """Every inequality A7 owns, each with a range or a reason it has none."""
    run = axc.AxisRun(axis=AXIS, caller_id=caller_id, config=config,
                      kb_version=pin, owned=OWNED, degraded=[])
    driven = driving_requested(goal, config)

    # gamma is the one input this axis can produce today, and producing it
    # changes what the abstentions say: they name one missing measurement
    # instead of two.
    served = responses["entries"]
    run.kb_refs = axc.refs_from(responses, pin)
    run.kb_gaps = axc.gaps_from(responses, pin, caller_id, GAP_IDS)
    viscosity = served.get("water_viscosity_293k")
    ambient = served.get("lab_ambient_temperature")
    diameter = axc.goal_number(goal, "tracer_diameter")
    gamma = None
    if viscosity and diameter:
        eta = next((n["value"] for n in viscosity.get("numbers", [])
                    if n.get("name") == "viscosity"), None)
        if eta is not None:
            gamma = stokes_drag(eta, diameter["value"] * 1e-6 / 2)
            window = (viscosity.get("validity") or {}).get("temperature") or {}
            if ambient:
                run.notes.append(
                    f"The viscosity holds between {window.get('min')} and {window.get('max')} "
                    f"{window.get('unit')} and the laboratory reads 293 K, so the value is used "
                    "inside its window rather than carried past it. Sample temperature is not "
                    "actuated here, so the ambient reading is the best statement of it, and that "
                    "is a claim about the room rather than about the sample."
                )
            # Carried so the computed number's inputs resolve inside this card.
            # Neither grade improves on the way (check 21).
            run.numbers.append({
                "name": "viscosity", "value": eta, "unit": "Pa*s",
                "source": "kb:water_viscosity_293k", "grade": "E3",
                "precision": "order_of_magnitude",
                "note": "the entry states it as of order one mPa*s, so one figure is all of it",
            })
            run.numbers.append(dict(diameter))
            run.numbers.append({
                "name": "stokes_drag", "symbol": "gamma_drag", "derived": True,
                "value": float(f"{gamma:.0e}"), "unit": "N*s/m",
                "source": "computed:stokes_drag", "grade": "E5",
                "precision": "order_of_magnitude",
                "formula": "3*pi*viscosity*tracer_diameter",
                "inputs": ["viscosity", "tracer_diameter"],
                "note": f"6*pi*eta*a with a = d/2, written on the diameter so no radius has to "
                        f"be invented as an intermediate. Unrounded it is {gamma:.3e} N*s/m "
                        f"({gamma * 1e6:.4f} pN*s/um); the value carries one figure because the "
                        "diameter is a nominal designation at E5 and a computed number inherits "
                        "the worst precision of its inputs (5.8). The symbol is gamma_drag and "
                        "not gamma on purpose: simulation's A7 owns shear rate (4.5.3), one "
                        "symbol has to mean one formula across both agents (5.7, check 36), and "
                        "the bridge compares the two A7 cards side by side.",
            })
            run.notes.append(
                "That drag is the unbounded-medium value and it is biased low near the "
                "coverslip. Faxen parallel to a wall gives +16.4% at a = 2.5 um and h = 10 um "
                "(+16.2% carrying the series past first order), against +12.7% for the 4 um bead "
                "the prior project cited. The bias is real and it is smaller than one "
                "significant figure, so it does not move an order-of-magnitude answer -- which "
                "is also why correcting by formula buys little next to a calibration in situ, "
                "where a measured corner frequency returns kappa and the wall-corrected drag "
                "together. h is not stated anywhere, so +16.4% stands on h = 10 um and nothing "
                "else. That argument has a condition and does not outlive it: it holds while "
                "this question is in explore mode, where 5.8 claims one figure and differences "
                "under 10x are ties. In confirm mode a 16% bias is inside what the answer "
                "claims, and calibrating in situ stops being the cheaper route and becomes the "
                "only correct one. Whoever reads this later should not carry away '16% is "
                "ignorable' without the mode it was ignorable in."
            )

    have = {"stokes_drag"} if gamma is not None else set()

    for ineq in OWNED:
        missing = [n for n in ineq.needs if n not in have and n in ABSENT]
        if not driven:
            run.outcomes.append(axc.Outcome(
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
            run.outcomes.append(axc.Outcome(
                inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
                kind="no_input", missing=missing,
                reason="; ".join(ABSENT[m] for m in missing),
            ))
            continue
        run.outcomes.append(axc.Outcome(
            inequality_id=ineq.id, parameter=ineq.parameter, state="failed",
            reason="every input is present and this axis has no code to emit the range: that is "
                   "a gap in this file, not an abstention (4.5.2.1)",
        ))

    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A7: driving and motion (4.5.3).")
    parser.add_argument("goal", type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--caller-id", required=True)
    parser.add_argument("--kb-version", required=True,
                        help="the pin to answer at; the store moves and siblings must agree")
    parser.add_argument("--responses", required=True, type=Path,
                        help="what the librarian returned for this caller_id at that pin")
    parser.add_argument("--prefix", default="",
                        help="filename prefix for a re-run of the whole fan-out, e.g. v2_ "
                             "(4.5.5); empty overwrites the card in place")
    parser.add_argument("--revision", type=int, default=1,
                        help="the card revision; v<N> in the caller_id follows it")
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
    return axc.write(run, goal, goal.get("qid", ""), created_at, args.revision, args.prefix)


if __name__ == "__main__":
    raise SystemExit(main())
