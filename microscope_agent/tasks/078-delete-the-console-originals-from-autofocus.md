# 078 — delete the console's originals from `autofocus/`, after its copy landed

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261015-1` (Microscope 3). Start after
card 077's commit B lands.** Both cards write `microscope_agent/autofocus/`,
and one seat writes it at a time. Card 064 gives you that tree. If you are
not `microscope-office-20261015-1`, take nothing from this card and report
up.

## Why

plan.md 15 moves the console in two commits, because check 35 refuses a
commit that writes into two boundaries.

- **The first has landed:** `908e55c8`, by `console-office-20261017-1`. It
  copies the crossing set into `console/`.
  manager-console-office-20261017-1 checked it off the trees, not off the
  seat's report: all 278 crossing files at `0cd095c` have the same blob id
  at their `console/` path, with 0 missing and 0 different. Six files
  under `console/` are new and have no original.
- **This card is the second commit: it deletes the originals.** Between the
  two commits the console exists twice, and only the new copy is run.

## What to do

1. **Check before deleting, off the trees.** For every file in the
   crossing set at `0cd095c`, compare its blob id with the file at its
   `console/` path in HEAD. The crossing set is:
   - the packages in `CROSSING_PACKAGES`, which are
     `dino_autofocus.server`, `.agents`, `.assistant` and `.auth`, under
     `src/dino_autofocus/`;
   - the test folders in `CROSSING_TEST_DIRS`, which are `agents`,
     `assistant`, `auth` and `server`, under `tests/`;
   - `web/`;
   - `docs/screens/`;
   - `docs/ui-spec.md`.

   These are the names `tests/test_console_cut_imports.py` holds at
   `0cd095c`. **Delete only a file whose blob matches.** If any file is
   missing or different, list it to this seat and to the console manager
   and delete nothing.

   Do not compare the six new console files, which have no original:
   `src/dino_autofocus/__init__.py`, `tests/conftest.py`,
   `tests/test_console_imports.py`, `pyproject.toml`, `uv.lock` and
   `.python-version`.
2. **Find every reader of the crossing paths that stays.** Search
   everything under `microscope_agent/autofocus/` that names one of those
   paths or packages: imports, the tree's own `pyproject.toml` package
   lists, `conftest.py`, scripts, and docs. Report each file and line.
   - A staying **test** that needs a crossing path is changed or retired in
     this commit. One is known: `tests/test_console_cut_imports.py::
     test_the_lists_name_real_packages` asserts that the crossing packages
     exist. Change it to assert that they are gone from `autofocus/` and
     present under `console/`, so the cut's lists keep meaning something.
   - A staying **doc** that points at a moved file gets that pointer
     changed to the `console/` path, and nothing else in it changes.
   - **Code** that stays and still imports a crossing package is a defect
     in card 077's cut. Report it and do not paper over it.
3. **Leave what stays.** `tools/launcher/` stays, because it hard-codes the
   frozen dino path. Everything that measures, moves or lights stays, and so
   do the six new console files, which are not yours.
4. **Delete in one commit**, in the microscope boundary only. The message
   carries:
   - the old-to-new path list, every deleted path with its `console/` path;
   - `908e55c8` as the commit the copies landed in;
   - every open card whose paths it touches. Card 001 is the console's,
     and the card 07x lines in `microscope_agent/tasks/` cite these paths.
     Name them; repointing a microscope card is this seat's, so tell me
     which.

## Done when

- Every file of the crossing set is gone from `microscope_agent/autofocus/`
  and was byte-equal to its copy at the moment it went.
- The staying suite, card 072's command, is green apart from what had
  already failed, with its counts before and after. The drop is explained
  by the tests that moved, by file.
- `git grep` over `microscope_agent/autofocus/` finds no staying import of
  a crossing package.

## Boundaries

- Write inside `microscope_agent/autofocus/` only. **Nothing under
  `console/`**: it is another boundary, check 35 refuses the mix, and it is
  the console seat's.
- No change to `microscope_agent/src/`, `envelope/`, `approvals/` or
  `contracts/`.
- Never unlock `BENCH_MOTION`.
- Commit and push through `contracts/tools/seat_commit.py`, naming each
  path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 5 lines at most:

- the commit;
- the byte check: files compared, matching, deleted;
- each staying reader found, and what was done to it;
- the suite's counts before and after;
- the cards whose paths it touched.
