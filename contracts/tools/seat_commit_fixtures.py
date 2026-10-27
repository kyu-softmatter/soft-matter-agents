#!/usr/bin/env python3
"""Fixtures for the commit tool (plan.md 8.3, HP-001).

Each fixture is a throwaway repository, built the way
`contracts/history_fixtures.py` builds them and never stored, and each is
run twice from scratch: once by the **naive** procedure a seat follows from
prose, which must reproduce the incident, and once **through the tool**,
which must not. A fixture counts only when both hold. One whose naive arm
stops reproducing tests nothing any more, and says so -- the completing
half the root CLAUDE.md asks for is watching a fixture fail, and this file
watches every one fail on every run.

    python contracts/tools/seat_commit_fixtures.py
    python contracts/tools/seat_commit_fixtures.py --only lock

A repository holds only what the tool reads: `contracts/seats.json`,
`contracts/validate.py` (for `seat_boundary_of`, read from HEAD) and the tool
itself, all copied from this tree, plus a few cards. The registry is the
real one with fixture seats appended, the way `_registry_with` in
history_fixtures.py does it: existing entries are never edited, so a
fixture cannot keep passing on its own idea of who owns what.

The gate here is a stub pre-commit hook, not the repository's. The real gate
takes minutes and judges contracts, and what these fixtures test is the
procedure around it: which tree reaches it, which HEAD the commit lands on,
which identity is spent, and what is reported. A stub is also the honest
stand-in for a working copy whose hooks are not installed, which the
microscope computer is. The stub writes a marker each time it runs, so a
fixture can say the gate was never reached, and it can move HEAD while it
runs, so a fixture can make the race happen instead of hoping for it.

Standard library only, like the tool.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
CONTRACTS = TOOLS.parent

PERSON = ("kyuhwan", "kyuchoi@stanford.edu")
FIX = "fixture-microscope-20261016-1"        # the seat committing
OTHER = "fixture-microscope-20261016-2"      # another seat in the same working copy
CLOSED = "fixture-microscope-20261016-3"
REOPENED = "fixture-microscope-20261016-4"
FROM_MESSAGE = f"{FIX}{chr(0xFF20)}seat.invalid"  # FIX's email as a session-id message delivers it
BRIDGE = "fixture-bridge-20261016-1"         # so a bridge path always has an owner to name
CARD = "microscope_agent/questions/q/card.json"
CARD_LINES = [f"line {i}" for i in range(1, 9)]

STUB_HOOK = r"""#!/bin/sh
# The fixtures' gate: say what it judges, leave a mark, and on request move
# HEAD as another seat while it runs, or refuse with a fatal line.
echo "pre-commit: fixture gate judging"
git diff --cached --name-only | sed 's#^#  #'
: > .git/fixture-gate-ran
if [ -f .git/fixture-move-head-once ]; then
    rm -f .git/fixture-move-head-once
    I=.git/fixture-other.index
    rm -f "$I"
    GIT_INDEX_FILE="$I" git read-tree HEAD
    printf 'another seat landed this while the gate ran\n' > microscope_agent/questions/q/other.json
    GIT_INDEX_FILE="$I" git update-index --add microscope_agent/questions/q/other.json
    T=$(GIT_INDEX_FILE="$I" git write-tree)
    C=$(echo "another seat, during the gate" | GIT_COMMITTER_NAME="seat:fixture-microscope-20261016-2" \
        GIT_COMMITTER_EMAIL="fixture-microscope-20261016-2@seat.invalid" git commit-tree "$T" -p HEAD)
    git update-ref HEAD "$C"
    rm -f "$I"
    echo "pre-commit: (fixture) another seat moved HEAD to $C"
fi
# And judge the way check 41 --staged does, against HEAD as it is NOW: a
# staged path the commit did not mean is refused. After HEAD moves under the
# gate, a tree built on the old HEAD shows the other seat's file as removed.
if [ -f .git/fixture-gate-refuses ]; then
    echo "  check 13 FAIL      a refusal on its merits, with HEAD where it was"
    exit 1
fi
if [ -f .git/fixture-gate-judges-head ] && git diff --cached --name-only | grep -q other.json; then
    echo "  check 41 FAIL      this path is another seat's [microscope_agent/questions/q/other.json]"
    exit 1
fi
exit 0
"""

STUB_PRE_PUSH = r"""#!/bin/sh
# The fixtures' push hook: on request, another push reaches the remote first,
# between this push reading the remote and updating it. The file holds
# `same` (that push carries this push's own commit) or a commit to push.
if [ -f .git/fixture-push-race ]; then
    WHAT=$(cat .git/fixture-push-race)
    rm -f .git/fixture-push-race
    while read lref lsha rref rsha; do
        [ "$WHAT" = same ] && WHAT=$lsha
        git push -q --no-verify "$2" "$WHAT:$rref"
        echo "pre-push: (fixture) another push published $WHAT first"
    done
