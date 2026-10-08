#!/usr/bin/env python3
"""The bridge's board: what has crossed, whose turn it is, and what is waiting
on a person's hand-over (plan.md 4.4).

    python3 contracts/bridge_board.py

It reads and prints, and writes nothing. The cards stay where their authors
put them -- the agents' `questions/`, the bridge's `threads/` -- and the board
is built from them each time it runs. Nothing is collected into the bridge
first: a copy of a result is a second place for one card, and a stale board
file is the drift that had the example round saying the human's turn for a
day after the round had opened. So there is no board file to commit, and the
board cannot go stale, because it is never stored.

It decides nothing. "Waiting on your hand-over" means a result exists and
has not crossed. It does not mean the result should cross: a result crosses
only when a person says so, and the board is there so the person can see
what there is to say it about. Operation plans -- a focus search with no goal,
a trap placed and confirmed, a piezo step -- verify a setup and ask nothing
of the other side, so they are counted and never offered.

The reader is the person, so what it prints carries file paths and dates and
none of plan.md's section or check numbers.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import (REPO, collect, describe_tree, is_operation_plan,  # noqa: E402
                      without_revision_marks)

SIDES = {"microscope_agent": "microscope", "simulation_agent": "simulation"}
OTHER = {"microscope_agent": "simulation", "simulation_agent": "microscope"}
FINISHED_PLAN = {"VALIDATED", "APPROVED", "RUNNING", "DONE"}
TURN = {"microscope_agent": "the microscope's", "simulation_agent": "the simulation's",
        "human": "yours", "bridge": "the bridge's"}


def side_of(rel: str) -> str | None:
    top = rel.split("/", 1)[0]
    return top if top in SIDES and "/questions/" in rel else None


def ident(card: dict) -> str:
    return without_revision_marks(str(card.get("id") or ""))


def build():
    b = collect([REPO])
    rounds = [c for c in b.of_kind("ask_simulation", "ask_experiment")
              if c.rel.startswith("bridge/threads/")]
    delivered = {(c.rel.split("/inbox/")[0], str(c.data.get("thread")), c.data.get("round"))
                 for c in b.of_kind("ask_simulation", "ask_experiment") if "/inbox/" in c.rel}
    statuses = {str(s.data.get("thread")): s.data for s in b.of_artifact("thread_status")
                if s.rel.startswith("bridge/threads/")}

    crossed: dict[str, list] = defaultdict(list)       # card identity -> rounds it went in
    for c in rounds:
        p = c.data.get("payload_card") or {}
        crossed[ident(p)].append((str(c.data.get("thread")), c.data.get("round"), p.get("revision") or 1))

    latest: dict[str, tuple] = {}                       # card identity -> (revision, rel)
    by_q: dict[tuple, list] = defaultdict(list)          # (side, qid) -> cards
    taken: dict[str, list] = defaultdict(list)           # "thr:rN" -> rels standing on it
    for c in b.cards:
        side = side_of(c.rel)
        if not side or "__unreadable__" in c.data:
            continue
        by_q[(side, str(c.data.get("qid")))].append(c)
        i = ident(c.data)
        rev = c.data.get("revision") or 1
        if i and (i not in latest or rev > latest[i][0]):
            latest[i] = (rev, c.rel)
        if c.data.get("from_round"):
            taken[str(c.data["from_round"])].append(c.rel)
    return rounds, delivered, statuses, crossed, latest, by_q, taken


def main() -> int:
    rounds, delivered, statuses, crossed, latest, by_q, taken = build()
    out: list[str] = ["# The bridge's board", ""]

    # -- threads -------------------------------------------------------------
    out += ["## Threads", ""]
    by_thread: dict[str, list] = defaultdict(list)
    for c in rounds:
        by_thread[str(c.data.get("thread"))].append(c)
    if not by_thread:
        out += ["Nothing has crossed yet.", ""]
    for thread in sorted(by_thread, key=lambda t: (statuses.get(t) or {}).get("updated_at") or "", reverse=True):
        st = statuses.get(thread) or {}
        last = max(by_thread[thread], key=lambda c: c.data.get("round") or 0)
        rnd = last.data.get("round")
        p = last.data.get("payload_card") or {}
        frm = SIDES.get(str(p.get("author")), p.get("author"))
        to = "simulation" if last.kind == "ask_simulation" else "microscope"
        receiver = f"{to}_agent" if to == "simulation" else "microscope_agent"
        line = (f"- **{thread}**, round {rnd}: {frm}'s {p.get('card')} `{p.get('id')}` went to the {to}. "
                f"Turn: {TURN.get(str(st.get('turn')), st.get('turn') or 'not recorded')}"
                f"{', held' if st.get('state') == 'held' else ''}"
                f"{', escalated to you' if st.get('state') == 'escalated' else ''}"
                f"{', closed' if st.get('state') == 'closed' else ''}.")
        out.append(line)
        if (receiver, thread, rnd) not in delivered:
            out.append(f"  - Not delivered: nothing is in `{receiver}/inbox/{thread}/`.")
        takers = taken.get(f"{thread}:r{rnd}", [])
        if takers:
            out.append(f"  - Taken as `{sorted(takers)[0]}`.")
        elif (receiver, thread, rnd) in delivered:
            out.append(f"  - Delivered and not yet taken up by the {to}.")
        rev_now = latest.get(ident(p), (None, None))
        if rev_now[0] and rev_now[0] > (p.get("revision") or 1):
            out.append(f"  - The {frm} has revised this card since it crossed: `{rev_now[1]}` is revision "
                       f"{rev_now[0]}, and the round carries revision {p.get('revision') or 1}.")
        if st.get("state") == "held" and st.get("open_question"):
            out.append(f"  - Waiting on you: {st['open_question']}")
    out.append("")

    # -- results and plans not crossed ----------------------------------------
    for side in SIDES:
        waiting, plans, operations = [], [], 0
        for (s, qid), cards in sorted(by_q.items()):
            if s != side:
                continue
            answers = sorted({str(c.data["from_round"]) for c in cards if c.data.get("from_round")})
            results = [c for c in cards if c.kind == "result" and ident(c.data) not in crossed]
            if results:
                newest = max(results, key=lambda c: c.data.get("created_at") or "")
                waiting.append((newest.data.get("created_at") or "", qid, len(results), newest.rel, answers))
            if not any(c.kind == "result" for c in cards):
                for c in cards:
                    if c.kind != "plan" or c.data.get("status") not in FINISHED_PLAN:
                        continue
                    if is_operation_plan(c.data):
                        operations += 1
                    elif ident(c.data) not in crossed and latest.get(ident(c.data), (0, c.rel))[1] == c.rel:
                        plans.append((c.data.get("created_at") or "", qid, c.rel))

        name = SIDES[side]
        out += [f"## The {name}'s results that have not crossed", ""]
        if not waiting:
            out += ["None.", ""]
        for created, qid, n, rel, answers in sorted(waiting, reverse=True):
            more = f" ({n} result cards; newest shown)" if n > 1 else ""
            out.append(f"- {created[:10]} **{qid}**: `{rel}`{more}")
            if answers:
                out.append(f"  - This answers {', '.join(answers)}, which the {OTHER[side]} sent. It goes "
                           f"back when you hand it over.")
        out += ["", f"## The {name}'s finished plans with no result that have not crossed", ""]
        if not plans:
            out.append("None.")
        for created, qid, rel in sorted(plans, reverse=True):
            out.append(f"- {created[:10]} **{qid}**: `{rel}`")
        if operations:
            out.append(f"\n{operations} operation plans (focus searches with no goal, trap placements, "
                       f"stage checks) are not listed: they set up the instrument and ask nothing of the "
                       f"other side, so they never cross.")
        out.append("")

    out += ["A result crosses only when you hand it over. A plan with a goal may cross when it is "
            "finished.", "", describe_tree()]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
