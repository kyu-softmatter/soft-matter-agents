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

# 4.3.2 names the first two as knowledge that belongs in the snapshot. They
# live in staging until they are decomposed; exporting changes where they are
# read, not who owns them.
#
# `samples` joined them on 2026-09-19 and is not an instrument table, which is
# the whole reason it needed adding rather than inheriting: architecture put it
# beside the device table precisely BECAUSE one sample is used by two agents --
# the simulation models what the microscope images -- and until this commit the
# publisher shipped it to neither.
TABLES = {"devices": "staging/devices.v0.json",
          "optical_paths": "staging/optical_paths.v0.json",
          "samples": "staging/samples.v0.json"}

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
    "samples": {
        "samples": "the table's own key",
        "sample": "the subject kind that resolves against this file and nothing else "
                  "(kb_entry.schema.json, check 44), added 2026-09-19",
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
              "optical_paths": ("configurations",),
              "samples": ("instances",)}


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

# Which tables each agent gets, BY NAME.
#
# This was a boolean per agent until 2026-09-19 -- gets the tables, or gets
# entries only -- and the boolean was not a shorthand, it was the model. Every
# table was an instrument table, every instrument was the microscope's, so one
# bit said everything there was to say. The sample table broke that on the day
# it was created and the publisher could not express the break: architecture's
# stated reason for putting samples beside the device table rather than inside
# the microscope's run records is that ONE SAMPLE IS USED BY TWO AGENTS, and a
# boolean can only offer the simulation all three tables or none. So it got
# none, and the table reached nobody at all for the first hours of its life.
#
# The lesson is not about tables. A field whose two values happen to cover
# every case today reads as a decision and is really an absence of one, and it
# fails the first time a third case appears -- silently, by having nowhere to
# put it. Naming the tables costs one line per agent and can be wrong out loud.
AGENTS = {
    "microscope_agent": ("devices", "optical_paths", "samples"),
    "simulation_agent": ("samples",),
    "bridge": (),
}

