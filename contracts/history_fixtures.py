#!/usr/bin/env python3
"""Fixtures for the checks that read git history (11-7).

`--expect-fail contracts/examples/rejected` proves a check still works by
handing it a card that must be refused. Four checks cannot be reached that
way, because what they read is not a file in a folder but **history** --
26 (an envelope snapshot against the export it names), 35 (a commit's paths
against one boundary), 41 (a commit's paths against its committer's seat),
46 (a vocabulary pin resolving in the commit it names). Until now their only
evidence was a sentence in a commit message, and a check nobody has ever seen
fail is a check nobody has tested.

**The repositories are built, not stored.** 11-7 settled the shape on
2026-09-20: keeping four repositories as fixtures is expensive, and `git init`
plus a handful of commits costs seconds. What is expensive is storage, not
creation -- and if a fixture is expensive the cost of adding one becomes the
cost of adding a check, so checks stop growing.

Each fixture copies `contracts/` into a temporary repository and runs **that**
copy of the validator there, so both the file side and the git side see the
fixture and nothing reaches back into the real tree. It is a directory copy of
about a megabyte and it is why this stays cheap.

Like a group fixture, each one **names the check it is for and the verdict it
expects**, and counting requires that verdict *from that check*. Without the
name a fixture passes on an unrelated failure and stays green after the defect
it was built for is gone, which is the state this whole folder exists to
prevent. Unrelated findings are tolerated for the same reason a group folder
tolerates them: the named check is what is counted.

Not every expectation is a refusal. `seats.json` sets `unknown_committer` to
`report`, so an unregistered committer is deliberately **not** refused -- a
seat that has not adopted an identity is not blocked. What that costs is
written in the registry: an unattributed commit gets no boundary checking at
all, because nothing says whose paths those were. The report is the only thing
between that and silence, so it is worth a fixture, and the fixture asserts a
PENDING rather than pretending the rule is stricter than it is.

    python3 contracts/history_fixtures.py

Every fixture must still fire, with the verdict it names. One that stops
firing means a check stopped working.

All four are covered: 35 and 41 landed first, 26 and 46 followed once the
harness had somewhere to put them.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parent
REPO = CONTRACTS.parent

PERSON = ["-c", "user.name=kyuhwan", "-c", "user.email=kyuchoi@stanford.edu"]


def run(repo: Path, *args: str, seat: str | None = None) -> str:
    """git, with the committer as a seat and the author as the person (6.2.1)."""
    env = dict(os.environ)
    if seat:
        env["GIT_COMMITTER_NAME"] = f"seat:{seat}"
        env["GIT_COMMITTER_EMAIL"] = f"{seat}@seat.invalid"
    out = subprocess.run(["git", "-C", str(repo), *PERSON, *args],
                         capture_output=True, text=True, env=env)
    if out.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {out.stderr.strip()}")
    return out.stdout


def write(repo: Path, rel: str, body) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body if isinstance(body, str) else json.dumps(body, indent=2) + "\n")


def commit(repo: Path, message: str, *paths: str, seat: str) -> str:
    run(repo, "add", "--", *paths)
    run(repo, "commit", "-q", "--no-verify", "-m", message, seat=seat)
    return run(repo, "rev-parse", "HEAD").strip()


def base(repo: Path) -> str:
    """A repository with the registry in it and one commit to hang a range off.

    seats.json is copied rather than invented: a fixture that carries its own
    idea of who owns what would keep passing after the real registry moved,
    which is the failure this file exists to catch one level down.
    """
    run(repo, "init", "-q", "-b", "main")
    shutil.copytree(CONTRACTS, repo / "contracts")
    write(repo, "README.md", "# fixture\n")
    return commit(repo, "base", "contracts", "README.md", seat="architecture")


# --------------------------------------------------------------------------- #
# the fixtures
# --------------------------------------------------------------------------- #

def fixture_35_one_commit_two_boundaries(repo: Path) -> str:
    """One commit writing into two agents at once.

    6.2's boundary is per session, so a single commit touching two agents is
    not a seat doing its job with a wide brush -- it is two sessions' work in
    one commit, or one session that went where it may not. Either way the
    record can no longer say who did what, which is what the boundary is for.
    """
    start = base(repo)
    write(repo, "microscope_agent/questions/q/goal.json", {"card": "goal"})
    write(repo, "simulation_agent/questions/q/goal.json", {"card": "goal"})
    commit(repo, "one commit, two agents",
           "microscope_agent", "simulation_agent", seat="microscope-1")
    return f"{start}..HEAD"


def fixture_41_seat_writes_outside_its_own(repo: Path) -> str:
    """A seat committing a path another boundary owns.

    The committer is the seat (6.2.1), so this is the one thing git records
    that says which session made a change. A microscope seat writing into
    bridge/ is the crossing 6.2 describes, and it is invisible to anything
    that reads only the tree: the file is well-formed and in a legal place.
    """
    start = base(repo)
    write(repo, "bridge/threads/t/status.json", {"artifact": "thread_status"})
    commit(repo, "microscope seat writes into the bridge's tree",
           "bridge", seat="microscope-1")
    return f"{start}..HEAD"


def fixture_41_unregistered_committer(repo: Path) -> str:
    """A commit by an identity seats.json does not list.

    `unknown_committer: report` means this is reported and not refused, so the
    fixture asserts the report happens. An unattributed commit gets no
    boundary checking at all -- nothing says whose paths those were -- so the
    report is the only thing standing between that and silence.
    """
    start = base(repo)
    write(repo, "bridge/threads/t/status.json", {"artifact": "thread_status"})
    commit(repo, "committed by nobody the registry knows",
           "bridge", seat="ghost-seat")
    return f"{start}..HEAD"


def fixture_26_snapshot_is_a_copy_of_another_commit(repo: Path) -> str:
    """An envelope snapshot whose embedded text belongs to a different commit.

    Check 26 can fail nine ways and its own docstring pins which one a fixture
    must be: the line runs between "this is not a copy of anything" -- a bogus
    commit, an absent entry, a missing `built_from_commit` -- and "this IS a
    copy, of something else". Only the second is 4.3.2's divergence, and only
    the second is reachable by accident: the others need a snapshot nobody
    could have produced.

    So this builds the honest mistake. The entry is exported at one commit,
    the store moves, and the snapshot keeps the newer text while still naming
    the older commit -- an export that was real when it was taken and is now a
    copy of something else. Nothing about it looks wrong from inside the file.
    """
    start = base(repo)
    write(repo, "librarian_agent/kb/index.json", {"entries": ["e1"]})
    write(repo, "librarian_agent/kb/entries/e1.json", {"entry_id": "e1", "claim": "as first written"})
    exported_at = commit(repo, "the store as it was exported", "librarian_agent", seat="librarian")

    write(repo, "librarian_agent/kb/entries/e1.json", {"entry_id": "e1", "claim": "after the store moved"})
    commit(repo, "the store moves on", "librarian_agent", seat="librarian")

    newer = (repo / "librarian_agent/kb/entries/e1.json").read_text()
    write(repo, "microscope_agent/envelope/snapshot.json", {
        "snapshot_version": "0.1",
        "agent": "microscope_agent",
        "kb_version": "kbv-fixture",
        "built_from_commit": exported_at,
        "entry_count": 1,
        "entries": {"e1": {"text": newer}},
        "tables": {},
    })
    commit(repo, "carry a snapshot that names one commit and holds another's bytes",
           "microscope_agent", seat="microscope-1")
    return f"{start}..HEAD"


def fixture_46_vocabulary_pin_that_never_stood(repo: Path) -> str:
    """A result pinning a vocabulary version no commit ever held.

    `estimation.vocabulary_version` is what makes `comparable` mean the same
    estimator ran on both sides. A pin that resolves nowhere says nothing --
    a version that was never committed hashes a working tree, and there is
    nothing to read back. Older is normal and is not the failure: the
    vocabulary grows an entry at a time and a result records what it ran
    against.
    """
    start = base(repo)
    write(repo, "microscope_agent/questions/q/result.json", {
        "card": "result",
        "schema_version": "0.1",
        "id": "result-fixture-001",
        "qid": "q",
        "estimation": {
            "vocabulary_version": "obs-000000000000",
            "followed": True,
        },
    })
    commit(repo, "a result pinning a vocabulary that never stood",
           "microscope_agent", seat="microscope-1")
    return f"{start}..HEAD"


# (check, expected verdict, a phrase the finding must carry, builder)
#
# The phrase is not decoration. Check 26 can fail nine ways and only two of
# them are the divergence 4.3.2 means; a fixture that fails on one of the
# other seven passes this harness and tests nothing it claims to. Naming the
# check was enough while each fixture had one way to fail. It is not any more.
def fixture_76_a_local_settings_file_is_named(repo: Path) -> str:
    """The untracked file that silenced three seats for a day.

    On 2026-09-20 one key in `.claude/settings.local.json` --
    `{"disabledMcpjsonServers": ["librarian"]}` -- turned the librarian's
    tools off in three sessions, and a deny beats the user-level allow that
    was already in force. Nothing in the repository could see it: the file is
    globally gitignored, so no commit and no tree holds it, and check 53 globs
    `settings.json` exactly and walks past it.

    So this fixture writes it AND DOES NOT COMMIT IT, which is the whole
    point -- a committed one would not reproduce the case. The tracked
    `settings.json` beside it is what makes the local one worth reporting.
    """
    head = base(repo)
    write(repo, ".claude/settings.json", {"permissions": {"deny": []}})
    run(repo, "add", "--", ".claude/settings.json")
    run(repo, "commit", "-q", "--no-verify", "-m", "settings", seat="architecture")
    # untracked on purpose, and never added
    write(repo, ".claude/settings.local.json",
          {"disabledMcpjsonServers": ["librarian"], "permissions": {"deny": ["Bash(rm*)"]}})
    return f"{head}..HEAD"


def fixture_76_an_export_says_it_could_not_have_seen_it(repo: Path) -> str:
    """Under the gate the absence has to read as unseeable, not as absent.

    The hook unpacks the index into a scratch directory, so an untracked file
    is not merely missing there -- it could not be there. A line saying "no
    local settings file" would be true of the export and false of the machine,
    and would be the most convincing wrong answer available: it looks like a
    clean bill of health.

    The file below IS written, so a check that ignored the export would find
    it and say PASS. Only one that knows where it is running says N/A.
    """
    head = base(repo)
    write(repo, ".claude/settings.json", {"permissions": {"deny": []}})
    run(repo, "add", "--", ".claude/settings.json")
    run(repo, "commit", "-q", "--no-verify", "-m", "settings", seat="architecture")
    write(repo, ".claude/settings.local.json", {"disabledMcpjsonServers": ["librarian"]})
    return f"{head}..HEAD"


fixture_76_an_export_says_it_could_not_have_seen_it.env = {"SMA_GIT_REPO": "/nonexistent/real/repo"}


def fixture_78_a_classifier_edit_orphans_a_path_in_history(repo: Path) -> str:
    """An edit to the path classifier that orphans a file already in history.

    This is the event check 78 exists for, built rather than described.
    Architecture proposed exactly it on 2026-09-23 -- removing `plan_ko\\.md`
    from SHARED_PATHS -- after reading the comment directly above the regex
    saying not to. A live-tree check passes that edit, because the orphaned
    file is not on disk to be counted. Only a sweep over history sees it.

    `enforced_from` is rewritten here, and it is the one field a fixture may
    honestly rewrite: it names a commit, and a SHA from the real repository
    does not exist in this one, so `git log` would error and the check would
    report PENDING instead of the failure. `owns` and `boundaries` are left
    exactly as the real registry has them, for the reason `base` gives.
    """
    start = base(repo)
    seats = json.loads((repo / "contracts" / "seats.json").read_text())
    seats["enforced_from"] = start
    write(repo, "contracts/seats.json", seats)
    commit(repo, "the enforcement line, named for this repository",
           "contracts/seats.json", seat="architecture")

    write(repo, "README.md", "# fixture, and a root file the classifier knows\n")
    commit(repo, "a root file both lists carry", "README.md", seat="architecture")

    # The edit itself: SHARED_PATHS stops knowing the name, and ALLOWED_PATHS
    # keeps permitting it. Targeted at that line rather than at the first
    # occurrence in the file -- DESIGN_OWNED carries `README\\.md|` too, for
    # an agent's own README, and hitting that one would test nothing.
    v = repo / "contracts" / "validate.py"
    lines = v.read_text().splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("SHARED_PATHS = "):
            lines[i] = line.replace("README\\.md|", "", 1)
            break
    else:
        raise AssertionError("no SHARED_PATHS assignment to edit")
    v.write_text("".join(lines))
    commit(repo, "the classifier stops knowing a name history still carries",
           "contracts/validate.py", seat="architecture")
    return f"{start}..HEAD"


def fixture_79_gitignore_excludes_a_directory_the_walker_enters(repo: Path) -> str:
    """A directory .gitignore excludes wholesale and SKIP_DIRS does not hold.

    Not a history fixture, and it is here because what it needs is a whole
    repository with a root `.gitignore` in it, which is what this file builds
    and the rejected-cards folder cannot -- those are cards, and neither of
    the two lists this compares is a card.

    The real event was `.pixi/` on 2026-09-23: in .gitignore, absent from
    SKIP_DIRS, and one `pixi install` turned 271 MB of somebody else's
    package cache into 10757 check-13 failures for every seat sharing the
    working copy. `build/` stands in for it so the fixture keeps failing
    after `.pixi` is in both lists, which it now is.
    """
    start = base(repo)
    write(repo, ".gitignore", "__pycache__/\n.venv/\n.pixi/\nbuild/\n*.pyc\n")
    commit(repo, "a .gitignore naming a directory the walker still enters",
           ".gitignore", seat="architecture")
    return f"{start}..HEAD"


def fixture_80_five_forms_and_five_that_must_not_fire(repo: Path) -> str:
    """All five declared forms in one file, beside five that must stay quiet.

    The check exists because two probes each missed a different form, so a
    fixture carrying only some of them would pass while the check saw part of
    the rule. All five are planted, including the two declared after the
    first three: a dictionary access with no `Compare` node, and a prefix
    test on a name bound from a registry accessor.

    **The quiet four matter as much.** A refusal message that QUOTES the test
    was a false positive of the first probe -- the message is real, another
    seat wrote it because card 028 asked a record to say what it searched --
    and reading with `ast` is what excludes it, so this carries one to prove
    the exclusion rather than assert it. Beside it: an assignment of declared
    ids, which can be a legitimate fact about a module; equality against a
    path id, which is the rule being KEPT; and a fragment under the length
    floor. And the fifth quiet case is the sharp one: the SAME `startswith`
    call on a name bound from anything else, which parses a source prefix and
    must not be counted -- 21 of the 23 such calls in the real trees are that.
    """
    head = base(repo)
    write(repo, "librarian_agent/kb/staging/devices.v0.json", {
        "schema_version": "0.1-provisional",
        "channels": [
            {"id": "stand_ti2e", "elements": [{"id": "nosepiece"}, {"id": "pfs"},
                                              {"id": "laser_shutter"}, {"id": "z_drive"}]},
        ],
        "optical_paths": [{"id": "confocal"}],
    })
    write(repo, "microscope_agent/src/probe_subject.py", SUBJECT_80)
    sha = commit(repo, "plant", "librarian_agent", "microscope_agent", seat="microscope-1")
    return f"{head}..{sha}"


SUBJECT_80 = """\"\"\"A module carrying one of each form, and four that must not fire.\"\"\"

