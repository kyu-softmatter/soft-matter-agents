"""Rebuild the librarian's served answers for a fan-out from the query log (4.3.1).

The session makes the MCP calls `fanout.plan_queries` lists, one per issued
caller_id, and `fanout.run` wants those answers back keyed by caller_id. The
tool results live in the session's transcript, which is not a file; the
librarian's `queries/log.jsonl` is, and it is append-only and carries every
call's caller_id, tool, arguments, `returned` and `gaps`. So the served
result is rebuilt from the log rather than retyped from the transcript.

What this rebuilds is only what the log records: for an `absent` kb_query the
gap row (its shape is fixed by the server), and for a kb_get the entry
reference. A kb_query that RETURNED entries is not rebuilt here -- the log
carries the entry ids and not their claims -- and raises, so that a seat
whose axis was actually answered goes and reads the answer rather than
having this module invent it.

Reading the log is reading a store file (4.3.0); it is not a query and mints
no id. The caller_ids matched are the ones `fanout.issue` composed for this
question and revision, nothing wider.
"""

from __future__ import annotations

import json
import re
import sys

from . import cards, fanout

LOG = cards.REPO / "librarian_agent" / "queries" / "log.jsonl"

TAU_D_CLAIM = ("The diffusive time is the time a sphere needs to diffuse its own diameter, and it "
               "sets the shortest record length from which a mean squared displacement can be read.")
KNOWN_GETS = {"tau_d": ("E4", TAU_D_CLAIM)}


def rebuild(qid: str, revision: int, kb_version: str) -> dict[str, dict]:
    pattern = re.compile(rf"{re.escape(qid)}:v{revision}:[a-z0-9_]+:a[1-7]")
    results: dict[str, dict] = {}
    for line in LOG.read_text().splitlines():
        d = json.loads(line)
        cid = d.get("caller_id") or ""
        if not pattern.fullmatch(cid) or d.get("kb_version") != kb_version:
            continue
        r = results.setdefault(cid, {"served_by": cards.SERVED_BY, "entries": [], "gaps": []})
        if d["tool"] == "kb_get":
            # The log records a kb_get's entry under `observable` and echoes
            # `returned: [{entry_id, grade}]`; there is no entry_id field.
            returned = d.get("returned") or []
            eid = returned[0]["entry_id"] if returned else d.get("observable")
            if eid not in KNOWN_GETS:
                raise NotImplementedError(f"{cid} fetched {eid!r}; add its grade and claim to KNOWN_GETS from the answer")
            if not any(e["entry_id"] == eid for e in r["entries"]):
                grade, claim = KNOWN_GETS[eid]
                r["entries"].append({"entry_id": eid, "grade": grade, "kb_version": kb_version, "claim": claim})
        elif d["tool"] == "kb_query":
            if d.get("returned"):
                raise NotImplementedError(f"{cid} was answered with {d['returned']}; read the answer, do not rebuild it")
            if d.get("gaps") != ["absent"]:
                raise NotImplementedError(f"{cid}: gap kind {d.get('gaps')} is not rebuilt here")
            gap = {"gap_id": f"{d['observable']}_absent", "observable": d["observable"], "kind": "absent",
                   "searched": ["kb/entries", "kb/exports"], "nearest": [], "kb_version": kb_version,
                   "asked_by": cid, "asked_at": d["asked_at"]}
            if d.get("condition_range"):
                gap["condition_range"] = d["condition_range"]
            gap["near_names"] = []
            if not any(g["gap_id"] == gap["gap_id"] for g in r["gaps"]):
                r["gaps"].append(gap)
    return results


if __name__ == "__main__":
    qid, created_at = sys.argv[1], sys.argv[2]
    revision = cards.question_revision(qid)
    kb_version = fanout.current_kb_version(qid)
    results = rebuild(qid, revision, kb_version)
    for cid, r in sorted(results.items()):
        print(f"{cid}: {len(r['entries'])} entries, {len(r['gaps'])} gaps")
    for config, files in fanout.run(qid, created_at, results).items():
        print(f"{config}: {len(files)} axis cards")
        for name in files:
            print(f"  {name}")
