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
    if mod is None:
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
