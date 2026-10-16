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
    (hooks / "pre-commit").write_bytes(STUB_HOOK.encode("utf-8"))
    os.chmod(hooks / "pre-commit", 0o755)
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
    code, said = tool(repo, "--seat", FIX, "--push", "--push-includes-others")
    return (code == 0 and out(remote, "rev-parse", "main") == out(repo, "rev-parse", "HEAD"),
            "refused with the other seat's commit listed; pushed once told, and read the remote back")


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
    write(repo, staged_rel, '{"v": 1}\n')
    commit_as(repo, "architecture", "a second card", staged_rel)
    # Another seat stages its own version of the second card in the shared index.
    write(repo, staged_rel, '{"v": "the other seat staged this"}\n')
    git(repo, "add", "--", staged_rel)
    staged_before = out(repo, "ls-files", "-s", "--", staged_rel)
    # Mine: both cards, saved as a patch from a different worktree state of the second.
    write(repo, CARD, card("MINE"))
    write(repo, staged_rel, '{"v": "mine"}\n')
    patch = repo / ".git" / "fixture-mine.patch"
    tool(repo, "--save-patch", str(patch), "--", CARD, staged_rel)
    code, said = tool(repo, "--seat", FIX, "-F", message(repo), "--patch", str(patch))
    clean = CARD not in out(repo, "diff", "--cached", "--name-only")
    kept = out(repo, "ls-files", "-s", "--", staged_rel) == staged_before
    return (code == 0 and clean and kept,
            f"the committed card's shared entry moved to the new commit; the card another seat had staged "
            f"was left as staged (exit {code}, clean={clean}, kept={kept})")


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
    ("the shared index left stale by a private-index commit", "index", naive_stale_index, tool_stale_index),
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