fi
exit 0
"""


# --------------------------------------------------------------------------- #
# building
# --------------------------------------------------------------------------- #

def env_for(seat: str | None = None, email: str | None = None, **extra: str) -> dict:
    env = dict(os.environ)
    for k in ("GIT_INDEX_FILE", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "GIT_DIR", "GIT_WORK_TREE"):
        env.pop(k, None)
    if seat:
        env["GIT_COMMITTER_NAME"] = f"seat:{seat}"
        env["GIT_COMMITTER_EMAIL"] = email or f"{seat}@seat.invalid"
    env.update(extra)
    return env


def git(repo: Path, *args: str, env: dict | None = None, check: bool = True,
        input: bytes | None = None) -> subprocess.CompletedProcess:
    out = subprocess.run(["git", *args], cwd=str(repo), env=env or env_for(), input=input,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and out.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {out.stdout.decode('utf-8', 'replace')}")
    return out


def out(repo: Path, *args: str, **kw) -> str:
    return git(repo, *args, **kw).stdout.decode("utf-8", "replace").strip()


def write(repo: Path, rel: str, body: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body.encode("utf-8"))


def card(*extra: str, replace: dict | None = None) -> str:
    lines = list(CARD_LINES)
    for i, v in (replace or {}).items():
        lines[i] = v
    return "\n".join(lines + list(extra)) + "\n"


def commit_as(repo: Path, seat: str, message: str, *paths: str) -> str:
    git(repo, "add", "--", *paths)
    git(repo, "commit", "-q", "--no-verify", "-m", message, env=env_for(seat))
    return out(repo, "rev-parse", "HEAD")


def plumbing_commit(repo: Path, seat: str, rel: str, body: str, message: str) -> str:
    """Another seat's commit, landing without touching the shared index -- the
    way a seat with a private index lands one, and the only way to land one
    while a fixture is holding .git/index.lock."""
    write(repo, rel, body)
    idx = repo / ".git" / "fixture-other.index"
    e = env_for(seat, GIT_INDEX_FILE=str(idx))
    git(repo, "read-tree", "HEAD", env=e)
    git(repo, "update-index", "--add", "--", rel, env=e)
    tree = out(repo, "write-tree", env=e)
    sha = out(repo, "commit-tree", tree, "-p", "HEAD", input=message.encode(), env=e)
    git(repo, "update-ref", "HEAD", sha)
    idx.unlink()
    return sha


def base(repo: Path) -> str:
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", PERSON[0])
    git(repo, "config", "user.email", PERSON[1])
    git(repo, "config", "core.autocrlf", "false")
    (repo / "contracts" / "tools").mkdir(parents=True)
    for rel in ("seats.json", "validate.py", "tools/seat_commit.py"):
        shutil.copy2(CONTRACTS / rel, repo / "contracts" / rel)
    reg = json.loads((repo / "contracts" / "seats.json").read_text(encoding="utf-8"))
    for name, status in ((FIX, None), (OTHER, None),
                         (CLOSED, "closed 2026-10-16 -- fixture: the person closed this session"),
                         (REOPENED, "closed 2026-10-12 -- fixture: closed by the person. REOPENED 2026-10-15: "
                                    "the person, in the session's own window. It had not seen the closed row.")):
        row = {"seat": name, "committer_email": f"{name}@seat.invalid", "owns": ["microscope_agent"],
               "note": "A fixture seat, appended in a throwaway repository only."}
        if status:
            row["status"] = status
        reg["seats"].append(row)
    reg["seats"].append({"seat": BRIDGE, "committer_email": f"{BRIDGE}@seat.invalid", "owns": ["bridge"],
                         "note": "A fixture seat, appended in a throwaway repository only."})
    write(repo, "contracts/seats.json", json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    write(repo, "README.md", "# fixture\n")
    write(repo, CARD, card())
    write(repo, "bridge/threads/t/status.json", '{"artifact": "thread_status"}\n')
    hooks = repo / ".fixture-hooks"
    hooks.mkdir()
    for name, body in (("pre-commit", STUB_HOOK), ("pre-push", STUB_PRE_PUSH)):
        (hooks / name).write_bytes(body.encode("utf-8"))
        os.chmod(hooks / name, 0o755)
    git(repo, "config", "core.hooksPath", ".fixture-hooks")
    write(repo, ".gitignore", ".fixture-hooks/\n")
    return commit_as(repo, "architecture", "base", "contracts", "README.md", CARD, "bridge", ".gitignore")


def message(repo: Path, body: str = "my change to the card\n") -> str:
    p = repo / ".git" / "fixture-message.txt"
    p.write_bytes(body.encode("utf-8"))
    return str(p)


def tool(repo: Path, *args: str, env: dict | None = None, timeout: float = 120) -> tuple:
    r = subprocess.run([sys.executable, str(repo / "contracts" / "tools" / "seat_commit.py"), *args],
                       cwd=str(repo), env=env or env_for(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", "replace")


class Running:
    """The tool in the background, its output read as it comes."""

    def __init__(self, repo: Path, *args: str):
        self.lines: list[str] = []
        self.p = subprocess.Popen([sys.executable, "-u", str(repo / "contracts" / "tools" / "seat_commit.py"),
                                   *args], cwd=str(repo), env=env_for(), stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
        self.t = threading.Thread(target=self._read, daemon=True)
        self.t.start()

    def _read(self) -> None:
        for raw in self.p.stdout:
            self.lines.append(raw.decode("utf-8", "replace").rstrip("\r\n"))

    def wait_for_line(self, needle: str, timeout: float = 60) -> bool:
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if any(needle in x for x in self.lines):
                return True
            if self.p.poll() is not None:
                self.t.join(2)
                return any(needle in x for x in self.lines)
            time.sleep(0.05)
        return False

    def finish(self, timeout: float = 120) -> tuple:
        code = self.p.wait(timeout)
        self.t.join(5)
        return code, "\n".join(self.lines)


def blob(repo: Path, ref: str, rel: str) -> str | None:
    r = git(repo, "show", f"{ref}:{rel}", check=False)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def last_record(repo: Path) -> dict:
    p = repo / ".git" / "sma-seat-commit.jsonl"
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []
    return rows[-1] if rows else {}


def naive_reads_success(output: str) -> bool:
    """How a seat read its commit's output on 2026-09-23 and 2026-10-15: filtered to FAIL lines."""
    return not [x for x in output.splitlines() if "FAIL" in x]


def private_index_commit_built_early(repo: Path, patch: Path, during_wait) -> str:
    """The procedure of 2026-10-15: build the private index, then wait, then commit from it."""
    idx = repo / ".git" / "fixture-private.index"
    e = env_for(FIX, GIT_INDEX_FILE=str(idx))
    git(repo, "read-tree", "HEAD", env=e)
    applied = git(repo, "apply", "--cached", str(patch), env=e, check=False).returncode == 0
    during_wait()
    r = git(repo, "commit", "-q", "-F", message(repo), env=e, check=False)
    idx.unlink(missing_ok=True)
    return f"applied={applied} commit_exit={r.returncode}"


def save_diff(repo: Path, rel: str) -> Path:
    """`git diff HEAD -- <path>`, saved right after editing, as the specification has the seat do."""
    p = repo / ".git" / "fixture-mine.patch"
    p.write_bytes(git(repo, "diff", "HEAD", "--binary", "--full-index", "--", rel).stdout)
    return p


# --------------------------------------------------------------------------- #
# the fixtures: (incident, naive arm, tool arm), each arm on its own repository
# --------------------------------------------------------------------------- #

def naive_held_lock(repo: Path) -> tuple:
    """2026-10-15: the wait loop passed, then another seat took .git/index.lock,
    and the commit failed with *File exists* while the output, filtered to FAIL
    lines, showed nothing -- read as done."""
    head = out(repo, "rev-parse", "HEAD")
    write(repo, CARD, card("MINE"))
    lock = repo / ".git" / "index.lock"
    while lock.exists():          # the wait loop, which passes
        time.sleep(0.1)
    lock.write_bytes(b"")         # another seat takes the lock just after
    r = git(repo, "commit", "-F", message(repo), "--", CARD, env=env_for(FIX), check=False)
    said = r.stdout.decode("utf-8", "replace")
    lock.unlink()
    made = out(repo, "rev-parse", "HEAD") != head
    return (naive_reads_success(said) and not made,
            f"read as done, and no commit was made: {said.strip().splitlines()[0][:110]!r}")


def tool_held_lock(repo: Path) -> tuple:
    head = out(repo, "rev-parse", "HEAD")
    write(repo, CARD, card("MINE"))
    patch = repo / ".git" / "fixture-mine.patch"
    code, said = tool(repo, "--save-patch", str(patch), "--", CARD)
    lock = repo / ".git" / "index.lock"
    lock.write_bytes(b"")
    # A lock nobody releases: refused at the limit, the lock left where it is.
    code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch), "--lock-wait", "1.5")
    if code != 1 or "still held" not in said or not lock.exists() or out(repo, "rev-parse", "HEAD") != head:
        return False, f"a lock never released was not refused cleanly (exit {code}): {said[-300:]}"
    # The same lock released once the tool is seen waiting on it, and the
    # branch's ref lock released once the tool is seen retrying on it: each
    # release follows the tool's own output, not a clock, so the order is the
    # same however slow the machine is. A lock already gone when the fixture
    # releases it was removed by the tool.
    ref_lock = repo / ".git" / "refs" / "heads" / "main.lock"
    ref_lock.write_bytes(b"")
    removed_by_someone_else = []

    def release(p: Path) -> None:
        try:
            p.unlink()
        except FileNotFoundError:
            removed_by_someone_else.append(p.name)

    run = Running(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch), "--retries", "30")
    if run.wait_for_line("waiting for .git/index.lock"):
        release(lock)
    if run.wait_for_line("the ref is locked"):
        release(ref_lock)
    code, said = run.finish()
    for p in (lock, ref_lock):
        if p.exists():
            p.unlink()
    rec = last_record(repo)
    if code != 0 or removed_by_someone_else:
        return False, f"exit {code}, locks removed by the tool: {removed_by_someone_else}: {said[-400:]}"
    if "MINE" not in (blob(repo, "HEAD", CARD) or "") or rec.get("retries", {}).get("ref_locked", 0) < 1:
        return False, f"committed without the change or without retrying the ref: {rec}"
    return True, (f"refused at the limit with the lock intact; then waited {rec['lock_wait_s']} s, retried the "
                  f"locked ref {rec['retries']['ref_locked']} times, committed, and read it back")


