# 002 — the console's package becomes sma_console

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, from 2026-10-18. If
you are not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

The console's code is in `console/` alone since `8e9d8d9`: card 078 deleted
the 278 originals from `microscope_agent/autofocus/`, and each was
blob-checked against your copy at `908e55c8`.

The import package is still called `dino_autofocus`, while the engine side
keeps a package of the same name. Two distributions that provide one
top-level name collide in any environment that installs both. Card 001 left
the rename for here, so that the copy stayed a copy.

## What to do

1. **Rename the import package, `console/src/dino_autofocus/` to
   `console/src/sma_console/`,** with `git mv`, so that every file is a
   rename git detects inside one boundary.
2. **Change what names the package, and nothing else:**
   - absolute imports in the tests (you counted 142 lines);
   - `-m dino_autofocus...` strings in code and tests;
   - the wheel's `packages` entry in `console/pyproject.toml`;
   - the project entry in `console/uv.lock`, re-resolved offline.

   The source's own imports are relative and should need no change. If one
   does, say which.
3. **Leave every string that names a place or an identity on disk
   unchanged**, even where it says "dino-autofocus":
   - the accounts and settings folder in `auth/config.py`
     (`%LOCALAPPDATA%\dino-autofocus`);
   - the logger name in `auth/applog.py`;
   - the environment variables `DINO_AF_*`;
   - the mock store's `ORIGIN` and the `origin` field in the mock cards;
   - the assistant's prompt text.

   Renaming any of these changes behaviour, not names. The accounts folder
   in particular holds the person's logins on the microscope computer, and a
   new name would silently start an empty one. List each such string you
   find in your report, and change none of them. Whether any of them should
   move, and how, is a later card with a migration.
4. **The store's default root.** `agents/sma_files.py` hard-codes
   `DEFAULT_ROOT = Path(r"D:\codes\github\soft-matter-agents")`. That is this
   computer's working copy, and it is wrong on the microscope computer. Make
   the default the repository the package sits in, found by walking up from
   the module's own file to the first folder that holds both `contracts/`
   and `console/`. Keep the environment variable as the override, and
   change the one test that asserts the old constant to assert the new
   rule. If no such folder is found, refuse with the reason; never fall
   back to a guessed path. `--store sma` still reads and never writes.
5. **Run the tests in the console's own environment and report the count.**
   The count was 505 before the rename, and it must be 505 after. Run your
   import walk too, pointed at `sma_console`, and show it still fails when a
   package is removed from its table.
6. **The validator, 0 failed.** The mock-data rule is keyed on
   `console/src/<package>/agents/mock_data/`, so it follows the rename.
   Check that no card-shaped file is judged under `console/`.
7. **Commit through `contracts/tools/seat_commit.py`**, paths under
   `console/` only. The message lists the strings left unchanged under
   step 3, and the test count before and after. Send me the hash.

## Not in this card

- `web/src/api/schema.ts`, the web areas that still call retired routes, and
  `docs/screens/`. Regenerating the schema needs Node, and the web packages
  are not installed; installing them is a download, and the person says yes
  to it first. That is a later card.
- The old launcher in `microscope_agent/autofocus/tools/launcher/`. It is not
  this folder's, and it points at the frozen dino repository.

## What you must not do

- Write outside `console/`, or edit `console/CLAUDE.md`, `console/README.md`,
  `console/tasks/` or `console/.claude/`.
- Start the server with anything but `--backend placeholder`.
- Fetch from the network, or run `npm install`.
- Change a behaviour under the name of a rename. Step 4 is the one change
  this card asks for.
