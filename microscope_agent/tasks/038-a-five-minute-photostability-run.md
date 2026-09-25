# 038 — a five-minute photostability run, one frame a second

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Assigned to `microscope-20260924-1`.** The person asked that seat directly
on 2026-09-24: *"run it longer time in fresh area I found"*. Asked the
cadence: *"you can take a picture every 1second"*. Light continuous, as in
the first run. Duration five minutes. **Card 033 is closed, and its route
was for its run only**, which is why this card exists.

**Everything card 033 set up stands unless this card changes it**: the
person moves the microscope by hand, the allow-list (`Aura`, `Kinetix_red`,
`Core` roles), `AutoShutter` 0 read back first, the configuration the person
chose loaded in place with its hash, the Lapp mirror moving at load as the
person accepted, the gates, the shutdown order, pixel size never taken from
frame metadata, the frames outside the tree.

## Repeats at other locations (added 2026-09-24 evening)

The person asked `microscope-20260924-1` after run `-006`: *"run it again
from other location"*. **This card covers such repeats**, on these terms:

- **`src/session_038.py` unchanged**, under a new run id, the first free
  one. A changed script is a changed run, and needs its own line here
- **every gate as in `-006`**: preload with the bench handed over in your
  window, NIS closed, the piezo controller's state and the lasers asked
  and logged; `approve_light` with the command list; `fresh_field`, asking
  that the new location has not been lit in green
- the log in the preparatory-run shape, in `runs/` and beside the frames,
  as `-006` was
- **analysis per the method in `microscope_agent/CLAUDE.md`** (`b48c9b3`):
  whole-frame totals or per-particle tracking, never a frame-0 mask, and a
  curve normalised to the settled level. **Report the drift beside the
  brightness**, since drift is what bounds the measurement
- still a preparatory run, so its brightness is an `observable_value` and is
  not for the store. It waits for card 034's plan, which cites the runs

## The analysis, saved (recorded after the fact, 2026-09-24 evening)

The person asked `microscope-20260924-1` to *"save that properly"*, and it
was done at `3fc720f` before this line existed. **The line records it and
covers it.** `src/analyse_photostability.py` follows the `CLAUDE.md` method,
and **checks each frame file's sha256 against its run log before reading
it**. Its output is `runs/<run_id>/photostability_analysis.json` for `-002`,
`-006` and `-007`, **beside the logs, which stay untouched**, so a closed
run folder gains a derived file and loses nothing. The findings items cite
it. Results, relative to the settled level: `-002` 99.3% after 60 s;
`-006` 97.4% and `-007` 96.4% after 299 s.

**For later repeats**: the same script, its output beside the log, and the
log never edited. A changed analysis is a changed script, and needs a line
here.

## One holder of the bench

`plan.md` 6.2.1, decided 2026-09-24: **you open a device only after the
person has said, in your window, that the bench is yours.** The person
asking you for this run is the request, and the hand-over should be said as
one. Ask for it if it was not. Three other microscope seats are running.
None of them may open a device, and none will unless the person hands the
bench to them. **When you finish, say you release the bench, and state
every device's state.**

## What this run is

**A preparatory run again**: no plan fits it, for the same reason as the
first (card 033 §6), and `plan.md` 11-21 makes that legal on four
conditions, which check 85 holds. **Write the log in that shape from the
start**, now that the schema exists:

- `plan_id` null, `revision` null, and `no_plan_because` in words
- `not_dispatched`, saying it did not come through the plan dispatcher, and why
- **`approved_commands` pointing at `microscope_agent/runs/<run_id>/commands.json`**,
  written there **before** the `approve_light` gate, with its sha256. Then
  the in-tree log and the one beside the frames are the same bytes, and
  nothing is added afterwards. Write it with LF endings
- nothing dispatched to the motion set, and no result card or KB entry of
  its own. Its numbers reach the record when card 034's plan cites it

## The design, as the person set it, and what is ruled here

| | |
|---|---|
| excitation | Aura GREEN at **100 per-mille**, read back. **`State=1` continuously for the whole 300 s**, as in run `-002`. Same intensity as that run; five times its duration |
| frames | **300 frames at 100 ms exposure, one per second** |
| pacing | the sequence call cannot pace this, because frame period equals exposure (`interval_ms_is_ignored_and_frame_period_equals_exposure`). So **`snapImage` in a loop, frame `i` scheduled at `t0 + i × 1 s`, from the integer `i`, never from an accumulated sum.** Log each frame's actual monotonic time and the camera's timestamps. **A late frame is recorded as late, not re-timed.** Snaps carry no `ImageNumber`, so the count is the loop index plus the timestamps: say that in the log |
| field | the person has found a fresh area. **Still ask, at the `fresh_field` gate, that it has not been lit in green**, and log the answer |
| script | **a new file, `src/session_038.py`.** Do not edit `src/session_033.py`: it is the record of what ran as `-001` and `-002`. Import from it where that helps |

**Repeat the full pre-light checks, the master-off dark test included.**
Run `-002` proved it on that load. This is a new load, and each run's log
has to stand on its own: *a run that cannot show the dark case cannot claim
the bright one*. It costs seconds, and the light stays off throughout.

**Add to the preload gate:** is NIS closed, and is the piezo controller off?
The piezo's second master is unsettled (card 035): if NIS drives its
analogue line, the sample can move under a five-minute series and nothing
here would see it. **The piezo question from `-002` is still open.** Log the
answer either way; if NIS is running, stop and ask.

## What to bring back

- the log, beside the frames and in `runs/`, and its hash
- **the curve, said honestly**: five minutes can tell one exponential from a
  multi-rate decay where one minute could not, so fit both and say which
  the data prefers, and by how much. Then say whether run `-002`'s bump
  near 51 s recurs, and whether the background rises again. **An analysis
  is not a result card**: numbers for the record go through 034's plan
- late frames, with how late, and any drift or focus change you can see
  (nothing here corrects focus, and the person focused by eye)
- your release of the bench, with every device's state

## Constraints

- the trapping laser off at its hand control, the LUN-F off at its power,
  the tweezers program closed, Micro-Manager closed, as before
- `envelope/safety.json` is the person's alone
- commit with `git commit -- <paths>` after `git diff HEAD -- <paths>`,
  naming new files individually. Hooks are not installed; say so

**Re-read this card immediately before committing.**
