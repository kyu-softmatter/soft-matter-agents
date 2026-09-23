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


FIXTURES = [
    (35, "FAIL", "a session writes inside one agent", fixture_35_one_commit_two_boundaries),
    (41, "FAIL", "this path is bridge's", fixture_41_seat_writes_outside_its_own),
    (41, "PENDING", "not a seat in", fixture_41_unregistered_committer),
    (26, "FAIL", "does not match the committed bytes", fixture_26_snapshot_is_a_copy_of_another_commit),
    (46, "FAIL", "obs-000000000000", fixture_46_vocabulary_pin_that_never_stood),
    (76, "PASS", "disabledMcpjsonServers", fixture_76_a_local_settings_file_is_named),
    (76, "N/A", "could not have been found", fixture_76_an_export_says_it_could_not_have_seen_it),
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
        m = re.match(r"\s*check\s+(\d+)\s+(PASS|FAIL|UNDECIDED|PENDING|N/A)\s+(.*)", line)
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
