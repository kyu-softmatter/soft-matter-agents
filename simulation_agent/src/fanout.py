"""S3.0 screening and the S3 fan-out executor (plan.md 4.5.2, 4.5.3, 4.3.1).

**This is the only place a `caller_id` is composed.** §4.3.1 rule 3 is explicit
that an id is issued and not chosen: a sub-agent that picks its own can
impersonate a sibling's, "and a directive mixed into retrieved literature
could do that too". While the axis modules minted their own the rule was
merely unobserved; the moment a librarian call is wired in it becomes the
leak the rule names. So the id is injected, the axis modules take it as a
parameter, and neither can change it.

Isolation is per `caller_id` and deliberately not per `qid`: the siblings that
must not see each other all share one `qid`, so that would isolate nothing.

**Screening decides which configurations exist, not which are good.** It keeps
what `capabilities/simulation.json` declares as producing the goal's
observable, and judges nothing else -- the discriminators available here are
the ones decidable from the capability table alone, because every other
criterion needs numbers S3 has not produced yet (4.5.3).

Over the cap it **stops rather than cutting**. Dropping a candidate without
grounds makes it permanently unattempted, and nothing then accumulates to
justify attempting it -- which is the self-fulfilling bias P16 names.
"""

from __future__ import annotations

import json
import sys

from . import cards
from . import axis_a1_stability, axis_a2_statistics, axis_a3_finite_size
from . import axis_a4_sampling, axis_a5_budget, axis_a7_driving

# A6 is absent and its number stays empty: A7 means the same thing on both
# sides, which is what lets the bridge put two a7 cards side by side (4.5.3).
AXIS_MODULES = {
    "a1": axis_a1_stability,
    "a2": axis_a2_statistics,
    "a3": axis_a3_finite_size,
    "a4": axis_a4_sampling,
    "a5": axis_a5_budget,
    "a7": axis_a7_driving,
}

LIMITS = json.loads((cards.CONTRACTS / "validation_limits.json").read_text())
CAPABILITIES = cards.CONTRACTS / "capabilities" / "simulation.json"
OBSERVABLES = cards.CONTRACTS / "observables.json"

# The store, read directly. 4.3.0 is explicit that this is allowed and does not
# go away: an agent reads the entry files and cites `kb:<entry_id>`, and direct
# reading survives the MCP server being down. It is the one part of another
# agent's directory this session may open (6.2 rule 3).
KB_INDEX = cards.REPO / "librarian_agent" / "kb" / "index.json"


class Refusal(Exception):
    """Screening ends the question here rather than producing a plan (P5)."""


class AskFirst(Exception):
    """Screening stops and puts one question to a person (4.5.1 c)."""


def screen(observable: str) -> list[str]:
    """Configurations declared to produce this observable (S3.0).

    Deterministic, and it reads the capability table only. `status:
    provisional` there does not mean "not listed is impossible": an observable
    nobody has declared comes back as name-it-first, never as a refusal.
    """
    table = json.loads(CAPABILITIES.read_text())
    kept = [c["config"] for c in table["configurations"] if observable in (c.get("produces") or [])]

    if not kept:
        declared = sorted({o for c in table["configurations"] for o in (c.get("produces") or [])})
        vocabulary = {o["id"] for o in json.loads(OBSERVABLES.read_text())["observables"]}
        # Two different answers, and 11-1 turns on the difference. An unnamed
        # observable comes back as name-it-first; a named one nothing here
        # produces is a statement about this side's capability table.
        if observable not in vocabulary:
            raise AskFirst(
                f"{observable!r} is not in contracts/observables.json, so it has no definition, "
                "no estimator and no units yet. The answer is to name it -- an entry is added "
                "when a question needs one -- not to screen against a name nobody has defined."
            )
        raise Refusal(
            f"{observable!r} is in the vocabulary but no configuration on this side declares it: "
            f"the table produces {declared}. Declaring a producer is a write to contracts/, which "
            "this session cannot make (6.2), and choosing a different observable would answer a "
            "different question."
        )
    cap = LIMITS["max_configs_after_screening"]
    if len(kept) > cap:
        raise AskFirst(
            f"{len(kept)} configurations produce {observable!r} and the cap is {cap}. The "
            "discriminators available here decide nothing between them, and cutting one without "
            "grounds makes it permanently unattempted (P16). Which to examine is a question for "
            f"whoever knows the purpose: {kept}"
        )
    return kept


def issue(qid: str, config: str, axis: str) -> str:
    """The one place an id is composed (4.3.1 rule 3)."""
    return f"{qid}:{config}:{axis}"


def current_kb_version() -> str:
    """The store state the siblings will all cite.

    `axis.schema.json` says kb_version is "pinned by S3.0; every sibling cites
    the same one (check 33)", so it is read once here rather than written into
    each axis module -- a constant copied six times goes stale six times, and
    the store's version changes whenever an entry does.

    Pinning is a record of what was read, not a subscription to the latest. A
    card written against an older store stays honestly stale, and check 25
    reports that rather than passing it.
    """
    if not KB_INDEX.exists():
        raise Refusal(
            f"{KB_INDEX.relative_to(cards.REPO)} does not exist, so there is no store state to "
            "pin. Every axis card has to cite one (check 33)."
        )
    return json.loads(KB_INDEX.read_text())["kb_version"]


def run(qid: str, created_at: str) -> dict[str, list[str]]:
    """Screen, then fan out one sub-agent per (configuration, axis)."""
    goal = cards.load_goal(qid)
    configs = screen(goal["observable"]["name"])

    planned = len(configs) * len(AXIS_MODULES)
    if planned > LIMITS["max_subagents_per_question"]:
        raise AskFirst(
            f"{len(configs)} configurations x {len(AXIS_MODULES)} axes is {planned} sub-agents, "
            f"over the cap of {LIMITS['max_subagents_per_question']}"
        )

    kb_version = current_kb_version()
    written: dict[str, list[str]] = {}
    for config in configs:
        for axis, module in AXIS_MODULES.items():
            caller_id = issue(qid, config, axis)
            card = module.build(qid, config, created_at, caller_id, kb_version)
            path = cards.write(
                cards.question_dir(qid) / f"axis_{config}_{axis}.json", card
            )
            written.setdefault(config, []).append(path.name)
    return written


if __name__ == "__main__":
    qid = sys.argv[1] if len(sys.argv) > 1 else "sim-20260917-001"
    created_at = sys.argv[2] if len(sys.argv) > 2 else "2026-09-18T10:00:00Z"
    try:
        for config, files in run(qid, created_at).items():
            print(f"{config}: {len(files)} axis cards")
            for name in files:
                print(f"  {name}")
    except Refusal as exc:
        print(f"REFUSED: {exc}")
        raise SystemExit(4)
    except AskFirst as exc:
        print(f"ASK FIRST: {exc}")
        raise SystemExit(5)