RETRACT_HINTS = ("z_drive", "pfs")          # an assignment: out of scope on purpose


def decide(element_id, elements, element, path, state, channel, source):
    if "shutter" in element_id:             # FORM 1 substring
        return "shutter"
    if "pfs" in elements:                   # FORM 2 membership
        return "stabiliser"
    if element == "nosepiece":              # FORM 3 equality
        return "turret"
    if state.get("nosepiece"):              # FORM 4 key-access
        return "seated"
    for e in channel.element_ids():
        if e.startswith("focus"):           # FORM 5 prefix, receiver from the registry
            return e
    if source.startswith("kb:"):            # the same call, parsing a prefix: QUIET
        return "kb"
    if path == "confocal":                  # a path id: the rule being KEPT
        return "path"
    if "z" in element_id:                   # under the length floor
        return "short"
    raise RuntimeError(
        "refusing: the test `'shutter' in element_id` over the registry found nothing")
"""


def fixture_81_an_agent_module_imports_what_is_in_no_commit(repo: Path) -> str:
    """A commit that leaves an agent's source importing a file nobody committed.

    Built rather than described, and it is the event of 2026-09-23: five axis
    modules gained `from . import axes_abp` from another seat's worktree
    while that module itself stayed untracked, so a clean export of the
    commit raised ImportError and the whole fan-out was unrunnable. The
    working copy kept running, which is why nobody saw it.

    The fixture leaves the imported module out of the TREE and does not
    write it to disk either, and the first version of this fixture got that
    wrong. It wrote the file untracked, to reproduce the real asymmetry
    exactly -- and then the check passed, correctly, because check 81
    resolves against REPO and in a bare run REPO is the working copy, where
    the file was sitting. A fixture that reproduces the whole situation can
    test nothing; what it has to reproduce is the state the check judges.

    So the split is worth stating. The check asks whether an import resolves
    in THE TREE IT IS GIVEN. Under the gate that tree is the index export and
    the untracked file is absent, which is where the real event is caught. In
    a bare run the tree is the working copy and an untracked module passes --
    correctly, because a bare run is judging no commit. This fixture gives it
    a tree that genuinely lacks the module, which is the same state the gate
    would have seen on 2026-09-23.

    Not a history fixture, and it is here for the reason fixture 79 is: what
    it needs is a whole repository whose tree is missing one file, which this
    file builds and the rejected-cards folder cannot.
    """
    start = base(repo)
    write(repo, "simulation_agent/src/__init__.py", "")
    write(repo, "simulation_agent/src/axis_a1_stability.py",
          "from . import axes_abp\n\n\ndef build(config):\n    return axes_abp.build(config)\n")
    commit(repo, "an axis module that dispatches to a module nobody committed",
           "simulation_agent/src/__init__.py", "simulation_agent/src/axis_a1_stability.py",
           seat="simulation")
    return f"{start}..HEAD"


def fixture_82_an_agent_imports_a_dependency_nobody_declared(repo: Path) -> str:
    """An agent module importing a third-party package the manifest does not have.

    The event of 2026-09-23: `gsd` was imported at three call sites and
    declared nowhere, and every run in the sim environment quietly wrote no
    trajectory. Nothing went red, because `trajectory.write` recorded
    `written: false` with the reason and that is honest. An honest record of
    a failure is not the same as a check.

    The fixture writes BOTH halves of the asymmetry into one repository so
    one run shows the two verdicts apart: a package imported and undeclared,
    which must FAIL, and a package declared and imported by nothing, which
    must only report. Splitting them across two fixtures would let the
    second one pass by never being reached.
    """
    start = base(repo)
    write(repo, "pyproject.toml",
          "[project]\nname = \"fixture\"\nversion = \"0\"\ndependencies = [\"numpy>=1\"]\n\n"
          "[tool.pixi.feature.sim.dependencies]\nscipy = \">=1.11\"\n")
    write(repo, "simulation_agent/src/__init__.py", "")
    write(repo, "simulation_agent/src/trajectory.py",
          '"""A module whose docstring says from time to time, so a regex would see an import.\n\n'
          'It also mentions the one thing it needs and the fields it writes.\n"""\n'
          "import numpy\n\n\ndef write(frames):\n    import gsd.hoomd\n    return gsd.hoomd, numpy\n")
    commit(repo, "a module importing a package the manifest never declared",
           "pyproject.toml", "simulation_agent/src/__init__.py",
           "simulation_agent/src/trajectory.py", seat="simulation")
    return f"{start}..HEAD"


