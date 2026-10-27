#!/usr/bin/env python3
"""The commit tool (plan.md 8.3, HP-001).

Seats here commit by re-performing a fragile procedure from prose, and the
record shows what that costs: an amend that replaced a commit with another
seat's work (28761d4, 2026-09-23), a private index built before a lock wait
that would have reverted the commit landing during it (17c2185, 2026-10-15),
and a commit left unmade by a lock race while the seat read its filtered
output as success (2026-10-15). This does that procedure in one place and
records what happened.

    seat_commit.py --save-patch P -- PATH...           save your own change, right after editing
    seat_commit.py --seat S -F MSG --patch P           patch mode: commit exactly that patch
    seat_commit.py --seat S -- PATH...                 whole-path mode: show every hunk and a digest
    seat_commit.py --seat S -F MSG --confirm D -- PATH...   ... and commit, if the digest still matches
    seat_commit.py --seat S --push                     list what a push would publish (and push if it is all yours)
    seat_commit.py --seat S --push --push-includes-others H1,H2   ... naming each other seat's commit
    seat_commit.py --seat S --hold C --why TEXT        your own commit is not to be pushed yet (and why)
    seat_commit.py --seat S --release C                ... and now it may be

What it does, by the numbers of the specification:

1. The identity comes from `contracts/seats.json` at HEAD -- the registry
   check 41 judges a commit against -- and never from a message or from
   `.git/config.worktree`. `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL`
   beat both, so they are set from the row, and `git var GIT_COMMITTER_IDENT`
   is the first line printed. A seat the registry does not hold is refused,
   and so is a closed one unless its row says it was reopened.
2. Every path is classified with the validator's own `seat_boundary_of`,
   loaded from HEAD's `contracts/validate.py`, and judged against the seat's
   `owns`, `excludes` and `paths` the way check 41 judges them, so a path the
   seat does not own is refused at once with the seats that do own it named.
3. The message comes from a file. There is no inline message and no option
   to amend, skip the gate or force; asking for one is refused by name.
4. Patch mode commits exactly the patch: a private index is built from HEAD
   *after* the lock wait and the patch applied to it, so another seat's hunk
   in the same file stays in the worktree. If the patch no longer applies the
   tool refuses and names the hunk. Whole-path mode prints every hunk with a
   digest and commits only when run again with `--confirm <digest>`; a
   worktree that changed in between gives another digest and is refused.
5. `.git/index.lock` is waited for and never removed. The commit is made with
   plumbing -- `write-tree`, `commit-tree -p <base>`, then `update-ref HEAD
   <new> <base>` -- so the ref update is a compare-and-swap on the very base
   the tree was built from. If HEAD moved while the gate ran, the swap fails,
   the tree is rebuilt on the new HEAD and judged again; if a ref lock is
   held (*File exists*), the swap is retried. A tree built on one HEAD is
   never committed onto another. The gate itself is the repository's own
   pre-commit hook, run with the private index as `git commit` runs it.
6. The outcome is read back: the new commit's parent, committer and paths
   are checked against what was meant, and the gate's last lines are printed
   unfiltered, so a `fatal:` is seen as well as a FAIL. Afterwards the shared
   index entry of each committed path is moved to the new commit, but only
   where it still equals the old HEAD's -- where nobody had staged anything.
   The index and both trees are read once each, not once per path, and a
   lock still held then leaves the commit made and names the entries it
   could not move; it never says that nothing was committed.
7. `--push` fetches first, refuses when the branch is behind (a merge is
   needed, and this tool does not merge), and when the push would carry
   other seats' commits it lists them and needs `--push-includes-others`
   naming every one of them by hash, and nothing else (HP-009): a bare flag
   is a yes given before the list is read, which is how a held commit was
   published on 2026-10-18. It
   pushes the exact commit it listed, not whatever HEAD is a moment later,
   and reads the remote back whatever the push exits with: a push rejected
   because another push already published the same commits says they are
   public, and exits 0.
8. Every use is appended to `.git/sma-seat-commit.jsonl`, outside every tree:
   seat, mode, paths, lock wait, retries, outcome, and for a commit what the
   shared index refresh did (`shared_index`: how many entries already
   matched, which were moved, kept as someone's staging or not moved, and
   each reset's exit code).
9. A hold is a record, not a sentence in a window (HP-011). `--hold <commit>
   --why <text>` and `--release <commit>` append to `.git/sma-seat-holds.jsonl`,
   beside that record, and only the seat that committed a commit may hold or
   release it. A push that would publish a held commit is refused, whatever
   `--push-includes-others` names, with the holder and the reason. A commit
   with no hold line is free.

Standard library only, and no syntax newer than 3.9, so it runs under any
interpreter the three computers have, Anaconda 3.9 included. Its fixtures are
`contracts/tools/seat_commit_fixtures.py`.
"""

from __future__ import annotations

import __future__ as _future
import argparse
import ast
import builtins
import hashlib
import json
import os
import posixpath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

RECORD_NAME = "sma-seat-commit.jsonl"
# Held commits (HP-011): append-only, outside every tree, beside the record.
HOLDS_NAME = "sma-seat-holds.jsonl"
# A seat committing with plain `git commit` holds .git/index.lock for the whole
# of its gate, and one pass of the gate took 3 min 58 s on the Office computer
# on 2026-10-16, so a wait shorter than that refuses ordinary work.
DEFAULT_LOCK_WAIT = 600.0
# The person's choice, not an arbitrary limit: "the commit tool's rebuild count
# stays at five as it is", said in the intake seat's window and committed
# verbatim at 51feb21b (Q-20261017-03). A refusal after the fifth rebuild is
# the seat's cue to run the same command again.
DEFAULT_RETRIES = 5
# The message a refusal at that limit carries.
AT_THE_LIMIT = ("nothing was committed. The limit is the person's choice (51feb21b); "
                "run the same command again")
GATE_TAIL = 30
# What '@' becomes in a message delivered by session id (root CLAUDE.md, 2026-09-23).
FULLWIDTH_AT = chr(0xFF20)
# Set in the gate's environment, so the hook can tell a commit made through
# this tool from one made by hand and say so of the second (8.3, HP-006).
MARKER = "SMA_SEAT_COMMIT"

# Asked for by name and refused by name, rather than left to argparse's
# "unrecognized arguments": a seat reaching for one of these is reaching for
# the thing the specification took out, and should be told which rule it is.
FORBIDDEN = {
    "--amend": "there is no amend here: --amend rewrites HEAD, and HEAD moves (28761d4). "
               "Correct a wrong message with a commit that says what the badly named one contains",
    "--no-verify": "the gate is not skippable from this tool. A bypass the person allows is made by "
                   "hand with git and said in its message",
    "-n": "-n is git commit's --no-verify; the gate is not skippable from this tool",
    "--force": "there is no force option: a push is refused when it is behind, and a merge is the answer",
    "-f": "there is no force option",
    "-m": "the message comes from a file (-F), never inline: a long inline message has failed silently twice",
    "--message": "the message comes from a file (-F), never inline",
    "--allow-empty": "an empty commit says nothing about any path, and this tool commits paths",
}


class Refused(Exception):
    """The tool stops, says why, and makes no commit."""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def say(msg: str = "") -> None:
    print(msg, flush=True)


def text(b: bytes) -> str:
    return b.decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# git
# --------------------------------------------------------------------------- #

