# 099 — the watcher's restart test does not read the wall clock

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat.** It is small,
and it comes after card 096 unless the runtime holder,
architecture-office-20261017-1, moves it. Mock only. If you are not that
seat, take nothing from this card and report up.

## Why

One test failed in a full-suite run twice, in two separate reports: after
card 091 and after card 092 (`44ff68a2c`). The test is
`test_watcher.py::T7TheLightAndTheLevel::test_a_later_matched_light_command_restarts_the_settled_level`.
Run alone, it passed 49 of 49 tests three times out of three, and the watcher
code was not touched either time. That is a test whose verdict depends on
machine load.

A test like that is worse than none. It teaches whoever reads a red suite to
read past one failure, and the next real failure in the same place will look
the same.

The test takes its times from `self.clock()`, which is `time.monotonic()`,
and sleeps 0.01 s between the second light command and the half-level
frame. Everything else in T7 passes fixed `t_mono` values. Whether that
sleep is the cause, or the watcher's own thread is, has not been found.

## What to do

1. **Find the cause before changing anything.** Make the failure reproduce
   on demand, for example by loading the machine, or by delaying the
   watcher's thread with a patched sleep in the test. Then state, in one
   sentence, what ordering the test assumes and what happens instead.
2. **Fix the ordering, not the tolerance.**
   - Do not widen `places`.
   - Do not add a retry, a longer sleep or a longer pump timeout.
   - Do not mark the test skipped or expected to fail.
   - The fix should give the test explicit times, the way the other T7 tests
     pass fixed `t_mono` values, or wait on the event the assertion actually
     depends on.
3. **If the cause is in `src/watcher.py`, not in the test,** stop and report
   it to this seat first. A watcher that misorders a light command and a
   frame under load is a defect in what the person sees, and it gets a card
   of its own.

## Tests

1. Watch the test fail at least once by reproducing the cause. Then watch it
   pass under the same reproduction.
2. Run `test_watcher.py` 20 times in a row under load, all green. Say how
   the load was made.
3. The rest of the suite is unchanged.

## Boundaries

- Write `microscope_runtime/tests/` only, plus `src/watcher.py` if step 3
  sends it back to you on a card.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.
- Run tests with `-p no:cacheprovider`. A `.pytest_cache` in the shared copy
  fails the validator.

## What comes back

Report to this seat in 3 lines at most:
- the cause, in one sentence;
- the commit;
- the reproduction, failing then passing, and the 20-run count.