# Why an agent does not get a table, per table rather than per agent. The old
# single reason -- "this agent has no instrument for it to describe" -- is true
# of the two instrument tables and false of the sample table, which nobody is
# excluded from for want of an instrument.
TABLE_WITHHELD = {
    "devices": "this agent has no instrument for it to describe (4.3.2)",
    "optical_paths": "this agent has no instrument for it to describe (4.3.2)",
    "samples": "this agent neither images nor models the sample; it carries cards between the "
               "two that do (4.4), and a thread's subject reaches it through the cards",
}

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
    wanted = AGENTS[agent]
    for name in sorted(wanted):
        rel = TABLES[name]
        text = (KB / rel).read_text()
        body["tables"][name] = {
            "text": text,
            "sha256": _digest(text),
            "from": f"kb/{rel}",
            "names": TABLE_NAMES.get(name, {name: "the table's own key"}),
            "columns": table_columns(json.loads(text), TABLE_ROWS.get(name, ())),
        }
    body["not_included"] = [
        f"{n} -- {TABLE_WITHHELD[n]}" for n in sorted(set(TABLES) - set(wanted))
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
    # Each agent gets the tables AGENTS names for it, and is told about the
    # rest. This asserted `sim["tables"]` was empty until 2026-09-19, which was
    # not a stricter version of the same check -- it was the boolean model
    # written down a second time, and it would have REFUSED the sample table
    # reaching the simulation, which is the thing architecture created that
    # table for. A test that encodes the shape of the code rather than the
    # rule the code is for turns into the reason the rule cannot be followed.
    for name, snap in (("microscope_agent", mic), ("simulation_agent", sim)):
        if set(snap["tables"]) != set(AGENTS[name]):
            bad(f"{name} got {sorted(snap['tables'])}, AGENTS says {sorted(AGENTS[name])}")
        withheld = {line.split(" -- ")[0] for line in snap["not_included"]}
        if withheld != set(TABLES) - set(AGENTS[name]):
            bad(f"{name} was told about {sorted(withheld)}, which is not what it was withheld")
    if not sim["not_included"]:
        bad("an agent that does not get every table should be told which ones and why")
    if "samples" not in mic["tables"] or "samples" not in sim["tables"]:
        bad("one sample is used by two agents (016); the sample table has to reach both, "
            "and it reached neither for the first hours it existed")
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

    # envelope_lag, against a built tree rather than against the live one.
    # It has to be exercised on a lag, and the live repository is allowed to
    # have none -- on the day this was written the microscope closed its 34
    # while the code was being written, so a property that waited for a real
    # lag would have passed by having nothing to look at. Same defect as the
    # one this file's table assertion had and as property 8b in mcp_server.py:
    # an invariant that needs an example cannot tell absent from broken.
    import tempfile

    real_repo, real_exports, real_agents = REPO, EXPORTS, AGENTS
    try:
        with tempfile.TemporaryDirectory() as d:
            cases = 0

            def fixture(published, envelope):
                # A fresh subtree per case. Reusing one tree made the
                # missing-envelope case pass by reading the PREVIOUS case's
                # envelope, which is a test that cannot fail for the reason it
                # names -- caught by the case failing when it should not have.
                nonlocal cases
                cases += 1
                root = Path(d) / f"case{cases}"
                exp = root / "exports"
                exp.mkdir(parents=True)
                for a, (kv, n) in published.items():
                    (exp / f"snapshot_{a}.json").write_text(
                        json.dumps({"kb_version": kv, "entry_count": n}))
                for a, body in envelope.items():
                    (root / a / "envelope").mkdir(parents=True, exist_ok=True)
                    (root / a / "envelope" / "snapshot.json").write_text(
                        body if isinstance(body, str) else json.dumps(body))
                globals()["REPO"], globals()["EXPORTS"] = root, exp
                globals()["AGENTS"] = {a: () for a in published}
                return "\n".join(envelope_lag())

            out = fixture({"a": ("kbv-1", 83)}, {"a": {"kb_version": "kbv-1", "entry_count": 83}})
            if not out.strip():
                bad("envelope_lag printed nothing when everything was current; silence and "
                    "clean read the same and one of them is a tool that stopped working")
            if "current with the published export: a" not in out:
                bad(f"a current envelope was not named: {out!r}")

            out = fixture({"a": ("kbv-2", 83)}, {"a": {"kb_version": "kbv-1", "entry_count": 49}})
            if "a: 34 entries behind" not in out:
                bad(f"a lagging envelope was not named with its distance: {out!r}")
            if "only the consuming agent can close this" not in out:
                bad("the report named a gap without saying who can close it, which invites "
                    "the reader to assume the reporter will (018)")

            # kb_version hashes every entry, so an EDIT moves it with no count
            # change. Reporting the delta alone would say "0 entries behind".
            out = fixture({"a": ("kbv-2", 83)}, {"a": {"kb_version": "kbv-1", "entry_count": 83}})
            if "0 entries behind" in out or "same entry count, different content" not in out:
                bad(f"an edited store read as no difference at equal count: {out!r}")

            out = fixture({"a": ("kbv-1", 83)}, {})
            # Matched on the header, not on the word "behind": the correct
            # output for this case CONTAINS "behind", inside "not behind".
            if "not matching the published export" in out or "no envelope yet" not in out:
                bad(f"a missing envelope was reported as a lag rather than as not started: {out!r}")
    finally:
        globals()["REPO"], globals()["EXPORTS"], globals()["AGENTS"] = (
            real_repo, real_exports, real_agents)

    print("self-test: ok" if ok else "self-test: FAILED")
    return 0 if ok else 1


def envelope_lag() -> list[str]:
    """Which consumers have not copied the published export yet. ADVISORY.

    Three things looked at snapshots and none of them looked at this. Check 26
    compares an envelope against the commit it NAMES, which is integrity, and
    it is right to pass an honest envelope of any age. `check()` above compares
    the exports against the store, which is the publisher's end. Nobody
    compared an export against the envelope that copied it, so a microscope
    envelope sat 34 entries behind inside a repository reading `0 failed`, and
    the only reason anyone noticed was a manager opening two files by hand.

    NOT A FINDING, AND NOT SOFTNESS. A stale envelope is not a defect: a
    consumer may pin deliberately, and an agent that has not run today is in
    breach of nothing. Make it fail and the gate reddens whenever a seat is
    idle, which on 2026-09-19 was most of them -- and a gate that reddens for
    correct inaction is one people learn to skip. What was missing is not a
    prohibition, it is a number nobody has to go and compute.

    THIS HALF TELLS THE PUBLISHER, AND THE PUBLISHER CANNOT ACT ON IT. The fix
    for a stale envelope is a re-copy and only the consumer can do that, but
    `--check` is the librarian's tool and the consumer never runs it. The other
    half is a validator check, which every seat does run; it needs a check
    number, the numbers are architecture's, and that seat is not up. So the
    limitation is printed in the output rather than only recorded here: a tool
    that reports a gap without saying who can close it invites the reader to
    assume the reporter will.
    """
    behind, current, absent = [], [], []
    for agent in sorted(AGENTS):
        target = EXPORTS / f"snapshot_{agent}.json"
        if not target.exists():
            continue                      # nothing published, so nothing to lag behind
        env = REPO / agent / "envelope" / "snapshot.json"
        if not env.exists():
            # Not behind -- not started. 4.3.2 leaves copying to each agent,
            # and an agent that has never copied has not fallen behind.
            absent.append(agent)
            continue
        try:
            copy = json.loads(env.read_text())
        except json.JSONDecodeError as exc:
            behind.append(("consumer", f"{agent}: envelope/snapshot.json does not parse ({exc})"))
            continue
        published = json.loads(target.read_text())
        if copy.get("kb_version") == published.get("kb_version"):
            current.append(agent)
            continue
        # kb_version is a hash over every entry, so an EDIT moves it exactly as
        # an addition does. Reporting only a count delta would print "0 behind"
        # for a store that really has changed, which is the same rule this
        # agent's CLAUDE.md already had to learn once about adding versus
        # editing mid-fan-out.
        delta = (published.get("entry_count") or 0) - (copy.get("entry_count") or 0)
        if delta > 0:
            how_far, whose = f"{delta} entries behind", "consumer"
        elif delta < 0:
            # Only reachable when the exports are the stale side, which
            # check() reports above. Kept because the alternative is calling
            # it "behind", and a row that says behind while the number says
            # ahead is the kind of line a reader trusts and should not.
            how_far, whose = (f"{-delta} entries AHEAD of the published export, so the "
                              f"exports are the stale side, not this envelope"), "publisher"
        else:
            how_far, whose = ("same entry count, different content -- entries were edited "
                              "rather than added, and kb_version covers both"), "consumer"
        behind.append((whose, f"{agent}: {how_far} (envelope at {copy.get('kb_version')}, "
                              f"published {published.get('kb_version')})"))

    out = []
    if behind:
        # The header does not say "behind": one of the rows it can carry says
        # the opposite, and a heading that contradicts a row under it is worse
        # than a vague one.
        out.append("envelopes not matching the published export (ADVISORY, not a failure):")
        out += [f"  {line}" for _, line in behind]
        whose = {w for w, _ in behind}
        if "consumer" in whose:
            out.append("  only the consuming agent can close this by re-copying; this tool "
                       "is the publisher's and the consumer does not run it")
        if "publisher" in whose:
            out.append("  the AHEAD rows are the publisher's to close by republishing, "
                       "which is this tool's own end")
    if current:
        # Named whether or not anything is behind, and said out loud when
        # nothing is. Silence and clean read the same, and one of the two is a
        # tool that stopped working -- so an empty report has to be a sentence.
        # Printing these only when the behind-list was empty would also have
        # hidden the more useful reading: which consumers kept up while another
        # did not.
        out.append(f"envelopes current with the published export: {', '.join(current)}")
    if absent:
        out.append(f"no envelope yet, which is not behind: {', '.join(absent)}")
    return out


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
        # Advisory, and deliberately after the verdict line so it cannot be
        # mistaken for part of it. The exit code is the publisher's end only:
        # a consumer being behind is not this tool's failure and must not
        # become one (018).
        for line in envelope_lag():
            print(line)
        return 1 if problems else 0
    for t in publish():
        snap = json.loads(t.read_text())
        print(f"wrote {t.name}: {snap['kb_version']}, {snap['entry_count']} entries, "
              f"{len(snap['tables'])} tables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
