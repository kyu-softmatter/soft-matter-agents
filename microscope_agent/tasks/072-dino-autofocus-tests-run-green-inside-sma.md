# 072 — dino-autofocus's own tests run green inside this repository

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261015-1`, after card 071 lands.** If you
are not that seat, take nothing from this card and report up.

## What to do

`microscope_agent/autofocus/` keeps its own `pyproject.toml` and `uv.lock`.
**Its environment is its own**: this repository's root `pyproject.toml` is
architecture's, and this card does not touch it.

1. Run dino's own test suite from inside the subtree, through its own lock,
   for example `uv run --directory microscope_agent/autofocus --frozen pytest`,
   or whatever its own `docs/runbooks/tests.md` prescribes. Record the
   command you used.
2. **Every test that passed at `95eee95` in dino passes here.** To know which
   those are, run the same suite on a clean checkout of dino at `95eee95`
   first, outside this repository, and keep both outputs.
3. **A test that fails here and passed there** usually means a path or a
   root-relative assumption the move broke. Fix it with the smallest change,
   inside `microscope_agent/autofocus/` only, and say what moved and why.
4. **A test that also failed at `95eee95`** is not this card's. List it, and
   leave it.
5. **A test that reaches for hardware, a Micro-Manager core or a network
   port** is skipped exactly as dino's own suite skips it. Never make one run
   against the instrument.

## Boundaries

Write inside `microscope_agent/autofocus/` only. Write nothing in
`microscope_agent/src/` or `tests/`, which belong to the other microscope
seat under card 064, and nothing at the repository root. **New text is
English from the first line**: the language exception covers only what
arrived with the import. Commit under your seat, through the gate, naming
each path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 5 lines at most: the commit, the test counts there and here
(passed, failed, skipped), each fix and why, and the tests that already
failed at `95eee95`.
