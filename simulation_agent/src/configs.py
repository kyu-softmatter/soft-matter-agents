"""Per-configuration axis logic (plan.md 4.5.2, 4.5.3).

The six axis modules in `src/` were written for `bd_overdamped` and carry its
physics in their bodies -- A1's assumption card says the tracers do not
interact, A2 counts independent MSD displacements, A3 clears a tracer from
its periodic image. Run on another configuration they emit cards that
validate and are wrong about the model, which is worse than no card.

So each axis module's `build()` first asks here whether the configuration has
its own module, `src/config_<config>.py`, and hands over if it does. Flat files, because the validator's path table admits `src/<file>` and
`src/devices/` only (check 13) and a new directory would need plan.md
section 7 and that table changed by two other seats. Five
seats each add one file rather than editing six shared ones; `bd_overdamped`
falls through to the bodies that already exist, unchanged.

A configuration module exposes `build(axis, qid, config, created_at,
caller_id, kb_version, kb_result, revision)` and `plan_queries(qid, revision,
config, issue)`. `issue` is fanout's and is the only place an id is composed
(4.3.1 rule 3); a configuration module receives it and does not reimplement it.
"""

from __future__ import annotations

import importlib


def module_for(config: str):
    """The configuration's own module, or None when it falls through."""
    try:
        return importlib.import_module(f"{__package__}.config_{config}")
    except ModuleNotFoundError as exc:
        if exc.name == f"{__package__}.config_{config}":
            return None
        raise


def dispatch(axis: str, qid: str, config: str, created_at: str, caller_id: str,
             kb_version: str, kb_result, revision: int):
    """The card from the configuration's module, or None to fall through."""
    mod = module_for(config)
    # A module without `build` falls through too. `abp_free` has one of these:
    # the axis modules hand the active configurations to `axes_abp` before
    # they reach here, so its configuration module carries only the S4 and S5
    # parts and defines no axis builder. Before this guard, A7 -- the one axis
    # that reaches the dispatch for an active configuration -- died on
    # AttributeError instead of falling through.
    if mod is None or not hasattr(mod, "build"):
        return None
    return mod.build(axis, qid, config, created_at, caller_id, kb_version, kb_result, revision)


def applicable(config: str, goal: dict) -> tuple[bool, str]:
    """Whether this configuration can answer THIS goal, and if not, why.

    S3.0 keeps every configuration that produces the observable, and two can:
    `bd_pairwise` and `bd_pairwise_driven_tracer` both produce
    structural_relaxation_time, one at zero drive and one under it. Which
    applies is decided by the goal -- whether it drives a particle -- and the
    capability table cannot say that. A configuration module may define
    `applicable(goal) -> (bool, reason)`; one without it applies to any goal.
    A rejection is returned with its reason so S4 records it (P1): a
    configuration that was never a candidate and one refused for this goal
    are different facts.
    """
    mod = module_for(config)
    if mod is None or not hasattr(mod, "applicable"):
        return True, ""
    return mod.applicable(goal)


def operating_point(config: str):
    """The configuration's S4 operating-point spec, or None to fall through.

    `synthesis.OPERATING_POINT` is a table keyed by configuration and held
    only `bd_overdamped`, so S4 raised `KeyError` for every configuration
    declared on 2026-09-23. The spec is per-configuration data of exactly the
    kind this module already keeps out of the shared files: the axis
    filenames a plan carries from, which numbers S4 computes, and what it
    rejected. Same shape as the table entry -- `carry`, `computed`, `ratio`,
    `point`, `rejected` -- so `synthesis.build` reads one or the other and
    nothing else changes.
    """
    mod = module_for(config)
    if mod is None or not hasattr(mod, "operating_point"):
        return None
    return mod.operating_point()


def plan_builder(config: str):
    """The configuration's own S5, or None to fall through.

    `plan_card.build` is `bd_overdamped`'s end to end -- it names that
    configuration's axis files, carries `tau_d` and `diffusivity`, and writes
    stop criteria against `box_length_min_dilution`. None of those exist for
    an active configuration, and parameterising the whole body in place would
    put five configurations' prose in one function. A configuration that
    needs a different plan supplies `build_plan(qid, created_at, revision)`
    and returns a whole card; `bd_overdamped` supplies nothing and the
    existing body runs unchanged.
    """
    mod = module_for(config)
    if mod is None or not hasattr(mod, "build_plan"):
        return None
    return mod.build_plan