def _decision_card(numbers: list, targets: list, kb_refs: list | None = None) -> dict:
    """A minimal axis card carrying the numbers under test. Unrelated findings
    are tolerated by this harness; only the named check and phrase count."""
    return {"card": "axis", "id": "axis-fixture", "schema_version": 1, "qid": "sim-20260923-901",
            "thread": None, "round": 1, "revision": 1, "author": "simulation_agent",
            "created_at": "2026-09-23T00:00:00Z", "status": "draft", "kb_version": "kbv-000000000000",
            "method": "fixture", "verdict": "constrains", "caller_id": "sim-20260923-901:v1:bd_overdamped:a2",
            "config": "bd_overdamped", "axis": "a2", "numbers": numbers, "targets": targets,
            "kb_refs": kb_refs or [], "kb_gaps": [], "degraded": []}


_KAPPA = {"name": "kappa", "value": 4.0, "unit": "1", "source": "assumed:fixture", "grade": "E5"}


def _one_card(repo: Path, card: dict, message: str, extra: dict | None = None) -> str:
    start = base(repo)
    paths = []
    for rel, body in (extra or {}).items():
        write(repo, rel, body)
        paths.append(rel)
    rel = "simulation_agent/questions/sim-20260923-901/axis_bd_overdamped_a2.json"
    write(repo, rel, card)
    commit(repo, message, rel, *paths, seat="simulation")
    return f"{start}..HEAD"


