# Optical tweezers — the live checklist (card 037, phase B)

Nothing on this list runs until **the person has said, in the executing seat's
own window, that the bench is that seat's, and that no other seat needs a
camera or the sample.** A relayed hand-over is none. When the bench is
released, say so, and leave the tweezers in a stated state: **traps off or
deleted, no pattern assigned, and the beam's state as the person states it** —
nothing here reads it.

**After any command to the tweezers the beam is assumed ON**, until the person
says it is blocked. A zero from the GUI is not a blocked beam.

**Trap motion is a planned operation.** A line below that moves a trap runs
under a plan the person approved. On 2026-09-24 this seat moved traps without
one, laser off, at the person's direction; that is in `failures.jsonl` and is
not a pass of any line here.

Each line says what is tested, why, and what it rests on. A line that rests on
no store entry says so and names the gap.

## 0. Before the tweezers program starts

| | test | why | rests on |
|---|---|---|---|
| 0a | **the person says whether the program restores its last project on start**, and if it might, that the saved project has every trap off | loading saved state is a command that turns output on with no output command. On 2026-09-24 the program was closed by the person with two traps active (strength 0.3 and 0.2) and a pattern loaded; if those return on start, output rises before this seat sends anything | **no entry** — gap `tweez300_restores_last_project`. The devices table does not yet say whether this channel's restore path can carry output |
| 0b | the person says which camera body the program opens, and no other seat is using it | the program takes a Kinetix and locks other processes out both ways | the devices table, `camera_red` `exclusive_with: optical_tweezers_gui`, E3; **which body** is a gap, `tweez300_camera_body` |
| 0c | the person says which objective is in the path, and whether the program was calibrated on it | both calibrations (pixel-to-micrometre and the trapping field) are invalidated silently by an objective change and neither is readable over TCP; without them no position is a micrometre | `objective_change_invalidates_trap_calibration`, E3 |
| 0d | the person sets the trapping power on the hand dial, and says what they set | the power has no software path; the setting is recorded only if the person states it | `trap_laser_power_has_no_software_path`, E3; the limit is `optical_power_max` in `envelope/safety.json`, and **nothing here can check compliance with it** |
| 0e | the person says whether emission is on or off at the start | software can switch emission (`LASER_ON` / `LASER_OFF` are in the command set), and this module refuses `LASER_ON` outright; who switched it last is not readable | vendor manual, to be entered by the librarian from the document — **no entry yet** |

## 1. Read-only, with the person present

| | test | why | rests on |
|---|---|---|---|
| 1a | the readiness probe (`TRAP_DELETE` of a name no one uses), answer recorded | the protocol has no query; a harmless command is the only liveness test. **Observed once, 2026-09-24: -22** | prior project's readiness shape, ruled transfer; codes theirs until measured, `MEASURED_HERE` empty in code until a commit fills it |
| 1b | the probe with the System Manager disconnected, and with the GUI locked, if the person will set those up | the "fix by hand" codes (-15, -18) are the vendor manual's and have never been seen here | **no entry** — gap `tweez300_readiness_codes` |
| 1c | which port the GUI listens on | the port is also the choice of GUI instance, and so of camera and calibration. **Observed 2026-09-24: 2070**, one instance | **no entry** |

## 2. Commands, laser off, one at a time, the person watching the GUI

**Before the first command, two gates, asked of the person in the executing
seat's window and logged as answered before anything is sent**
(architecture's ruling at `49a94cc`, held by check 85 at `d284a04`):
`trapping_laser_off` — the trapping laser is off at its hand control — and
`no_sample_mounted`. Both answered yes make this a legal preparatory run whose
log goes into `runs/`. A statement made after a move does not count, and a log
is never rebuilt to add one. Without both, a trap command is motion and needs a
plan.

Each was **seen once on 2026-09-24**, laser off, with `no_sample_mounted` never
asked before the first move — so that record is not a preparatory run and stays
outside `runs/`. Re-run with both gates before anything here is relied on.

| | test | why | rests on |
|---|---|---|---|
| 2a | create a trap; a new trap's strength | **seen: a new trap starts at strength 0**, so an active new trap delivers nothing until a strength is set | **no entry** yet — offered to the librarian |
| 2b | absolute position `0 0`, then a relative move | **seen: 0 0 is the image centre; +x is right on screen; a relative move landed once** | **no entry** yet — offered to the librarian |
| 2c | strength set twice on one trap | **seen: the last value shows** | **no entry** yet |
| 2d | load a pattern (name first, absolute path), assign it | **seen: it loads, and runs on assignment with no start command** | **no entry** yet |
| 2e | a busy answer | the wrapper re-sends on busy and never on silence; **neither has been seen live** | the fake-GUI tests only |
| 2f | silence | after a silence the wrapper sends only trap-off and laser-off until a person acknowledges; **never seen live** | the fake-GUI tests only |

## 3. With light — not before 0a–0e are answered and a plan is approved

| | test | why | rests on |
|---|---|---|---|
| 3a | the person switches emission on at the instrument, at the dial level from 0d, with every trap off | the order: traps off before emission rises | safety rule 4's ordering |
| 3b | one trap on, at a low strength, the person watching the camera | the first light at the sample; heating is noticed by eye only above about 20% on the dial, by recall | `trap_heating_detection_bound`, E5 |
| 3c | identify the trapped bead by moving the stage, not by brightness | in a crowded field brightness does not identify it | `trapped_bead_is_the_one_that_does_not_translate`, E3 |
| 3d | release: every trap off, pattern removed, the person switches emission off and says so | the beam stays assumed on until the person says it is blocked | card 037 |
