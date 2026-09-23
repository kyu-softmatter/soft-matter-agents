"""bd_pairwise_driven_tracer -- bd_pairwise plus one particle whose position
is imposed, moving at a set velocity along a set direction (a kinematic
constraint, not a force). Produces `structural_relaxation_time` under the
conditions driving_velocity and driving_direction; the undriven
configuration is the v = 0 row of the same observable.

This module currently decides only APPLICABILITY. It applies to a goal that
imposes a drive -- a selector named `drive` on the goal card -- and to no
other: an undriven question is bd_pairwise's, and without this the screen
kept both configurations for sim-20260923-001 and the driven one fell
through to bd_overdamped's A2, which crashed on a goal with no lag time.
The axis bodies for the driven question (sim-20260923-002) are written
when that question reaches S3; until then `build` refuses loudly rather
than emitting a card about physics it has not yet stated.
"""

from __future__ import annotations

from .config_bd_pairwise import goal_drives


def applicable(goal: dict) -> tuple[bool, str]:
    if not goal_drives(goal):
        return False, ("bd_pairwise_driven_tracer imposes a drive and this goal carries no `drive` "
                       "selector; bd_pairwise is the configuration for an undriven question")
    return True, ""


def plan_queries(qid: str, revision: int, config: str, issue) -> list[dict]:
    raise NotImplementedError(
        "bd_pairwise_driven_tracer: the axis bodies for a driven goal are not written yet; "
        "this module decides applicability only"
    )


def build(axis, qid, config, created_at, caller_id, kb_version, kb_result, revision):
    raise NotImplementedError(
        f"bd_pairwise_driven_tracer {axis}: the axis bodies for a driven goal are not written yet"
    )