def fixture_17_a_target_input_that_resolves_nowhere(repo: Path) -> str:
    """A computed number citing the person's target where the card holds none.

    Proves the NEW path fires and not the old one. Before decision inputs
    existed a `target:` string was simply an unknown name and failed as
    "neither numbers of this card nor kb: entries"; both versions refuse this
    card, so a phrase-blind fixture could not tell them apart. This one names
    the phrase only the resolver says.
    """
    n = {"name": "record_factor", "value": 400.0, "unit": "1", "source": "computed:fixture", "grade": "E5",
         "formula": "kappa / drag_offset", "inputs": ["kappa", "target:drag_offset"]}
    return _one_card(repo, _decision_card([_KAPPA, n], []), "a target input with no target behind it")


def fixture_17_a_target_metric_that_shadows_a_number(repo: Path) -> str:
    """The formula names a target by its metric, and that metric is also a
    number on the card -- one name meaning two things in one formula."""
    shadow = dict(_KAPPA, name="drag_offset")
    n = {"name": "record_factor", "value": 400.0, "unit": "1", "source": "computed:fixture", "grade": "E5",
         "formula": "kappa / drag_offset", "inputs": ["kappa", "target:drag_offset"]}
    tg = [{"metric": "drag_offset", "kind": "uncertainty", "value": 0.01, "unit": "1"}]
    return _one_card(repo, _decision_card([_KAPPA, shadow, n], tg), "a target metric that shadows a number")


