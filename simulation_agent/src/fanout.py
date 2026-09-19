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


def current_kb_version(qid: str | None = None) -> str:
    """The store state this question cites -- pinned once, then kept.

    `axis.schema.json` says kb_version is "pinned by S3.0; every sibling cites
    the same one (check 33)". Read once per *question*, not once per run: the
    store moves within minutes while an agent is working -- three versions
    passed in one afternoon -- so re-reading it on every regeneration turns the
    pin from a record of what was read into a record of the last time someone
    happened to re-run the fan-out.

    So if this question's goal card already cites a version, that is the pin.
    It is what S2 actually read, and rewriting it would claim a reading that
    never happened. Only a question with nothing pinned yet takes the store's
    current state.

    A card left behind by a moving store is honestly stale, and check 25 says
    so as PENDING -- confirming an older version needs the store's git history.
    That report is correct and is not something to chase away.
    """
    if qid is not None:
        pinned = {
            ref["kb_version"]
            for ref in (cards.load_goal(qid).get("kb_refs") or [])
            if ref.get("kb_version")
        }
        if len(pinned) == 1:
            return pinned.pop()
        if len(pinned) > 1:
            raise Refusal(
                f"the goal of {qid} cites {sorted(pinned)}; S3.0 pins one store state and every "
                "sibling cites it (check 33)"
            )
    if not KB_INDEX.exists():
        raise Refusal(
            f"{KB_INDEX.relative_to(cards.REPO)} does not exist, so there is no store state to "
            "pin. Every axis card has to cite one (check 33)."
        )
    return json.loads(KB_INDEX.read_text())["kb_version"]


def plan_queries(qid: str) -> list[dict]:
    """The librarian calls this question needs, one per issuing caller_id.

    Derived from the goal and the axis set, so the list is the same every time
    and nothing is composed by whoever happens to run it. Each entry is the
    tool name and its arguments exactly as 4.3.1 declares them -- the session
    makes the calls, because an MCP tool is the model's to invoke and not
    Python's, and hands the answers back to `run` keyed by caller_id.

    Two shapes appear, for the reason 11-5 settled: a dimensionless group is
    found **by symbol**, and a condition range is not a query term for it. So
    A1 and A4 want `kb_group`, while A3 wants `kb_query` -- whether a measured
    diffusivity exists for these conditions at all, which is the gap this
    question currently records by hand.
    """
    goal = cards.load_goal(qid)
    nums = {n["name"]: n for n in goal["numbers"]}
    observable = goal["observable"]["name"]
    kb_version = current_kb_version(qid)
    out: list[dict] = []
    for config in screen(observable):
        for axis in ("a1", "a4"):
            out.append({
                "tool": "kb_group",
                "caller_id": issue(qid, config, axis),
                "args": {"kb_version": kb_version, "symbol": "tau_d"},
                "why": "the diffusive time is cited, not re-derived; check 36 compares the definition",
            })
        out.append({
            "tool": "kb_query",
            "caller_id": issue(qid, config, "a3"),
            "args": {
                "kb_version": kb_version,
                "observable": observable,
                "condition_range": {
                    "temperature": {
                        "min": nums["temperature"]["value"],
                        "max": nums["temperature"]["value"],
                        "unit": nums["temperature"]["unit"],
                    },
                    "bead_diameter": {
                        "min": nums["bead_diameter"]["value"],
                        "max": nums["bead_diameter"]["value"],
                        "unit": nums["bead_diameter"]["unit"],
                    },
                },
                "purpose": goal["purpose"],
            },
            "why": "is there a measured diffusivity for these conditions, or is the expectation standing on an absence",
        })
    return out


def run(qid: str, created_at: str, kb_results: dict[str, dict] | None = None) -> dict[str, list[str]]:
    """Screen, then fan out one sub-agent per (configuration, axis).

    `kb_results` is keyed by caller_id and comes from the session having made
    the calls in `plan_queries`. An axis with no entry is told so, and writes
    `degraded: ["librarian_agent"]` -- which is the honest card while the
    service is unreachable. Passing a result that cannot name its server counts
    as no result: see `cards.evidence`.
    """
    goal = cards.load_goal(qid)
    configs = screen(goal["observable"]["name"])

    planned = len(configs) * len(AXIS_MODULES)
    if planned > LIMITS["max_subagents_per_question"]:
        raise AskFirst(
            f"{len(configs)} configurations x {len(AXIS_MODULES)} axes is {planned} sub-agents, "
            f"over the cap of {LIMITS['max_subagents_per_question']}"
        )

    kb_version = current_kb_version(qid)
    # The derived cards belong to the revision of the question they were
    # derived from. Leaving them at 1 while the goal moved on produced a plan
    # that claimed revision 1 and was built from revision 6.
    revision = cards.question_revision(qid)
    written: dict[str, list[str]] = {}
    for config in configs:
        for axis, module in AXIS_MODULES.items():
            caller_id = issue(qid, config, axis)
            card = module.build(qid, config, created_at, caller_id, kb_version,
                                (kb_results or {}).get(caller_id), revision)
            target = cards.question_dir(qid) / cards.artifact_name(
                f"axis_{config}_{axis}.json", revision
            )
            cards.refuse_overwrite(target, revision)
            written.setdefault(config, []).append(cards.write(target, card).name)
    return written


if __name__ == "__main__":
    qid = sys.argv[1] if len(sys.argv) > 1 else "sim-20260917-001"
    created_at = sys.argv[2] if len(sys.argv) > 2 else "2026-09-18T10:00:00Z"
    if len(sys.argv) > 3 and sys.argv[3] == "--queries":
        for q in plan_queries(qid):
            print(f"{q['tool']}(caller_id={q['caller_id']!r}, **{q['args']})")
            print(f"    why: {q['why']}")
        raise SystemExit(0)
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
