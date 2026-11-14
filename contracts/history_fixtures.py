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

import copy
import json
import hashlib
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
    return commit(repo, "base", "contracts", "README.md", seat="design")


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
           "microscope_agent", "simulation_agent", seat="microscope")
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
           "bridge", seat="microscope")
    return f"{start}..HEAD"


def fixture_35_a_root_commit_in_the_range_is_judged(repo: Path) -> str:
    """A range whose first commit is the repository's root, and writes into two agents.

    A root commit has no ~1, and check 35 built `<root>~1..<root>` for it and
    crashed ("cannot read commit range") rather than judging it.
    architecture-20261007-1 found that on the trial dino-autofocus import on
    2026-10-15. The root is now diffed against the empty tree, so it is judged
    like any other commit -- and this root writes into two agents, so the
    finding is the two-boundary refusal, which the crash never reached.
    """
    run(repo, "init", "-q", "-b", "main")
    write(repo, "microscope_agent/questions/q/goal.json", {"card": "goal"})
    write(repo, "simulation_agent/questions/q/goal.json", {"card": "goal"})
    commit(repo, "a root commit writing into two agents",
           "microscope_agent", "simulation_agent", seat="microscope")
    shutil.copytree(CONTRACTS, repo / "contracts")
    write(repo, "README.md", "# fixture\n")
    commit(repo, "the registry, after the root", "contracts", "README.md", seat="design")
    return "HEAD"


def fixture_41_an_imported_history_is_not_attributed(repo: Path) -> str:
    """A subtree import: the merge is judged, the imported project's own commits are not.

    `git subtree add` brings the imported repository's whole history in on the
    merge's second parent, by committers who were never seats here and with
    paths relative to that repository's root. Checks 35 and 41 walked them as
    this repository's commits until 2026-10-15 (the dino-autofocus import).
    Now both read only the first-parent line: the one commit judged is the
    merge, made by a registered seat, whose paths fall in its own boundary.
    The imported repository here has two commits by an unregistered
    committer, so the old walk counted three commits and reported the stranger.
    """
    start = base(repo)
    src = repo.parent / "imported"
    src.mkdir()
    run(src, "init", "-q", "-b", "main")
    write(src, "src/pkg/core.py", "VALUE = 1\n")
    commit(src, "the imported project's first commit", "src", seat="not-a-seat-here")
    write(src, "docs/notes.md", "# notes\n")
    commit(src, "the imported project's second commit", "docs", seat="not-a-seat-here")
    run(repo, "subtree", "add", "-q", "--prefix=microscope_agent/autofocus", str(src), "main",
        seat="microscope")
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


def readme(first: str, middle: str, last: str) -> str:
    """README.md with a first, a middle and a last line far enough apart to merge cleanly."""
    return "".join(line + chr(10) for line in [first, "", "one", "two", middle, "four", "five", "", last])


def _two_sided_readme(repo: Path) -> str:
    """Both sides of a merge edit README.md, the first line on main and the last on a branch.

    The regions are apart, so git merges them with no hand. Returns the range
    start, before main's edit; the caller makes the merge as microscope-1,
    whose paths do not cover README.md.
    """
    base(repo)
    write(repo, "README.md", readme("# fixture", "three", "end"))
    start = commit(repo, "a README with room for two edits", "README.md", seat="design")
    run(repo, "checkout", "-q", "-b", "other")
    write(repo, "README.md", readme("# fixture", "three", "end, on the branch"))
    commit(repo, "the branch edits the last line", "README.md", seat="design")
    run(repo, "checkout", "-q", "main")
    write(repo, "README.md", readme("# fixture, on main", "three", "end"))
    commit(repo, "main edits the first line", "README.md", seat="design")
    return start


def fixture_41_a_clean_merge_attributes_nothing(repo: Path) -> str:
    """A merge git made without a hand, by a seat that does not own the file both sides edited.

    plan.md 6.2.1 (e284452f): the seat whose push is refused as behind makes
    the merge, and what a merge contributes is what `--cc` shows. Check 41
    read a merge's paths with `--cc --name-only`, which lists every path that
    differs from all parents, so it attributed README.md to microscope-1 and
    refused. That refused the intake seat's merge e9c9ad52 on 2026-10-27, where
    the file was plan.md. The dense patch prints no hunk here, so nothing is
    attributed.
    """
    start = _two_sided_readme(repo)
    run(repo, "merge", "-q", "--no-ff", "--no-edit", "other", seat="microscope")
    return f"{start}..HEAD"


def fixture_41_a_merge_that_adds_its_own_line_is_judged(repo: Path) -> str:
    """The same merge, with a line in no parent added while merging, outside the merger's seat.

    The other half of reading `--cc` by its hunks: a change the merge made
    itself still lands on the merging seat, so the fix for the clean merge
    cannot turn into skipping merges.
    """
    start = _two_sided_readme(repo)
    run(repo, "merge", "-q", "--no-ff", "--no-commit", "other", seat="microscope")
    write(repo, "README.md", readme("# fixture, on main", "three, added while merging", "end, on the branch"))
    commit(repo, "a merge that adds a line of its own", "README.md", seat="microscope")
    return f"{start}..HEAD"


def fixture_41_the_runtime_seat_inside_the_runtime(repo: Path) -> str:
    """The microscope name committing runtime code is admitted.

    microscope_runtime/ sits in the microscope boundary (plan.md 15) and one
    name, `microscope`, commits all of it. A classifier that refused every
    runtime path to everyone would refuse this commit.
    """
    start = base(repo)
    write(repo, "microscope_runtime/src/operator.py", "VALUE = 1\n")
    commit(repo, "the microscope writes its run engine", "microscope_runtime", seat="microscope")
    return f"{start}..HEAD"

def fixture_35_the_design_and_runtime_folders_are_one_boundary(repo: Path) -> str:
    """One commit into microscope_agent/ and microscope_runtime/ is one boundary.

    plan.md 15 chose a narrowing over a new boundary, so the runtime's move --
    renames out of microscope_agent/ into microscope_runtime/, in one commit
    so git sees renames -- must pass check 35. Check 41 then decides whose it
    is, by the committer's paths.
    """
    start = base(repo)
    write(repo, "microscope_agent/src/run_lock.py", "VALUE = 1\n")
    write(repo, "microscope_runtime/src/operator.py", "VALUE = 1\n")
    commit(repo, "one commit across the microscope's two folders",
           "microscope_agent", "microscope_runtime", seat="microscope")
    return f"{start}..HEAD"


def fixture_35_one_commit_into_the_runtime_and_another_agent(repo: Path) -> str:
    """One commit writing into microscope_runtime/ and simulation_agent/ at once.

    Until the classifier knew microscope_runtime/, its paths were
    `unattributable`, which check 35 does not count, so this read as one
    boundary and passed. The runtime is the microscope's, so it is two.
    """
    start = base(repo)
    write(repo, "microscope_runtime/src/operator.py", "VALUE = 1\n")
    write(repo, "simulation_agent/src/engine.py", "VALUE = 1\n")
    commit(repo, "one commit, the runtime and another agent",
           "microscope_runtime", "simulation_agent", seat="microscope")
    return f"{start}..HEAD"


def fixture_01_an_artifact_in_a_tree_without_cards_is_judged(repo: Path) -> str:
    """Check 1 judges an artifact when no card is present (2026-10-22).

    Check 1 once returned N/A ("no cards found") before it reached its artifact
    loop, so a tree holding an artifact and no card had none of them
    schema-checked. The live tree always holds cards and a rejected group is
    judged together with every other fixture, so neither can show the case.
    Only a built tree with every card taken out can. The examples are removed
    in a commit of their own, and then a lint report carrying a value is added.
    """
    base(repo)
    shutil.rmtree(repo / "contracts" / "examples")
    start = commit(repo, "the copied examples, and every card with them, out", "contracts", seat="design")
    write(repo, "librarian_agent/queries/lint-20261103.json",
          _kb_lint(past_valid_until=[{"entry_id": "e4", "valid_until": "2026-10-01", "value": 0.108}]))
    commit(repo, "a lint report carrying a value, in a tree with no card", "librarian_agent/queries",
           seat="librarian")
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
           "microscope_agent", seat="microscope")
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
           "microscope_agent", seat="microscope")
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
    run(repo, "commit", "-q", "--no-verify", "-m", "settings", seat="design")
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
    run(repo, "commit", "-q", "--no-verify", "-m", "settings", seat="design")
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
           "contracts/seats.json", seat="design")

    write(repo, "README.md", "# fixture, and a root file the classifier knows\n")
    commit(repo, "a root file both lists carry", "README.md", seat="design")

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
           "contracts/validate.py", seat="design")
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
           ".gitignore", seat="design")
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
    sha = commit(repo, "plant", "librarian_agent", "microscope_agent", seat="microscope")
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
    commit(repo, message, "contracts/seats.json", seat="design")
    return f"{start}..HEAD"


def fixture_84_two_seats_share_one_committer_email(repo: Path) -> str:
    """Two seats, one committer email. Measured in a scratch copy before this
    check was asked for: the gate passed it and check 41 then handed one seat's
    commits to the other, because a seat is identified by its email."""
    return _registry_with(repo, {"seat": "simulation", "committer_email":
                                 "simulation@seat.invalid", "owns": ["simulation_agent"]},
                          "a second entry reusing an email already registered")


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
    sha = commit(repo, "plant", "microscope_agent", "contracts", seat="microscope")
    return f"{head}..{sha}"


