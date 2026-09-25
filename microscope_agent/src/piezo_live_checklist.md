# Piezo stage — the live checklist (card 035, phase B)

Nothing on this list runs until **the person has said, in the executing seat's
own window, that the bench is that seat's.** A relayed hand-over is none.
When the bench is released, say so, and leave the controller in a stated
state: **its security level as found, no position written since the last
line of this list, the vendor program's state as found.**

Each line says what is tested, why, and what it rests on. A line that rests on
no store entry says so and names the gap.

## 0. Before the port is opened

| | test | why | rests on |
|---|---|---|---|
| 0a | the vendor program (NanoBench 6000) is closed | the serial port is exclusive; the program holds it while a session is open | the devices table, `piezo_stage.exclusive_with`, E3 |
| 0b | **the person says whether NIS-Elements is running and driving the stage through the analogue line `Dev1/ao2`** | two masters on one actuator: the vendor manual says an analogue and a digital command are *summed* when both are enabled, so either can move the sample | **no entry** — gap `piezo_analogue_path`; the prior project's "the mode bits say it is ignored" is downgraded E3 |
| 0c | no loaded Micro-Manager configuration declares an analogue-output device on `Dev1/ao2` | an analogue-output adapter writes 0 V when it initialises, which on that line would command a position | **no entry** — raised with the person, not carried as a rule; `microscope-20260924-1`'s run loaded no NIDAQ analogue output (`dad0f5e`) |
| 0d | no other seat is imaging | a piezo move shifts the sample another seat is imaging | the bench rule, plan.md 6.2.1 |
| 0e | `envelope/safety.json` holds `piezo_{x,y,z}_position_{min,max}` and each floor is below its ceiling | the wrapper refuses every command on an axis without them; nothing defaults to the device range | the person's file, written 2026-09-24 at `58d55cd`, `carried_over`, to be re-signed physical after this check |

## 1. Read-only, with the person present

| | test | why | rests on |
|---|---|---|---|
| 1a | open the real address named by the person, read the library version and the controller identity | the prior project ran library 2.7.9 in code and 2.8.1 on disk; which one is here is a reading, not an inference | **no entry** — gap `piezo_controller_identity` |
| 1b | read the security level, and record what it reads as | the level is controller-side state that outlives a session, and the wrapper refuses to unlock from a level it cannot restore | **no entry** — gap `piezo_security_levels`; the simulator reads `None` locked and `User` after the User code |
| 1c | read each channel's measured position | the wrapper refuses a start outside the limit and never corrects it; the positions found are the first record | the person's limits |
| 1d | read each channel's calibrated range minimum and maximum | fixes the position unit: a 600 um axis reading 6.0e8 is picometres. The wrapper converts by picometres and must not until this agrees | prior reading, downgraded E3; **no entry here** — gap `piezo_position_unit` |
| 1e | read the mode word on each channel (analogue and digital command enables) | settles half of 0b by reading, and the mode word is writable at User level, so it is read, never assumed | **no entry** — gap `piezo_analogue_path` |

## 2. The security levels, deliberately

| | test | why | rests on |
|---|---|---|---|
| 2a | `DllLink.learn_levels()` once, and read that the level found is restored | it changes the level while it runs, so it is a checklist step and never part of a command | the simulator run of 2026-09-24 (found `None`, restored `None`) |
| 2b | at User level, list which commands exist that did not exist locked | the command set depends on the level; "invalid command name" can mean gated, not absent | prior discovery structure, ruled transfer; the counts are theirs and not carried |

## 3. The first motion — a planned operation, not a session script

A run that moves the piezo needs a plan the person approves; a plan-less run
that dispatches to `piezo_stage` is refused by check 85.

| | test | why | rests on |
|---|---|---|---|
| 3a | one small step on channel 1, then 2, the size the person's, **watching the image** | verifies the channel-to-axis mapping, the way the camera was verified by a frame | the person's statement 1/2/3 = x/y/z; prior E3 corroboration |
| 3b | read back after each step and report the difference | there is no position tolerance in the envelope, so nothing is marked verified until the person says what agreement means | **no entry** — gap `piezo_position_tolerance` |
| 3c | **Z: a direction-finding step only**, the size the person's, with the person watching the objective | which piezo-Z direction approaches the objective is unmeasured; a travel limit is not a clearance limit | **no entry** — gap `piezo_z_direction`, the same shape as `pfs_offset_sign_unmeasured` |
| 3d | after the mapping holds, the facts leave as a result card for the librarian | graded by how they were established | — |

## Refused regardless of this list

- **the controller's waveform generator**, until its input unit is measured
  here (failures.jsonl, 2026-09-24). A sine is a host-stepped sequence of
  position writes, each checked against the envelope, as a planned operation
- **super-user**, ever
- **any piezo-Z motion beyond the person's direction-finding step**, until the
  direction is measured and recorded

## Questions only the person can answer

1. Is NIS-Elements running, and does it drive the stage through `Dev1/ao2`?
2. May the waveform generator ever be used? If so, its unit has to be
   measured first, on a lateral axis only.
3. What size is the first step on each channel, and the Z direction-finding
   step?
4. What read-back difference counts as "the stage went where it was told"?
   Until it is stated, nothing is marked verified.
5. For the sine asked for on 2026-09-24: a 600 um amplitude cannot fit a
   0 to 600 um limit. The largest that fits is 300 um about 300 um. Which
   amplitude, which rate, and how long?