def fixture_17_an_envelope_field_named_twice(repo: Path) -> str:
    """The real shape of simulation's budget.json: `wall_clock_max` is both the
    person's 2 h ceiling and the smoke-run ceiling. The bare name is ambiguous
    and must be refused with the matching paths named, not guessed at. The
    first draft of the resolver matched the leaf name alone and would have
    left the ceiling impossible to cite; the qualified form resolves it."""
    budget = {"artifact": "budget", "targets": [{"target": "local", "limits": {
        "wall_clock_max": {"value": 2, "unit": "h"},
        "smoke_budget": {"wall_clock_max": {"value": 5, "unit": "min"}}}}]}
    n = {"name": "steps", "value": 4.0, "unit": "1", "source": "computed:fixture", "grade": "E5",
         "formula": "kappa", "inputs": ["kappa", "envelope:budget.json#wall_clock_max"]}
    return _one_card(repo, _decision_card([_KAPPA, n], []), "an envelope field that is named twice",
                     {"simulation_agent/envelope/budget.json": budget})


def fixture_21_a_formula_on_a_graded_store_entry(repo: Path) -> str:
    """A computed number on an E5 store entry, claiming E4.

    Until 2026-09-23 the grade composed over "every input that is in
    numbers[]", which skipped decisions correctly and skipped kb: inputs
    wrongly -- so a formula on an E5 entry came out E4, better than its own
    input. Written out as "graded inputs compose, decisions do not" it takes
    the kb: grade from kb_refs, and this card is refused. No real card held a
    kb: input when it was found, so nothing on disk moved.
    """
    n = {"name": "scaled", "value": 2.0, "unit": "1", "source": "computed:fixture", "grade": "E4",
         "formula": "2", "inputs": ["kb:weak_entry"]}
    refs = [{"entry_id": "weak_entry", "grade": "E5"}]
    return _one_card(repo, _decision_card([n], [], refs), "a formula on an E5 entry claiming E4")


def fixture_40_a_sweep_point_run_without_its_window(repo: Path) -> str:
    """A sweep plan whose window moves with the axis, and one run point lacks it.

    Before 2026-09-23 check 40 read the top-level conditions alone, so a
    sweep carrying its window PER POINT -- a multiple of each point's own
    relaxation time, the case simulation-8 hit -- could not pass however
    correct it was. Reading the points fixed that and opened this failure:
    a point that was actually run with no window in either place. The phrase
    is the new one; the old code said "must carry ... as a condition", so a
    fixture matching it would pass on either version and test nothing.

    A third point is marked `skipped` and also lacks the window, and must NOT
    be named: a cell that was never measured has nothing to label.
    """
    start = base(repo)
    W = {"name": "win_a", "value": 1.0, "unit": "s", "source": "assumed:fixture", "grade": "E5"}
    plan = {"card": "plan", "id": "plan-fixture", "schema_version": 1, "qid": "sim-20260923-902",
            "thread": None, "round": 1, "revision": 1, "author": "simulation_agent",
            "created_at": "2026-09-23T00:00:00Z", "status": "draft", "goal_id": "goal-fixture",
            "purpose": "characterize", "intent": "explore",
            "observable": {"name": "tracer_diffusivity", "unit": "um^2/s"},
            "system_configuration": "bd_overdamped",
            "numbers": [W], "conditions": [{"parameter": "temperature", "number": "win_a"}],
            "sweep": {"axes": [{"parameter": "trap_stiffness", "levels": ["win_a", "win_a"]}],
                      "points": [
                          {"point": "soft", "conditions": [{"parameter": "max_lag_time", "number": "win_a"}]},
                          {"point": "stiff", "conditions": [{"parameter": "trap_stiffness", "number": "win_a"}]},
                          {"point": "corner", "skipped": "diverges",
                           "conditions": [{"parameter": "trap_stiffness", "number": "win_a"}]}]},
            "actions": [], "envelope_check": {}, "cost": {}, "stop_criteria": [],
            "success_criteria": [], "open_risks": [], "kb_refs": [], "kb_gaps": [], "degraded": []}
    rel = "simulation_agent/questions/sim-20260923-902/plan_simulation_sim-20260923-902.json"
    write(repo, rel, plan)
    commit(repo, "a sweep point run without its window", rel, seat="simulation")
    return f"{start}..HEAD"