def _guides_repo(repo: Path, store: str, exports: str, footers: list[str | None], message: str) -> str:
    """A store with an index, one export and one guide per footer, for check 87.

    The index and the export carry nothing but the version the check reads.
    Other checks will object to a store that thin, and they are allowed to:
    the row counts check 87's verdict alone, the same tolerance a group folder
    has.
    """
    start = base(repo)
    kb = "librarian_agent/kb"
    write(repo, f"{kb}/index.json", {"schema_version": 1, "kb_version": store, "entry_count": 0,
                                     "entries": {}, "handles": {}})
    write(repo, f"{kb}/exports/snapshot_microscope_agent.json", {"agent": "microscope_agent", "kb_version": exports,
                                                                 "entry_count": 0, "entries": {}})
    for i, v in enumerate(footers):
        tail = (f"<sub>Generated from the knowledge store at {v}. Do not edit by hand: correct the store "
                f"and regenerate.</sub>\n") if v else "Edited by hand, and the footer went with it.\n"
        write(repo, f"{kb}/guides/safety_device_{i}.md", f"# Device {i}\n\nWhat the manufacturer warns about.\n\n{tail}")
    commit(repo, message, kb, seat="librarian")
    return f"{start}..HEAD"


def fixture_87_a_publish_that_left_the_guides_behind(repo: Path) -> str:
    """The shape of 2026-09-29: the store and its export both moved, the guides
    did not. One guide of two is current. The row matches the behind-both
    wording and the trailing guide's path as one string, so only that finding
    can satisfy it -- the right guide, for the right reason."""
    return _guides_repo(repo, "kbv-bbbbbbbbbbbb", "kbv-bbbbbbbbbbbb", ["kbv-bbbbbbbbbbbb", "kbv-aaaaaaaaaaaa"],
                        "a publish that regenerated one guide of two")


def fixture_87_a_guide_with_no_footer(repo: Path) -> str:
    """A page that cannot say which store it shows, which is what a hand edit
    most often leaves behind."""
    return _guides_repo(repo, "kbv-bbbbbbbbbbbb", "kbv-bbbbbbbbbbbb", [None],
                        "a guide edited by hand")


def fixture_87_guides_at_the_published_version_while_the_store_moved(repo: Path) -> str:
    """Entries committed between publishes move the index and not the export,
    and the guides stay at what was published. That is publishing working, and
    it has to pass: refusing it would make every per-paper commit of task 039
    fail its own gate."""
    return _guides_repo(repo, "kbv-cccccccccccc", "kbv-bbbbbbbbbbbb", ["kbv-bbbbbbbbbbbb"],
                        "an entry committed after the last publish")


def fixture_87_guides_regenerated_before_the_publish(repo: Path) -> str:
    """The house order before 2026-09-29: `aa34700` regenerated the guides in
    its content commit and `b7dcc9b` published after it. Between the two the
    guides name the store's own version and the export is behind. It has to
    pass, or the order that was always right is refused."""
    return _guides_repo(repo, "kbv-cccccccccccc", "kbv-bbbbbbbbbbbb", ["kbv-cccccccccccc"],
                        "entries and their guides, committed before the publish")


def _wiki_repo(repo: Path, store: str, exports: str, footers: list[str], message: str,
               wiki_map: dict | None = None) -> str:
    """A store with an index, one export and one wiki page per footer line, for
    check 87's wiki half (librarian task 054). No safety guide at all, so the
    pages are judged on their own and a guide cannot satisfy a row.
    `footers` are whole last lines, so a row can plant the wrong form.
    `wiki_map`, when given, is written as kb/wiki/map.json (task 060)."""
    start = base(repo)
    kb = "librarian_agent/kb"
    write(repo, f"{kb}/index.json", {"schema_version": 1, "kb_version": store, "entry_count": 0,
                                     "entries": {}, "handles": {}})
    write(repo, f"{kb}/exports/snapshot_microscope_agent.json", {"agent": "microscope_agent", "kb_version": exports,
                                                                 "entry_count": 0, "entries": {}})
    for i, line in enumerate(footers):
        write(repo, f"{kb}/wiki/device_dev{i}.md",
              f"# Device {i}\n\nGenerated from the store; cite the entries, as `kb:<entry_id>`, not this page.\n\n"
              f"{line}\n")
    if wiki_map is not None:
        write(repo, f"{kb}/wiki/map.json", wiki_map)
    commit(repo, message, kb, seat="librarian")
    return f"{start}..HEAD"


def _wiki_footer(v: str) -> str:
    return f"Generated from the knowledge store at {v}. Do not edit by hand: correct the store and regenerate."


def _wiki_map(v: str, footer_v: str | None = None, node: dict | None = None) -> dict:
    """A kb_map as task 060 shapes it: one page node, one entry node, one edge."""
    return {"artifact": "kb_map", "schema_version": "0.1", "kb_version": v,
            "footer": _wiki_footer(footer_v or v),
            "nodes": [{"id": "page:device_dev0", "kind": "device", "page": "device_dev0.md",
                       "coverage": {"E1": 0, "E2": 0, "E3": 1, "E4": 0, "E5": 0}, "disputed": 0},
                      node or {"id": "entry:e1", "kind": "entry", "grade": "E3", "source": "spec:x",
                               "status": "current"}],
            "edges": [{"type": "about", "from": "entry:e1", "to": "page:device_dev0", "stated_by": "e1"}],
            "dangling": []}


def fixture_87_a_publish_that_left_the_map_behind(repo: Path) -> str:
    """The pages were regenerated at the publish and the map was not."""
    return _wiki_repo(repo, "kbv-bbbbbbbbbbbb", "kbv-bbbbbbbbbbbb", [_wiki_footer("kbv-bbbbbbbbbbbb")],
                      "a publish that regenerated the pages and not the map",
                      wiki_map=_wiki_map("kbv-aaaaaaaaaaaa"))


def fixture_87_a_map_whose_footer_names_another_store(repo: Path) -> str:
    """kb_version current, footer from an older render: a hand edit of one
    field, so the map cannot say which store it shows."""
    return _wiki_repo(repo, "kbv-bbbbbbbbbbbb", "kbv-bbbbbbbbbbbb", [_wiki_footer("kbv-bbbbbbbbbbbb")],
                      "a map whose version field was bumped by hand",
                      wiki_map=_wiki_map("kbv-bbbbbbbbbbbb", footer_v="kbv-aaaaaaaaaaaa"))


def fixture_87_a_map_carrying_a_value(repo: Path) -> str:
    """An entry node with its number on it: shown on the map, the number is
    away from the page that puts its provenance beside it."""
    return _wiki_repo(repo, "kbv-bbbbbbbbbbbb", "kbv-bbbbbbbbbbbb", [_wiki_footer("kbv-bbbbbbbbbbbb")],
                      "a map node carrying the entry's value",
                      wiki_map=_wiki_map("kbv-bbbbbbbbbbbb",
                                         node={"id": "entry:e1", "kind": "entry", "grade": "E3", "source": "spec:x",
                                               "status": "current", "value": 1.15}))


def fixture_87_map_at_the_published_version_while_the_store_moved(repo: Path) -> str:
    """Pages and map left at what was published while an entry moved the
    index: publishing working, and it has to pass."""
    return _wiki_repo(repo, "kbv-cccccccccccc", "kbv-bbbbbbbbbbbb", [_wiki_footer("kbv-bbbbbbbbbbbb")],
                      "an entry committed after the last publish, with the wiki and map at the published version",
                      wiki_map=_wiki_map("kbv-bbbbbbbbbbbb"))


def fixture_01_a_map_entry_node_without_its_grade(repo: Path) -> str:
    """An entry drawn on the map with no grade beside it: the console would
    show a relation whose provenance it cannot say. Current in every other
    respect, so check 87 passes it and only the schema refuses it."""
    return _wiki_repo(repo, "kbv-bbbbbbbbbbbb", "kbv-bbbbbbbbbbbb", [_wiki_footer("kbv-bbbbbbbbbbbb")],
                      "a map entry node without its grade",
                      wiki_map=_wiki_map("kbv-bbbbbbbbbbbb",
                                         node={"id": "entry:e1", "kind": "entry", "source": "spec:x",
                                               "status": "current"}))


def _kb_lint(**over) -> dict:
    """A kb_lint report as task 065 shapes it: one open conflict pair, one
    unfiled entry, nothing else found."""
    body = {"artifact": "kb_lint", "schema_version": "0.1", "kb_version": "kbv-bbbbbbbbbbbb",
            "run_at": "2026-11-03T23:50:00-08:00", "run_by": "librarian-20261007-1",
            "trigger": "publish", "query_log_lines": 0,
            "unresolved_relations": [{"entry_id": "e1", "field": "conflict_with", "names": "e2",
                                      "problem": "open_pair"}],
            "past_valid_until": [], "unfiled": ["e3"], "unpaged_names": [], "repeated_gaps": []}
    body.update(over)
    return body


def fixture_01_a_lint_report_that_conforms(repo: Path) -> str:
    """The librarian's standing lint (D-20261103-office-11), as its tool will
    write it beside the query log."""
    start = base(repo)
    write(repo, "librarian_agent/queries/lint-20261103.json", _kb_lint())
    commit(repo, "a lint report", "librarian_agent/queries", seat="librarian")
    return f"{start}..HEAD"


def fixture_01_a_lint_report_carrying_an_entry_value(repo: Path) -> str:
    """A lint finding that copies the entry's number into the report: the
    report would become a second place a value lives. Only the schema refuses it."""
    start = base(repo)
    write(repo, "librarian_agent/queries/lint-20261103.json",
          _kb_lint(past_valid_until=[{"entry_id": "e4", "valid_until": "2026-10-01", "value": 0.108}]))
    commit(repo, "a lint report carrying a value", "librarian_agent/queries", seat="librarian")
    return f"{start}..HEAD"