class Git:
    """git in one repository, with one environment.

    `GIT_INDEX_FILE` is removed from the base environment, so that a question
    about "the index" is about the shared one unless a private index is named
    on purpose. The committer is set from the registry once it is known.
    """

    def __init__(self, root: Path, env: dict):
        self.root = root
        self.env = env

    def run(self, *args: str, env: dict | None = None, input: bytes | None = None,
            check: bool = True, merge: bool = False) -> subprocess.CompletedProcess:
        out = subprocess.run(["git", *args], cwd=str(self.root), env=env or self.env, input=input,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT if merge else subprocess.PIPE)
        if check and out.returncode:
            err = text(out.stdout if merge else out.stderr).strip()
            raise Refused(f"git {' '.join(args[:3])} failed: {err}")
        return out

    def out(self, *args: str, **kw) -> str:
        return text(self.run(*args, **kw).stdout).strip()

    def rev(self, ref: str) -> str | None:
        r = self.run("rev-parse", "--verify", "-q", f"{ref}^{{commit}}", check=False)
        if r.returncode:
            return None
        return text(r.stdout).strip() or None

    def path_in_gitdir(self, name: str) -> Path:
        p = Path(self.out("rev-parse", "--git-path", name))
        return p if p.is_absolute() else self.root / p

    def intent_to_add(self, path: str) -> bool:
        """Whether the shared index holds `path` as `git add -N` leaves it.

        Such an entry is no one's staging: it says a file exists and holds
        nothing of it. ls-files -s shows it as the empty blob, the same as a
        staged empty file, so the flag is read from --debug: git's
        CE_INTENT_TO_ADD bit, 0x20000000.
        """
        raw = text(self.run("--literal-pathspecs", "ls-files", "--debug", "--", path).stdout)
        m = re.search(r"flags:\s*([0-9a-fA-F]+)", raw)
        return bool(m and int(m.group(1), 16) & 0x20000000)

    def entry(self, ref_or_index: str, path: str, env: dict | None = None) -> tuple:
        """(mode, sha) of one path in a tree, or in the shared index when given ":index"."""
        if ref_or_index == ":index":
            raw = self.run("--literal-pathspecs", "ls-files", "-s", "-z", "--", path, env=env).stdout
            for row in raw.split(b"\0"):
                if row:
                    meta, _, _ = row.partition(b"\t")
                    mode, sha, _stage = text(meta).split()
                    return (mode, sha)
            return ("", "")
        raw = self.run("--literal-pathspecs", "ls-tree", "-z", ref_or_index, "--", path).stdout
        for row in raw.split(b"\0"):
            if row:
                meta, _, _ = row.partition(b"\t")
                mode, _kind, sha = text(meta).split()
                return (mode, sha)
        return ("", "")

    def entries(self, ref_or_index: str, paths: list[str]) -> dict:
        """`entry` for many paths, from one read of the whole index or tree.

        One git call costs about a quarter of a second on the Office computer,
        so reading three entries per path held the shared index stale for
        29.4 s after a 37-path commit (dc4a7843a, 2026-10-26). The paths are
        not passed as pathspecs, so a long list never meets a command-line limit.
        """
        if ref_or_index == ":index":
            raw, in_tree = self.run("ls-files", "-s", "-z").stdout, False
        else:
            raw, in_tree = self.run("ls-tree", "-r", "-z", "--full-tree", ref_or_index).stdout, True
        want, found = set(paths), {}
        for row in raw.split(b"\0"):
            meta, tab, name = row.partition(b"\t")
            p = text(name)
            if not tab or p not in want or p in found:  # the first stage of a conflicted path, as `entry`
                continue
            f = text(meta).split()
            found[p] = (f[0], f[2]) if in_tree else (f[0], f[1])
        return {p: found.get(p, ("", "")) for p in paths}


def base_env() -> dict:
    env = dict(os.environ)
    env.pop("GIT_INDEX_FILE", None)
    return env


def to_top(git: Git, paths: list[str]) -> list[str]:
    """The caller's paths, relative to the root git commands here run in.

    An agent seat runs from its own directory, so `questions/q/card.json` from
    microscope_agent/ is `microscope_agent/questions/q/card.json` to git
    running at the root. A path that leaves the working copy is refused.
    """
    prefix = text(subprocess.run(["git", "rev-parse", "--show-prefix"], stdout=subprocess.PIPE,
                                 env=git.env).stdout).strip()
    out = []
    for p in paths:
        if p.startswith(":"):
            out.append(p)
            continue
        if os.path.isabs(p):
            p = os.path.relpath(p, os.getcwd())
        q = posixpath.normpath(posixpath.join(prefix, p.replace("\\", "/")))
        if q == ".." or q.startswith("../") or posixpath.isabs(q) or re.match(r"^[A-Za-z]:", q):
            raise Refused(f"{p!r} is outside this working copy")
        out.append("." if q == "." else q)
    return out


def find_root() -> Path:
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=base_env())
    if r.returncode:
        raise Refused("not inside a git working copy")
    return Path(text(r.stdout).strip())


# --------------------------------------------------------------------------- #
# the record (8)
# --------------------------------------------------------------------------- #

class Record:
    """One line per use in .git/sma-seat-commit.jsonl, written however it ends."""

    def __init__(self, git: Git | None, argv: list[str]):
        self.git = git
        self.row = {"ts": now(), "pid": os.getpid(), "seat": None, "mode": None, "paths": [],
                    "lock_wait_s": 0.0, "retries": {"head_moved": 0, "ref_locked": 0},
                    "outcome": None, "reason": None, "base": None, "commit": None, "gate": None,
                    "argv": argv}

    def write(self) -> None:
        if self.git is None:
            return
        try:
            common = Path(self.git.out("rev-parse", "--git-common-dir"))
            common = common if common.is_absolute() else self.git.root / common
            self.row["lock_wait_s"] = round(self.row["lock_wait_s"], 2)
            with open(common / RECORD_NAME, "a", encoding="utf-8") as f:
                f.write(json.dumps(self.row, ensure_ascii=False) + "\n")
        except (OSError, Refused) as exc:  # the record must never turn an outcome into a crash
            say(f"seat_commit: could not append to {RECORD_NAME}: {exc}")


# --------------------------------------------------------------------------- #
# the registry (1) and the boundary (2)
# --------------------------------------------------------------------------- #

