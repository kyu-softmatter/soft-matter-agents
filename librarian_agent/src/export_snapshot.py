#!/usr/bin/env python3
"""Publish the store as a snapshot each execution agent copies into its envelope.

Why a copy exists at all is P0 rule 2, fail-closed: **a safety judgement must
not depend on a live server call** (4.3.2). Preflight needs the device registry
and the calibrations every time it runs, and "the librarian was up" is not an
acceptable precondition for deciding whether a move is allowed.

Why it is published rather than written: this session cannot write into another
agent's directory (D11, 6.2). So the librarian publishes to
`kb/exports/snapshot_<agent>.json` and each agent copies it into its own
`envelope/snapshot.json`. That the copy passes through the other session's hand
is the point, not a cost -- when an agent took which KB version into its
envelope ends up in that agent's own commit.

Two copies cannot drift into two values, because both carry entry hashes and
the validator compares them against the store (check 26).

## What goes in, and the one judgement made here

Everything. The same entry set goes to every agent, because selecting a subset
needs a relevance judgement nothing in an entry supports -- there is no field
saying which agent an entry is for -- and a subset missing an entry fails in
the worst direction: the consumer does not find a value, falls back to an
assumption, and records an E5 where an E3 was sitting in the store.

The per-agent difference is only the two instrument tables. 4.3.2 names the
device registry and the valid optical-path table as knowledge that belongs in
the snapshot, and they go to the agent that has the instrument they describe.
A simulation of Brownian motion does not need a COM port map.

## Raw text, not parsed objects, and the hash is why

Each entry is embedded as the **bytes of its file** plus the sha256 of those
bytes -- the same digest `kb/index.json` records, so the two agree by
construction. A parsed copy would need its own canonical form and its own
hash, and then one entry would have two digests that can disagree; worse, a
copy sitting in an agent's envelope could not be checked at all without
reaching back to the original file. Embedded text is self-verifying: hash what
is there and compare it with what is claimed.

`load()` is provided so no consumer hand-rolls that.

## No timestamp

Nothing here records when it was published, deliberately. A timestamp would
make the output differ on every run, and `--check` -- the thing that catches a
stale export -- would report staleness that is only the clock. The commit
carries the date.

    python3 librarian_agent/src/export_snapshot.py            # publish
    python3 librarian_agent/src/export_snapshot.py --check    # fail if stale
    python3 librarian_agent/src/export_snapshot.py --verify <file>
    python3 librarian_agent/src/export_snapshot.py --self-test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb_index                                             # noqa: E402

AGENT = Path(__file__).resolve().parent.parent
KB = AGENT / "kb"
EXPORTS = KB / "exports"

# 4.3.2 names these two as knowledge that belongs in the snapshot. They live in
# staging until they are decomposed; exporting changes where they are read,
# not who owns them.
TABLES = {"devices": "staging/devices.v0.json",
          "optical_paths": "staging/optical_paths.v0.json"}

# What each table answers to, and where each name came from. A table needs this
# for the reason an entry needed `subject`: the store could not say where a
# thing lives, so it said the thing did not exist. On 2026-09-19 five of seven
# kb_query calls came back `absent` and every one of the five named something
# published here.
#
# Only three sources of name are admitted -- the table's own key, the term the
# design uses, and a word a caller actually typed. No invented plurals or
# variants: guessing at variants is the same move as normalising whitespace,
# and each guess makes two different strings answer to one name.
TABLE_NAMES = {
    "devices": {
        "devices": "the table's own key",
        "device_registry": "4.3.2 calls it the device registry; asked for on 2026-09-19",
        "control_channel": "4.6 calls each row a control channel; asked for on 2026-09-19",
    },
    "optical_paths": {
        "optical_paths": "the table's own key",
        "optical_path_valid_tuples": "4.5.3 requires a combination to be a valid tuple of the "
                                     "optical path table; asked for on 2026-09-19",
    },
}


# Which lists in each table hold rows a consumer reads. Declared rather than
# discovered: walking every key at every depth gave 164 names including `note`,
# `status` and `what`, and a query for `note` answered "it is in the device
# table" -- true, useless, and the shape of a report people stop reading. These
# are the lists the tables' own `consumers` block names: A4 and S3.0 screen
# configurations, the orchestrator compiles channels into locks, O1 preflight
# reads elements.
TABLE_ROWS = {"devices": ("channels", "elements"),
              "optical_paths": ("configurations",)}


def table_columns(table: dict, row_lists: tuple[str, ...]) -> list[str]:
    """The keys of the rows a consumer reads, and nothing else.

    `read_back` and `automatable_condition` are both keys of a `channels` row,
    and both were asked for and answered `absent`.
    """
    names: set[str] = set()

    def walk(node, inside: bool):
        if isinstance(node, dict):
            if inside:
                names.update(k for k in node if isinstance(k, str))
            for k, v in node.items():
                walk(v, inside or k in row_lists)
        elif isinstance(node, list):
            for v in node:
                walk(v, inside)

    walk(table, False)
    return sorted(names)

# Which agents get the instrument tables, and which get entries only.
AGENTS = {"microscope_agent": True, "simulation_agent": False, "bridge": False}

SNAPSHOT_VERSION = "0.1"


class Stale(Exception):
    """The published snapshot no longer matches the store."""


REPO = AGENT.parent
INPUTS = ["librarian_agent/kb/index.json", "librarian_agent/kb/entries",
          "librarian_agent/kb/staging"]


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, check=True).stdout


def built_from_commit() -> str:
    """The commit whose content this snapshot publishes.

    Required, and requiring it is what closes a hole that discipline was
    holding shut. A consumer that pins `kb_version` still could not pin a
    snapshot: three snapshots inside ten minutes on 2026-09-19 all claimed
    kbv-67f9ad766d92 with identical entry text and identical entry hashes,
    because what moved was the export's own structure, not the knowledge.
    That is correct by design -- a version identifies knowledge, not its
    packaging -- and it left nothing saying which packaging came from where.
    A `published_in.sha256` then pointed at bytes that were in no commit.

    Naming the commit makes publishing from a dirty tree impossible rather
    than merely discouraged: there is no commit to name. Same argument as
    making `published_in` conditionally required -- a field nobody must fill
    is a field nobody fills.

    Only the snapshot's own inputs have to be clean. Six seats commit here
    hourly and blocking on somebody else's unrelated edit would make this
    refuse correct work, which is how a gate gets bypassed.
    """
    dirty = [line[3:] for line in _git("status", "--porcelain", "--", *INPUTS).splitlines()
             if line.strip()]
    if dirty:
        raise Stale(
            "refusing to publish from an uncommitted store: " + ", ".join(sorted(dirty)) +
            ". The snapshot would name a commit whose content is not what it carries, and its "
            "sha256 would point at bytes nothing can read back. Commit the store, then publish."
        )
    return _git("rev-parse", "HEAD").strip()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build(agent: str) -> dict:
    """The snapshot for one agent. Deterministic: same store, same bytes."""
    if agent not in AGENTS:
        raise ValueError(f"{agent!r} is not an agent this store publishes to: {sorted(AGENTS)}")
    index = json.loads((KB / "index.json").read_text())

    entries = {}
    for p in sorted((KB / "entries").glob("*.json")):
        text = p.read_text()
        eid = json.loads(text)["entry_id"]
        entries[eid] = {"text": text, "sha256": _digest(text)}

    stored = {k: v.get("sha256") for k, v in (index.get("entries") or {}).items()}
    disagree = sorted(e for e in entries if stored.get(e) != entries[e]["sha256"])
    if disagree or set(stored) != set(entries):
        raise Stale(f"kb/index.json does not match entries/ ({disagree or 'set differs'}); "
                    "rebuild it with src/kb_index.py before publishing")

    body = {
        "snapshot_version": SNAPSHOT_VERSION,
        "agent": agent,
        "kb_version": index["kb_version"],
        "built_from_commit": built_from_commit(),
        "entry_count": len(entries),
        "entries": entries,
        "tables": {},
        "not_included": [],
    }
    if AGENTS[agent]:
        for name, rel in TABLES.items():
            text = (KB / rel).read_text()
            body["tables"][name] = {
                "text": text,
                "sha256": _digest(text),
                "from": f"kb/{rel}",
                "names": TABLE_NAMES.get(name, {name: "the table's own key"}),
                "columns": table_columns(json.loads(text), TABLE_ROWS.get(name, ())),
            }
    else:
        body["not_included"] = [
            f"{n} -- this agent has no instrument for it to describe (4.3.2)" for n in sorted(TABLES)
        ]

    # Every name the store answers to, so discovery does not require guessing
    # it. On 2026-09-19 the service answered `absent` to `numerical_aperture`
    # while six entries carried a number called `na`, and to `objective` while
    # eight answered to `nosepiece`. Neither is missing knowledge and neither
    # is a published table -- the store simply had a different word, and a
    # caller had no way to see which words exist.
    #
    # The list rather than synonyms, deliberately. Teaching the server that
    # `numerical_aperture` means `na` is inventing a namespace: it needs a
    # rule for what may be a synonym of what, and the guesses that rule
    # licenses are the same move as normalising whitespace. Publishing what
    # the store does answer to invents nothing, and the snapshot already
    # carried every one of these names inside the entries -- each consumer
    # would otherwise re-derive the same list.
    index: dict[str, list[str]] = {}
    for eid, text in ((k, v["text"]) for k, v in entries.items()):
        for name, origin in kb_index.handles(json.loads(text)):
            index.setdefault(name, [])
            if origin not in index[name]:
                index[name].append(origin)
    body["handles"] = {
        "note": "every name kb_query and kb_get answer to at this kb_version, with where each "
                "comes from. Matching folds case and nothing else, so a name not here does not "
                "answer -- there are no synonyms, and asking for one gets `absent` even when the "
                "store holds the fact under another word.",
        "names": {k: sorted(v) for k, v in sorted(index.items())},
    }

    body["how_to_verify"] = (
        "sha256 of each entry's `text` must equal its `sha256`, and sha256 over the canonical "
        "JSON of this object without `snapshot_hash` must equal `snapshot_hash`. A hand-edited "
        "copy fails both. `built_from_commit` names the commit this was built from, so every "
        "byte here is readable back with `git show <commit>:<path>` -- a kb_version identifies "
        "the knowledge and this identifies the packaging. Do not edit a copy: fix the KB and "
        "re-export (4.3.2)."
    )
    body["snapshot_hash"] = _digest(_canonical(body))
    return body


def load(snapshot: dict) -> dict:
    """Parse the embedded texts. Consumers call this instead of hand-rolling it."""
    return {
        "kb_version": snapshot["kb_version"],
        "entries": {eid: json.loads(e["text"]) for eid, e in snapshot["entries"].items()},
        "tables": {n: json.loads(t["text"]) for n, t in (snapshot.get("tables") or {}).items()},
    }


def verify(snapshot: dict) -> list[str]:
    """Check a copy on its own terms. Empty means it is intact."""
    problems: list[str] = []
    claimed = snapshot.get("snapshot_hash")
    body = {k: v for k, v in snapshot.items() if k != "snapshot_hash"}
    if _digest(_canonical(body)) != claimed:
        problems.append("snapshot_hash does not cover this content: the copy was edited, or it "
                        "was written by something that does not build it the same way")
    for eid, e in (snapshot.get("entries") or {}).items():
        if _digest(e.get("text", "")) != e.get("sha256"):
            problems.append(f"entry {eid}: the embedded text does not hash to the recorded sha256")
        try:
            if json.loads(e["text"])["entry_id"] != eid:
                problems.append(f"entry {eid}: the embedded entry calls itself something else")
        except (json.JSONDecodeError, KeyError):
            problems.append(f"entry {eid}: the embedded text is not a readable entry")
    for name, t in (snapshot.get("tables") or {}).items():
        if _digest(t.get("text", "")) != t.get("sha256"):
            problems.append(f"table {name}: the embedded text does not hash to the recorded sha256")
    return problems


def publish() -> list[Path]:
    EXPORTS.mkdir(parents=True, exist_ok=True)
    written = []
    for agent in sorted(AGENTS):
        target = EXPORTS / f"snapshot_{agent}.json"
        target.write_text(json.dumps(build(agent), indent=2, ensure_ascii=False) + "\n")
        written.append(target)
    return written


def check() -> list[str]:
    """Has the KNOWLEDGE moved since this was published?

    Not "was it built at the current HEAD". Every commit by any of six seats
    moves HEAD, and rebuilding to compare made every snapshot read as stale
    the moment anybody committed anything -- including commits that touched
    no entry and no table. A staleness report that fires on normal activity
    is one people stop reading, which is the same failure as not having it,
    and it had already cost one broken command chain.

    So `built_from_commit` is held constant for the comparison and the rest
    of the content is compared. A snapshot built two hours and forty commits
    ago is current if the entries and tables it carries are the ones the store
    has now. What is checked about the commit instead is that it still exists.
    """
    problems = []
    for agent in sorted(AGENTS):
        target = EXPORTS / f"snapshot_{agent}.json"
        if not target.exists():
            problems.append(f"{target.name} has not been published")
            continue
        published = json.loads(target.read_text())
        body = build(agent)
        body["built_from_commit"] = published.get("built_from_commit")
        body.pop("snapshot_hash")
        body["snapshot_hash"] = _digest(_canonical(body))
        if json.dumps(body, indent=2, ensure_ascii=False) + "\n" != target.read_text():
            differing = sorted(k for k in set(body) | set(published)
                               if body.get(k) != published.get(k))
            problems.append(f"{target.name} is stale: {differing} differ from the store "
                            f"(published at {published.get('kb_version')}, store at "
                            f"{body.get('kb_version')})")
            continue
        commit = published.get("built_from_commit")
        try:
            _git("cat-file", "-e", f"{commit}^{{commit}}")
        except (OSError, subprocess.CalledProcessError):
            problems.append(f"{target.name} names built_from_commit {commit}, which this "
                            "repository does not have -- nothing can read its bytes back")
    return problems


def _self_test() -> int:
    ok = True

    def bad(why: str) -> None:
        nonlocal ok
        print(f"FAIL: {why}")
        ok = False

    mic = build("microscope_agent")
    sim = build("simulation_agent")

    if verify(mic) or verify(sim):
        bad(f"a freshly built snapshot did not verify: {verify(mic) or verify(sim)}")
    if build("microscope_agent") != mic:
        bad("two builds of one store differ; the export is not deterministic")
    if set(mic["tables"]) != set(TABLES) or sim["tables"]:
        bad(f"the instrument tables went to the wrong agents: {sorted(mic['tables'])}, {sorted(sim['tables'])}")
    if not sim["not_included"]:
        bad("an agent that does not get the tables should be told which ones and why")
    if mic["entries"].keys() != sim["entries"].keys():
        bad("the entry set differs between agents; selecting a subset needs a basis no entry carries")

    # the hash has to catch an edit, which is the only reason it is there
    tampered = json.loads(json.dumps(mic))
    eid = sorted(tampered["entries"])[0]
    tampered["entries"][eid]["text"] = tampered["entries"][eid]["text"].replace('"E3"', '"E1"', 1)
    found = verify(tampered)
    if not any("does not hash" in p for p in found):
        bad(f"an edited entry passed verification: {found}")

    relabelled = json.loads(json.dumps(mic))
    relabelled["kb_version"] = "kbv-000000000000"
    if not any("snapshot_hash" in p for p in verify(relabelled)):
        bad("a copy claiming a different kb_version passed verification")

    # the embedded text must parse back to what the store holds
    loaded = load(mic)
    live = {p.stem: json.loads(p.read_text()) for p in (KB / "entries").glob("*.json")}
    if {e["entry_id"] for e in loaded["entries"].values()} != set(live):
        bad("load() did not round-trip the store")
    if loaded["tables"]["devices"]["schema_version"] != "0.1-provisional":
        bad("the device table did not survive the round trip")

    try:
        build("envelope")
        bad("published to something that is not an agent")
    except ValueError:
        pass

    print("self-test: ok" if ok else "self-test: FAILED")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if a published snapshot is stale")
    ap.add_argument("--verify", type=Path, help="verify a snapshot file on its own terms")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return _self_test()
    if args.verify:
        problems = verify(json.loads(args.verify.read_text()))
        for p in problems:
            print(p)
        print(f"{args.verify}: {'intact' if not problems else str(len(problems)) + ' problems'}")
        return 1 if problems else 0
    if args.check:
        problems = check()
        for p in problems:
            print(p)
        print("exports are current" if not problems else "exports are stale")
        return 1 if problems else 0
    for t in publish():
        snap = json.loads(t.read_text())
        print(f"wrote {t.name}: {snap['kb_version']}, {snap['entry_count']} entries, "
              f"{len(snap['tables'])} tables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
