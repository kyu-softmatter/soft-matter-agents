# 023 — what must change before the first real run

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to `microscope-1`**, the seat that ran the mock pass. **Ordered
as P0 orders harm** — the first item is a collision, not a convenience, and
the rest wait behind it.

The mock pass is done (`run-20260921-001`). **Everything below is a
difference between mock and real that mock could not show**, found by
running the same plan against a non-mock backend and by reading what `run()`
does with the limit it resolves.

## 1. The plan rotates the turret with no retract — and nothing stops it

```
act_set_nosepiece_position   nosepiece   ->  position 5 = 100x oil, WD 0.13 mm
act_set_intermediate_magnification
act_acquire                  camera_red
```

**There is no retract action in this plan.** I looked for one by every name
— `retract`, `z_`, `focus`, `escape` — and there is none.

And the store says what that means (`nosepiece_write_runs_no_escape`, E3):

> The stand runs **no objective escape** when the nosepiece is rotated by a
> Micro-Manager write: **Z does not move**, so whatever height the outgoing
> objective was at is where the incoming one arrives. Rotating at the stand
> or in NIS does run the Ti2's own escape.

**So the plan drives the shortest-working-distance objective on the stand to
wherever the previous one was sitting.** On mock nothing moves. On the
instrument that is the collision this agent's standing orders name first.

`microscope_agent/CLAUDE.md` already says it and the plan does not do it:
**the retract is a step a plan issues and verifies, not a property it may
assume.**

**Add it, and verify it.** Issue the retract, read Z back, and only then
rotate. The stand reads back (`read_back: true`), so this one is verifiable
— unlike the two channels that are not.

## 2. The clearance floor is recorded and not enforced

```python
for resolution in resolve_limits(plan, safety):
    o.record(event="limit_resolved", **resolution)
```

**That is the whole of it.** The lookup runs, resolves `0.13 mm` for this
objective, writes it to the log — and **nothing compares anything against
it.** Check 5 says the same from the other side: *comparing a plan's
conditions against them is not implemented yet.*

**At this objective there is no margin to absorb the omission.**
`objective_clearance_min` resolves to 0.13 mm and
`objective_clearance_absolute_min` is 130 µm: the lookup and the backstop
**coincide exactly**, because the person chose the tightest lens on the
stand. Anywhere else the backstop would catch a bad lookup. Here it cannot,
because there is nothing between them.

**And `resolve_limits` still skips the backstop entirely** — `if not spec:
continue` passes over every constant limit, so `objective_clearance_absolute_min`
is not in that loop at all. The envelope says *the LARGER of the two binds*
and no code takes a larger of anything.

**This is the P0 item behind the retract.** A comparison that refuses is
what makes item 1 enforced rather than remembered.

## 3. `micromanager.py` is written and cannot be reached

Run the router against a non-mock backend and every channel fails the same
way:

```
Orchestrator(backend="micromanager").module_for("camera_red")
  -> GapError: channel 'camera_red' needs devices/dev_camera_red.py,
     which does not exist
```

`module_for` builds `dev_<channel_id>` and `devices/` holds `manual.py`,
`micromanager.py`, `mock.py`. **Card 012's work is complete and
unreachable** — the module implements preflight, apply, read and abort for
`camera_red`, `stand_ti2e` and `widefield_source_a`, and the router asks for
three filenames that were never going to exist.

**Decide which half is wrong and say which in the commit.** Either the
router resolves a channel to its *driver* (the registry's `driver` column
already names `micromanager` for six channels), or the modules are named
per channel. **The registry route looks right** — it is the same split card
012 argued for, *the backend knows how to address MMCore and the channel row
knows what to address* — but it is your call and you wrote both sides.

**One thing not to do**: do not make `module_for` fall back to `mock` when a
module is missing. A real run that silently becomes a mock run is the worst
failure available here, and today's mock produced a log that looks exactly
like a real one.

## 4. `verification: none` stops being honest

The mock log carries `none` seven times and **that is correct** — mock wrote
and queried nothing. On the instrument it stops being correct for the
channels that can answer.

| | |
|---|---|
| `camera_red`, `stand_ti2e`, `confocal_csuw1` | `read_back: true` → **query after the write and compare**; `readback` only if it matched |
| `laser_combiner`, `optical_tweezers` | `read_back: false` → **`none`, always** |

**A return code is not a read-back.** Check 66 will fail a `readback`
claimed on either of the two that report nothing.

## 5. What the person owes, and it is one visit for four

Card 018 holds the full checklist. What blocks a real run specifically:

- **One bench visit closes four**: the emission wheel designation, the
  `light_path_port` label, the `filter_turret_1` label, and the red-path
  designation. Two of them are why `camera_red` is standing as a decision
  rather than a reading
- **The Lapp branch** needs an acquisition, not a look — the prior project
  booked it falsified for two days following a swapped label
- **A Micro-Manager configuration must be loaded**; `micromanager.py`
  refuses until one is, and the prior project's must not be copied
- **The exposure grid**, ten minutes of set-and-read-back

## The order, and why

**1 and 2 first, and they need no instrument.** A retract the plan issues
and a comparison that refuses can both be written and tested on mock today.
**Do them before anything else, because they are the two that hurt.**

**Then 3**, which is also mock-testable: the router either resolves or it
does not, and that is checkable without a device answering.

**Then 4**, which needs a device to be meaningful but can be written now.

**Then the bench.** Nothing above needs the person, and everything the
person owes is useless until the above holds.

## Done when

```bash
python3 contracts/validate.py
python3 microscope_agent/src/plan_card.py --qid mic-20260920-001
```

`0 failed`, and **read the tree the run names with it.**

A second mock run with the retract in it, and a log whose `limit_resolved`
event is followed by something that could have refused. **Report what the
comparison would do if the plan asked for a clearance below the floor** —
if it cannot refuse, item 2 is not done.

**Re-read this card immediately before committing.**