def _deletion_repo(repo: Path, met, why=None) -> str:
    """A plan declaring a STOP criterion, a result card evaluating it, and a run
    log that deleted the trajectory citing that criterion. Only `met` varies."""
    start = base(repo)
    q = "simulation_agent/questions/sim-20260923-903"
    plan = {"card": "plan", "id": "plan-sim-20260923-903-r1", "schema_version": 1,
            "qid": "sim-20260923-903", "revision": 1, "author": "simulation_agent",
            "observable": {"name": "tracer_diffusivity", "unit": "um^2/s"},
            "system_configuration": "bd_overdamped", "numbers": [], "conditions": [],
            "stop_criteria": [{"id": "step_displacement_diverged"}], "success_criteria": [],
            "assumptions": [], "kb_refs": [], "kb_gaps": [], "degraded": []}
    row = {"id": "step_displacement_diverged", "met": met}
    if why is not None:
        row["why_unevaluated"] = why
    result = {"card": "result", "id": "result-903", "schema_version": 1, "qid": "sim-20260923-903",
              "revision": 1, "author": "simulation_agent", "run_id": "run-20260923-903",
              "plan_id": "plan-sim-20260923-903-r1", "criteria_evaluation": [row],
              "numbers": [], "kb_refs": [], "kb_gaps": [], "degraded": []}
    log = {"run_id": "run-20260923-903", "plan_path": f"{q}/plan.json", "events": [
        {"event": "trajectory_deleted", "t": 1.0, "deletion": {
            "what": ["simulation_agent/runs/run-20260923-903/trajectory.txt"], "bytes_freed": 1,
            "triggered_by": {"kind": "criterion", "id": "step_displacement_diverged",
                             "declared_in": "plan-sim-20260923-903-r1"}}}]}
    for rel, doc in ((f"{q}/plan_simulation_sim-20260923-903.json", plan),
                     (f"{q}/result_run-20260923-903.json", result),
                     ("simulation_agent/runs/run-20260923-903/log.json", log)):
        write(repo, rel, doc)
    commit(repo, "a trajectory deleted on a criterion", q, "simulation_agent/runs", seat="simulation")
    return f"{start}..HEAD"


def fixture_77_a_deletion_on_a_criterion_nobody_evaluated(repo: Path) -> str:
    """The defect architecture found on 2026-09-23: `met: null` was SKIPPED.

    The result card says it could not evaluate the stop criterion, and the
    trajectory was deleted citing that criterion anyway. The old check skipped
    the row, added no failure, and its final line then counted this deletion
    among those "that fired" -- an irreversible act passed on a condition
    nobody checked. The phrase is the new one; the old code produced none.
    """
    return _deletion_repo(repo, None, "the run was aborted before the window closed")


def fixture_77_a_deletion_on_a_stop_criterion_that_did_not_fire(repo: Path) -> str:
    """A stop criterion fires by being MET. Here it is met: false -- the run
    behaved -- and the trajectory was deleted on it anyway. This path existed
    before and no fixture reached it, which is the second half of the report:
    the resolution path had never been watched to fail."""
    return _deletion_repo(repo, False)


def fixture_83_a_written_trajectory_deleted_by_hand(repo: Path) -> str:
    """A run that recorded writing its trajectory, whose file is now gone, and
    whose log holds no pipeline deletion -- the person deleted it by hand.

    Intended, and not a failure: the person decides what to keep. The check
    exists so the absence is SEEN, and a report is the verdict it must give --
    naming the rerun that regenerates the file and the hash that verifies it.
    Measured on 2026-09-23: a trajectory removed by hand moved no verdict in
    either run, which is the silence this fixture now makes loud.
    """
    start = base(repo)
    run = "simulation_agent/runs/run-20260923-904"
    H = "c" * 64
    meta = {"artifact": "trajectory_meta", "schema_version": 1, "run_id": "run-20260923-904",
            "trajectory": {"written": True, "format": "txt", "file": "trajectory.txt", "sha256": H,
                           "coords_sha256": H, "dtype": "float64", "sig_figs": 17, "time_base": "step_index",
                           "save_interval_steps": 100, "frames": 10, "particles": 5, "engine": "hoomd",
                           "engine_version": "7.2.0", "seed": 7, "plan_hash": "p", "box": [1, 1, 0],
                           "units": "m", "columns": [{"name": "step", "unit": "1", "meaning": "step index"}]}}
    log = {"run_id": "run-20260923-904", "plan_id": "plan-904", "backend": "hoomd_backend", "events": []}
    for rel, doc in ((f"{run}/trajectory_meta.json", meta), (f"{run}/log.json", log)):
        write(repo, rel, doc)
    # trajectory.txt is deliberately never written: it is the file the person removed.
    commit(repo, "a run that wrote a trajectory the person later deleted", run, seat="simulation")
    return f"{start}..HEAD"


