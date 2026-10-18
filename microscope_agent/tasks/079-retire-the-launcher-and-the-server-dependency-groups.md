# 079 — retire dino's launcher and the server's dependency groups from `autofocus/`

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261015-1` (Microscope 3).** Card 064
gives you `microscope_agent/autofocus/`, and cards 077 and 078 are done. If
you are not that seat, take nothing from this card and report up.

## Why

Card 078 (`8e9d8d9`) left two things behind in `microscope_agent/autofocus/`
that point at what moved to `console/`.

**`tools/launcher/`.** The console manager ruled that it retires rather than
moving: "nothing in this repository should build it". Its build rewrites its
target to the clone it runs from, and either target is wrong:
- built from this tree, it points at a server that is gone and fails with
  "Server not found";
- built from the frozen dino clone (its default, `D:\AutoFocus\dino-autofocus`),
  it starts frozen dino's server, which still has `mm-real` and
  `/api/commands`. That is the second execution path cards 077 and 078 just
  removed here.

A launcher for the console, if the person wants one, is new work on a console
card. It points at `console/` and offers only `--backend placeholder`.

**`pyproject.toml`'s `server` and `web` dependency groups**, which install
FastAPI, Node tooling and the rest of the server's dependencies, are still
default groups. No server code is left in this tree to use them.

## What to do

1. **Retire `tools/launcher/` whole**, in one commit with its tests and
   docs:
   - Find every reader of it under `microscope_agent/autofocus/` first, and
     report each: tests such as `tests/server/test_server_launcher` if any
     stayed, runbooks, the README, scripts.
   - A test about the launcher goes with it.
   - A doc that tells someone to build or run it gets one line saying it is
     retired (card 079, `8e9d8d9`) and that the console's launcher, if any,
     is a console card. Change nothing else in that doc.
   - `docs/integration-sma.md`, `docs/integration-sma-workplan.md` and
     `docs/PLAN.md` are records, so leave them, as card 078 ruled.
2. **Remove the `server` and `web` groups** from `pyproject.toml`'s
   dependency groups and its default groups, and **regenerate `uv.lock`**:
   - Run `uv lock` there, offline if the cache allows. If it can't resolve
     without the network, stop and report what it needs, and leave both
     files unchanged rather than hand-editing a lock.
   - Remove only what nothing staying imports. Read the imports with the
     same AST walk card 077 used, and list each package removed.
   - **Do not touch** the hardware, model or synthesis extras. They are
     the measuring side's.
3. **Re-run card 072's suite** before and after. It must be as green as it
   was at `8e9d8d9`: 1317 passed, 0 failed, 10 skipped, less any launcher
   tests removed, each named.

## Out of this card

- **A launcher already built** on the microscope computer's desktop. No
  commit reaches it. The console manager has put that to the person through
  the intake seat, as a question.
- Any change under `console/`.
- Anything that measures, moves or lights.

## Boundaries

- Write inside `microscope_agent/autofocus/` only. Never `console/`,
  `microscope_agent/src/`, `envelope/`, `approvals/` or `contracts/`.
- Never unlock `BENCH_MOTION`.
- Commit and push through `contracts/tools/seat_commit.py`, naming each
  path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 5 lines at most:

- the commits;
- the launcher's readers, and what was done to each;
- the packages removed from the lock;
- the suite's counts before and after;
- anything `uv lock` could not do offline.
