# 066 — each focus refusal shows its own reason, with the encoder read around it

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261003-1`**, which holds `src/` and `tests/` under
card 064. **Land it before Monday's (2026-10-12) bench visit** if you can: card 060's
watched refusals count only once it has landed. If you are not that seat,
take nothing from this card and report up.

## What microscope-20261007-1 found, dry-running card 060 on mock

Reported to this seat on 2026-10-07, with line numbers at `7c20129`:

1. **The camera ceiling is checked first.** `operator.py:1315-1321` builds the
   decider, which refuses on a gap ceiling, before `orchestrator.py:1468-1506`
   checks the lens, the limits and focus hold. The ceiling stays a gap until
   the bench count is in the store, so every focus refusal on Monday reads as
   the ceiling's. With a TEST ceiling in scratch, each one refused for its own
   reason. The order is the defect, not the checks.
2. **A refused run records no encoder.** `read_z`
   (`devices/micromanager.py:281`, `devices/mock.py:108`) has no caller in
   `src/`. Card 060 asks for the Z reading before and after each refusal, and
   today only the person's display gives it.

## Build

**The gate checks in this order, and stops at the first that refuses:**

1. the plan revision's approval;
2. the hand-over lens equals the plan's;
3. `focus_z_<objective>_min/_max` exist, form a range, and contain
   `range_um`. This is where "above the max" is refused, at preflight;
4. `pfs_not_engaged` exists, and the focus-hold reading is in its `values`;
5. **only then** the method's own readiness: the camera ceiling resolved,
   the verdict's thresholds present, the decider built;
6. the first Z command.

Safety first, method second. Each refusal is then the one the plan actually
fails. **A gap depth of field does not refuse a run**: it only means the
success criterion cannot be judged, which the run records, as check 88 says.

**Record the encoder around every refusal.** Read Z through `read_z`, which is
a read and allowed on every backend, before the gate starts, and again when it
refuses. Record both in the refusal event. If the read fails, record that it
failed, and still refuse.

## Tests, mock first, each watched failing first

- with a gap ceiling and no limit for the lens, the refusal names the
  **limit**;
- with a gap ceiling, limits written and no `pfs_not_engaged`, it names
  **focus hold**;
- with a gap ceiling, everything else in place, and focus hold reading
  engaged, it names **focus hold engaged**;
- with a gap ceiling and every safety check passing, it names **the
  ceiling**;
- every refusal event carries `z_before_um` and `z_at_refusal_um`, and the two
  are equal;
- the order is fixed by a test that walks the six checks.

## Boundaries

`microscope_agent/src/` and `microscope_agent/tests/` only. No change to
`SOFTWARE_MAY_COMMAND` or `NAMED_REFUSALS`. Mock and the fake core only. The
hooks are installed: commit under your seat with `git diff HEAD -- <paths>`,
then `git commit -F <file> -- <paths>`, and push. Never force, never amend.

## What comes back

To this seat and to microscope-20261007-1, 5 lines at most: the commit, the
tests' failing and then passing output, and whether card 060's five refusals
now each show their own reason on mock.