def _registry_with(repo: Path, extra: dict, message: str) -> str:
    """The real registry, its dated-form epoch set to this repository's base,
    and ONE entry appended. Only the epoch is rewritten -- it names a commit and
    a SHA from the real repository does not exist here (fixture 78's reason) --
    and existing entries are never edited, for the reason `base` gives."""
    start = base(repo)
    doc = json.loads((repo / "contracts" / "seats.json").read_text())
    doc["dated_form_from"] = start
    doc["seats"].append(extra)
    write(repo, "contracts/seats.json", doc)
    commit(repo, message, "contracts/seats.json", seat="architecture")
    return f"{start}..HEAD"


def fixture_84_a_seat_registered_after_the_epoch_with_an_undated_name(repo: Path) -> str:
    """A seat added after the dated form took effect, named the old way.

    The person asked on 2026-09-23 for <role>-<YYYYMMDD>-<n>. Entries that
    existed then keep their names; a new one that does not follow the form is
    refused. The name here also carries a date that is not on the calendar,
    so the parse has to reject both the shape and the thirteenth month."""
    return _registry_with(repo, {"seat": "simulation-20261345-1", "committer_email":
                                 "simulation-20261345-1@seat.invalid", "owns": ["simulation_agent"]},
                          "a seat whose date does not exist")


def fixture_84_two_seats_share_one_committer_email(repo: Path) -> str:
    """Two seats, one committer email. Measured in a scratch copy before this
    check was asked for: the gate passed it and check 41 then handed one seat's
    commits to the other, because a seat is identified by its email."""
    return _registry_with(repo, {"seat": "manager-simulation", "committer_email":
                                 "manager-simulation@seat.invalid", "owns": ["design"],
                                 "excludes": ["contracts/seats.json"]},
                          "a second entry reusing an email already registered")


def fixture_84_a_manager_that_can_write_the_registry(repo: Path) -> str:
    """A manager entry without contracts/seats.json in `excludes`. Measured
    before it was asked for: such an entry passed check 41 on seats.json AND
    plan.md -- a design seat able to rewrite the file that bounds it."""
    return _registry_with(repo, {"seat": "manager-sweep-20260923-1", "committer_email":
                                 "manager-sweep-20260923-1@seat.invalid", "owns": ["design"],
                                 "paths": ["contracts/"]},
                          "a manager entry with no exclusion of the registry")


def fixture_68_a_superseded_record_cannot_be_rewritten(repo: Path) -> str:
    """A glued gap name in a superseded axis card, beside the same one live.

    **The prefix here means the opposite of what it means on a plan card, and
    getting that backwards is what this fixture is really guarding.** For
    axis cards a re-run writes `v2_axis_*` BESIDE `axis_*` and `synthesis.py`
    reads the highest prefix present, so **`v2_` is the live set and the
    unprefixed one is superseded.** `card_revision.displace()` is the other
    way round and its docstring calls itself "the axis cards' convention",
    which it is not.

    So this plants `axis_live_a2.json` as the superseded record and
    `v2_axis_live_a2.json` as the live one, and asserts LOST for the first
    and FAIL for the second **by path**. A check that read the prefix the
    plan-card way reports them swapped, and matching on the branches' wording
    did not catch that -- one LOST and one FAIL were still produced, just
    from the wrong files. That version of this fixture was written, run
    against the swap, and passed 25/25; the paths are here because of it.

    The `searched` line is what makes the superseded one unrewritable: it
    quotes the call actually made, and editing `observable` over it would
    claim a quantity nobody asked for.
    """
    head = base(repo)
    gap = {
        "gap_id": "tracer_loading",
        "observable": "tracer_number_density",
        "kind": "absent",
        "kb_version": "kbv-000000000000",
        "searched": ["kb_query(observable=tracer_number_density) -> absent"],
    }
    card = {"card": "axis", "schema_version": "0.1", "kb_gaps": [gap]}
    write(repo, "microscope_agent/questions/q/axis_live_a2.json", card)      # superseded
    write(repo, "microscope_agent/questions/q/v2_axis_live_a2.json", card)   # live
    reg = json.loads((repo / "contracts" / "quantities.json").read_text())
    reg["quantities"].append({"id": "number_density", "definition": "count per volume",
                              "unit": "1/ml", "kind": "physical"})
    write(repo, "contracts/quantities.json", reg)
    sha = commit(repo, "plant", "microscope_agent", "contracts", seat="microscope-1")
    return f"{head}..{sha}"


