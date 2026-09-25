"""Stop hook: before a session stops, make it answer for its uncommitted work.

Asked for by the person on 2026-09-25: sessions should commit and push the
valuable things they produce and learn once their task is done, before they
close. Every session shares one working copy, so this hook does NOT commit or
push anything itself. A hook cannot tell a finished card from a draft, or one
seat's file from another's in a shared tree, and an automatic `git add` is
exactly the shared-index hazard CLAUDE.md spends a page on. The session knows
both, so the hook asks and the session decides.

What it does: when the assistant is about to stop, list the uncommitted paths
inside this session's boundary. If there are any, block the stop once with a
reason that tells the session to commit what is finished and validated under
its own identity, push, write down what it learned, or say in one line why
not. Never block twice in a row (`stop_hook_active`), never nag about an
unchanged set of paths, and at most once per COOLDOWN_S per session, so a
session mid-task is not interrupted after every turn. Any error means allow the
stop: a reminder must never trap a session.

The boundary comes from the working directory. A session rooted in an agent
directory answers for that directory. A session at the root, architecture or a
manager, answers for everything outside the four agent trees plus each agent's
CLAUDE.md, README.md, .claude/ and tasks/, which are the design seats' paths.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

COOLDOWN_S = 30 * 60
LIST_MAX = 15
AGENT_DIRS = ("microscope_agent", "simulation_agent", "librarian_agent", "bridge")
DESIGN_IN_AGENT = ("CLAUDE.md", "README.md", ".claude/", "tasks/")


def allow() -> None:
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        allow()
    if data.get("stop_hook_active"):
        allow()

    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd,
                             capture_output=True, text=True, encoding="utf-8").stdout.strip()
        raw = subprocess.run(["git", "status", "--porcelain", "-z", "--untracked-files=all"], cwd=top,
                             capture_output=True).stdout.decode("utf-8", "replace")
    except Exception:
        allow()
    if not top:
        allow()

    rel_cwd = os.path.relpath(os.path.abspath(cwd), os.path.abspath(top)).replace(os.sep, "/")
    agent = rel_cwd.split("/")[0] if rel_cwd.split("/")[0] in AGENT_DIRS else None

    paths = []
    entries = raw.split("\0")
    i = 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        status, path = e[:2], e[3:]
        if status[0] in "RC":          # a rename carries its source as the next entry
            i += 1
        paths.append(path)

    def mine(p: str) -> bool:
        head = p.split("/")[0]
        if agent:
            return head == agent
        if head not in AGENT_DIRS:
            return True
        rest = p[len(head) + 1:]
        return any(rest == d or rest.startswith(d) for d in DESIGN_IN_AGENT)

    own = sorted(p for p in paths if mine(p))
    if not own:
        allow()

    state_dir = os.path.join(tempfile.gettempdir(), "soft-matter-agents-endcheck")
    os.makedirs(state_dir, exist_ok=True)
    state_file = os.path.join(state_dir, (data.get("session_id") or "unknown") + ".json")
    digest = hashlib.sha256("\n".join(own).encode("utf-8")).hexdigest()
    try:
        with open(state_file, encoding="utf-8") as f:
            last = json.load(f)
    except Exception:
        last = {}
    now = time.time()
    if last.get("digest") == digest or now - last.get("at", 0) < COOLDOWN_S:
        allow()
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"digest": digest, "at": now}, f)

    shown = "\n".join("  - " + p for p in own[:LIST_MAX])
    more = f"\n  ... and {len(own) - LIST_MAX} more" if len(own) > LIST_MAX else ""
    where = f"`{agent}/`" if agent else "the design paths (root files, contracts/, agents' CLAUDE.md, .claude/, tasks/)"
    reason = (
        f"End-of-turn check: {len(own)} uncommitted path(s) in {where}:\n{shown}{more}\n\n"
        "Before you stop, answer for them:\n"
        "1. If your task is FINISHED, run the validator. For each path that is YOURS and finished, check "
        "`git diff HEAD -- <paths>`, commit under your seat identity with a message file "
        "(`git commit -F <file> -- <paths>`, committer from contracts/seats.json), then push with "
        "`git -c credential.helper=manager push origin main`.\n"
        "2. If you LEARNED something a future session needs -- a failure, a correction, a fact -- write it where "
        "your instructions put it (failures.jsonl, a findings file, your task report) and commit that too.\n"
        "3. If the work is unfinished, fails the validator, or is another seat's, say so in one line and stop. "
        "Do not commit it to make the tree look clean. You will not be asked again about this same set."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    allow()


if __name__ == "__main__":
    main()