def _skills_tool(repo: Path):
    """The skill table's tool, loaded from the built repository's own copy."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_fixture_skills_tool", repo / "contracts" / "tools" / "skills.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render_skill_pages(repo: Path) -> None:
    """Write what the table renders for the microscope: its skill pages and its one dispatcher skill."""
    tool = _skills_tool(repo)
    for rel, text in tool.generated(tool.load(repo)).items():
        if rel.startswith("microscope_agent/"):
            write(repo, rel, text)


def fixture_99_the_skill_table_and_its_generated_pages(repo: Path) -> str:
    """The skill table as committed (plan.md 4.5.2.2), with the pages and the
    one Claude Code skill it renders for the microscope.

    Three rows read this one repository. Check 1 judges the real table base
    copies. Check 13 sees `.claude/skills/run-skills/SKILL.md`, four folders
    inside an agent and one deeper than this repository's own limit, and
    passes it because the layout is Claude Code's. Check 99 finds the pages
    equal to what the table renders. Each was watched on 2026-11-11: without
    the `.claude` exemption the check 13 row stops answering; without the
    ARTIFACT_SCHEMA line the check 1 row does; and with check 99 taken out of
    CHECKS all four of its rows do.
    """
    start = base(repo)
    _render_skill_pages(repo)
    commit(repo, "the generated skill pages", "microscope_agent/.claude", seat="design")
    return f"{start}..HEAD"


def fixture_01_a_skill_manifest_naming_no_code(repo: Path) -> str:
    """A manifest with no `entry`: a skill declared with no code behind it.
    The table is the record of which code computes a bound, so this would
    leave a session told to run nothing, and a model to fill the gap by hand.
    Only the schema refuses it."""
    start = base(repo)
    path = repo / "contracts" / "skills.json"
    table = json.loads(path.read_text(encoding="utf-8"))
    del table["planned"][0]["entry"]
    write(repo, "contracts/skills.json", table)
    commit(repo, "a manifest with no entry", "contracts", seat="design")
    return f"{start}..HEAD"


def fixture_99_a_skill_page_edited_by_hand(repo: Path) -> str:
    """A generated page that no longer says what the table says. A session
    reads the page, so an edited page is a second, unreviewed table."""
    start = base(repo)
    _render_skill_pages(repo)
    page = "microscope_agent/.claude/skill-docs/camera_blur_ceiling_v1.md"
    write(repo, page, (repo / page).read_text(encoding="utf-8") + "\nCompute it by hand when the dispatcher is slow.\n")
    commit(repo, "the pages, one edited by hand", "microscope_agent/.claude", seat="design")
    return f"{start}..HEAD"


def fixture_99_a_pinned_source_that_changed(repo: Path) -> str:
    """A skill pinned to a store entry whose bytes then changed. The skill's
    code implements what the entry said when it was pinned, so a changed
    entry must be caught at commit -- it is, here, and never by refusing a run."""
    start = base(repo)
    path = repo / "contracts" / "skills.json"
    table = json.loads(path.read_text(encoding="utf-8"))
    entry = table["planned"][0]["source"]["entry"]
    table["planned"][0]["source"]["sha256"] = "0" * 64
    write(repo, "contracts/skills.json", table)
    commit(repo, "a manifest pinned to an entry", "contracts", seat="design")
    write(repo, f"librarian_agent/kb/entries/{entry}.json", {"entry_id": entry, "claim": "the formula, revised"})
    commit(repo, "the entry, changed after the pin", "librarian_agent/kb", seat="librarian")
    return f"{start}..HEAD"


def fixture_99_a_skill_file_with_no_manifest(repo: Path) -> str:
    """Code under src/skills/ that the table does not name. The dispatcher
    runs only what the table declares, so an undeclared file is either dead
    or run by hand, and neither is a skill."""
    start = base(repo)
    write(repo, "microscope_agent/src/skills/quick_estimate_v1.py", "def bound(inputs):\n    return {}\n")
    commit(repo, "a skill file nobody declared", "microscope_agent/src", seat="microscope")
    return f"{start}..HEAD"


def fixture_99_a_suggestion_for_a_safety_candidate(repo: Path) -> str:
    """A row that suggests leaving a safety candidate out. A candidate that
    rests on the safety policy is always used, and no suggestion and no fixed
    decision may say otherwise: a suggestion a model reads is a nudge, and a
    model makes no safety decision."""
    start = base(repo)
    path = repo / "contracts" / "skills.json"
    table = json.loads(path.read_text(encoding="utf-8"))
    table["rows"][0]["suggestions"].append(
        {"ref": "legacy:power_within_safety", "verdict": "not_applied",
         "why": "the trap is run far below any power that could approach the limit"})
    write(repo, "contracts/skills.json", table)
    commit(repo, "a suggestion to drop a safety candidate", "contracts", seat="design")
    return f"{start}..HEAD"


def _skill_runs(**over) -> dict:
    """A run sheet as the dispatcher writes it: one candidate the model chose to use, which ran."""
    ref = "drag_parallel_to_wall@v1"
    body = {
        "artifact": "skill_runs", "schema_version": "0.1", "question": "mic-20261111-001", "revision": 1,
        "config": "transmitted", "agent": "microscope_agent", "table_sha256": "a" * 64,
        "skills_considered": [{"ref": ref, "decided_by": "model", "verdict": "used",
                               "why": "The drag at each height is what this question measures."}],
        "planned_missing": [],
        "incomplete_because": [],
        "runs": [{"ref": ref, "verdict": "ran",
                  "inputs": {"bead_radius": "kb:tracer_diameter_measured", "viscosity": "kb:water_viscosity_293k",
                             "bead_centre_height": "bead_height_from_nominal_focus@v1:bead_centre_height"},
                  "outputs": [{"name": "drag_coefficient", "side": "value", "value": 0.05, "unit": "pN*s/um",
                               "source": f"computed:{ref}", "grade": "E4", "value_kind": "computed",
                               "basis": {"skill": ref, "inputs": {"bead_radius": "kb:tracer_diameter_measured"}}}]}],
    }
    body.update(over)
    return body


def fixture_01_a_run_sheet_that_conforms(repo: Path) -> str:
    """The dispatcher's run sheet, in the question's folder."""
    start = base(repo)
    write(repo, "microscope_agent/questions/mic-20261111-001/v1_skill_runs_transmitted.json", _skill_runs())
    commit(repo, "a run sheet", "microscope_agent/questions", seat="microscope")
    return f"{start}..HEAD"


def fixture_01_a_run_sheet_dropping_a_safety_candidate(repo: Path) -> str:
    """A sheet in which a candidate decided by code is not applied. Code
    decides only the candidates that rest on the safety policy, and those are
    always used: a model makes no safety decision. Only the schema refuses it."""
    start = base(repo)
    sheet = _skill_runs(skills_considered=[{"ref": "legacy:power_within_safety", "decided_by": "code",
                                            "verdict": "not_applied",
                                            "why": "the plan stays far below any power that could matter"}],
                        runs=[])
    write(repo, "microscope_agent/questions/mic-20261111-001/v1_skill_runs_transmitted.json", sheet)
    commit(repo, "a run sheet that drops a safety candidate", "microscope_agent/questions", seat="microscope")
    return f"{start}..HEAD"


def fixture_01_a_run_sheet_with_a_choice_and_no_reason(repo: Path) -> str:
    """A sheet in which the model marked a candidate not applied and gave no
    reason. The model may choose; it may not choose silently, because the
    reason is the only thing a person can check. Only the schema refuses it."""
    start = base(repo)
    sheet = _skill_runs(skills_considered=[{"ref": "legacy:heating_budget", "decided_by": "model",
                                            "verdict": "not_applied"}],
                        runs=[])
    write(repo, "microscope_agent/questions/mic-20261111-001/v1_skill_runs_transmitted.json", sheet)
    commit(repo, "a run sheet with a choice and no reason", "microscope_agent/questions", seat="microscope")
    return f"{start}..HEAD"


def fixture_25_a_card_citing_a_wiki_page(repo: Path) -> str:
    """A card whose kb_ref names a wiki page instead of an entry.

    The person's decision of 2026-11-03 (D-20261103-office-11 item 4) makes
    kb/wiki and kb/guides a generated reading layer that no card may cite.
    No check of its own enforces that, because none is needed: a card reaches
    the store only through kb_refs and kb: sources, both resolve against the
    index's entries, and a page is never an entry. This row is the evidence
    that the structural answer holds -- the page sits in the store, its stem
    is the cited id, and the citation is refused as naming nothing.
    """
    start = base(repo)
    kb = "librarian_agent/kb"
    write(repo, f"{kb}/entries/e1.json", {"id": "e1"})
    write(repo, f"{kb}/index.json", {"schema_version": 1, "kb_version": "kbv-bbbbbbbbbbbb", "entry_count": 1,
                                     "entries": {"e1": {"file": "entries/e1.json", "grade": "E3"}},
                                     "handles": {}})
    write(repo, f"{kb}/wiki/device_laser_combiner.md",
          "# laser_combiner\n\nWhat the store holds about it [e1].\n\n"
          "<sub>Generated from the knowledge store at kbv-bbbbbbbbbbbb. Do not edit by hand: correct the store "
          "and regenerate.</sub>\n")
    commit(repo, "a store with one entry and one page", kb, seat="librarian")
    ref = {"entry_id": "device_laser_combiner", "grade": "E3", "kb_version": "kbv-bbbbbbbbbbbb"}
    card = dict(_decision_card([_KAPPA], [], kb_refs=[ref]), kb_version="kbv-bbbbbbbbbbbb")
    rel = "simulation_agent/questions/sim-20260923-901/axis_bd_overdamped_a2.json"
    write(repo, rel, card)
    commit(repo, "a card citing the page", rel, seat="simulation")
    return f"{start}..HEAD"


def fixture_87_a_publish_that_left_the_wiki_behind(repo: Path) -> str:
    """The guides' 2026-09-29 shape, on a wiki page: the store and its export
    moved, and one page of two was not regenerated."""
    return _wiki_repo(repo, "kbv-bbbbbbbbbbbb", "kbv-bbbbbbbbbbbb",
                      [_wiki_footer("kbv-bbbbbbbbbbbb"), _wiki_footer("kbv-aaaaaaaaaaaa")],
                      "a publish that regenerated one wiki page of two")


def fixture_87_a_wiki_page_footed_like_a_guide(repo: Path) -> str:
    """The right version in the wrong form: the guides' footer, <sub> and all.
    A guide may carry it; a wiki page may not, because the console reads the
    last line and shows no HTML."""
    return _wiki_repo(repo, "kbv-bbbbbbbbbbbb", "kbv-bbbbbbbbbbbb",
                      [f"<sub>{_wiki_footer('kbv-bbbbbbbbbbbb')}</sub>"],
                      "a wiki page footed the guides' way")


def fixture_87_wiki_at_the_published_version_while_the_store_moved(repo: Path) -> str:
    """Pages left at what was published while entries move the index: that is
    publishing working, as for the guides, and it has to pass."""
    return _wiki_repo(repo, "kbv-cccccccccccc", "kbv-bbbbbbbbbbbb", [_wiki_footer("kbv-bbbbbbbbbbbb")],
                      "an entry committed after the last publish, with the wiki at the published version")


def _real_permit(repo: Path, extra: dict, message: str) -> str:
    """A scope approval in an agent's approvals/, where real permits live.

    Here because a rejected card cannot be one: every file under
    contracts/examples/ is an example to check 19 now, so a fixture for how a
    REAL permit is judged has to be a tree with one outside that folder.
    """
    start = base(repo)
    card = {"card": "scope_approval", "schema_version": "0.1", "id": "scope-fixture-real-permit",
            "qid": "mic-20260917-001", "thread": "solo-mic-20260917-001", "round": 0, "revision": 1,
            "author": "human", "created_at": "2026-09-17T09:05:00Z", "status": "APPROVED",
            "agent": "microscope_agent", "config": "brightfield",
            "range": [{"parameter": "exposure_time", "unit": "s", "max": 0.05, "basis": ["exposure_time_max"]}],
            "devices": ["camera1"], "max_runs": 20, "runs_used": 1, "max_grade": "E3", "voided": None,
            "approved_by": "kyuhwan", "approved_at": "2026-09-17T09:05:00Z",
            "numbers": [{"name": "exposure_time_max", "value": 0.05, "unit": "s", "source": "assumed:a_exp",
                         "grade": "E5", "precision": "order_of_magnitude"}],
            "assumptions": [{"rationale_id": "a_exp", "statement": "fixture", "numbers": ["exposure_time_max"],
                             "falsifier": "fixture"}],
            "kb_refs": [], "degraded": ["librarian_agent"]}
    card.update(extra)
    write(repo, "microscope_agent/approvals/scope-fixture-real-permit.json", card)
    commit(repo, message, "microscope_agent", seat="microscope")
    return f"{start}..HEAD"


def fixture_19_a_real_permit_declaring_an_example_instant(repo: Path) -> str:
    """HP-007 (2026-10-17) lets an example under contracts/examples/ choose the
    instant it is judged at. A real permit that could do the same would have
    no clock at all, so the field on one is refused -- with a window that is
    still open by the wall clock, so nothing but the field can fail it."""
    return _real_permit(repo, {"valid_until": "2099-01-01T00:00:00Z",
                               "example_judged_at": "2026-09-17T09:05:00Z"},
                        "a real permit that declares the instant it is judged at")


def fixture_19_a_real_permit_is_judged_by_the_wall_clock(repo: Path) -> str:
    """The other side of HP-007: a real permit whose window has closed is still
    refused, although its approved_at -- an example's fallback instant -- lies
    inside the window. A check that judged every card the example's way would
    pass this one."""
    return _real_permit(repo, {"valid_until": "2026-09-18T00:00:00Z"},
                        "a real permit whose window closed by the clock")


def fixture_79_a_runtime_status_file_forced_into_a_commit(repo: Path) -> str:
    """The runtime's idle status file, committed (2026-10-22, plan.md 15.1 item 3).

    microscope_runtime/.runtime_status/ is in SKIP_DIRS, so the walk never
    enters it and no check judges what is in it. The file there is volatile
    and never a record; .gitignore hides it, and a commit carries it only when
    someone forces it. This forces it, with git add -f, as the runtime seat,
    whose boundary and paths otherwise cover the folder.
    """
    start = base(repo)
    write(repo, "microscope_runtime/.runtime_status/idle_status.json", {"artifact": "idle_status"})
    run(repo, "add", "-f", "--", "microscope_runtime/.runtime_status/idle_status.json")
    run(repo, "commit", "-q", "--no-verify", "-m", "the idle status file, forced in", seat="microscope")
    return f"{start}..HEAD"


def fixture_41_the_runtime_seat_commits_an_approval(repo: Path) -> str:
    """The runtime seat commits a plan approval (2026-10-22, plan.md 15.1 item 4).

    Its boundary and its paths both cover microscope_runtime/, so until this
    day check 41 passed it. Only the person writes and commits an approval.
    """
    start = base(repo)
    write(repo, "microscope_runtime/approvals/appr-x.json", {"card": "plan_approval"})
    commit(repo, "a seat commits the person's approval", "microscope_runtime/approvals/appr-x.json",
           seat="microscope")
    return f"{start}..HEAD"


def fixture_41_a_planning_seat_commits_the_safety_policy(repo: Path) -> str:
    """A microscope seat commits envelope/safety.json in its own tree."""
    start = base(repo)
    write(repo, "microscope_agent/envelope/safety.json", {"limits": {}})
    commit(repo, "a seat commits the person's safety policy", "microscope_agent/envelope/safety.json",
           seat="microscope")
    return f"{start}..HEAD"


def fixture_41_the_person_commits_an_approval(repo: Path) -> str:
    """The person, under the opt-in human seat, commits an approval: not refused."""
    start = base(repo)
    write(repo, "microscope_runtime/approvals/appr-x.json", {"card": "plan_approval"})
    commit(repo, "the person's approval", "microscope_runtime/approvals/appr-x.json", seat="human")
    return f"{start}..HEAD"


def _device_label_store(repo: Path, change=None) -> str:
    """Librarian card 061 (2026-10-26): a device row's Micro-Manager label is a copy of its cited entry's.

    Check 96 reads no history; it is here because its input is the store's
    own files, which a rejected group cannot carry -- a group is found through
    a card or an artifact, and the device table and the entries are neither.
    The store is built small and synthetic so the fixtures do not move when
    the real one does: a camera labelled from an entry measured here, with
    its configuration digest, and a light engine's designation labelled from
    a specification. `change(table, entries)` breaks one thing.
    """
    start = base(repo)
    entries = {
        "label_kinetix_red_read_here": {
            "entry_id": "label_kinetix_red_read_here", "source": "measured:run-20261026-001", "grade": "E1",
            "supersedes": None, "refuted_by": [],
            "identifiers": {"mm_label": "Kinetix_red", "mm_config_sha256": "a" * 64}},
        "label_aura_is_the_aura_iii": {
            "entry_id": "label_aura_is_the_aura_iii", "source": "spec:Aura III", "grade": "E3",
            "supersedes": None, "refuted_by": [], "identifiers": {"mm_device": "Aura"}},
        "label_lightengine_is_the_spectra_iii": {
            "entry_id": "label_lightengine_is_the_spectra_iii", "source": "spec:Spectra III", "grade": "E3",
            "supersedes": None, "refuted_by": [], "identifiers": {"mm_label": "LightEngine"}},
    }
    table = {
        "channels": [
            {"id": "camera_red", "mm_label": {"label": "Kinetix_red", "entry_ref": "label_kinetix_red_read_here",
                                              "config_sha256": "a" * 64}},
            {"id": "widefield_source_a"},
            {"id": "stand_ti2e", "elements": [{"id": "z_drive"}]},
        ],
        "light_engines": {"installed": [
            {"model": "Aura III 5-NII-WA", "mm_label": {"label": "Aura", "entry_ref": "label_aura_is_the_aura_iii"}},
        ]},
    }
    if change is not None:
        change(table, entries)
    kb = "librarian_agent/kb"
    for eid, e in entries.items():
        write(repo, f"{kb}/entries/{eid}.json", e)
    write(repo, f"{kb}/staging/devices.v0.json", table)
    commit(repo, "device rows labelled from the entries that hold the labels", kb, seat="librarian")
    return f"{start}..HEAD"


def _z_drive(table: dict) -> dict:
    return table["channels"][2]["elements"][0]


def fixture_96_device_labels_copied_from_their_entries(repo: Path) -> str:
    return _device_label_store(repo)


def fixture_96_a_label_cites_no_entry(repo: Path) -> str:
    return _device_label_store(repo, lambda t, e: _z_drive(t).update(
        mm_label={"label": "ZDrive", "entry_ref": "mm_label_zdrive_nowhere"}))


def fixture_96_a_label_its_entry_does_not_hold(repo: Path) -> str:
    return _device_label_store(repo, lambda t, e: _z_drive(t).update(
        mm_label={"label": "ZDrive", "entry_ref": "label_aura_is_the_aura_iii"}))


def fixture_96_a_label_from_a_refuted_entry(repo: Path) -> str:
    return _device_label_store(repo, lambda t, e: e["label_aura_is_the_aura_iii"].update(
        refuted_by=["aura_answers_under_another_label"]))


def fixture_96_a_label_from_a_superseded_entry(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        e["label_aura_read_here"] = {"entry_id": "label_aura_read_here", "source": "measured:run-20261026-002",
                                     "grade": "E1", "supersedes": "label_aura_is_the_aura_iii", "refuted_by": [],
                                     "identifiers": {"mm_label": "Aura"}}
    return _device_label_store(repo, change)


def fixture_96_one_label_on_two_rows(repo: Path) -> str:
    return _device_label_store(repo, lambda t, e: _z_drive(t).update(
        mm_label={"label": "Aura", "entry_ref": "label_aura_is_the_aura_iii"}))


def fixture_96_a_widefield_source_labelled(repo: Path) -> str:
    return _device_label_store(repo, lambda t, e: t["channels"][1].update(
        mm_label={"label": "LightEngine", "entry_ref": "label_lightengine_is_the_spectra_iii"}))


def fixture_96_a_digest_that_is_not_hex(repo: Path) -> str:
    return _device_label_store(repo, lambda t, e: t["channels"][0]["mm_label"].update(config_sha256="A" * 64))


def fixture_96_a_digest_its_entry_does_not_record(repo: Path) -> str:
    return _device_label_store(repo, lambda t, e: t["channels"][0]["mm_label"].update(config_sha256="b" * 64))


def fixture_96_a_digest_from_no_run(repo: Path) -> str:
    return _device_label_store(repo, lambda t, e: e["label_aura_is_the_aura_iii"]["identifiers"].update(
        mm_config_sha256="c" * 64))


def fixture_96_a_label_with_a_grade_of_its_own(repo: Path) -> str:
    return _device_label_store(repo, lambda t, e: t["light_engines"]["installed"][0]["mm_label"].update(
        grade="E1"))


def _binding_store(repo: Path, change=None) -> str:
    """Librarian card 062 (2026-10-27): a row's bindings and state words are copies of their cited entries.

    Check 98 reads no history; it is here for check 96's reason -- its input
    is the store's own files at a fixed path. The store is small and
    synthetic: a camera whose `Exposure` is bound from a run measured here,
    with its digest; the confocal unit's port, whose `empty` slot resolves
    from a run that acquired and lit the camera that slot reaches; the disk,
    whose word is a key of its own `states`; the branch selector, whose word
    comes only from the path table; and the confocal unit's shutter, a row no
    label warning names, whose word stands on a specification.
    `change(table, entries)` breaks one thing.
    """
    start = base(repo)
    run = "measured:run-20261027-001"

    def state(eid: str, label: str, word: str, mm_state: str, lit: list) -> dict:
        return {"entry_id": eid, "source": run, "grade": "E1", "supersedes": None, "refuted_by": [],
                "identifiers": {"mm_label": label, "path_word": word, "mm_state_label": mm_state,
                                "lit_detectors": lit}}
    entries = {
        "exposure_is_ms_on_kinetix_red": {
            "entry_id": "exposure_is_ms_on_kinetix_red", "source": run, "grade": "E1",
            "supersedes": None, "refuted_by": [],
            "identifiers": {"mm_label": "Kinetix_red", "mm_property": "Exposure", "quantity": "exposure_time",
                            "unit": "ms", "mm_config_sha256": "a" * 64}},
        "port_empty_lights_red": state("port_empty_lights_red", "CSUW1-Port", "empty", "Position-1",
                                       ["camera_red"]),
        "disk_out_lights_red": state("disk_out_lights_red", "CSUW1-Disk", "out", "Bright Field", ["camera_red"]),
        "branch_inline_lights_red": state("branch_inline_lights_red", "LAPP-Branch", "inline", "State-0",
                                          ["camera_red"]),
        "shutter_open_is_labelled_open": {
            "entry_id": "shutter_open_is_labelled_open", "source": "spec:CSU-W1", "grade": "E3",
            "supersedes": None, "refuted_by": [],
            "identifiers": {"mm_label": "CSUW1-Shutter", "path_word": "open", "mm_state_label": "Open"}},
    }
    table = {
        "channels": [
            {"id": "camera_red", "mm_label": {"label": "Kinetix_red", "entry_ref": "exposure_is_ms_on_kinetix_red"},
             "mm_bindings": [{"quantity": "exposure_time", "property": "Exposure", "unit": "ms",
                              "entry_ref": "exposure_is_ms_on_kinetix_red", "config_sha256": "a" * 64}]},
            {"id": "camera_blue"},
            {"id": "csuw1_port", "mm_label": {"label": "CSUW1-Port", "entry_ref": "port_empty_lights_red"},
             "verify_by": "acquisition", "slot_order": None,
             "slot_contents": [{"content": "empty", "reaches": ["camera_red"], "starves": ["camera_blue"]},
                               {"content": "100/0 mirror", "reaches": ["camera_blue"], "starves": ["camera_red"]}],
             "mm_states": [{"word": "empty", "state_label": "Position-1", "entry_ref": "port_empty_lights_red"}]},
            {"id": "csuw1_disk_position", "mm_label": {"label": "CSUW1-Disk", "entry_ref": "disk_out_lights_red"},
             "states": {"in": "confocal", "out": "widefield fluorescence and brightfield"},
             "mm_states": [{"word": "out", "state_label": "Bright Field", "entry_ref": "disk_out_lights_red"}]},
            {"id": "lapp_branch", "mm_label": {"label": "LAPP-Branch", "entry_ref": "branch_inline_lights_red"},
             "mm_states": [{"word": "inline", "state_label": "State-0", "entry_ref": "branch_inline_lights_red"}]},
            {"id": "csuw1_shutter", "mm_label": {"label": "CSUW1-Shutter", "entry_ref": "shutter_open_is_labelled_open"},
             "mm_states": [{"word": "open", "state_label": "Open", "entry_ref": "shutter_open_is_labelled_open"}]},
        ],
    }
    paths = {"configurations": [
        {"id": "widefield_inline", "required_selectors": {
            "csuw1_port": "the slot that reaches the camera being used", "lapp_branch": "inline"}},
        {"id": "widefield_side", "required_selectors": {"lapp_branch": "side"}},
        {"id": "confocal", "required_selectors": {"csuw1_shutter": "open"}},
    ]}
    if change is not None:
        change(table, entries)
    kb = "librarian_agent/kb"
    for eid, e in entries.items():
        write(repo, f"{kb}/entries/{eid}.json", e)
    write(repo, f"{kb}/staging/devices.v0.json", table)
    write(repo, f"{kb}/staging/optical_paths.v0.json", paths)
    commit(repo, "device rows carry the bindings and state words their entries hold", kb, seat="librarian")
    return f"{start}..HEAD"


def _row(table: dict, rid: str) -> dict:
    return next(r for r in table["channels"] if r.get("id") == rid)


def _binding(table: dict) -> dict:
    return _row(table, "camera_red")["mm_bindings"][0]


def _port_state(table: dict) -> dict:
    return _row(table, "csuw1_port")["mm_states"][0]


def fixture_98_bindings_and_words_copied_from_their_entries(repo: Path) -> str:
    return _binding_store(repo)


def fixture_98_a_label_alone_is_not_judged(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        for r in t["channels"]:
            r.pop("mm_bindings", None)
            r.pop("mm_states", None)
    return _binding_store(repo, change)


def fixture_98_a_binding_with_a_grade_of_its_own(repo: Path) -> str:
    return _binding_store(repo, lambda t, e: _binding(t).update(grade="E1"))


def fixture_98_a_state_word_on_a_row_with_no_label(repo: Path) -> str:
    return _binding_store(repo, lambda t, e: _row(t, "lapp_branch").pop("mm_label"))


def fixture_98_a_binding_cites_no_entry(repo: Path) -> str:
    return _binding_store(repo, lambda t, e: _binding(t).update(entry_ref="exposure_nowhere"))


def fixture_98_a_binding_its_entry_does_not_hold(repo: Path) -> str:
    return _binding_store(repo, lambda t, e: e["exposure_is_ms_on_kinetix_red"]["identifiers"].update(unit="s"))


def fixture_98_a_state_word_its_entry_does_not_hold(repo: Path) -> str:
    return _binding_store(repo, lambda t, e: _port_state(t).update(state_label="Position-2"))


def fixture_98_a_binding_from_a_refuted_entry(repo: Path) -> str:
    return _binding_store(repo, lambda t, e: e["exposure_is_ms_on_kinetix_red"].update(
        refuted_by=["exposure_reads_in_seconds"]))


def fixture_98_a_state_word_from_a_superseded_entry(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        e["port_empty_lights_red_again"] = dict(copy.deepcopy(e["port_empty_lights_red"]),
                                                entry_id="port_empty_lights_red_again",
                                                supersedes="port_empty_lights_red")
    return _binding_store(repo, change)


def fixture_98_a_binding_on_an_unregistered_quantity(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        _binding(t).update(quantity="exposure_duration")
        e["exposure_is_ms_on_kinetix_red"]["identifiers"].update(quantity="exposure_duration")
    return _binding_store(repo, change)


def fixture_98_frame_count_bound(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        e["frames_on_kinetix_red"] = {
            "entry_id": "frames_on_kinetix_red", "source": "spec:Kinetix", "grade": "E3", "supersedes": None,
            "refuted_by": [], "identifiers": {"mm_label": "Kinetix_red", "mm_property": "Frames",
                                              "quantity": "frame_count", "unit": "1"}}
        _row(t, "camera_red")["mm_bindings"].append({"quantity": "frame_count", "property": "Frames", "unit": "1",
                                                     "entry_ref": "frames_on_kinetix_red"})
    return _binding_store(repo, change)


def fixture_98_a_unit_units_json_lacks(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        _binding(t).update(unit="msec")
        e["exposure_is_ms_on_kinetix_red"]["identifiers"].update(unit="msec")
    return _binding_store(repo, change)


def fixture_98_a_fraction_of_scale_in_unit_one(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        e["green_intensity_on_the_engine"] = {
            "entry_id": "green_intensity_on_the_engine", "source": "spec:Spectra III", "grade": "E3",
            "supersedes": None, "refuted_by": [],
            "identifiers": {"mm_label": "Kinetix_red", "mm_property": "GREEN_Intensity",
                            "quantity": "illumination_power", "unit": "1"}}
        _row(t, "camera_red")["mm_bindings"].append({"quantity": "illumination_power", "property": "GREEN_Intensity",
                                                     "unit": "1", "entry_ref": "green_intensity_on_the_engine"})
    return _binding_store(repo, change)


def fixture_98_one_quantity_into_two_properties(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        e["exposure_is_also_trigger_width"] = {
            "entry_id": "exposure_is_also_trigger_width", "source": "spec:Kinetix", "grade": "E3",
            "supersedes": None, "refuted_by": [],
            "identifiers": {"mm_label": "Kinetix_red", "mm_property": "TriggerWidth",
                            "quantity": "exposure_time", "unit": "ms"}}
        _row(t, "camera_red")["mm_bindings"].append({"quantity": "exposure_time", "property": "TriggerWidth",
                                                     "unit": "ms", "entry_ref": "exposure_is_also_trigger_width"})
    return _binding_store(repo, change)


def fixture_98_two_words_for_one_state_label(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        e["disk_in_is_bright_field"] = {
            "entry_id": "disk_in_is_bright_field", "source": "measured:run-20261027-001", "grade": "E1",
            "supersedes": None, "refuted_by": [],
            "identifiers": {"mm_label": "CSUW1-Disk", "path_word": "in", "mm_state_label": "Bright Field",
                            "lit_detectors": ["camera_red"]}}
        _row(t, "csuw1_disk_position")["mm_states"].append({"word": "in", "state_label": "Bright Field",
                                                            "entry_ref": "disk_in_is_bright_field"})
    return _binding_store(repo, change)


def fixture_98_a_word_the_path_table_never_writes(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        _row(t, "lapp_branch")["mm_states"][0].update(word="straight")
        e["branch_inline_lights_red"]["identifiers"].update(path_word="straight")
    return _binding_store(repo, change)


def fixture_98_a_port_word_read_off_a_label(repo: Path) -> str:
    return _binding_store(repo, lambda t, e: e["port_empty_lights_red"].update(
        source="prior_run:agentic-microscope@34a432c", grade="E3"))


def fixture_98_a_branch_word_from_a_run_that_lit_nothing(repo: Path) -> str:
    return _binding_store(repo, lambda t, e: e["branch_inline_lights_red"]["identifiers"].pop("lit_detectors"))


def fixture_98_a_branch_word_lighting_a_detector_the_table_lacks(repo: Path) -> str:
    return _binding_store(repo, lambda t, e: e["branch_inline_lights_red"]["identifiers"].update(
        lit_detectors=["camera_green"]))


def fixture_98_a_port_word_whose_run_lit_the_other_camera(repo: Path) -> str:
    return _binding_store(repo, lambda t, e: e["port_empty_lights_red"]["identifiers"].update(
        lit_detectors=["camera_blue"]))


def fixture_98_a_binding_digest_that_is_not_hex(repo: Path) -> str:
    return _binding_store(repo, lambda t, e: _binding(t).update(config_sha256="A" * 64))


def fixture_98_a_binding_digest_its_entry_does_not_record(repo: Path) -> str:
    return _binding_store(repo, lambda t, e: _binding(t).update(config_sha256="b" * 64))


def _line_store(repo: Path, change=None) -> str:
    """Librarian card 064 (2026-10-27): a binding's line and step, and a calibration's conversion.

    `_binding_store` plus a light engine bound one line at a time: GREEN
    with a step read off the device and a calibration that converts watts
    into its per-mille setting, and NIR with no step read and no calibration,
    which is a binding nothing is written through. `change(table, entries)`
    breaks one thing.
    """
    run, cal = "measured:run-20261027-002", "measured:run-20261027-003"

    def line(eid: str, name: str, numbers: list) -> dict:
        return {"entry_id": eid, "source": run, "grade": "E1", "supersedes": None, "refuted_by": [],
                "numbers": numbers,
                "identifiers": {"mm_label": "Spectra", "mm_property": f"{name}_Intensity",
                                "quantity": "illumination_power", "unit": "permille", "line": name}}

    def add(t: dict, e: dict) -> None:
        e["spectra_green_intensity_is_permille"] = line(
            "spectra_green_intensity_is_permille", "GREEN",
            [{"name": "property_step", "value": 1, "unit": "permille", "source": run, "grade": "E1"}])
        e["spectra_nir_intensity_is_permille"] = line("spectra_nir_intensity_is_permille", "NIR", [])
        e["spectra_green_power_calibration"] = {
            "entry_id": "spectra_green_power_calibration", "kind": "calibration",
            "source": "calibration:cal-20261027-001", "grade": "E2", "supersedes": None, "refuted_by": [],
            "identifiers": {"mm_label": "Spectra", "mm_property": "GREEN_Intensity",
                            "quantity": "illumination_power", "line": "GREEN"},
            "validity": {"illumination_power": {"min": 0.0005, "max": 0.005, "unit": "W"}},
            "valid_until": {"event": "the next power calibration of the GREEN line"},
            "conversion": {
                "direction": "physical_to_control", "rule": "piecewise_linear_within_points",
                "physical": {"quantity": "illumination_power", "unit": "W"}, "control": {"unit": "permille"},
                "points": [{"physical": {"value": x, "unit": "W"}, "control": {"value": y, "unit": "permille"},
                            "source": cal} for x, y in ((0.0005, 20), (0.002, 300), (0.005, 1000))]}}
        t["light_engines"] = {"installed": [{
            "id": "spectra_iii", "mm_label": {"label": "Spectra", "entry_ref": "label_spectra"},
            "mm_bindings": [
                {"quantity": "illumination_power", "property": "GREEN_Intensity", "unit": "permille",
                 "line": "GREEN", "step": {"value": 1, "unit": "permille"},
                 "entry_ref": "spectra_green_intensity_is_permille"},
                {"quantity": "illumination_power", "property": "NIR_Intensity", "unit": "permille",
                 "line": "NIR", "entry_ref": "spectra_nir_intensity_is_permille"}]}]}
        if change is not None:
            change(t, e)
    return _binding_store(repo, add)


def _green(t: dict) -> dict:
    return t["light_engines"]["installed"][0]["mm_bindings"][0]


def _conversion(e: dict) -> dict:
    return e["spectra_green_power_calibration"]["conversion"]


def fixture_98_lines_steps_and_a_conversion_copied(repo: Path) -> str:
    return _line_store(repo)


def fixture_98_a_conversion_alone_is_judged(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        for r in t["channels"] + t["light_engines"]["installed"]:
            r.pop("mm_bindings", None)
            r.pop("mm_states", None)
    return _line_store(repo, change)


def fixture_98_a_step_its_entry_does_not_hold(repo: Path) -> str:
    return _line_store(repo, lambda t, e: _green(t).update(step={"value": 10, "unit": "permille"}))


def fixture_98_a_step_nobody_read(repo: Path) -> str:
    return _line_store(repo, lambda t, e: t["light_engines"]["installed"][0]["mm_bindings"][1].update(
        step={"value": 1, "unit": "permille"}))


def fixture_98_a_step_read_and_not_copied(repo: Path) -> str:
    return _line_store(repo, lambda t, e: _green(t).pop("step"))


def fixture_98_a_step_in_another_unit(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        _green(t)["step"]["unit"] = "percent"
        e["spectra_green_intensity_is_permille"]["numbers"][0]["unit"] = "percent"
    return _line_store(repo, change)


def fixture_98_a_step_of_zero(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        _green(t)["step"]["value"] = 0
        e["spectra_green_intensity_is_permille"]["numbers"][0]["value"] = 0
    return _line_store(repo, change)


def fixture_98_a_line_its_entry_does_not_hold(repo: Path) -> str:
    return _line_store(repo, lambda t, e: e["spectra_green_intensity_is_permille"]["identifiers"].update(
        line="RED"))


def fixture_98_a_line_left_off_the_row(repo: Path) -> str:
    return _line_store(repo, lambda t, e: t["light_engines"]["installed"][0]["mm_bindings"][1].pop("line"))


def fixture_98_one_line_bound_twice(repo: Path) -> str:
    return _line_store(repo, lambda t, e: t["light_engines"]["installed"][0]["mm_bindings"][1].update(
        line="GREEN"))


def fixture_98_a_quantity_bound_on_a_line_and_without(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        t["light_engines"]["installed"][0]["mm_bindings"][1].pop("line")
        e["spectra_nir_intensity_is_permille"]["identifiers"].pop("line")
    return _line_store(repo, change)


def fixture_98_a_calibration_serving_a_binding_with_no_conversion(repo: Path) -> str:
    return _line_store(repo, lambda t, e: e["spectra_green_power_calibration"].pop("conversion"))


def fixture_98_a_conversion_on_a_claim(repo: Path) -> str:
    return _line_store(repo, lambda t, e: e["spectra_green_power_calibration"].update(kind="claim"))


def fixture_98_a_conversion_read_backwards(repo: Path) -> str:
    return _line_store(repo, lambda t, e: _conversion(e).update(direction="control_to_physical"))


def fixture_98_a_conversion_with_a_fit(repo: Path) -> str:
    return _line_store(repo, lambda t, e: _conversion(e).update(fit={"slope": 2.0e5, "intercept": -80}))


def fixture_98_a_conversion_of_another_quantity(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        _conversion(e)["physical"]["quantity"] = "exposure_time"
        e["spectra_green_power_calibration"]["validity"] = {"exposure_time": {"min": 0.0005, "max": 0.005,
                                                                              "unit": "W"}}
    return _line_store(repo, change)


def fixture_98_a_conversion_in_milliwatts(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        c = _conversion(e)
        c["physical"]["unit"] = "mW"
        for p, x in zip(c["points"], (0.5, 2, 5)):
            p["physical"] = {"value": x, "unit": "mW"}
        e["spectra_green_power_calibration"]["validity"] = {"illumination_power": {"min": 0.5, "max": 5,
                                                                                   "unit": "mW"}}
    return _line_store(repo, change)


def fixture_98_a_conversion_mixing_units(repo: Path) -> str:
    return _line_store(repo, lambda t, e: _conversion(e)["points"][1].update(
        control={"value": 30, "unit": "percent"}))


def fixture_98_a_conversion_of_one_point(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        c = _conversion(e)
        c["points"] = c["points"][:1]
        e["spectra_green_power_calibration"]["validity"]["illumination_power"]["max"] = 0.0005
    return _line_store(repo, change)


def fixture_98_a_conversion_across_a_plateau(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        c = _conversion(e)
        c["points"].insert(0, {"physical": {"value": 0.0005, "unit": "W"},
                               "control": {"value": 5, "unit": "permille"}, "source": c["points"][0]["source"]})
    return _line_store(repo, change)


def fixture_98_a_conversion_that_turns_back(repo: Path) -> str:
    return _line_store(repo, lambda t, e: _conversion(e)["points"][2]["control"].update(value=200))


def fixture_98_a_conversion_wider_than_its_validity(repo: Path) -> str:
    return _line_store(repo, lambda t, e: e["spectra_green_power_calibration"]["validity"][
        "illumination_power"].update(max=0.004))


def fixture_98_a_conversion_with_an_open_validity(repo: Path) -> str:
    return _line_store(repo, lambda t, e: e["spectra_green_power_calibration"]["validity"][
        "illumination_power"].pop("max"))


def fixture_98_a_conversion_point_from_a_specification(repo: Path) -> str:
    return _line_store(repo, lambda t, e: _conversion(e)["points"][1].update(source="spec:Spectra-III"))


def fixture_98_a_conversion_no_row_binds(repo: Path) -> str:
    return _line_store(repo, lambda t, e: e["spectra_green_power_calibration"]["identifiers"].update(
        mm_property="TEAL_Intensity"))


def fixture_98_a_conversion_into_another_unit(repo: Path) -> str:
    def change(t: dict, e: dict) -> None:
        c = _conversion(e)
        c["control"]["unit"] = "percent"
        for p in c["points"]:
            p["control"]["unit"] = "percent"
    return _line_store(repo, change)


def fixture_98_a_conversion_for_another_line(repo: Path) -> str:
    return _line_store(repo, lambda t, e: e["spectra_green_power_calibration"]["identifiers"].update(
        line="TEAL"))


def fixture_98_two_steps_for_one_property(repo: Path) -> str:
    return _line_store(repo, lambda t, e: e["spectra_green_intensity_is_permille"]["numbers"].append(
        {"name": "property_step", "value": 2, "unit": "permille", "source": "spec:Spectra-III", "grade": "E3"}))


FIXTURES = [
    (35, "FAIL", "a session writes inside one agent", fixture_35_one_commit_two_boundaries),
    (41, "FAIL", "this path is bridge's", fixture_41_seat_writes_outside_its_own),
    (41, "PENDING", "not a seat in", fixture_41_unregistered_committer),
    (35, "FAIL", "a session writes inside one agent", fixture_35_a_root_commit_in_the_range_is_judged),
    (41, "PASS", "1 commits stay inside the seat that made them", fixture_41_an_imported_history_is_not_attributed),
    (41, "PASS", "1 commits stay inside the seat that made them", fixture_41_the_runtime_seat_inside_the_runtime),
    (41, "PASS", "and 1 merges contributed nothing of their own", fixture_41_a_clean_merge_attributes_nothing),
    (41, "FAIL", "owns ['microscope_agent']; this path is design's", fixture_41_a_merge_that_adds_its_own_line_is_judged),
    (35, "PASS", "stay inside one boundary (microscope_agent)",
     fixture_35_the_design_and_runtime_folders_are_one_boundary),
    (35, "FAIL", "one commit writes into ['microscope_agent', 'simulation_agent']",
     fixture_35_one_commit_into_the_runtime_and_another_agent),
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
    (84, "FAIL", "is the committer email of 2 seats", fixture_84_two_seats_share_one_committer_email),
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
    # Matched on the branch's last words and the guide's path as one string, for
    # the reason the check 68 rows give: a phrase alone is satisfied by the
    # wrong file, and a path alone by the wrong branch.
    (87, "FAIL", "with the publish or before it [librarian_agent/kb/guides/safety_device_1.md]",
     fixture_87_a_publish_that_left_the_guides_behind),
    (87, "FAIL", "a guide is never edited by hand [librarian_agent/kb/guides/safety_device_0.md]",
     fixture_87_a_guide_with_no_footer),
    (87, "PASS", "the store has moved to kbv-cccccccccccc since",
     fixture_87_guides_at_the_published_version_while_the_store_moved),
    (87, "PASS", "at kbv-cccccccccccc, the store's own version",
     fixture_87_guides_regenerated_before_the_publish),
    # The wiki half of 87 (librarian task 054), matched on the branch's words
    # and the page's path, for the same reason as the guide rows above.
    (87, "FAIL", "commit the pages with the publish or before it [librarian_agent/kb/wiki/device_dev1.md]",
     fixture_87_a_publish_that_left_the_wiki_behind),
    (87, "FAIL", "a page is never edited by hand [librarian_agent/kb/wiki/device_dev0.md]",
     fixture_87_a_wiki_page_footed_like_a_guide),
    (87, "PASS", "1 wiki pages at kbv-bbbbbbbbbbbb, the published version",
     fixture_87_wiki_at_the_published_version_while_the_store_moved),
    # The map (librarian task 060).
    (87, "FAIL", "commit the map with the publish or before it [librarian_agent/kb/wiki/map.json]",
     fixture_87_a_publish_that_left_the_map_behind),
    (87, "FAIL", "the map is never edited by hand [librarian_agent/kb/wiki/map.json]",
     fixture_87_a_map_whose_footer_names_another_store),
    (87, "FAIL", "holds no number taken from one",
     fixture_87_a_map_carrying_a_value),
    (87, "PASS", "the map at kbv-bbbbbbbbbbbb, the published version",
     fixture_87_map_at_the_published_version_while_the_store_moved),
    # The map's schema (2026-10-27). A check 87 row reads only check 87, so a
    # map that check 1 refused passed all of the rows above; these read check 1.
    (1, "PASS", "conform to their schema",
     fixture_87_map_at_the_published_version_while_the_store_moved),
    (1, "FAIL", "'grade' is a required property [librarian_agent/kb/wiki/map.json]",
     fixture_01_a_map_entry_node_without_its_grade),
    (87, "PASS", "the map at kbv-bbbbbbbbbbbb",
     fixture_01_a_map_entry_node_without_its_grade),
    # The lint report's schema (2026-11-03, D-20261103-office-11), wired before
    # its tool exists so the first real report is not an unknown artifact.
    (25, "FAIL", "kb_ref cites 'device_laser_combiner', which the store does not have",
     fixture_25_a_card_citing_a_wiki_page),
    (1, "PASS", "conform to their schema", fixture_01_a_lint_report_that_conforms),
    (1, "FAIL", "Additional properties are not allowed ('value' was unexpected) "
                "[librarian_agent/queries/lint-20261103.json]",
     fixture_01_a_lint_report_carrying_an_entry_value),
    # The skill table and the dispatcher's run sheet (2026-11-11, plan.md
    # 4.5.2.2), each wired with its schema in one commit; check 13's `.claude`
    # exemption, which lets Claude Code's skill layout sit one folder deeper
    # than the agent limit; and check 99, which holds the table to its files,
    # its generated pages and its pinned sources.
    (1, "PASS", "conform to their schema", fixture_99_the_skill_table_and_its_generated_pages),
    (13, "PASS", "files sit in declared paths", fixture_99_the_skill_table_and_its_generated_pages),
    (99, "PASS", "agree with their files, registries, generated pages and pinned entries",
     fixture_99_the_skill_table_and_its_generated_pages),
    (1, "FAIL", "'entry' is a required property [contracts/skills.json]",
     fixture_01_a_skill_manifest_naming_no_code),
    (99, "FAIL", "differs from what the table renders", fixture_99_a_skill_page_edited_by_hand),
    (99, "FAIL", "the source changed after the skill landed", fixture_99_a_pinned_source_that_changed),
    (99, "FAIL", "a file under src/skills/ that no manifest in the table names",
     fixture_99_a_skill_file_with_no_manifest),
    (99, "FAIL", "which is marked safety: it is always used",
     fixture_99_a_suggestion_for_a_safety_candidate),
    (1, "PASS", "conform to their schema", fixture_01_a_run_sheet_that_conforms),
    (1, "FAIL", "'used' was expected [microscope_agent/questions/mic-20261111-001/v1_skill_runs_transmitted.json]",
     fixture_01_a_run_sheet_dropping_a_safety_candidate),
    (1, "FAIL", "'why' is a required property [microscope_agent/questions/mic-20261111-001/v1_skill_runs_transmitted.json]",
     fixture_01_a_run_sheet_with_a_choice_and_no_reason),
    # HP-007: an example is judged at its own instant, a real permit by the
    # clock. Matched on the path as well, so the example files every built
    # repository carries cannot satisfy either row.
    (19, "FAIL", "is for committed examples under contracts/examples/ only; a real permit is judged by the wall "
                 "clock [microscope_agent/approvals/", fixture_19_a_real_permit_declaring_an_example_instant),
    (19, "FAIL", "(the wall clock), but is not marked voided [microscope_agent/approvals/",
     fixture_19_a_real_permit_is_judged_by_the_wall_clock),
    (1, "FAIL", "Additional properties are not allowed ('value' was unexpected) "
                "[librarian_agent/queries/lint-20261103.json]",
     fixture_01_an_artifact_in_a_tree_without_cards_is_judged),
    (79, "FAIL", "is tracked by git inside a directory SKIP_DIRS names",
     fixture_79_a_runtime_status_file_forced_into_a_commit),
    (41, "FAIL", "commits the person's own file", fixture_41_the_runtime_seat_commits_an_approval),
    (41, "FAIL", "commits the person's own file", fixture_41_a_planning_seat_commits_the_safety_policy),
    (41, "PASS", "1 commits stay inside the seat that made them", fixture_41_the_person_commits_an_approval),
    # librarian card 061 (2026-10-26): a device row's label is its cited entry's.
    (96, "PASS", "device rows carry a Micro-Manager label that their cited",
     fixture_96_device_labels_copied_from_their_entries),
    (96, "FAIL", "and no entry by that id",
     fixture_96_a_label_cites_no_entry),
    (96, "FAIL", "the row's label is a copy of the entry's",
     fixture_96_a_label_its_entry_does_not_hold),
    (96, "FAIL", "a refuted entry backs no label",
     fixture_96_a_label_from_a_refuted_entry),
    (96, "FAIL", "supersedes; cite the entry that replaced it",
     fixture_96_a_label_from_a_superseded_entry),
    (96, "FAIL", "sits on 2 rows",
     fixture_96_one_label_on_two_rows),
    (96, "FAIL", "lapp_branch_assignment",
     fixture_96_a_widefield_source_labelled),
    (96, "FAIL", "is not 64 lowercase hex",
     fixture_96_a_digest_that_is_not_hex),
    (96, "FAIL", "the row's digest is a copy of the entry's",
     fixture_96_a_digest_its_entry_does_not_record),
    (96, "FAIL", "not a measured: run",
     fixture_96_a_digest_from_no_run),
    (96, "FAIL", "the field has no grade or source",
     fixture_96_a_label_with_a_grade_of_its_own),
    # librarian card 062 (2026-10-27): a row's bindings and state words are its cited entries'.
    (98, "PASS", "5 bindings and state words on 5 device rows are copies",
     fixture_98_bindings_and_words_copied_from_their_entries),
    (98, "N/A", "no device row carries mm_bindings or mm_states",
     fixture_98_a_label_alone_is_not_judged),
    (98, "FAIL", "the field has no grade or source of its own",
     fixture_98_a_binding_with_a_grade_of_its_own),
    (98, "FAIL", "carries bindings or state words and no mm_label",
     fixture_98_a_state_word_on_a_row_with_no_label),
    (98, "FAIL", "and no entry by that id",
     fixture_98_a_binding_cites_no_entry),
    (98, "FAIL", "unit 's' against 'ms'",
     fixture_98_a_binding_its_entry_does_not_hold),
    (98, "FAIL", "mm_state_label 'Position-1' against 'Position-2'",
     fixture_98_a_state_word_its_entry_does_not_hold),
    (98, "FAIL", "a refuted entry backs nothing",
     fixture_98_a_binding_from_a_refuted_entry),
    (98, "FAIL", "supersedes; cite the entry that replaced it",
     fixture_98_a_state_word_from_a_superseded_entry),
    (98, "FAIL", "a binding keys on a registered name only",
     fixture_98_a_binding_on_an_unregistered_quantity),
    (98, "FAIL", "frame_count is a verb's argument",
     fixture_98_frame_count_bound),
    (98, "FAIL", "which is not a symbol in contracts/units.json",
     fixture_98_a_unit_units_json_lacks),
    (98, "FAIL", "'1' cannot tell 10 from 1 per cent",
     fixture_98_a_fraction_of_scale_in_unit_one),
    (98, "FAIL", "quantity 'exposure_time' appears in 2 mm_bindings items",
     fixture_98_one_quantity_into_two_properties),
    (98, "FAIL", "state_label 'Bright Field' appears in 2 mm_states items",
     fixture_98_two_words_for_one_state_label),
    (98, "FAIL", "is not a word the path table writes for this row",
     fixture_98_a_word_the_path_table_never_writes),
    (98, "FAIL", "observed by a run that acquired, not read off a label",
     fixture_98_a_port_word_read_off_a_label),
    (98, "FAIL", "not the detector rows that got light",
     fixture_98_a_branch_word_from_a_run_that_lit_nothing),
    (98, "FAIL", "not the detector rows that got light",
     fixture_98_a_branch_word_lighting_a_detector_the_table_lacks),
    (98, "FAIL", "the observation and the table disagree",
     fixture_98_a_port_word_whose_run_lit_the_other_camera),
    (98, "FAIL", "is not 64 lowercase hex (librarian card 062)",
     fixture_98_a_binding_digest_that_is_not_hex),
    (98, "FAIL", "the digest is a copy of the entry's",
     fixture_98_a_binding_digest_its_entry_does_not_record),
    # librarian card 064 (2026-10-27): a binding's line and step, and a calibration's conversion form.
    (98, "PASS", "7 bindings and state words on 6 device rows are copies of their cited entries, and 1 conversion follows",
     fixture_98_lines_steps_and_a_conversion_copied),
    (98, "FAIL", "a conversion serves a binding",
     fixture_98_a_conversion_alone_is_judged),
    (98, "FAIL", "step 10 permille against its entry's property_step 1 permille",
     fixture_98_a_step_its_entry_does_not_hold),
    (98, "FAIL", "a step nobody read is left off, never filled in",
     fixture_98_a_step_nobody_read),
    (98, "FAIL", "and the row carries no step",
     fixture_98_a_step_read_and_not_copied),
    (98, "FAIL", "a step is in the unit the property is written in",
     fixture_98_a_step_in_another_unit),
    (98, "FAIL", "a step being a positive {value, unit}",
     fixture_98_a_step_of_zero),
    (98, "FAIL", "line 'RED' against 'GREEN'",
     fixture_98_a_line_its_entry_does_not_hold),
    (98, "FAIL", "line 'NIR' against None",
     fixture_98_a_line_left_off_the_row),
    (98, "FAIL", "quantity 'illumination_power' on line 'GREEN' appears in 2 mm_bindings items",
     fixture_98_one_line_bound_twice),
    (98, "FAIL", "is bound both on a line and without one",
     fixture_98_a_quantity_bound_on_a_line_and_without),
    (98, "FAIL", "and carries no conversion",
     fixture_98_a_calibration_serving_a_binding_with_no_conversion),
    (98, "FAIL", "only a calibration converts",
     fixture_98_a_conversion_on_a_claim),
    (98, "FAIL", "not {direction: physical_to_control",
     fixture_98_a_conversion_read_backwards),
    (98, "FAIL", "not {direction: physical_to_control",
     fixture_98_a_conversion_with_a_fit),
    (98, "FAIL", "the key is the conversion's quantity",
     fixture_98_a_conversion_of_another_quantity),
    (98, "FAIL", "the physical side is in canonical units",
     fixture_98_a_conversion_in_milliwatts),
    (98, "FAIL", "one form never mixes units",
     fixture_98_a_conversion_mixing_units),
    (98, "FAIL", "a rule between points needs two",
     fixture_98_a_conversion_of_one_point),
    (98, "FAIL", "a repeated value is a plateau",
     fixture_98_a_conversion_across_a_plateau),
    (98, "FAIL", "are not strictly monotone",
     fixture_98_a_conversion_that_turns_back),
    (98, "FAIL", "the two are one range, exactly",
     fixture_98_a_conversion_wider_than_its_validity),
    (98, "FAIL", "not a min and a max",
     fixture_98_a_conversion_with_an_open_validity),
    (98, "FAIL", "derives E3, not E1",
     fixture_98_a_conversion_point_from_a_specification),
    (98, "FAIL", "no device row binds that property",
     fixture_98_a_conversion_no_row_binds),
    (98, "FAIL", "control unit 'percent' against the binding's 'permille'",
     fixture_98_a_conversion_into_another_unit),
    (98, "FAIL", "line 'TEAL' against the binding's 'GREEN'",
     fixture_98_a_conversion_for_another_line),
    (98, "FAIL", "a property takes one step",
     fixture_98_two_steps_for_one_property),
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
