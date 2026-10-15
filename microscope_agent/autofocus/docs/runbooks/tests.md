# Tests: what to run, where, and what the two crash codes mean

Two test trees live in this repository and a third gate waits in soft-matter-agents for the files
that will be copied there (docs/integration-sma-workplan.md, item R-06). Nothing here runs in CI;
the commands below are the gates, run by hand before a review request and by the review session
before a merge.

## 1. The dino gates (this repository)

Run them from your own worktree with its own `.venv` (`uv sync` once per worktree; the shared
folder's `.venv` is not for tests, see the session rules in the internal notes).

```
uv run pytest tests microscope_agent/tests -q
uv run npm --prefix web test
uv run npm --prefix web run typecheck
uv run npm --prefix web run build
uv run ruff check src tests
```

- `tests/` is pytest; `microscope_agent/tests/` is flat `unittest` files in the soft-matter-agents
  shape (loaded by path, no package). pytest collects both, so one command covers them. The same
  files also run the way soft-matter-agents runs them:
  `PYTHONUTF8=1 uv run python -m unittest discover -s microscope_agent/tests`.
- `tests/test_sma_shape.py` is the shape gate for `microscope_agent/`: flat src, flat tests,
  stdlib + numpy imports only, no relative or `dino_autofocus` imports. It mirrors soft-matter-agents'
  checks 13, 16 and 82 so a file that would be refused there fails here first.
- `tests/engine/test_safety_baseline.py` (D-00) pins the two bench locks, the per-lens approach
  ceilings and the inventory of direct Micro-Manager write calls. It fails on purpose when one of
  those changes; read the docstring before "fixing" it.
- `web/src/api/schema.ts` is generated: after a change to a pydantic model run
  `uv run npm --prefix web run gen:api` and commit the result; never edit it by hand.
- Optional extras: tests that need torch, scikit-learn, scikit-image, yaml or gsd call
  `pytest.importorskip(...)` and skip in an environment without that extra (`uv sync` installs
  every extra through the `dev` group, so on a dev machine nothing skips for that reason).

### One BLAS thread, at most three suites at once

`tests/conftest.py` sets `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS` and `MKL_NUM_THREADS` to 1 before
numpy is imported (about 1 GiB of commit charge per pytest process otherwise). Set them yourself when
you run pytest outside `tests/` (the `microscope_agent/tests` command above, or `unittest`):

```
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run pytest ...      # bash
$env:OPENBLAS_NUM_THREADS=1; $env:OMP_NUM_THREADS=1; $env:MKL_NUM_THREADS=1       # PowerShell
```

The desktop's limit is Windows commit charge, not RAM. **At most three full suites run at the same
time on this machine**, and only the review session and its helpers run full suites; an execution
session runs the files it touched. Planning sessions run no suites.

### The two crash codes are not test failures

`0xc000070a` and `0x8007000e` in a pytest run, in unrelated places, mean the machine ran out of commit charge while other
suites or many sessions were open. Re-run when the machine is quieter; do not card a code fix from
them. A run that hangs at 22-25 % (the e2e and mm-demo band, native pymmcore adapters) under
parallel load is the same class; a lone run passes.

## 2. The soft-matter-agents gate (after the copy, item G-06)

Run from the soft-matter-agents checkout, in its pixi `mic` environment, with `python` (not
`python3`, which is a Store alias on the microscope PC) and `PYTHONUTF8=1`:

```
python contracts/validate.py                                 # must end "0 failed"
python contracts/validate.py --expect-fail contracts/examples/rejected   # every fixture still rejected
PYTHONUTF8=1 python -m unittest microscope_agent/tests/test_focus_core.py   # one file at a time
```

- Read the validator's last line: it names the tree it judged (a commit, or a commit plus
  uncommitted paths with a digest). A bare run in a shared working copy is nobody's commit.
- `--expect-fail` prints two totals, cards and groups; both must still be fully rejected.
- The validator's own tests and hooks are that repository's; nothing from this repository is run
  there, and this repository never writes into that tree.

## 3. Review checklist for a merge

1. The branch was made from a fixed `main` hash and brought up with `git merge main`, not rebased.
2. `git diff --cached --stat` shows only the branch's paths.
3. The dino gates in section 1 pass on the merged tree (the review session runs them from a
   `git archive` of the merge into its scratch folder, never by resetting the shared folder).
4. If `microscope_agent/` changed: `tests/test_sma_shape.py` passes and the drift check against the
   soft-matter-agents copy, once it exists (item D-03), reports no drift.
5. No `.venv`, `web/node_modules`, `web/dist`, `data/`, `outputs/`, `.agent/` or `.claude/` path is
   in the diff.