def _other_lands(repo: Path) -> str:
    return plumbing_commit(repo, OTHER, "microscope_agent/questions/q/librarian_cards.json",
                           '{"two cards": "the other seat\'s commit, landed during the wait"}\n',
                           "another seat's commit, during the wait")


def naive_head_moves_in_wait(repo: Path) -> tuple:
    """2026-10-15 (17c2185): a private index built from HEAD before the lock wait.
    HEAD moved during the wait, and the commit's tree undid the commit that landed."""
    write(repo, CARD, card("MINE"))
    patch = save_diff(repo, CARD)
    other = {}
    detail = private_index_commit_built_early(repo, patch, lambda: other.setdefault("sha", _other_lands(repo)))
    gone = blob(repo, "HEAD", "microscope_agent/questions/q/librarian_cards.json") is None
    parent_is_other = out(repo, "rev-parse", "HEAD^") == other["sha"]
    return (gone and parent_is_other,
            f"the commit's parent is the other seat's and its tree removes that seat's file ({detail})")


def tool_head_moves_in_wait(repo: Path) -> tuple:
    write(repo, CARD, card("MINE"))
    patch = save_diff(repo, CARD)
    lock = repo / ".git" / "index.lock"
    lock.write_bytes(b"")
    run = Running(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
    if not run.wait_for_line("waiting for .git/index.lock"):
        lock.unlink()
        return False, "the tool never waited: " + run.finish()[1][-300:]
    other = _other_lands(repo)
    lock.unlink()
    code, said = run.finish()
    if code != 0:
        return False, f"exit {code}: {said[-400:]}"
    kept = blob(repo, "HEAD", "microscope_agent/questions/q/librarian_cards.json") is not None
    mine = "MINE" in (blob(repo, "HEAD", CARD) or "")
    on_other = out(repo, "rev-parse", "HEAD^") == other
    return (kept and mine and on_other,
            f"built after the wait on the other seat's commit; both changes are in HEAD "
            f"(kept={kept} mine={mine} parent-is-other={on_other})")


def _conflicting_lands(repo: Path) -> str:
    return plumbing_commit(repo, OTHER, CARD, card(replace={2: "line 3, as the other seat committed it"}),
                           "another seat rewrites line 3, during the wait")


def naive_patch_stops_applying(repo: Path) -> tuple:
    """The same early-built private index, when the commit landing in the wait
    rewrote the lines the patch changes: the commit lands anyway, and undoes it."""
    write(repo, CARD, card(replace={2: "line 3, as I edited it"}))
    patch = save_diff(repo, CARD)
    detail = private_index_commit_built_early(repo, patch, lambda: _conflicting_lands(repo))
    now = blob(repo, "HEAD", CARD) or ""
    return ("as the other seat committed it" not in now and "as I edited it" in now,
            f"committed over the other seat's line 3, which is gone from HEAD ({detail})")


def tool_patch_stops_applying(repo: Path) -> tuple:
    write(repo, CARD, card(replace={2: "line 3, as I edited it"}))
    patch = save_diff(repo, CARD)
    lock = repo / ".git" / "index.lock"
    lock.write_bytes(b"")
    run = Running(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
    if not run.wait_for_line("waiting for .git/index.lock"):
        lock.unlink()
        return False, "the tool never waited: " + run.finish()[1][-300:]
    other = _conflicting_lands(repo)
    lock.unlink()
    code, said = run.finish()
    named = f"{CARD}, the hunk starting at line" in said and "HEAD moved since this run began" in said
    untouched = out(repo, "rev-parse", "HEAD") == other
    return (code == 1 and named and untouched,
            f"refused, naming the hunk, and HEAD is still the other seat's commit (exit {code}, named={named}, "
            f"untouched={untouched})")


def naive_digest(repo: Path) -> tuple:
    """Root CLAUDE.md, 2026-09-20: `git commit -- <path>` builds from the worktree,
    so another seat's hunk in the same file, written after you looked, goes in
    under your identity."""
    write(repo, CARD, card("MINE"))
    looked = out(repo, "diff", "HEAD", "--", CARD)
    write(repo, CARD, card("MINE", "OTHER SEAT"))
    git(repo, "commit", "-q", "-F", message(repo), "--", CARD, env=env_for(FIX))
    carried = "OTHER SEAT" in (blob(repo, "HEAD", CARD) or "")
    return (carried and "OTHER SEAT" not in looked,
            "the diff looked at showed only MINE, and the commit carries the other seat's line too")


def tool_digest(repo: Path) -> tuple:
    head = out(repo, "rev-parse", "HEAD")
    write(repo, CARD, card("MINE"))
    code, said = tool(repo, "--seat", FIX, "--", CARD)
    digest = next((x.split("digest ", 1)[1].split(".")[0] for x in said.splitlines() if "digest " in x), None)
    if code != 0 or not digest:
        return False, f"no digest shown (exit {code}): {said[-300:]}"
    write(repo, CARD, card("MINE", "OTHER SEAT"))
    code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--confirm", digest, "--", CARD)
    refused = code == 1 and f"not {digest}" in said
    if not refused or out(repo, "rev-parse", "HEAD") != head:
        return False, f"a digest that no longer matched was not refused (exit {code}): {said[-300:]}"
    # And when the other seat's line arrives DURING the lock wait, after the
    # digest matched on arrival: only the comparison inside the wait sees it.
    write(repo, CARD, card("MINE"))
    lock = repo / ".git" / "index.lock"
    lock.write_bytes(b"")
    run = Running(repo, "--seat", FIX, "-F", message(repo), "--confirm", digest, "--", CARD)
    waited = run.wait_for_line("waiting for .git/index.lock")
    write(repo, CARD, card("MINE", "OTHER SEAT"))
    lock.unlink()
    code, said = run.finish()
    late = waited and code == 1 and "something changed while waiting" in said
    return (late and out(repo, "rev-parse", "HEAD") == head,
            f"digest {digest} no longer matched, before the wait and again inside it, so nothing was "
            f"committed (exit {code})")


def naive_identity(repo: Path) -> tuple:
    """2026-09-23: an email copied out of a message arrives with U+FF20 for '@';
    and 2026-09-22: .git/config.worktree pins committer.* over `-c user.*`."""
    from_message = FROM_MESSAGE
    write(repo, CARD, card("MINE"))
    git(repo, "commit", "-q", "-F", message(repo), "--", CARD, env=env_for(FIX, email=from_message))
    a = out(repo, "log", "-1", "--format=%ce")
    git(repo, "config", "extensions.worktreeConfig", "true")
    git(repo, "config", "--worktree", "committer.name", f"seat:{OTHER}")
    git(repo, "config", "--worktree", "committer.email", f"{OTHER}@seat.invalid")
    write(repo, CARD, card("MINE", "AGAIN"))
    git(repo, "-c", f"user.email={FIX}@seat.invalid", "-c", f"user.name=seat:{FIX}",
        "commit", "-q", "-F", message(repo), "--", CARD)
    b = out(repo, "log", "-1", "--format=%ce")
    return (a == from_message and b == f"{OTHER}@seat.invalid",
            f"one commit went out as {a!r}, which no row holds, and the next as {b!r}, another seat")


def tool_identity(repo: Path) -> tuple:
    git(repo, "config", "extensions.worktreeConfig", "true")
    git(repo, "config", "--worktree", "committer.name", f"seat:{OTHER}")
    git(repo, "config", "--worktree", "committer.email", f"{OTHER}@seat.invalid")
    write(repo, CARD, card("MINE"))
    patch = save_diff(repo, CARD)
    code, said = tool(repo, "--seat", FROM_MESSAGE, "-F", message(repo), "--patch", str(patch))
    if code != 1 or "looks like an email" not in said:
        return False, f"an email from a message was not refused (exit {code}): {said[-300:]}"
    ambient = env_for(FIX, email=FROM_MESSAGE)
    code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch), env=ambient)
    ce = out(repo, "log", "-1", "--format=%cn <%ce>")
    first = said.splitlines()[0] if said else ""
    return (code == 0 and ce == f"seat:{FIX} <{FIX}@seat.invalid>" and first.startswith(f"committing as: seat:{FIX}"),
            f"the email form was refused; with the pin and a wrong ambient email both present, it committed as {ce}")


