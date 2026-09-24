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

# Resolve the interpreter by RUNNING it, not by finding it.
#
# This block used `command -v python3 || command -v python` and said above it
# that a stock Windows install provides `python` and no `python3`. On the
# microscope computer that is false, and false in the way this script exists
# to prevent: `python3` IS on PATH, as a Microsoft Store App Execution Alias --
# a real file that is not Python. `command -v` finds it, so the fallback never
# fires; it prints "Python was not found" and exits 49. On 2026-09-24 the
# checker was the thing that went silent, on exactly the machine the old
# comment named, by exactly the mechanism it claimed to guard against.
# Existence is not runnability, so each candidate is probed (plan.md 11-22).
PYBIN=""
STUBS=""
for c in python3 python py; do
  cpath="$(command -v "$c" 2>/dev/null)"
  [ -n "$cpath" ] || continue
  if "$c" -c '' >/dev/null 2>&1; then
    PYBIN="$c"
    break
  fi
  STUBS="$STUBS      - $cpath is on PATH and is not a working interpreter
"
done
if [ -z "$PYBIN" ]; then
  printf '\n  librarian MCP: THIS SESSION WILL HAVE NO TOOLS\n'
  printf '    - no runnable python on PATH, so the server cannot start\n'
  [ -n "$STUBS" ] && printf '%s' "$STUBS"
  printf '\n'
  exit 0
fi
# A name that exists and does not run is worth saying even when a later
# candidate worked: it is what silences every OTHER caller that stops at the
# first name, and those are what actually break.
if [ -n "$STUBS" ]; then
  printf '\n  python: a name on PATH is not an interpreter\n'
  printf '%s' "$STUBS"
  printf '      - resolved to %s instead\n' "$(command -v "$PYBIN")"
  printf '      - anything still naming python3 directly is broken here (plan.md 11-22)\n\n'
fi

# The server imports `mcp`. That is a third-party package and not agent
# code, so reading for it stays on this side of 6.2 rule 3 -- and on the
# microscope computer it is the cause that outlived the interpreter fix:
# the launcher resolves, python runs, and the server still cannot serve.
if ! "$PYBIN" -c 'import mcp' >/dev/null 2>&1; then
  printf '
  librarian MCP: THIS SESSION WILL HAVE NO TOOLS
'
  printf '    - %s cannot import mcp, so the server exits instead of serving
' "$(command -v "$PYBIN")"
  printf '    - the configuration below may be perfectly correct and it will not help

'
fi

# Windows defaults to cp1252 and this tree reads text without naming an
# encoding, so the check below dies on the first non-ASCII byte without this.
PYTHONUTF8=1
export PYTHONUTF8

"$PYBIN" - "$ROOT" "$PWD" <<'PY' 2>/dev/null
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

PREFLIGHT_STATUS=$?
if [ "$PREFLIGHT_STATUS" -ne 0 ]; then
  # Silence here used to be indistinguishable from a clean bill of health:
  # the old form was `|| exit 0`, so an interpreter that could not run the
  # check produced no output and exit 0 -- which is what a PASSING preflight
  # also produces. That is how this reported nothing on 2026-09-24.
  printf '
  librarian MCP: PREFLIGHT DID NOT COMPLETE
'
  printf '    - %s failed to run this check, so nothing above was verified
' "$PYBIN"
  printf '    - call a librarian tool to find out; a refused probe costs nothing

'
fi

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