MARK = re.compile(r"\b(closed|deferred|reopened)\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def seat_state(row: dict) -> str:
    """open, closed, deferred -- or unreadable, which stops.

    `status` is free text in the registry, and what it says is dated:
    `closed 2026-10-12 -- ...`, `deferred 2026-09-18`, and for a seat the
    person opened again, `... REOPENED 2026-10-15: ...` later in the same
    string. The latest dated word decides. An undated "closed" in the prose
    of a reopened row ("had not seen the closed row") is not a marker. A
    status carrying no dated word at all is not guessed at (P0). A row with
    no status whose note opens with CLOSED is closed: one registered seat is
    recorded that way.
    """
    status = str(row.get("status") or "")
    marks = [(m.group(2), m.start(), m.group(1).lower()) for m in MARK.finditer(status)]
    if marks:
        latest = max(marks)[2]
        return "open" if latest == "reopened" else latest
    if status.strip():
        return "unreadable"
    if str(row.get("note") or "").startswith("CLOSED"):
        return "closed"
    return "open"


def load_registry(git: Git, ref: str = "HEAD") -> dict:
    """The registry at `ref`: what check 41 reads for the commit about to be made."""
    r = git.run("show", f"{ref}:contracts/seats.json", check=False)
    if r.returncode:
        raise Refused(f"{ref} holds no contracts/seats.json, so no seat has an identity here")
    try:
        return json.loads(text(r.stdout))
    except json.JSONDecodeError as exc:
        raise Refused(f"contracts/seats.json at {ref} is not JSON: {exc}")


def load_boundary_of(git: Git, ref: str = "HEAD"):
    """`seat_boundary_of` from the validator at `ref`, and only it.

    The validator reads its sibling files at import, so importing a copy of
    it means exporting contracts/. Instead the function and every top-level
    name it reaches are lifted out of the source by `ast` and run alone --
    the validator's own text, not a rewrite of it, so the two cannot drift.
    HEAD's copy, not the working copy's: another seat may be mid-edit in the
    shared file (root CLAUDE.md, "--commit-range freezes the data and not
    the checker"). A name it reaches that is neither top-level nor a builtin
    stops the tool rather than being guessed at.
    """
    r = git.run("show", f"{ref}:contracts/validate.py", check=False)
    if r.returncode:
        raise Refused(f"{ref} holds no contracts/validate.py, so no path can be classified")
    src = text(r.stdout)
    tree = ast.parse(src)
    top: dict = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            top[node.name] = node
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    top[t.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            top[node.target.id] = node
    allowed = {"re"} | set(dir(builtins))
    want, seen, pick = ["seat_boundary_of"], set(), []
    while want:
        name = want.pop()
        if name in seen:
            continue
        seen.add(name)
        if name not in top:
            if name in allowed:
                continue
            raise Refused(f"the validator's seat_boundary_of reaches {name!r}, which this tool "
                          "cannot load on its own; classify by hand and tell a manager")
        node = top[name]
        local = set()
        if isinstance(node, ast.FunctionDef):
            local = {a.arg for a in node.args.args + node.args.kwonlyargs}
            local |= {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in local:
                want.append(n.id)
        if node not in pick:
            pick.append(node)
    pick.sort(key=lambda n: n.lineno)
    mod = ast.Module(body=pick, type_ignores=[])
    ns = {"re": re, "__builtins__": builtins}
    exec(compile(mod, f"{ref}:contracts/validate.py", "exec",
                 flags=_future.annotations.compiler_flag, dont_inherit=True), ns)
    return ns["seat_boundary_of"]


def judge(row: dict, path: str, boundary_of) -> str | None:
    """Why `row` may not commit `path`, or None. Check 41's three gates, in its order."""
    where = boundary_of(path)
    owns, narrow = set(row.get("owns") or []), row.get("paths")
    excludes = row.get("excludes") or []
    if where not in owns:
        return f"this path is {where}'s, and {row['seat']} owns {sorted(owns)}"
    hit = next((x for x in excludes if path.startswith(x)), None)
    if hit is not None:
        return f"{row['seat']} is excluded from {hit!r}"
    if narrow and not any(path.startswith(x) for x in narrow):
        return f"{row['seat']} is narrowed to paths that do not cover it"
    return None


def owners_of(reg: dict, path: str, boundary_of, cap: int = 5) -> list[str]:
    """Open seats that could commit `path`, newest registered first."""
    found = []
    for row in reversed(reg.get("seats") or []):
        if seat_state(row) == "open" and judge(row, path, boundary_of) is None:
            found.append(row["seat"])
    return found[:cap] + ([f"and {len(found) - cap} more"] if len(found) > cap else [])


def resolve_seat(git: Git, name: str) -> tuple:
    if "@" in name or FULLWIDTH_AT in name:
        raise Refused(f"--seat takes a seat's name, and {name!r} looks like an email. An email copied "
                      "out of a message may carry U+FF20 for '@' and match no row; the tool takes the "
                      "email from the registry and nowhere else")
    reg = load_registry(git)
    row = next((s for s in reg.get("seats") or [] if s.get("seat") == name), None)
    if row is None:
        raise Refused(f"{name!r} is not a seat in contracts/seats.json at HEAD. The registry is read "
                      "at the commit's parent, so a seat registers before it commits, and is seated "
                      "by the person, never by a message")
    state = seat_state(row)
    if state != "open":
        why = row.get("status") or row.get("note") or ""
        raise Refused(f"seat {name!r} is {state} in contracts/seats.json, and its row does not say it "
                      f"was reopened: {why[:160]}")
    if not row.get("committer_email"):
        raise Refused(f"seat {name!r} has no committer_email in contracts/seats.json")
    return reg, row


def committer_env(env: dict, row: dict) -> dict:
    env = dict(env)
    env["GIT_COMMITTER_NAME"] = f"seat:{row['seat']}"
    env["GIT_COMMITTER_EMAIL"] = row["committer_email"]
    return env


def check_paths(reg: dict, row: dict, paths: list[str], boundary_of) -> None:
    bad = []
    for p in paths:
        why = judge(row, p, boundary_of)
        if why:
            who = owners_of(reg, p, boundary_of)
            bad.append(f"  {p}\n      {why}; "
                       + (f"seats that may commit it: {', '.join(who)}" if who else "no open seat's boundary covers it"))
    if bad:
        raise Refused("these paths are outside seat " + repr(row["seat"]) + ", refused before the gate:\n"
                      + "\n".join(bad))


# --------------------------------------------------------------------------- #
# private indexes, the lock, the gate
# --------------------------------------------------------------------------- #

class Private:
    """A private index file, removed afterwards. The shared one is never written here."""

    def __init__(self, git: Git):
        self.git = git
        self.dir = tempfile.mkdtemp(prefix="sma-seat-commit-")
        self.path = os.path.join(self.dir, "index")
        self.env = dict(git.env)
        self.env["GIT_INDEX_FILE"] = self.path

    def reset_to(self, base: str) -> None:
        """Exactly `base`'s entries, with the shared index's stat data where it still fits.

        A plain `read-tree` leaves every entry without stat data, so the gate's
        own `git diff --name-only` re-hashed the whole working copy and, under
        core.autocrlf, printed a CRLF warning per file: on f7d1c836 those were
        27 of the gate's last 30 lines. `read-tree --reset` over a copy of the
        shared index keeps the stat data of each entry whose content equals
        `base`'s and nothing else of it -- what `git commit -- <paths>` gets by
        starting from the shared index. The copy is read, never the shared
        file written. Without a readable shared index it falls back to the
        plain form, which is slower and as correct.
        """
        if os.path.exists(self.path):
            os.remove(self.path)
        try:
            shutil.copyfile(str(self.git.path_in_gitdir("index")), self.path)
        except OSError:
            pass
        if os.path.exists(self.path):
            if self.git.run("read-tree", "--reset", base, env=self.env, check=False).returncode == 0:
                return
            os.remove(self.path)
        self.git.run("read-tree", base, env=self.env)

    def paths(self, base: str) -> list[str]:
        raw = self.git.run("diff", "--cached", "--name-only", "-z", "--no-renames", base, "--",
                           env=self.env).stdout
        return [text(x) for x in raw.split(b"\0") if x]

    def diff(self, base: str, binary: bool = True) -> bytes:
        args = ["diff", "--cached", "--no-renames", "--no-color", "--no-ext-diff"]
        args += ["--binary", "--full-index"] if binary else []
        return self.git.run(*args, base, "--", env=self.env).stdout

    def close(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


def wait_for(path: Path, limit: float, label: str, rec: Record) -> None:
    """Wait while another git process holds `path`. Never remove it."""
    t0 = time.monotonic()
    told = False
    while path.exists():
        if not told:
            say(f"seat_commit: waiting for {label} -- another git process holds it, and this tool "
                "never removes it")
            told = True
        if time.monotonic() - t0 > limit:
            rec.row["lock_wait_s"] += time.monotonic() - t0
            raise Refused(f"{label} was still held after {limit:.0f} s, so nothing was committed. It was "
                          "not removed: a lock is removed by the process that took it, or by a person "
                          "who has checked that no git process is running")
        time.sleep(0.2)
    rec.row["lock_wait_s"] += time.monotonic() - t0
    if told:
        say(f"seat_commit: {label} is free after {time.monotonic() - t0:.1f} s")


class GateRun:
    """One run of the gate: its lines and exit code, held until it is known
    whether this run judged the commit that lands (HP-010)."""

    def __init__(self, lines: list, code: int, installed: bool = True):
        self.lines, self.code, self.installed = lines, code, installed

    @property
    def refused(self) -> bool:
        return self.installed and self.code != 0


def run_gate(git: Git, priv: Private, msgfile: str, rec: Record) -> GateRun:
    """The repository's own pre-commit hook, judged on the private index.

    `git commit` points GIT_INDEX_FILE at the index it is committing and runs
    the hook; this does the same, so the hook judges exactly the tree that
    will be committed. Its lines are returned, not printed: whether they are
    this commit's verdict is known only once HEAD has been read again, and a
    run judged against a moved HEAD is printed marked as discarded
    (show_gate). A hook that is not installed is said, not hidden -- `git
    commit` would also commit without it, and installing it is a manager's
    call (root CLAUDE.md).
    """
    env = dict(priv.env)
    env[MARKER] = "1"
    out = git.run("hook", "run", "pre-commit", env=env, check=False, merge=True)
    body = text(out.stdout)
    if out.returncode and "cannot find a hook named pre-commit" in body:
        rec.row["gate"] = "not installed"
        say("seat_commit: NO pre-commit hook is installed in this working copy, so no gate judged "
            "this commit. git commit would not have run one either")
        return GateRun([], 0, installed=False)
    run = GateRun(body.rstrip("\n").splitlines(), out.returncode)
    if run.refused:
        return run
    cm = git.run("hook", "run", "--ignore-missing", "commit-msg", "--", msgfile, env=env,
                 check=False, merge=True)
    if cm.returncode:
        say(text(cm.stdout))
        raise Refused("the commit-msg hook refused the message; nothing was committed")
    return run


def show_gate(run: GateRun, attempt: int, base: str, moved_to: str | None = None) -> None:
    """Print one gate run: as this commit's verdict, or marked as discarded.

    HP-010 (2026-10-18): a run judged against a HEAD that moved under it
    printed check 41 FAIL lines charging another seat's file, bare, and the
    commit then landed on the rebuild. Read filtered for FAIL -- which the
    root CLAUDE.md warns against and a seat did anyway -- that said the
    landed commit carried a file it never touched. So every line of a
    discarded run carries the attempt and its base, and only the run that
    judged the outcome is printed plain. All of a refusal, the tail of a
    pass: a refusal's first FAIL is the one to read.
    """
    if not run.installed:
        return
    shown = run.lines if run.code else run.lines[-GATE_TAIL:]
    span = f"all {len(shown)}" if len(shown) == len(run.lines) else f"last {len(shown)} of {len(run.lines)}"
    if moved_to is None:
        say(f"--- gate attempt {attempt} on {base[:9]}: {span} lines, unfiltered (exit {run.code}) ---")
        for line in shown:
            say(line)
        say("--- end of the gate ---")
        return
    say(f"--- gate attempt {attempt} on {base[:9]}: DISCARDED, HEAD moved to {moved_to[:9]} while it ran, "
        f"so these {span} lines (exit {run.code}) are not this commit's verdict ---")
    for line in shown:
        say(f"discarded attempt {attempt} on {base[:9]} | {line}")
    say(f"--- end of discarded attempt {attempt} ---")


def clean_message(git: Git, path: str) -> bytes:
    """git commit -F's default cleanup ("whitespace") is git stripspace."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise Refused(f"cannot read the message file {path}: {exc}")
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise Refused(f"{path} is UTF-16 (PowerShell 5.1's redirection writes that); write it as UTF-8")
    msg = git.run("stripspace", input=raw).stdout
    if not msg.strip():
        raise Refused(f"the message in {path} is empty")
    return msg


# --------------------------------------------------------------------------- #
# building the tree
# --------------------------------------------------------------------------- #

FAILED_AT = re.compile(r"patch failed: (.+?):(\d+)")


def apply_patch(git: Git, priv: Private, base: str, patch: Path, moved_from: str | None) -> None:
    r = git.run("apply", "--cached", "--recount", "--whitespace=nowarn", "-v", str(patch),
                env=priv.env, check=False, merge=True)
    if r.returncode == 0:
        return
    err = text(r.stdout)
    where = FAILED_AT.findall(err)
    hunks = []
    body = text(patch.read_bytes())
    for f, line in where:
        head = next((h for h in re.findall(r"^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@.*$", body, re.M)
                     if h == line), None)
        hunks.append(f"{f}, the hunk starting at line {line}" + ("" if head else " (as git reports it)"))
    moved = (f" HEAD moved since this run began ({moved_from[:9]} -> {base[:9]}), and the patch no longer "
             "applies to what is there now." if moved_from and moved_from != base else "")
    raise Refused("the patch does not apply to HEAD " + base[:9] + "." + moved
                  + (" Failing: " + "; ".join(hunks) + "." if hunks else "")
                  + " Nothing was committed, and no tree built on an earlier HEAD is used instead."
                  + "\n" + "\n".join("    " + x for x in err.strip().splitlines()[-12:]))


def build(git: Git, priv: Private, base: str, mode: str, patch: Path | None,
          pathspecs: list[str], moved_from: str | None = None) -> list[str]:
    priv.reset_to(base)
    if mode == "patch":
        apply_patch(git, priv, base, patch, moved_from)
    else:
        r = git.run("add", "-A", "--", *pathspecs, env=priv.env, check=False)
        if r.returncode:
            raise Refused(f"git add in the private index failed: {text(r.stderr).strip()}")
    paths = priv.paths(base)
    if not paths:
        raise Refused("nothing differs from HEAD " + base[:9] + " in "
                      + ("the patch" if mode == "patch" else "these paths") + "; nothing to commit")
    return paths


def digest_of(diff: bytes) -> str:
    return hashlib.sha256(diff).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# committing
# --------------------------------------------------------------------------- #

def commit(git: Git, args, row: dict, reg: dict, boundary_of, rec: Record) -> str:
    mode = "patch" if args.patch else "whole-path"
    rec.row["mode"] = mode
    patch = Path(args.patch).resolve() if args.patch else None
    if patch is not None and not patch.is_file():
        raise Refused(f"no patch file at {args.patch}")
    msg = clean_message(git, args.message_file)
    subject = text(msg).splitlines()[0][:200]
    msgdir = tempfile.mkdtemp(prefix="sma-seat-commit-msg-")
    msgfile = os.path.join(msgdir, "COMMIT_EDITMSG")
    Path(msgfile).write_bytes(msg)
    index_lock = git.path_in_gitdir("index.lock")
    priv = Private(git)
    try:
        # Before the wait: refuse early what would be refused anyway.
        first = git.rev("HEAD")
        if not first:
            raise Refused("HEAD has no commit to build on")
        paths = build(git, priv, first, mode, patch, args.paths)
        rec.row["paths"] = paths
        check_paths(reg, row, paths, boundary_of)
        if mode == "whole-path" and digest_of(priv.diff(first)) != args.confirm:
            raise Refused(f"the digest of these paths is now {digest_of(priv.diff(first))}, not "
                          f"{args.confirm}: the worktree or HEAD changed since you looked. Run without "
                          "--confirm, read every hunk again, and confirm the new digest")
        if patch is not None:
            show_patch_summary(git, priv, first)
        for p in paths:
            say_shared(git, first, p)

        attempt = 0
        gate_runs = 0
        while True:
            # Inside the wait: the tree is built only after the lock is free,
            # on the HEAD read at that moment.
            wait_for(index_lock, args.lock_wait, ".git/index.lock", rec)
            base = git.rev("HEAD")
            rec.row["base"] = base
            paths = build(git, priv, base, mode, patch, args.paths, moved_from=first)
            rec.row["paths"] = paths
            check_paths(reg, row, paths, boundary_of)
            if mode == "whole-path":
                d = digest_of(priv.diff(base))
                if d != args.confirm:
                    raise Refused(f"the digest of these paths is now {d}, not {args.confirm}: something "
                                  "changed while waiting. Nothing was committed; look again")
            gate_runs += 1
            gate = run_gate(git, priv, msgfile, rec)
            if gate.refused:
                # The gate compares this tree with HEAD as it is when it
                # runs, so a commit that landed meanwhile shows up as this
                # seat removing that commit's work -- check 41 refused
                # plan.md twice on 2026-10-17 that way. That verdict is on the
                # wrong pair of trees, so it is a moved HEAD, not a refusal.
                head = git.rev("HEAD")
                if head == base:
                    show_gate(gate, gate_runs, base)
                    rec.row["gate"] = "refused"
                    raise Refused("the gate refused this tree; read its lines above. Nothing was committed")
                show_gate(gate, gate_runs, base, moved_to=head)
                attempt += 1
                rec.row["retries"]["head_moved"] += 1
                if attempt > args.retries:
                    raise Refused(f"HEAD moved under the gate {attempt} times; {AT_THE_LIMIT}")
                say(f"seat_commit: the gate refused, and HEAD moved to {git.rev('HEAD')[:9]} while it ran, so "
                    f"it judged a tree built on {base[:9]} against a newer HEAD. Not a verdict: rebuilt on the "
                    "new HEAD and judged again")
                continue
            tree = git.out("write-tree", env=priv.env)
            sign = ["-S"] if git.out("config", "--bool", "--default", "false", "commit.gpgsign") == "true" else []
            new = git.out("commit-tree", tree, "-p", base, *sign, "-F", msgfile)
            moved = False
            for _ in range(args.retries + 1):
                wait_for(index_lock, args.lock_wait, ".git/index.lock", rec)
                r = git.run("update-ref", "-m", f"commit: {subject}", "HEAD", new, base, check=False)
                if r.returncode == 0:
                    break
                if git.rev("HEAD") != base:
                    moved = True
                    break
                rec.row["retries"]["ref_locked"] += 1
                say(f"seat_commit: the ref is locked by another git process ({text(r.stderr).strip()}); "
                    "retrying, not reporting it done")
                time.sleep(0.5)
            else:
                raise Refused(f"HEAD could not be updated after {args.retries + 1} tries because another "
                              f"process kept its ref locked. Nothing was committed; commit {new[:9]} "
                              "exists unattached and will be collected")
            if not moved:
                show_gate(gate, gate_runs, base)
                break
            show_gate(gate, gate_runs, base, moved_to=git.rev("HEAD"))
            attempt += 1
            rec.row["retries"]["head_moved"] += 1
            if attempt > args.retries:
                raise Refused(f"HEAD moved under the gate {attempt} times; {AT_THE_LIMIT}")
            say(f"seat_commit: HEAD moved to {git.rev('HEAD')[:9]} while the gate ran, so the tree built "
                f"on {base[:9]} is discarded and rebuilt on the new HEAD")
        rec.row["commit"] = new
        rec.row["gate"] = "passed" if gate.installed else "not installed"
        rec.row["gate_runs"] = gate_runs
        rec.row["outcome"] = "committed-unverified"
        verify(git, row, new, base, paths)
        reset_shared_entries(git, base, new, paths, args.lock_wait, rec)
        say(git.out("log", "-1", "--stat", "--format=%H%n  committer %cn <%ce>%n  author    %an <%ae>%n%n    %s",
                    new))
        # The last word is the commit actually made: a run marked discarded
        # above is history, and this line is what landed (HP-010).
        say(f"seat_commit: committed {new[:9]} on {base[:9]}, judged by gate attempt {gate_runs}, "
            f"{len(paths)} paths: {', '.join(paths)}")
        rec.row["outcome"] = "committed"
        return new
    finally:
        priv.close()
        shutil.rmtree(msgdir, ignore_errors=True)


def show_patch_summary(git: Git, priv: Private, base: str) -> None:
    """What the patch holds, so a hunk that is not the seat's can still be seen and cut."""
    say("seat_commit: the patch holds")
    say(text(git.run("diff", "--cached", "--stat", "--no-renames", base, "--", env=priv.env).stdout).rstrip())
    heads = re.findall(rb"^(?:diff --git .*|@@ .*)$", priv.diff(base, binary=False), re.M)
    for h in heads[:60]:
        say("    " + text(h))
    if len(heads) > 60:
        say(f"    ... and {len(heads) - 60} more")


def verify(git: Git, row: dict, new: str, base: str, paths: list[str]) -> None:
    """Read the commit back; a mismatch is reported, never assumed away."""
    info = git.out("log", "-1", "--format=%P%x00%cn%x00%ce", new).split("\x00")
    parents, cn, ce = info[0].split(), info[1], info[2]
    got = sorted(text(x) for x in git.run("diff-tree", "--no-commit-id", "--name-only", "-r", "-z",
                                          "--no-renames", new).stdout.split(b"\0") if x)
    head = git.rev("HEAD")
    contained = head == new or git.run("merge-base", "--is-ancestor", new, head, check=False).returncode == 0
    wrong = []
    if parents != [base]:
        wrong.append(f"its parent is {parents}, not {base}")
    if ce != row["committer_email"] or cn != f"seat:{row['seat']}":
        wrong.append(f"its committer is {cn} <{ce}>, not seat:{row['seat']} <{row['committer_email']}>")
    if got != sorted(paths):
        wrong.append(f"it touches {got}, not {sorted(paths)}")
    if not contained:
        wrong.append("HEAD does not contain it")
    if wrong:
        raise Refused(f"commit {new[:9]} was made and is NOT what was meant: " + "; ".join(wrong)
                      + ". Do not amend it; tell the person")
    say(f"seat_commit: read back {new[:9]}: parent {base[:9]}, committer {cn}, {len(paths)} paths, in HEAD")


def reset_shared_entries(git: Git, base: str, new: str, paths: list[str], limit: float, rec: Record) -> None:
    """Move the shared index entries of committed paths to the new commit -- where nobody staged.

    A commit from a private index moves HEAD and leaves `.git/index` where it
    was, so `git diff --cached` shows the inverse of what was just committed
    and the next plain `git commit` from anyone carries that reversal
    (2026-10-15). An entry that still equals the old HEAD's is stale and is
    moved. One that equals the new commit's needs nothing. Any other entry is
    somebody's staging, and is left exactly as it is.

    The commit has landed by now, so nothing here may say it did not: a lock
    still held, or a reset that fails, leaves the commit made and names the
    paths whose entries do not match it. What was done goes into the record
    as `shared_index` -- before it, a seat could not tell from disk whether
    this ran and moved nothing or never ran (dc4a7843a, 2026-10-26).
    """
    shared, old, now_ = git.entries(":index", paths), git.entries(base, paths), git.entries(new, paths)
    stale, kept = [], []
    done = {"already": 0, "moved": [], "kept": kept, "not_moved": [], "resets": []}
    rec.row["shared_index"] = done
    for p in paths:
        if shared[p] == now_[p]:
            done["already"] += 1
        elif shared[p] == old[p]:
            stale.append(p)
        elif git.intent_to_add(p):
            # `git add -N` marks a file and stages none of it, so it is no
            # one's staging. Left alone, it reads as a staged deletion of the
            # file just committed (`DA`), which the next plain commit from
            # anyone would carry (004da816, 2026-10-18).
            say(f"seat_commit: {p} had an intent-to-add entry (git add -N) in the shared index; it is moved "
                "to the commit. This tool takes untracked files itself, so add -N is not needed before it")
            stale.append(p)
        else:
            kept.append(p)
    for p in kept:
        say_shared(git, new, p, after=True)
    why = ""
    for _ in range(3 if stale else 0):
        try:
            wait_for(git.path_in_gitdir("index.lock"), limit, ".git/index.lock", rec)
        except Refused:
            # wait_for's own refusal says nothing was committed, which stopped
            # being true at update-ref.
            done["resets"].append("index.lock held")
            why = f".git/index.lock was still held after {limit:.0f} s"
            break
        r = git.run("--literal-pathspecs", "reset", "-q", new, "--", *stale, check=False)
        done["resets"].append(r.returncode)
        if r.returncode == 0:
            break
        why = f"git reset exited {r.returncode}: {text(r.stderr).strip()[-300:]}"
        time.sleep(0.5)
    after = git.entries(":index", stale) if stale else {}
    done["moved"] = [p for p in stale if after[p] == now_[p]]
    done["not_moved"] = [p for p in stale if after[p] != now_[p]]
    matched = (f"{len(done['moved']) + done['already']} of {len(paths)} committed paths "
               f"({len(done['moved'])} moved, {done['already']} already there)")
    if not done["not_moved"]:
        say(f"seat_commit: the shared index now matches {new[:9]} for {matched}"
            + (f"; the other {len(kept)} are left as they are, named above" if kept else ""))
        return
    done["error"] = (why or "the reset exited 0 and the entries still differ")[:500]
    say(f"seat_commit: the commit is made, and the shared index does not match it for "
        f"{', '.join(done['not_moved'])} -- {done['error']}. It matches for {matched}. `git diff --cached` "
        "shows the inverse of each until `git reset -q -- <path>` is run for it, if nobody has staged it since")


def stale_since(git: Git, ref: str, path: str, shared: tuple) -> str | None:
    """The commit whose version of `path` the shared index still holds, if any.

    A commit made from a private index moves HEAD and not `.git/index`, so
    the shared entry is left at the version before it -- a version history
    has. Content history never had is somebody's staging instead. One
    `git log --raw` over the path's last changes answers which.
    """
    raw = git.out("-c", "core.quotepath=false", "log", "-n", "30", "--no-renames", "--raw", "--no-abbrev",
                  "--format=C %H", ref, "--", path)

    def same(mode: str, sha: str) -> bool:
        return not shared[1] if set(sha) == {"0"} else (mode, sha) == shared

    commit = None
    for line in raw.splitlines():
        if line.startswith("C "):
            commit = line[2:].strip()
        elif line.startswith(":") and commit:
            meta, _, p = line.partition("\t")
            if p != path:
                continue
            src_mode, dst_mode, src, dst = meta[1:].split()[:4]
            if same(dst_mode, dst):
                return commit
            if same(src_mode, src):
                return f"{commit}^"
    return None


def say_shared(git: Git, ref: str, path: str, after: bool = False) -> None:
    """Say what the shared index holds for `path` when it is not `ref`'s version.

    This tool never reads the shared index to commit, so neither case changes
    what it commits. The stale case is said because it is the one that cost a
    seat an hour on 2026-10-15: `git diff --cached` shows the inverse of a
    commit already made, and a plain `git commit` from anyone carries it.
    """
    shared = git.entry(":index", path)
    if shared == git.entry(ref, path):
        return
    if git.intent_to_add(path):
        say(f"seat_commit: {path} has an intent-to-add entry (git add -N) in the shared index. It is not "
            "needed -- this tool takes untracked files itself -- and it is moved to the commit afterwards")
        return
    since = stale_since(git, ref, path, shared)
    if since:
        say(f"seat_commit: STALE shared index entry: .git/index holds {path} as it was at {since[:10]}, not "
            f"as {'the new commit' if after else 'HEAD'} has it -- most likely left by a commit made from a "
            "private index. `git diff --cached` shows its inverse and a plain `git commit` from anyone "
            f"would carry it. `git reset -q -- {path}` clears it, if nobody meant to stage that")
    else:
        say(f"seat_commit: {path} is staged in the shared index with content no commit has: someone's "
            "staging. This tool does not read the shared index, and leaves it as it is")


def show(git: Git, args, row: dict, reg: dict, boundary_of, rec: Record) -> None:
    """Whole-path mode, first run: every hunk, and the digest that confirms them."""
    rec.row["mode"] = "whole-path-show"
    if not args.paths:
        raise Refused("name the paths after --, or pass --patch")
    priv = Private(git)
    try:
        base = git.rev("HEAD")
        paths = build(git, priv, base, "whole-path", None, args.paths)
        rec.row["paths"] = paths
        check_paths(reg, row, paths, boundary_of)
        say(f"seat_commit: git diff HEAD -- {' '.join(args.paths)}, as it would be committed on {base[:9]}")
        say(text(git.run("diff", "--cached", "--stat", "--no-renames", base, "--", env=priv.env).stdout).rstrip())
        say(text(priv.diff(base, binary=False)).rstrip())
        for p in paths:
            say_shared(git, base, p)
        d = digest_of(priv.diff(base))
        say("")
        say(f"seat_commit: digest {d}. Every hunk above goes in under {row['seat']}. If each one is yours,")
        msg = args.message_file or "<message file>"
        say("    " + " ".join(shlex.quote(x) for x in
                              ["python", "contracts/tools/seat_commit.py", "--seat", row["seat"], "-F", msg,
                               "--confirm", d, "--", *args.shown_paths]))
        rec.row["outcome"] = "shown"
        rec.row["reason"] = d
    finally:
        priv.close()


def save_patch(git: Git, args, rec: Record) -> None:
    """Your own change, saved right after editing, as patch mode reads it.

    `git diff HEAD` leaves out new files and, redirected by PowerShell 5.1,
    is written as UTF-16 that git apply cannot read. This builds the diff in
    a private index -- HEAD plus the worktree state of these paths, new files
    included -- and writes its bytes as they are.
    """
    rec.row["mode"] = "save-patch"
    if not args.paths:
        raise Refused("name the paths after --")
    priv = Private(git)
    try:
        base = git.rev("HEAD")
        paths = build(git, priv, base, "whole-path", None, args.paths)
        rec.row["paths"] = paths
        Path(args.save_patch).write_bytes(priv.diff(base))
        say(f"seat_commit: saved the diff of {len(paths)} paths against {base[:9]} to {args.save_patch}")
        say(text(git.run("diff", "--cached", "--stat", "--no-renames", base, "--", env=priv.env).stdout).rstrip())
        say("seat_commit: every hunk in it is committed as yours. If one is another seat's, cut it from the file")
        rec.row["outcome"] = "saved"
    finally:
        priv.close()


# --------------------------------------------------------------------------- #
# pushing (7)
# --------------------------------------------------------------------------- #

def push(git: Git, args, row: dict, rec: Record) -> None:
    rec.row["mode"] = (rec.row["mode"] + "+push") if rec.row["mode"] else "push"
    branch = git.run("symbolic-ref", "-q", "--short", "HEAD", check=False)
    branch = text(branch.stdout).strip()
    if not branch:
        raise Refused("HEAD is detached; there is no branch to push")
    remote = args.remote or git.out("config", "--default", "origin", f"branch.{branch}.remote")
    cred = []
    if os.name == "nt" and not git.run("config", "--get", "credential.helper", check=False).stdout.strip():
        cred = ["-c", "credential.helper=manager"]  # the microscope computer's git has none (root CLAUDE.md)
    f = git.run(*cred, "fetch", "-q", remote, branch, check=False, merge=True)
    if f.returncode:
        body = text(f.stdout)
        if "couldn't find remote ref" not in body:
            raise Refused(f"could not fetch {remote} {branch} first, so what a push would publish is "
                          f"unknown: {body.strip()}")
        theirs = None
    else:
        theirs = git.rev("FETCH_HEAD")
    tip = git.rev("HEAD")
    if theirs:
        behind = git.out("rev-list", "--count", f"{tip}..{theirs}")
        if behind != "0":
            raise Refused(f"{branch} is {behind} commits behind {remote}/{branch}. A merge is needed first, "
                          "and this tool does not merge; nothing was pushed")
        ahead_spec = [f"{theirs}..{tip}"]
    else:
        ahead_spec = [tip, "--not", f"--remotes={remote}"]
    rows = git.out("log", "--reverse", "--format=%H%x00%ce%x00%cn%x00%s", *ahead_spec)
    ahead = [r.split("\x00") for r in rows.splitlines() if r.strip()]
    if not ahead:
        say(f"seat_commit: {branch} has nothing {remote} lacks; nothing to push")
        rec.row["outcome"] = (rec.row["outcome"] + "+nothing-to-push") if rec.row["outcome"] else "nothing-to-push"
        return
    others = [a for a in ahead if a[1] != row["committer_email"]]
    say(f"seat_commit: a push of {branch} to {remote} publishes {len(ahead)} commits:")
    for sha, ce, cn, subj in ahead:
        say(f"    {sha[:9]}  {cn:<36} {subj[:70]}")
    check_held(ahead, current_holds(git))
    check_named_others(others, args.push_includes_others, row)
    r = git.run(*cred, "push", remote, f"{tip}:refs/heads/{branch}", check=False, merge=True)
    lines = text(r.stdout).rstrip("\n").splitlines()
    say(f"--- the push's last {min(len(lines), GATE_TAIL)} lines, unfiltered (exit {r.returncode}) ---")
    for line in lines[-GATE_TAIL:]:
        say(line)
    say("--- end of the push ---")
    # Each commit the push carried, and whose: without it the class HP-009
    # answers (a push publishing a commit its seat had held) cannot be counted.
    rec.row["pushed"] = {"remote": remote, "branch": branch, "tip": tip, "commits": len(ahead),
                         "others": len(others),
                         "published": [{"commit": a[0], "committer": a[1]} for a in ahead]}
    # What the remote holds is read back either way, because the exit code
    # does not say it. On 2026-10-16 a push was rejected with "cannot lock
    # ref" because another seat's push had published the same commits a
    # moment earlier, and this said "nothing was published" of commits that
    # were public (architecture-20261003-1, the tool's first real push).
    there = remote_contains(git, cred, remote, branch, tip)
    if r.returncode:
        if there:
            say(f"seat_commit: the push was rejected, and {remote}/{branch} is {there[:9]}, which already "
                f"contains {tip[:9]}: another push published these commits first. They are public")
            rec.row["outcome"] = (rec.row["outcome"] + "+already-published") if rec.row["outcome"] \
                else "already-published"
            return
        raise Refused(f"the push was refused, and {remote}/{branch} does not contain {tip[:9]}, read back "
                      "after the refusal; read the push's lines above")
    if not there:
        raise Refused(f"the push reported success and {remote}/{branch} does not contain {tip[:9]}, read back")
    say(f"seat_commit: {remote}/{branch} is {there[:9]}, which contains {tip[:9]}, read back from the remote")
    rec.row["outcome"] = (rec.row["outcome"] + "+pushed") if rec.row["outcome"] else "pushed"


def holds_file(git: Git) -> Path:
    common = Path(git.out("rev-parse", "--git-common-dir"))
    return (common if common.is_absolute() else git.root / common) / HOLDS_NAME


def current_holds(git: Git) -> dict:
    """Commit -> its hold row, for every commit whose latest line is a hold. No line means free."""
    state: dict = {}
    p = holds_file(git)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("commit"):
                state[r["commit"]] = r
    return {c: r for c, r in state.items() if r.get("action") == "hold"}


def hold_or_release(git: Git, args, row: dict, reg: dict, rec: Record) -> None:
    """Record that a commit must not be pushed yet, or that it may (HP-011).

    On 2026-10-18 the person's word to hold e0d09c02 lived in one window, where
    no tool could see it, and a push published it. A hold is now a line a push
    reads. Only the seat that committed the commit may hold or release it, and
    when the person asked for the hold, --why carries their words verbatim.
    """
    action = "hold" if args.hold else "release"
    rec.row["mode"] = action
    sha = git.rev(args.hold or args.release)
    if not sha:
        raise Refused(f"{args.hold or args.release!r} is not a commit here")
    ce = git.out("log", "-1", "--format=%ce", sha)
    if ce != row["committer_email"]:
        owner = next((s["seat"] for s in reg.get("seats") or [] if s.get("committer_email") == ce), ce)
        raise Refused(f"{sha[:9]} is {owner}'s commit, and only its own seat holds or releases it (HP-011)")
    held = current_holds(git)
    if action == "hold" and not (args.why or "").strip():
        raise Refused("--why is required: say why it is held, with the person's words verbatim if they asked")
    if action == "release" and sha not in held:
        raise Refused(f"{sha[:9]} is not held, so there is nothing to release")
    line = {"ts": now(), "action": action, "commit": sha, "seat": row["seat"],
            "why": (args.why or None) if action == "hold" else None}
    with open(holds_file(git), "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    rec.row["paths"] = []
    rec.row["commit"] = sha
    rec.row["outcome"] = "held" if action == "hold" else "released"
    say(f"seat_commit: {sha[:9]} is {'held: a push that would publish it is refused' if action == 'hold' else 'released'}"
        + (f" ({args.why})" if action == "hold" else ""))


def check_held(ahead: list, held: dict) -> None:
    """Refuse a push that would publish a held commit, whatever --push-includes-others names (HP-011)."""
    blocked = [(a, held[a[0]]) for a in ahead if a[0] in held]
    if blocked:
        raise Refused("this push would publish held commits, so nothing was pushed: "
                      + "; ".join(f"{a[0][:12]} {a[3][:50]!r}, held by {h.get('seat')} at {h.get('ts')}: "
                                  f"{h.get('why')}" for a, h in blocked)
                      + ". Only the holding seat releases a hold (--release <commit>)")


def check_named_others(others: list, named, row: dict) -> None:
    """Refuse unless `named` is exactly the other seats' commits this push publishes (HP-009).

    A bare yes can be given before the list it answers is read, and on
    2026-10-18 one was: `--push --push-includes-others` in one command
    published a commit the person had asked be committed and not pushed. So
    the yes names what it is a yes to. Each hash is a prefix of at least
    seven hex digits that matches exactly one of the other seats' commits; a
    missing one, an extra one, or a bare flag is refused, and the refusal
    gives the flag to pass once the list has been read.
    """
    if not others:
        return
    want = {a[0]: a for a in others}
    exact = "--push-includes-others " + ",".join(a[0][:12] for a in others)
    if named is None:
        raise Refused(f"{len(others)} of them are not {row['seat']}'s, and on a shared branch a push publishes "
                      "everyone's work. Read the list above, check that no seat asked for its commit to be held, "
                      f"and name each one: {exact}")
    if not named.strip():
        raise Refused("--push-includes-others names the other seats' commits it publishes; a bare flag names "
                      "none, and a yes given before the list is read is not a reading of it. "
                      f"Once you have read the list above: {exact}")
    given = [x.strip().lower() for x in named.split(",") if x.strip()]
    found, extra = set(), []
    for h in given:
        hits = [s for s in want if s.startswith(h)] if re.fullmatch(r"[0-9a-f]{7,40}", h) else []
        if len(hits) == 1:
            found.add(hits[0])
        else:
            extra.append(h)
    missing = [want[s] for s in want if s not in found]
    if missing or extra:
        said = []
        if missing:
            said.append("not named: " + "; ".join(f"{a[0][:12]} {a[2]} {a[3][:50]}" for a in missing))
        if extra:
            said.append("named but not another seat's commit in this push: " + ", ".join(extra))
        raise Refused("--push-includes-others must name exactly the other seats' commits this push publishes. "
                      + ". ".join(said) + f". The exact flag: {exact}")


def remote_contains(git: Git, cred: list, remote: str, branch: str, tip: str) -> str | None:
    """The remote branch's commit if it contains `tip`, read from the remote; otherwise None."""
    f = git.run(*cred, "fetch", "-q", remote, branch, check=False, merge=True)
    if f.returncode:
        return None
    theirs = git.rev("FETCH_HEAD")
    if not theirs:
        return None
    if theirs == tip or git.run("merge-base", "--is-ancestor", tip, theirs, check=False).returncode == 0:
        return theirs
    return None


# --------------------------------------------------------------------------- #

def parse(argv: list[str]):
    head = argv[: argv.index("--")] if "--" in argv else argv
    for a in head:
        key = a.split("=", 1)[0]
        if key in FORBIDDEN:
            raise Refused(f"{key}: {FORBIDDEN[key]}")
    ap = argparse.ArgumentParser(prog="seat_commit.py", allow_abbrev=False,
                                 description="Commit as a seat (plan.md 8.3, HP-001).")
    ap.add_argument("--seat", help="the seat's name as contracts/seats.json holds it")
    ap.add_argument("-F", dest="message_file", help="the commit message, from a file")
    ap.add_argument("--patch", help="patch mode: commit exactly this patch (saved with --save-patch)")
    ap.add_argument("--confirm", metavar="DIGEST", help="whole-path mode: commit, if the digest still matches")
    ap.add_argument("--save-patch", metavar="FILE", help="write your own change under PATH... to FILE")
    ap.add_argument("--push", action="store_true", help="push the branch after committing, or alone")
    ap.add_argument("--push-includes-others", metavar="HASHES", nargs="?", const="", default=None,
                    help="the other seats' commits a push publishes, comma-separated, exactly as --push listed "
                         "them; a bare flag is refused")
    ap.add_argument("--hold", metavar="COMMIT", help="record that your own commit must not be pushed yet")
    ap.add_argument("--why", help="why it is held; the person's words verbatim when they asked for the hold")
    ap.add_argument("--release", metavar="COMMIT", help="release a hold you recorded on your own commit")
    ap.add_argument("--remote", help="the remote to push to (default: the branch's, else origin)")
    ap.add_argument("--lock-wait", type=float, default=DEFAULT_LOCK_WAIT,
                    help=f"seconds to wait for .git/index.lock (default {DEFAULT_LOCK_WAIT:.0f})")
    ap.add_argument("--retries", type=int, default=DEFAULT_RETRIES,
                    help=f"times to rebuild when HEAD moves, or retry a locked ref (default {DEFAULT_RETRIES})")
    ap.add_argument("paths", nargs="*", help="whole-path mode and --save-patch: the paths, after --")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    git = None
    rec = Record(None, argv)
    try:
        root = find_root()
        git = Git(root, base_env())
        rec.git = git
        args = parse(argv)
        shown_paths = list(args.paths)
        args.paths = to_top(git, args.paths)
        args.shown_paths = shown_paths
        if args.save_patch:
            rec.row["seat"] = args.seat
            save_patch(git, args, rec)
            return 0
        if not args.seat:
            raise Refused("--seat is required")
        rec.row["seat"] = args.seat
        try:
            reg, row = resolve_seat(git, args.seat)
        except Refused:
            say("committing as: " + git.out("var", "GIT_COMMITTER_IDENT") + "  (git's own choice; refused below)")
            raise
        git.env = committer_env(git.env, row)
        ident = git.out("var", "GIT_COMMITTER_IDENT")
        say("committing as: " + ident)
        if not ident.startswith(f"seat:{row['seat']} <{row['committer_email']}>"):
            raise Refused(f"git would commit as {ident}, which is not the registry's identity for {row['seat']}")
        if args.hold or args.release:
            if args.hold and args.release:
                raise Refused("--hold and --release are two acts; make one at a time")
            if args.patch or args.confirm or args.push or args.paths:
                raise Refused("--hold and --release record a hold and do nothing else; run them on their own")
            hold_or_release(git, args, row, reg, rec)
            return 0
        if args.why:
            raise Refused("--why goes with --hold")
        if args.patch and args.paths:
            raise Refused("--patch says which change is yours; paths after -- are for whole-path mode")
        if args.confirm and args.patch:
            raise Refused("--confirm is whole-path mode's; patch mode needs no digest")
        committing = bool(args.patch or args.confirm)
        if committing and not args.message_file:
            raise Refused("-F <message file> is required to commit")
        if not committing and not args.push:
            show(git, args, row, reg, load_boundary_of(git), rec)
            return 0
        if committing:
            commit(git, args, row, reg, load_boundary_of(git), rec)
        if args.push:
            push(git, args, row, rec)
        return 0
    except Refused as exc:
        rec.row["outcome"] = (rec.row["outcome"] + "+refused") if rec.row["outcome"] else "refused"
        rec.row["reason"] = str(exc)[:2000]
        say(f"seat_commit: REFUSED. {exc}")
        return 1
    except SystemExit as exc:  # argparse
        rec.row["outcome"] = "usage"
        return int(exc.code or 0)
    finally:
        rec.write()


if __name__ == "__main__":
    sys.exit(main())