def naive_closed(repo: Path) -> tuple:
    """A closed seat's identity still commits: check 41 judges paths, not whether the seat is open."""
    write(repo, CARD, card("MINE"))
    git(repo, "commit", "-q", "-F", message(repo), "--", CARD, env=env_for(CLOSED))
    ce = out(repo, "log", "-1", "--format=%ce")
    return ce == f"{CLOSED}@seat.invalid", f"committed under the closed seat {ce}"


def tool_closed(repo: Path) -> tuple:
    head = out(repo, "rev-parse", "HEAD")
    write(repo, CARD, card("MINE"))
    patch = save_diff(repo, CARD)
    code, said = tool(repo, "--seat", CLOSED, "-F", message(repo), "--patch", str(patch))
    if code != 1 or "is closed" not in said or out(repo, "rev-parse", "HEAD") != head:
        return False, f"the closed seat was not refused (exit {code}): {said[-300:]}"
    code, said = tool(repo, "--seat", REOPENED, "-F", message(repo), "--patch", str(patch))
    ce = out(repo, "log", "-1", "--format=%ce")
    return (code == 0 and ce == f"{REOPENED}@seat.invalid",
            f"the closed seat was refused; the seat whose row says REOPENED committed as {ce}")


def naive_outside(repo: Path) -> tuple:
    """A microscope seat commits into bridge/. With no gate installed -- the
    microscope computer -- nothing refuses it; with one, the refusal comes
    after the whole gate and names no owner."""
    write(repo, "bridge/threads/t/status.json", '{"artifact": "thread_status", "edited": "by the microscope"}\n')
    git(repo, "commit", "-q", "-F", message(repo), "--", "bridge/threads/t/status.json", env=env_for(FIX))
    touched = out(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD")
    return touched == "bridge/threads/t/status.json", f"a microscope seat's commit landed in {touched}"


def tool_outside(repo: Path) -> tuple:
    head = out(repo, "rev-parse", "HEAD")
    write(repo, "bridge/threads/t/status.json", '{"artifact": "thread_status", "edited": "by the microscope"}\n')
    patch = save_diff(repo, "bridge/threads/t/status.json")
    marker = repo / ".git" / "fixture-gate-ran"
    marker.unlink(missing_ok=True)
    code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
    named = "this path is bridge's" in said and f"seats that may commit it: {BRIDGE}" in said
    return (code == 1 and named and not marker.exists() and out(repo, "rev-parse", "HEAD") == head,
            f"refused before the gate ran, naming the bridge's seats (exit {code}, gate ran={marker.exists()})")


def _remote_ahead(repo: Path) -> Path:
    """A remote holding the base, and another seat's commit pushed to it from elsewhere."""
    remote = repo.parent / "remote.git"
    git(repo.parent, "init", "-q", "--bare", "-b", "main", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    git(repo, "fetch", "-q", "origin")
    elsewhere = repo.parent / "elsewhere"
    git(repo.parent, "clone", "-q", str(remote), str(elsewhere))
    git(elsewhere, "config", "user.name", PERSON[0])
    git(elsewhere, "config", "user.email", PERSON[1])
    write(elsewhere, "microscope_agent/questions/q/theirs.json", '{"pushed": "from another computer"}\n')
    commit_as(elsewhere, OTHER, "another seat's commit, pushed from another computer",
              "microscope_agent/questions/q/theirs.json")
    git(elsewhere, "push", "-q", "origin", "main")
    write(repo, CARD, card("MINE"))
    commit_as(repo, FIX, "my commit, not yet pushed", CARD)
    return remote


def naive_behind(repo: Path) -> tuple:
    """Without a fetch, the branch looks ahead and never behind, so a seat
    believes its push publishes its own commit and nothing else is needed."""
    _remote_ahead(repo)
    behind = out(repo, "rev-list", "--count", "HEAD..origin/main")
    ahead = out(repo, "rev-list", "--count", "origin/main..HEAD")
    return (behind == "0" and ahead == "1",
            f"git reports {ahead} ahead and {behind} behind, while the remote holds a commit this branch lacks")


def tool_behind(repo: Path) -> tuple:
    remote = _remote_ahead(repo)
    before = out(remote, "rev-parse", "main")
    code, said = tool(repo, "--seat", FIX, "--push")
    return (code == 1 and "behind" in said and "merge is needed" in said and out(remote, "rev-parse", "main") == before,
            f"fetched first, refused as behind with a merge needed, and the remote is unchanged (exit {code})")


def _others_unpushed(repo: Path) -> Path:
    remote = repo.parent / "remote.git"
    git(repo.parent, "init", "-q", "--bare", "-b", "main", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    write(repo, "microscope_agent/questions/q/theirs.json", '{"committed": "by another seat, here"}\n')
    commit_as(repo, OTHER, "another seat's commit in this working copy", "microscope_agent/questions/q/theirs.json")
    write(repo, CARD, card("MINE"))
    commit_as(repo, FIX, "my commit", CARD)
    return remote


def naive_publishes_others(repo: Path) -> tuple:
    """Root memory, 2026-10: on a shared branch, a push for one's own commit publishes everyone's."""
    remote = _others_unpushed(repo)
    git(repo, "push", "-q", "origin", "main")
    published = out(remote, "log", "--format=%ce", "main")
    return (f"{OTHER}@seat.invalid" in published,
            "a push made for one commit published the other seat's too, and nothing listed it")


def tool_publishes_others(repo: Path) -> tuple:
    remote = _others_unpushed(repo)
    before = out(remote, "rev-parse", "main")
    code, said = tool(repo, "--seat", FIX, "--push")
    listed = "another seat's commit in this working copy" in said and "--push-includes-others" in said
    if code != 1 or not listed or out(remote, "rev-parse", "main") != before:
        return False, f"pushed, or refused without listing (exit {code}): {said[-300:]}"
    theirs = out(repo, "rev-parse", "HEAD~1")
    code, said = tool(repo, "--seat", FIX, "--push", "--push-includes-others", theirs[:12])
    return (code == 0 and out(remote, "rev-parse", "main") == out(repo, "rev-parse", "HEAD"),
            "refused with the other seat's commit listed; pushed once told, and read the remote back")


def _two_others_unpushed(repo: Path) -> tuple:
    """A remote at the base, then two other seats' commits and one of this seat's, all unpushed."""
    remote = repo.parent / "remote.git"
    git(repo.parent, "init", "-q", "--bare", "-b", "main", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    write(repo, "microscope_agent/questions/q/held.json", '{"committed": "and the person said: do not push"}\n')
    held = commit_as(repo, OTHER, "another seat's commit, held from the remote", "microscope_agent/questions/q/held.json")
    write(repo, "microscope_agent/questions/q/theirs.json", '{"committed": "by a third seat"}\n')
    third = commit_as(repo, REOPENED, "a third seat's commit", "microscope_agent/questions/q/theirs.json")
    write(repo, CARD, card("MINE"))
    mine = commit_as(repo, FIX, "my commit", CARD)
    return remote, held, third, mine


def naive_yes_before_the_list(repo: Path) -> tuple:
    """INC-20261018-01: a push with the yes given in the same command as the
    first --push published architecture-office-20261016-2's e0d09c02, which
    the person had asked be committed and not pushed. The list was printed,
    after the answer to it."""
    remote, held, _third, _mine = _two_others_unpushed(repo)
    git(repo, "push", "-q", "origin", "main")
    published = held in out(remote, "log", "--format=%H", "main")
    return published, "a push made for one seat's commit published the held commit, which nobody had named"


def tool_yes_before_the_list(repo: Path) -> tuple:
    remote, held, third, mine = _two_others_unpushed(repo)
    before = out(remote, "rev-parse", "main")
    checks = []
    for label, flag in (("a bare flag", []), ("one of two named", [held[:12]]),
                        ("an extra hash named", [held[:12], third[:12], mine[:12]])):
        args = ["--seat", FIX, "--push", "--push-includes-others"] + ([",".join(flag)] if flag else [])
        code, said = tool(repo, *args)
        listed = held[:9] in said and third[:9] in said
        checks.append((label, code == 1 and listed and out(remote, "rev-parse", "main") == before))
    code, said = tool(repo, "--seat", FIX, "--push", "--push-includes-others", f"{third[:10]},{held[:10]}")
    rec = last_record(repo)
    published = {p.get("commit"): p.get("committer") for p in (rec.get("pushed") or {}).get("published") or []}
    exact = (code == 0 and out(remote, "rev-parse", "main") == mine and published.get(held) == f"{OTHER}@seat.invalid"
             and len(published) == 3)
    bad = [label for label, ok in checks if not ok]
    return (not bad and exact,
            "a bare flag, a missing hash and an extra hash were each refused with the list, the remote unchanged; "
            f"the exact list pushed and the record names each published commit and whose it was "
            f"(refusals failed: {bad or 'none'}, exact push: {exact})")


def _held_under_mine(repo: Path) -> tuple:
    remote = repo.parent / "remote.git"
    git(repo.parent, "init", "-q", "--bare", "-b", "main", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    write(repo, "microscope_agent/questions/q/held.json", '{"committed": "and the person said: not yet"}\n')
    held = commit_as(repo, OTHER, "another seat's commit the person asked to hold", "microscope_agent/questions/q/held.json")
    write(repo, CARD, card("MINE"))
    mine = commit_as(repo, FIX, "my commit", CARD)
    return remote, held, mine


def naive_hold_said_in_a_window(repo: Path) -> tuple:
    """HP-011, from INC-20261018-01: the person's word to hold e0d09c02 lived
    in one window, where no tool could see it, and a push published it. A
    hold that is said and not recorded is nothing a push can read."""
    remote, held, _mine = _held_under_mine(repo)
    git(repo, "push", "-q", "origin", "main")
    return (held in out(remote, "log", "--format=%H", "main"),
            "the hold was said and not recorded, and the push published the held commit")


def tool_hold_said_in_a_window(repo: Path) -> tuple:
    remote, held, mine = _held_under_mine(repo)
    before = out(remote, "rev-parse", "main")
    reason = "the person, in that seat's window: not yet"
    steps = []
    code, said = tool(repo, "--seat", FIX, "--hold", held, "--why", "not mine to hold")
    steps.append(("another seat's commit cannot be held", code == 1 and "only its own seat" in said))
    code, said = tool(repo, "--seat", OTHER, "--hold", held, "--why", reason)
    steps.append(("the owner holds it", code == 0))
    code, said = tool(repo, "--seat", FIX, "--release", held)
    steps.append(("another seat's commit cannot be released", code == 1 and "only its own seat" in said))
    code, said = tool(repo, "--seat", FIX, "--push", "--push-includes-others", held[:12])
    steps.append(("a held commit refuses the push, even with the exact list",
                  code == 1 and OTHER in said and reason in said and out(remote, "rev-parse", "main") == before))
    code, said = tool(repo, "--seat", OTHER, "--release", held)
    steps.append(("the owner releases it", code == 0))
    code, said = tool(repo, "--seat", FIX, "--push", "--push-includes-others", held[:12])
    steps.append(("after release it pushes", code == 0 and out(remote, "rev-parse", "main") == mine))
    write(repo, CARD, card("MINE", "AGAIN"))
    again = commit_as(repo, FIX, "my second commit", CARD)
    tool(repo, "--seat", FIX, "--hold", again, "--why", "my own, not yet")
    code, said = tool(repo, "--seat", FIX, "--push")
    steps.append(("a hold on one's own commit refuses one's own push",
                  code == 1 and "my own, not yet" in said and out(remote, "rev-parse", "main") == mine))
    bad = [s for s, ok in steps if not ok]
    return (not bad, "only the owner holds or releases; a held commit refuses a push whatever the list names, "
                     f"and pushes once released; one's own hold binds one's own push (failed: {bad or 'none'})")


def naive_head_moves_in_gate(repo: Path) -> tuple:
    """HEAD moving while the gate runs: `git commit` fails with fatal:, and a
    reader filtering for FAIL sees nothing and reads it as done."""
    head = out(repo, "rev-parse", "HEAD")
    write(repo, CARD, card("MINE"))
    (repo / ".git" / "fixture-move-head-once").write_bytes(b"")
    r = git(repo, "commit", "-F", message(repo), "--", CARD, env=env_for(FIX), check=False)
    said = r.stdout.decode("utf-8", "replace")
    mine_in = "MINE" in (blob(repo, "HEAD", CARD) or "")
    return (naive_reads_success(said) and not mine_in and "fatal:" in said and head != out(repo, "rev-parse", "HEAD"),
            "the commit was not made, and the output carried fatal: and no FAIL")


def tool_head_moves_in_gate(repo: Path) -> tuple:
    write(repo, CARD, card("MINE"))
    patch = save_diff(repo, CARD)
    (repo / ".git" / "fixture-move-head-once").write_bytes(b"")
    code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
    rec = last_record(repo)
    kept = blob(repo, "HEAD", "microscope_agent/questions/q/other.json") is not None
    mine = "MINE" in (blob(repo, "HEAD", CARD) or "")
    return (code == 0 and kept and mine and rec.get("retries", {}).get("head_moved") == 1,
            f"the swap on HEAD failed, the tree was rebuilt on the new HEAD and judged again, and both "
            f"changes are in (exit {code}, rebuilt {rec.get('retries', {}).get('head_moved')} time)")


def naive_gate_refuses_a_moved_head(repo: Path) -> tuple:
    """2026-10-17, twice in a row: a plan.md commit landed while the gate ran,
    and check 41 -- which compares the tree being committed with HEAD as it
    is then -- refused plan.md as this seat's. The verdict was on the wrong
    pair of trees, and it reads as the commit's own fault."""
    head = out(repo, "rev-parse", "HEAD")
    write(repo, CARD, card("MINE"))
    for m in ("fixture-move-head-once", "fixture-gate-judges-head"):
        (repo / ".git" / m).write_bytes(b"")
    r = git(repo, "commit", "-F", message(repo), "--", CARD, env=env_for(FIX), check=False)
    said = r.stdout.decode("utf-8", "replace")
    mine_in = "MINE" in (blob(repo, "HEAD", CARD) or "")
    return (r.returncode != 0 and "other.json" in said and not mine_in and out(repo, "rev-parse", "HEAD") != head,
            "refused for another seat's path that landed while the gate ran, and the commit was not made")


def tool_gate_refuses_a_moved_head(repo: Path) -> tuple:
    write(repo, CARD, card("MINE"))
    patch = save_diff(repo, CARD)
    for m in ("fixture-move-head-once", "fixture-gate-judges-head"):
        (repo / ".git" / m).write_bytes(b"")
    code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
    rec = last_record(repo)
    kept = blob(repo, "HEAD", "microscope_agent/questions/q/other.json") is not None
    mine = "MINE" in (blob(repo, "HEAD", CARD) or "")
    if not (code == 0 and kept and mine and rec.get("retries", {}).get("head_moved") == 1):
        return False, f"exit {code}, rebuilt {rec.get('retries', {}).get('head_moved')} times: {said[-300:]}"
    # And a refusal on its merits, with HEAD where it was, stays a refusal.
    (repo / ".git" / "fixture-gate-refuses").write_bytes(b"")
    write(repo, CARD, card("MINE", "AGAIN"))
    patch = save_diff(repo, CARD)
    code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
    rec = last_record(repo)
    return (code == 1 and "the gate refused this tree" in said and rec.get("retries", {}).get("head_moved") == 0,
            f"the refusal of a tree judged against a moved HEAD was not taken as a verdict: rebuilt on the new "
            f"HEAD, judged again, committed; a refusal with HEAD in place stayed one, with no rebuild (exit {code})")


def naive_discarded_gate_lines(repo: Path) -> tuple:
    """HP-010 (2026-10-18), b362056f and 54d26c26: a gate run judged against a
    moved HEAD printed check 41 FAIL lines charging another seat's file. Read
    filtered for FAIL, which is how one seat read it, that says the commit
    carries a file it never touched."""
    write(repo, CARD, card("MINE"))
    for m in ("fixture-move-head-once", "fixture-gate-judges-head"):
        (repo / ".git" / m).write_bytes(b"")
    r = git(repo, "commit", "-F", message(repo), "--", CARD, env=env_for(FIX), check=False)
    fails = [x for x in r.stdout.decode("utf-8", "replace").splitlines() if "FAIL" in x]
    return (any("other.json" in x for x in fails),
            "read filtered for FAIL, the output charges this seat with another seat's file")


def tool_discarded_gate_lines(repo: Path) -> tuple:
    write(repo, CARD, card("MINE"))
    patch = save_diff(repo, CARD)
    for m in ("fixture-move-head-once", "fixture-gate-judges-head"):
        (repo / ".git" / m).write_bytes(b"")
    code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
    lines = [x for x in said.splitlines() if x.strip()]
    bare = [x for x in lines if "FAIL" in x and "discarded attempt" not in x]
    last = lines[-1] if lines else ""
    sha = out(repo, "rev-parse", "HEAD")
    ends = last.startswith(f"seat_commit: committed {sha[:9]}") and CARD in last
    return (code == 0 and not bare and ends,
            f"the discarded run's lines are each marked as discarded, no bare FAIL is left, and the output ends "
            f"with the commit made and its paths (exit {code}, bare FAIL lines {len(bare)}, ends right {ends})")


NEW = "microscope_agent/questions/q/new_card.json"


def naive_intent_to_add_left_behind(repo: Path) -> tuple:
    """2026-10-18, 004da816: a seat ran `git add -N` on eleven new files before
    committing them from a private index. The commit was right, and the shared
    index kept the intent-to-add entries, which then read as staged deletions
    (`DA`) of the files just committed. A plain commit by anyone would have
    deleted them."""
    write(repo, NEW, '{"card": "new"}\n')
    git(repo, "add", "-N", "--", NEW)
    idx = repo / ".git" / "fixture-private.index"
    e = env_for(FIX, GIT_INDEX_FILE=str(idx))
    git(repo, "read-tree", "HEAD", env=e)
    git(repo, "add", "-A", "--", NEW, env=e)
    git(repo, "commit", "-q", "-F", message(repo), env=e)
    status = out(repo, "status", "--porcelain", "--", NEW)
    return status.startswith("D"), f"git status reads {status!r} for the file just committed: a staged deletion"


def tool_intent_to_add_left_behind(repo: Path) -> tuple:
    results = []
    for mode in ("whole-path", "patch"):
        rel = NEW.replace("new_card", f"new_card_{mode.replace('-', '_')}")
        write(repo, rel, '{"card": "new"}\n')
        git(repo, "add", "-N", "--", rel)
        if mode == "whole-path":
            code, said = tool(repo, "--seat", FIX, "--", rel)
            digest = next((x.split("digest ", 1)[1].split(".")[0] for x in said.splitlines() if "digest " in x), "")
            code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--confirm", digest, "--", rel)
        else:
            patch = repo / ".git" / "fixture-mine.patch"
            tool(repo, "--save-patch", str(patch), "--", rel)
            code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
        status = out(repo, "status", "--porcelain", "--", rel)
        results.append((mode, code == 0 and status == "" and "intent-to-add" in said, status))
    bad = [(m, s) for m, ok, s in results if not ok]
    return (not bad, "in both modes the intent-to-add entry was named and moved to the commit, and git status is "
                     f"clean for the file (failed: {bad or 'none'})")


def naive_stale_index(repo: Path) -> tuple:
    """2026-10-15: a commit from a private index moves HEAD and not .git/index,
    so `git diff --cached` shows the inverse of what was just committed, and
    the next plain commit from anyone would carry that reversal."""
    write(repo, CARD, card("MINE"))
    patch = save_diff(repo, CARD)
    private_index_commit_built_early(repo, patch, lambda: None)
    inverse = out(repo, "diff", "--cached", "--name-only")
    return inverse == CARD, f"git diff --cached lists {inverse!r} straight after the commit"


def tool_stale_index(repo: Path) -> tuple:
    staged_rel = "microscope_agent/questions/q/staged.json"
    stale_rel = "microscope_agent/questions/q/stale.json"
    write(repo, staged_rel, '{"v": 1}\n')
    write(repo, stale_rel, '{"v": 1}\n')
    commit_as(repo, "architecture", "a second and a third card", staged_rel, stale_rel)
    # Another seat stages its own version of the second card in the shared index.
    write(repo, staged_rel, '{"v": "the other seat staged this"}\n')
    git(repo, "add", "--", staged_rel)
    staged_before = out(repo, "ls-files", "-s", "--", staged_rel)
    # And commits the third from a private index, leaving the shared entry stale.
    plumbing_commit(repo, OTHER, stale_rel, '{"v": 2}\n', "another seat's commit from a private index")
    # Mine: all three cards, saved as a patch from a different worktree state of the other two.
    write(repo, CARD, card("MINE"))
    write(repo, staged_rel, '{"v": "mine"}\n')
    write(repo, stale_rel, '{"v": "mine"}\n')
    patch = repo / ".git" / "fixture-mine.patch"
    tool(repo, "--save-patch", str(patch), "--", CARD, staged_rel, stale_rel)
    code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
    clean = CARD not in out(repo, "diff", "--cached", "--name-only")
    kept = out(repo, "ls-files", "-s", "--", staged_rel) == staged_before
    # architecture-20261007-1 asked for this on 2026-10-16: a stale entry is
    # named as stale, with the command that clears it, and not as staging.
    named = (f"STALE shared index entry: .git/index holds {stale_rel}" in said
             and f"{staged_rel} is staged in the shared index with content no commit has" in said
             and f"STALE shared index entry: .git/index holds {staged_rel}" not in said)
    # And the record says which entries moved, so the next seat reads it off
    # disk instead of off a watched output (dc4a7843a, 2026-10-26).
    si = last_record(repo).get("shared_index", {})
    recorded = (si.get("moved") == [CARD] and sorted(si.get("kept", [])) == sorted([staged_rel, stale_rel])
                and si.get("not_moved") == [] and si.get("resets") == [0] and si.get("already") == 0)
    return (code == 0 and clean and kept and named and recorded,
            f"the committed card's shared entry moved to the new commit; the card another seat had staged "
            f"was left as staged and called staging; the stale one was named stale with its fix; the record "
            f"names each (exit {code}, clean={clean}, kept={kept}, named={named}, recorded={si or None})")


REFERENCE_TRANSACTION = r"""#!/bin/sh
# The fixtures' ref hook: on request, another git process takes
# .git/index.lock the moment a ref update lands -- inside the tool's window
# between moving HEAD and moving the shared index to it.
G=$(git rev-parse --git-dir)
if [ "$1" = committed ] && [ -f "$G/fixture-lock-after-commit" ]; then
    rm -f "$G/fixture-lock-after-commit"
    : > "$G/index.lock"
fi
cat > /dev/null
exit 0
"""


def _lock_after_commit(repo: Path, *lines: str) -> Path:
    """My change saved as a patch, and the index lock taken as soon as it lands."""
    hook = repo / ".fixture-hooks" / "reference-transaction"
    if not hook.exists():
        hook.write_bytes(REFERENCE_TRANSACTION.encode("utf-8"))
        os.chmod(hook, 0o755)
    write(repo, CARD, card(*lines))
    patch = repo / ".git" / "fixture-mine.patch"
    tool(repo, "--save-patch", str(patch), "--", CARD)
    (repo / ".git" / "fixture-lock-after-commit").write_bytes(b"")
    return patch


def naive_refresh_window(repo: Path) -> tuple:
    """2026-10-26, dc4a7843a: a seat watched the tool's output, stopped at
    "read back", and read `git diff --cached` while the tool was still moving
    the shared index to the commit. It saw the inverse of the commit, reset
    by hand, and nothing on disk could say afterwards whether the tool had
    moved anything."""
    patch = _lock_after_commit(repo, "MINE")
    run = Running(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
    seen = run.wait_for_line("read back")
    inverse = out(repo, "diff", "--cached", "--name-only") if seen else ""
    (repo / ".git" / "index.lock").unlink(missing_ok=True)
    run.finish()
    return seen and inverse == CARD, f"at \"read back\", git diff --cached lists {inverse!r}"


def tool_refresh_window(repo: Path) -> tuple:
    lock = repo / ".git" / "index.lock"
    # The lock released once the tool is seen waiting for it.
    patch = _lock_after_commit(repo, "MINE")
    run = Running(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
    waited = run.wait_for_line("waiting for .git/index.lock")
    lock.unlink(missing_ok=True)
    code, said = run.finish()
    si = last_record(repo).get("shared_index", {})
    first = (waited and code == 0 and "now matches" in said and si.get("moved") == [CARD]
             and si.get("not_moved") == [] and si.get("resets") == [0]
             and out(repo, "diff", "--cached", "--name-only") == "")
    if not first:
        return False, f"a lock released in the window: exit {code}, record {si or None}: {said[-400:]}"
    # And a lock nobody releases: the commit is made and says so, and names the
    # entry it could not move with the command that moves it.
    patch = _lock_after_commit(repo, "MINE", "AGAIN")
    code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch), "--lock-wait", "1")
    rec = last_record(repo)
    si = rec.get("shared_index", {})
    inverse = out(repo, "diff", "--cached", "--name-only")
    lock.unlink(missing_ok=True)
    second = (code == 0 and rec.get("outcome") == "committed" and "nothing was committed" not in said
              and "does not match it" in said and "git reset -q -- <path>" in said
              and "AGAIN" in (blob(repo, "HEAD", CARD) or "") and inverse == CARD
              and si.get("not_moved") == [CARD] and si.get("resets") == ["index.lock held"])
    if not second:
        return False, f"a lock never released in the window: exit {code}, record {rec or None}: {said[-400:]}"
    return True, ("a lock released in the window: waited, moved the entry, and the record says so; one never "
                  "released: the commit is reported made, and the entry it could not move is named in the "
                  "output and the record")


AROUND = "not made through contracts/tools/seat_commit.py"


def _hook_with_notice(repo: Path, with_block: bool) -> bool:
    """The stub gate, plus the real hook's own notice for a seat committing by hand.

    The notice is lifted out of contracts/hooks/pre-commit between its two
    marker lines, with the hook's own IDENT line, so this runs the hook's
    text and not a copy of it. `with_block=False` is the hook as it was
    before HP-006. Returns whether the real hook carries the block at all.
    """
    real = (CONTRACTS / "hooks" / "pre-commit").read_text(encoding="utf-8")
    ident = next((x for x in real.splitlines() if x.startswith("IDENT=$(git var GIT_COMMITTER_IDENT")), "")
    start, end = "# >>> seat-commit-tool notice", "# <<< seat-commit-tool notice"
    found = start in real and end in real
    block = real.split(start, 1)[1].split(end, 1)[0] if found else ""
    body = STUB_HOOK.rstrip("\n")
    assert body.endswith("exit 0"), "the stub gate's last line is its exit"
    body = body[: -len("exit 0")].rstrip("\n")
    extra = (ident + "\n" + block) if (with_block and found and ident) else ""
    hook = repo / ".fixture-hooks" / "pre-commit"
    hook.write_bytes((body + "\n" + extra + "\nexit 0\n").encode("utf-8"))
    os.chmod(hook, 0o755)
    return found and bool(ident)


def naive_around_the_tool(repo: Path) -> tuple:
    """INC-20261016-03 and -05: after the tool landed, 2 of the next 9 commits
    (aa9941d6, 2fcc3bc5) were made by hand, and the gate said nothing about it."""
    _hook_with_notice(repo, with_block=False)
    head = out(repo, "rev-parse", "HEAD")
    write(repo, CARD, card("MINE"))
    r = git(repo, "commit", "-F", message(repo), "--", CARD, env=env_for(FIX), check=False)
    said = r.stdout.decode("utf-8", "replace")
    made = out(repo, "rev-parse", "HEAD") != head
    return (made and AROUND not in said, "a seat's commit by hand went through, and the gate's output said nothing of it")


def tool_around_the_tool(repo: Path) -> tuple:
    if not _hook_with_notice(repo, with_block=True):
        return False, "contracts/hooks/pre-commit carries no seat-commit-tool notice block"
    write(repo, CARD, card("MINE"))
    r = git(repo, "commit", "-F", message(repo), "--", CARD, env=env_for(FIX), check=False)
    by_hand = r.stdout.decode("utf-8", "replace")
    write(repo, CARD, card("MINE", "AGAIN"))
    patch = save_diff(repo, CARD)
    code, through = tool(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
    write(repo, CARD, card("MINE", "AGAIN", "THE PERSON"))
    r = git(repo, "commit", "-F", message(repo), "--", CARD, check=False)
    person = r.stdout.decode("utf-8", "replace")
    ok = AROUND in by_hand and code == 0 and AROUND not in through and AROUND not in person
    return (ok, f"the hook named the seat's commit by hand, and said nothing for the tool's commit or for the "
                f"person's (by hand={AROUND in by_hand}, tool={AROUND in through}, person={AROUND in person})")


def _race(repo: Path) -> Path:
    """A remote at the base, and one commit of this seat's to push."""
    remote = repo.parent / "remote.git"
    git(repo.parent, "init", "-q", "--bare", "-b", "main", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    write(repo, CARD, card("MINE"))
    commit_as(repo, FIX, "my commit", CARD)
    return remote


def naive_push_race(repo: Path) -> tuple:
    """2026-10-16, the tool's first real push: another seat's push published the
    same commits a moment first, this push was rejected ("cannot lock ref"), and
    a rejected push reads as nothing published while the commits are public."""
    remote = _race(repo)
    (repo / ".git" / "fixture-push-race").write_bytes(b"same")
    r = git(repo, "push", "origin", "main", check=False)
    public = out(remote, "rev-parse", "main") == out(repo, "rev-parse", "HEAD")
    return (r.returncode != 0 and public,
            f"the push exited {r.returncode}, and the remote holds its commit anyway")


def tool_push_race(repo: Path) -> tuple:
    remote = _race(repo)
    (repo / ".git" / "fixture-push-race").write_bytes(b"same")
    code, said = tool(repo, "--seat", FIX, "--push")
    rec = last_record(repo)
    if code != 0 or "already contains" not in said or rec.get("outcome") != "already-published":
        return False, f"a rejected push already on the remote was not reported as published (exit {code}): {said[-300:]}"
    # And when the push that got there first carried something else, the
    # refusal stands: what the remote holds does not contain this commit.
    write(repo, CARD, card("MINE", "AGAIN"))
    commit_as(repo, FIX, "my second commit", CARD)
    there = out(remote, "rev-parse", "main")
    other = out(repo, "commit-tree", f"{there}^{{tree}}", "-p", there, input=b"another seat's push\n",
                env=env_for(OTHER))
    (repo / ".git" / "fixture-push-race").write_bytes(other.encode())
    code, said = tool(repo, "--seat", FIX, "--push")
    return (code == 1 and "does not contain" in said and out(remote, "rev-parse", "main") == other,
            f"a push beaten by its own commits exited 0 as already published; one beaten by another commit "
            f"was refused, the remote read back (exit {code})")


FIXTURES = [
    ("a held lock", "lock", naive_held_lock, tool_held_lock),
    ("HEAD moving during the wait, in patch mode", "wait", naive_head_moves_in_wait, tool_head_moves_in_wait),
    ("a patch that no longer applies", "apply", naive_patch_stops_applying, tool_patch_stops_applying),
    ("a digest that no longer matches", "digest", naive_digest, tool_digest),
    ("an identity taken from a message", "identity", naive_identity, tool_identity),
    ("a closed seat", "closed", naive_closed, tool_closed),
    ("a path outside the seat's boundary", "boundary", naive_outside, tool_outside),
    ("a push that is behind", "behind", naive_behind, tool_behind),
    # Beyond the specification's list, for what the tool also claims.
    ("a push that carries other seats' commits", "others", naive_publishes_others, tool_publishes_others),
    ("HEAD moving while the gate runs", "gate", naive_head_moves_in_gate, tool_head_moves_in_gate),
    ("a gate refusal caused by HEAD moving under it", "moved", naive_gate_refuses_a_moved_head,
     tool_gate_refuses_a_moved_head),
    ("a discarded gate run's lines read as a refusal", "discarded", naive_discarded_gate_lines,
     tool_discarded_gate_lines),
    ("the shared index left stale by a private-index commit", "index", naive_stale_index, tool_stale_index),
    ("the shared index read before the tool has moved it", "refresh", naive_refresh_window,
     tool_refresh_window),
    ("another push reaching the remote first", "race", naive_push_race, tool_push_race),
    # HP-009 (2026-10-18): the yes to publishing others' commits names them.
    ("the yes to others' commits given before the list", "yes", naive_yes_before_the_list,
     tool_yes_before_the_list),
    # HP-011 (2026-10-18): a hold is a record a push can read.
    ("a hold said in a window and not recorded", "hold", naive_hold_said_in_a_window,
     tool_hold_said_in_a_window),
    ("an intent-to-add entry left behind as a staged deletion", "ita", naive_intent_to_add_left_behind,
     tool_intent_to_add_left_behind),
    # HP-006 (2026-10-17): not a defect the tool prevents but one the gate reports.
    ("a seat committing around the tool", "around", naive_around_the_tool, tool_around_the_tool),
]


def _writable(func, path, _exc) -> None:
    """git leaves its objects read-only, and on Windows rmtree cannot remove those."""
    os.chmod(path, 0o700)
    func(path)


def run_arm(arm) -> tuple:
    tmp = tempfile.mkdtemp(prefix="sma-seat-commit-")
    try:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        base(repo)
        return arm(repo)
    except Exception as exc:  # an arm that crashes has proved nothing either way
        return False, f"crashed: {type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(tmp, onerror=_writable)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", help="run the fixtures whose key or name contains this")
    args = ap.parse_args(argv)
    chosen = [f for f in FIXTURES if not args.only or args.only in f[1] or args.only in f[0]]
    ok, broken = 0, []
    for name, key, naive, through in chosen:
        reproduced, nd = run_arm(naive)
        held, td = run_arm(through)
        print(f"  [{key}] {name}")
        print(f"      naive: {'FAILS, as on the record' if reproduced else 'DOES NOT REPRODUCE'} -- {nd}")
        print(f"      tool:  {'holds' if held else 'DOES NOT HOLD'} -- {td}")
        if reproduced and held:
            ok += 1
        else:
            broken.append(name + (" (the naive arm no longer fails, so this tests nothing)" if not reproduced
                                  else " (the tool does not hold)"))
    print(f"seat_commit: {ok}/{len(chosen)} fixtures fail the naive way and hold through the tool")
    for b in broken:
        print(f"  BROKEN  {b}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
