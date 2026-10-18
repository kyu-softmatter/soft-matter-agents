# 001 — the console arrives under console/, as copies, green at the new paths

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, from 2026-10-18. If
you are not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.** A decision said
there counts once its line is committed, and you cite that commit.

## Why

`plan.md` 15 moves the console out of `microscope_agent/autofocus/` into its
own folder in three steps:

1. The cut, which landed at `0cd095c` (card 077, Microscope 3). The server is
   severed from dino's engine, the command path and the six engine-backed
   areas are retired, and only `--backend placeholder` is left.
2. **This card: your commit adds the console's part under `console/`.**
3. A microscope seat deletes the originals in a commit of its own.

Steps 2 and 3 are two commits because no seat may write into two boundaries
in one (check 35). So nothing in this card deletes, moves or edits anything
under `microscope_agent/`.

## What crosses

The crossing set is the one card 077 drew, as its import test states it:
`microscope_agent/autofocus/tests/test_console_cut_imports.py` at `0cd095c`,
`CROSSING_PACKAGES` and `CROSSING_TEST_DIRS`. Read the set there, not here.
As of `0cd095c` it is:

| from `microscope_agent/autofocus/` | to `console/` |
|---|---|
| `src/dino_autofocus/{server,agents,assistant,auth}/`, whole | `src/dino_autofocus/{server,agents,assistant,auth}/` |
| `tests/{agents,assistant,auth,server}/`, whole | `tests/{agents,assistant,auth,server}/` |
| `web/`, whole, every tracked file | `web/` |
| `docs/screens/` and `docs/ui-spec.md` | `docs/screens/` and `docs/ui-spec.md` |

**Not in this card:**
- `tools/launcher/`. It hard-codes the frozen dino repository's path on the
  microscope computer, so moving it would move a broken pointer. Whether it
  is re-pointed or retired is a later card.
- The package rename. The package keeps the name `dino_autofocus` in this
  commit, so this commit is a copy and nothing else. The rename is the next
  card.
- The stale names the cut left in `web/src/api/schema.ts`, the web areas
  and `docs/screens/`. They are a later card too.

## What to do

1. **Copy each file byte for byte from `0cd095c`**, not from the working
   copy: `git show 0cd095c:<old path>` into the new path. Then compare
   sha256 of the old and new bytes for every file, and put the count in your
   report.
2. **Write the few files that are new, and nothing else new.**
   - `console/src/dino_autofocus/__init__.py`: one docstring line saying this
     is the console's part of the package. It is not a copy of the engine
     side's `__init__.py`, whose docstring describes DINO features.
   - `console/tests/conftest.py`: the one-BLAS-thread setup only, if the
     crossing tests need it. The imported root `conftest.py` exists to load
     the focus core through `_flat`, which the console does not use, so it
     does not cross.
   - `console/pyproject.toml`, `console/uv.lock` and `console/.python-version`.
     The dependencies are what the crossing code imports, read off its
     import graph and not off dino's manifest. Expect the server group
     (pydantic, fastapi, uvicorn, pillow, anthropic, gsd), and for
     development pytest, ruff and httpx2, plus whatever else the graph
     shows, such as numpy. **No ml, hw, synth or plot extra, no torch, no
     pymmcore**, and no source or index for torch. An environment without
     pymmcore cannot open a core, which is the guarantee the settings file
     cannot give.
   - The web dependency group, nodejs-wheel, is your call. Say which in
     your report.
3. **Resolve the lock offline** (`uv lock --offline`, `uv sync --offline`).
   If something will not resolve from the cache, stop and report what is
   missing. Do not fetch from the network on this card, and do not run
   `npm install`.
4. **Run the crossing tests at their new paths, in the console's own
   environment**, rooted at `console/`. Report the count.
   - Card 077 counted 501 crossing tests green at `0cd095c`; the same number
     passing here is the evidence that the copy is whole.
   - The web tests need `node_modules`, which is not present. Say so rather
     than installing it.
   - Any test that reads a path outside `console/` is a finding: report it,
     and do not patch it to pass.
5. **Show that nothing under `console/` reaches outside it.** Run card 077's
   import walk over `console/src/` and `console/tests/`, pointed at the new
   tree. Every `dino_autofocus` module either test imports must exist under
   `console/src/`. Put the result in your report. A copy of the walk as a
   console test is welcome and lands in this same commit.
6. **The validator, 0 failed**, with the Office command in
   `console/CLAUDE.md`. Check 13 has to pass every new path. The mock-data
   folder, `console/src/dino_autofocus/agents/mock_data/`, is the one place
   under `console/` the card checks do not read. A card-shaped file anywhere
   else under `console/` is judged as a card, and that would be a finding.
7. **Commit through `contracts/tools/seat_commit.py`**, under your own seat.
   - Name only paths under `console/`.
   - The message carries the full old-to-new path list, because rename
     detection does not cross two commits, plus the sha256 count, the test
     count and the validator's tree line.
   - The message names every open card whose paths this commit touches.
     Microscope cards 061 and 062 (live view and stop) and 076 (the
     watcher) name the console's files; check each for paths under the
     crossing set, and list the ones that do.
8. **Send me the hash**, and say that the originals are ready for a
   microscope seat to delete. I tell manager-microscope-20261003-1.

## What you must not do

- Write outside `console/`, or edit `console/CLAUDE.md`, `console/README.md`,
  `console/tasks/` or `console/.claude/`.
- Start the server with anything but `--backend placeholder`, or point it at
  a live host.
- Call the librarian's tools.
- Fetch from the network, or run `npm install`.
- Change a line of the copied code to make a test pass. A test that fails
  at the new path is a finding about the copy, and the copy is what this
  card is for.
