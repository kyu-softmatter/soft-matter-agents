#!/usr/bin/env python3
"""Commit under one of the six names in contracts/seats.json (plan.md 6.2.1).

    seat_commit.py --seat NAME -F MSGFILE -- PATH...
    seat_commit.py --seat human --persons-word "TEXT" -F MSGFILE -- PATH...
    seat_commit.py --seat NAME --removes-check 89 -F MSGFILE -- PATH...
    seat_commit.py --push

What it does, and nothing else:

1. The committer is the named row of `contracts/seats.json` at HEAD, the
   registry check 41 judges the commit against. `GIT_COMMITTER_NAME` and
   `GIT_COMMITTER_EMAIL` are set from it, because they beat both `user.*` and
   a `committer.*` pinned in `.git/config.worktree`; the author stays whoever
   git says, which is the person. `git var GIT_COMMITTER_IDENT` is printed
   first, so the identity that is spent is the identity that is seen.
2. `human` is the person's name and the only one that may commit an approval
   or a safety limit. The tool takes it only with `--persons-word`, the
   person's own words for this commit, and writes them into the message as a
   `Persons-word:` trailer, so the history says on whose word it was used.
3. Only the named paths are committed (`git commit --only`), on top of HEAD,
   whatever else is staged. The message comes from a file. There is no amend,
   no `--no-verify` and no force: the gate is the repository's pre-commit
   hook, and it runs on every commit made here.
4. Deleting a check is declared, by number, with `--removes-check`. The hook
   refuses a commit that removes a check HEAD has unless that exact set was
   declared, and the declaration goes into the message as a trailer.
5. `.git/index.lock` is waited for and never removed. Afterwards the commit is
   read back -- its committer and its paths -- and the hook's output is
   printed unfiltered, so a `fatal:` is seen as well as a FAIL.
6. `--push` fetches, refuses when the branch is behind its upstream, and
   otherwise pushes HEAD to it. On Windows it adds `credential.helper=manager`
   when no helper is configured.

Standard library only, and nothing newer than Python 3.9, so bare `python`
runs it on every computer here.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PERSON = "human"
LOCK_WAIT_S = 120


class Refused(Exception):
    pass


def git(*args: str, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    out = subprocess.run(["git", *args], capture_output=True, text=True, env=env,
                         encoding="utf-8", errors="replace")
    if check and out.returncode:
        raise Refused(f"git {' '.join(args)} failed: {out.stderr.strip() or out.stdout.strip()}")
    return out


def registry_row(name: str) -> dict:
    shown = git("show", "HEAD:contracts/seats.json", check=False)
    if shown.returncode:
        raise Refused("HEAD holds no contracts/seats.json, so no name has an identity here")
    try:
        rows = json.loads(shown.stdout).get("seats") or []
    except ValueError as exc:
        raise Refused(f"contracts/seats.json at HEAD is not JSON: {exc}")
    for row in rows:
        if row.get("seat") == name:
            if not row.get("committer_email"):
                raise Refused(f"{name!r} has no committer_email in contracts/seats.json")
            return row
    names = ", ".join(str(r.get("seat")) for r in rows)
    raise Refused(f"{name!r} is not a name in contracts/seats.json at HEAD; the names are: {names}")


def wait_for_lock(root: Path) -> None:
    lock = Path(git("rev-parse", "--git-path", "index.lock").stdout.strip())
    if not lock.is_absolute():
        lock = root / lock
    waited = 0.0
    while lock.exists():
        if waited >= LOCK_WAIT_S:
            raise Refused(f"{lock} has been held for {LOCK_WAIT_S} s. It is never removed here: another "
                          "git may still be writing. Find out whose it is.")
        time.sleep(1.0)
        waited += 1.0
    if waited:
        print(f"seat_commit: waited {waited:.0f} s for the index lock")


def commit(args) -> int:
    row = registry_row(args.seat)
    if args.seat == PERSON and not (args.persons_word or "").strip():
        raise Refused("human is the person's name. It is used only on the person's word for this commit: "
                      "pass --persons-word with what the person said")
    if args.seat != PERSON and args.persons_word:
        raise Refused("--persons-word belongs to a commit under human; this commit is not the person's")
    if not args.message_file:
        raise Refused("the message comes from a file: pass -F MSGFILE")
    if not args.paths:
        raise Refused("name the paths to commit after --")

    root = Path(git("rev-parse", "--show-toplevel").stdout.strip())
    body = Path(args.message_file).read_text(encoding="utf-8").rstrip() + "\n"
    trailers = []
    if args.persons_word:
        trailers.append(f"Persons-word: {args.persons_word.strip()}")
    removed = sorted({int(n) for n in args.removes_check or []})
    if removed:
        trailers.append("Removes-check: " + ", ".join(str(n) for n in removed))
    if trailers:
        body += "\n" + "\n".join(trailers) + "\n"

    env = dict(os.environ)
    env["GIT_COMMITTER_NAME"] = f"seat:{row['seat']}"
    env["GIT_COMMITTER_EMAIL"] = row["committer_email"]
    env["SMA_REMOVES_CHECKS"] = " ".join(str(n) for n in removed)
    print("seat_commit: " + git("var", "GIT_COMMITTER_IDENT", env=env).stdout.strip())

    before = git("rev-parse", "HEAD").stdout.strip()
    wait_for_lock(root)
    fd, msg = tempfile.mkstemp(prefix="seat-commit-msg-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        done = git("commit", "--only", "-F", msg, "--", *args.paths, env=env, check=False)
    finally:
        try:
            os.unlink(msg)
        except OSError:
            pass
    tail = (done.stdout + done.stderr).rstrip().splitlines()
    print("\n".join(tail[-40:]))
    after = git("rev-parse", "HEAD").stdout.strip()
    if done.returncode or after == before:
        print(f"seat_commit: no commit was made (git exited {done.returncode}); HEAD is still {before[:9]}")
        return 1

    parent = git("rev-parse", f"{after}^").stdout.strip()
    ce = git("log", "-1", "--format=%ce", after).stdout.strip()
    paths = [p for p in git("diff-tree", "--no-commit-id", "--name-only", "-r", after).stdout.splitlines() if p]
    wanted = [p.rstrip("/") for p in args.paths]
    stray = [p for p in paths if not any(p == w or p.startswith(w + "/") for w in wanted)]
    problems = []
    if parent != before:
        problems.append(f"its parent is {parent[:9]}, not the HEAD it was made on, {before[:9]}")
    if ce != row["committer_email"]:
        problems.append(f"it was committed as {ce}, not {row['committer_email']}")
    if stray:
        problems.append("it carries paths that were not named: " + ", ".join(stray[:8]))
    print(f"seat_commit: committed {after[:9]} as {row['seat']}, {len(paths)} paths")
    if problems:
        print("seat_commit: READ THIS COMMIT BY HAND -- " + "; ".join(problems))
        return 1
    return 0


def push(args) -> int:
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    up = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", check=False)
    if up.returncode:
        raise Refused(f"{branch} has no upstream. Set one with `git push -u <remote> {branch}` the first time, "
                      "after the person says this branch is to be published")
    remote, _, rbranch = up.stdout.strip().partition("/")
    cred = []
    if os.name == "nt" and not git("config", "--get", "credential.helper", check=False).stdout.strip():
        cred = ["-c", "credential.helper=manager"]
    git(*cred, "fetch", remote, rbranch)
    behind = int(git("rev-list", "--count", f"HEAD..{remote}/{rbranch}").stdout.strip() or 0)
    if behind:
        raise Refused(f"{branch} is {behind} commits behind {remote}/{rbranch}. Merge first; this tool does not merge")
    ahead = git("log", "--format=%h %ce %s", f"{remote}/{rbranch}..HEAD").stdout.strip()
    if not ahead:
        print(f"seat_commit: nothing to push; {branch} is at {remote}/{rbranch}")
        return 0
    print("seat_commit: pushing\n" + "\n".join("  " + x[:120] for x in ahead.splitlines()))
    done = git(*cred, "push", remote, f"HEAD:{rbranch}", check=False)
    print((done.stdout + done.stderr).rstrip())
    return done.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seat", help="one of the names in contracts/seats.json")
    ap.add_argument("-F", dest="message_file", help="the commit message, from a file")
    ap.add_argument("--persons-word", help="for --seat human only: what the person said for this commit")
    ap.add_argument("--removes-check", action="append", metavar="N",
                    help="a check this commit deletes, by number; repeat for each")
    ap.add_argument("--push", action="store_true", help="push HEAD to its upstream after fetching")
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args(argv)
    try:
        if args.push:
            if args.paths or args.message_file:
                raise Refused("--push takes no paths and no message")
            return push(args)
        if not args.seat:
            raise Refused("pass --seat with one of the names in contracts/seats.json")
        return commit(args)
    except Refused as exc:
        print(f"seat_commit: refused. {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
