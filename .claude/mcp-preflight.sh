#!/bin/sh
# SessionStart: say out loud when this session will not have the librarian's tools.
#
# Why this exists: a seat without them gets NO error. It proceeds on the degraded
# path, which is legitimate here, so a silent day looks like an ordinary one. On
# 2026-09-20 three seats ran a full day that way and none could state the cause
# from inside its own boundary, because the cause was one key in a file that is
# untracked, globally gitignored, and invisible to the commit gate (plan.md 11-18).
#
# This reads configuration only. It executes no agent code and calls no service:
# reading or running librarian_agent/src/ is that agent's side (6.2 rule 3), and a
# hook at the root is not a seat that may cross it. So it cannot prove the tools
# are live -- only that nothing in the configuration is refusing them. The cheapest
# proof of life is still for the seat to call one tool; a refused probe costs
# nothing (CLAUDE.md).
#
# Always exits 0. Degraded is a legitimate state, so this reports and never blocks.

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$ROOT" ] || exit 0
[ -f "$ROOT/.mcp.json" ] || exit 0

# Resolve the interpreter rather than naming python3: a stock Windows install
# provides `python` and no `python3`, and the machine where this check matters
# most is the one where naming it would make the CHECKER the thing that goes
# silent. If neither exists, say so without needing either.
PYBIN="$(command -v python3 2>/dev/null || command -v python 2>/dev/null)"
if [ -z "$PYBIN" ]; then
  printf '\n  librarian MCP: THIS SESSION MAY HAVE NO TOOLS\n'
  printf '    - no python3 and no python on PATH, so the server cannot start\n\n'
  exit 0
fi

"$PYBIN" - "$ROOT" "$PWD" <<'PY' 2>/dev/null || exit 0
import json, os, sys

root, cwd = sys.argv[1], sys.argv[2]
SERVER = "librarian"
problems, notes = [], []

def load(p):
    try:
        with open(os.path.expanduser(p)) as f:
            return json.load(f)
    except Exception:
        return None

# 1. is the server declared at all
mcp = load(os.path.join(root, ".mcp.json")) or {}
if SERVER not in (mcp.get("mcpServers") or {}):
    problems.append(".mcp.json does not declare %r" % SERVER)

# 2. does the repository carry its own approval
shared = load(os.path.join(root, ".claude/settings.json")) or {}
if SERVER not in (shared.get("enabledMcpjsonServers") or []):
    problems.append(
        ".claude/settings.json does not enable %r -- the approval is then "
        "machine-local and a fresh clone has none" % SERVER)

# 3. anything refusing it. A deny beats an allow, and these two files are where
#    the 2026-09-20 outage lived. Neither is in any tree a check can read.
local = os.path.join(root, ".claude/settings.local.json")
d = load(local)
if d and SERVER in (d.get("disabledMcpjsonServers") or []):
    problems.append("%s disables %r -- A DENY BEATS AN ALLOW. Remove that key."
                    % (local, SERVER))

home = load("~/.claude.json") or {}
for path, entry in (home.get("projects") or {}).items():
    if (path == cwd or path == root or path.startswith(root + os.sep)) \
       and SERVER in (entry.get("disabledMcpjsonServers") or []):
        problems.append("~/.claude.json projects[%s] disables %r" % (path, SERVER))

# 4. the interpreter the server is launched with. .mcp.json resolves it rather
#    than naming python3, so either name is fine and neither is not.
import shutil
if not (shutil.which("python3") or shutil.which("python")):
    problems.append("neither python3 nor python is on PATH, so the server cannot start")
if not shutil.which("git"):
    problems.append("git is not on PATH, and .mcp.json locates the server with "
                    "git rev-parse --show-toplevel")
if not shutil.which("sh"):
    problems.append("sh is not on PATH -- on Windows this comes with Git for Windows, "
                    "which a clone of this repository already needed")

if problems:
    print("")
    print("  librarian MCP: THIS SESSION MAY HAVE NO TOOLS")
    for p in problems:
        print("    - " + p)
    print("    Settings are read at session start, so fixing these needs a restart.")
    print("    Degraded is legitimate -- cards default `degraded` and never claim")
    print("    the librarian answered. This is a schedule problem, not an evidence one.")
    print("")
PY

# --- committer identity ---------------------------------------------------
# Not about MCP, and here because this is the only thing in the repository
# that runs at session start and can see outside the tree. .git/config.worktree
# can hold committer.name and committer.email; those beat user.* and lose only
# to the GIT_COMMITTER_* environment variables. The file is shared by every
# session and is in no tree, so the commit gate -- which judges the tree a
# commit would create -- can never see it, and seats writing their own
# identity into it are racing: last writer wins. A seat whose boundary happens
# to match the winner commits silently under another seat's name; a seat whose
# boundary does not is refused by check 41 naming a seat it has never heard
# of. Reporting it is the whole of the remedy available. See plan.md 6.2.1.
IDENT="$(git var GIT_COMMITTER_IDENT 2>/dev/null | sed 's/ [0-9][0-9]* [-+][0-9]*$//')"
CFG="$(git rev-parse --git-dir 2>/dev/null)/config.worktree"
if [ -n "$IDENT" ] && [ -f "$CFG" ] && grep -q '^\[committer\]' "$CFG" 2>/dev/null; then
  printf '\n  git: this working copy pins a committer identity for every session\n'
  printf '    - %s\n' "$IDENT"
  printf '    - from %s, which is shared and in no tree\n' "$CFG"
  printf '    - if that is not your seat, pass GIT_COMMITTER_NAME and\n'
  printf '      GIT_COMMITTER_EMAIL on the commit rather than rewriting the file;\n'
  printf '      rewriting it is the same race one lap further on\n\n'
fi

exit 0