FIXTURES = [
    (35, "FAIL", "a session writes inside one agent", fixture_35_one_commit_two_boundaries),
    (41, "FAIL", "this path is bridge's", fixture_41_seat_writes_outside_its_own),
    (41, "PENDING", "not a seat in", fixture_41_unregistered_committer),
    (26, "FAIL", "does not match the committed bytes", fixture_26_snapshot_is_a_copy_of_another_commit),
    (46, "FAIL", "obs-000000000000", fixture_46_vocabulary_pin_that_never_stood),
    (76, "PASS", "disabledMcpjsonServers", fixture_76_a_local_settings_file_is_named),
    (76, "N/A", "could not have been found", fixture_76_an_export_says_it_could_not_have_seen_it),
    (78, "FAIL", "classify into no boundary", fixture_78_a_classifier_edit_orphans_a_path_in_history),
    (79, "FAIL", "SKIP_DIRS does not", fixture_79_gitignore_excludes_a_directory_the_walker_enters),
    (81, "FAIL", "is in no file of this tree", fixture_81_an_agent_module_imports_what_is_in_no_commit),
    (82, "FAIL", "declared nowhere in pyproject.toml", fixture_82_an_agent_imports_a_dependency_nobody_declared),
    (17, "FAIL", "reads a decision that does not resolve", fixture_17_a_target_input_that_resolves_nowhere),
    (17, "FAIL", "would mean two things", fixture_17_a_target_metric_that_shadows_a_number),
    (17, "FAIL", "so the reference is ambiguous", fixture_17_an_envelope_field_named_twice),
    (21, "FAIL", "max(E4, worst) = E5", fixture_21_a_formula_on_a_graded_store_entry),
    (40, "FAIL", "were run without", fixture_40_a_sweep_point_run_without_its_window),
    (77, "FAIL", "did not evaluate it", fixture_77_a_deletion_on_a_criterion_nobody_evaluated),
    (77, "FAIL", "that criterion NOT firing", fixture_77_a_deletion_on_a_stop_criterion_that_did_not_fire),
    (83, "PASS", "deleted outside the pipeline", fixture_83_a_written_trajectory_deleted_by_hand),
    (84, "FAIL", "with a real calendar date", fixture_84_a_seat_registered_after_the_epoch_with_an_undated_name),
    (84, "FAIL", "is the committer email of 2 seats", fixture_84_two_seats_share_one_committer_email),
    (84, "FAIL", "can write the registry", fixture_84_a_manager_that_can_write_the_registry),
    (80, "PASS", "5 site(s) decide a device's role", fixture_80_five_forms_and_five_that_must_not_fire),
    (68, "LOST", "/axis_live_a2.json]", fixture_68_a_superseded_record_cannot_be_rewritten),
    # The same built repository, asserted from the other side. Two rows because
    # one leaves the split half tested -- making EVERY record LOST satisfies a
    # lone LOST row while the live card quietly stops being a failure.
    #
    # AND THEY MATCH ON THE PATH, not on the message. Phrases from the two
    # branches' wording passed a mutation that read the axis prefix the
    # plan-card way and swapped the verdicts: the rows ask only for one LOST
    # and one FAIL from check 68, and a swap still supplies both. The leading
    # slash is load-bearing -- `/axis_live_a2.json]` is not a substring of
    # `/v2_axis_live_a2.json]`, so each row can only be satisfied by its own
    # file. Watched: the swap now breaks both.
    (68, "FAIL", "/v2_axis_live_a2.json]", fixture_68_a_superseded_record_cannot_be_rewritten),
]


# --------------------------------------------------------------------------- #

def findings_for(repo: Path, commit_range: str,
                 extra_env: dict[str, str] | None = None) -> list[tuple[int, str, str]]:
    """Run the fixture's own copy of the validator and parse its lines.

    The copy is what makes this honest: REPO and GIT_REPO both resolve inside
    the fixture, so a check cannot accidentally read the real tree and pass on
    evidence the fixture never provided.

    `extra_env` exists for the one thing a built repository cannot express by
    being built: the pre-commit hook sets `SMA_GIT_REPO`, and a check that
    behaves differently under the gate can only be watched doing it if the
    variable can be set. A builder asks by carrying an `env` attribute, so the
    FIXTURES rows keep their four-element shape -- check 65 parses them with a
    regex, and widening the tuple would make that regex see nothing and report
    every history check as having no fixture at all.
    """
    env = dict(os.environ)
    env.update(extra_env or {})
    out = subprocess.run([sys.executable, str(repo / "contracts" / "validate.py"),
                          "--commit-range", commit_range],
                         capture_output=True, text=True, cwd=repo, env=env)
    found = []
    for line in (out.stdout + out.stderr).splitlines():
        m = re.match(r"\s*check\s+(\d+)\s+(PASS|FAIL|UNDECIDED|PENDING|LOST|N/A)\s+(.*)", line)
        if m:
            found.append((int(m.group(1)), m.group(2), m.group(3)))
    return found


def main() -> int:
    ok, broken = 0, []
    for want, verdict, phrase, build in FIXTURES:
        with tempfile.TemporaryDirectory(prefix="sma-history-") as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            commit_range = build(repo)
            found = findings_for(repo, commit_range, getattr(build, "env", None))
            mine = [f for f in found if f[0] == want and f[1] == verdict and phrase in f[2]]
            if mine:
                ok += 1
                word = "rejected" if verdict == "FAIL" else "reported"
                print(f"  {word} by check {want}  {build.__name__}")
                print(f"      {mine[0][2][:150]}")
            else:
                got = sorted({(f[0], f[1]) for f in found if f[1] in ("FAIL", "PENDING")})
                loose = [f for f in found if f[0] == want and f[1] == verdict]
                why = (f" -- check {want} did say {verdict}, on {loose[0][2][:90]!r}, which is a different "
                       f"branch than {phrase!r}") if loose else (f" (saw {got})" if got else " (nothing fired)")
                broken.append(f"{build.__name__} is a fixture for check {want} {verdict} carrying {phrase!r}"
                              + why)
    print(f"history: {ok}/{len(FIXTURES)} built repositories answered as intended")
    for b in broken:
        print(f"  NOT REJECTED  {b}")
    if broken:
        print("a fixture that stops failing means a check stopped working")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
