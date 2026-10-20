# 056 — the trapping laser's level has a software path after all, says work outside this repository

renumbered 053 to 056 on 2026-10-20 by manager-librarian-scope-20261019-4 when it took these four from branch `claude/rea-evidence-cards` (`f0af976c`) into main, on the person's word (Q-20261019-10, `02aaf2ee`): main had already issued 053-055 to other cards. Every card number below was renumbered with it; nothing else changed. Still a draft: landing it is not issuing it.

status: **draft, not issued** · drafted 2026-10-16 by a side session working
from `D:\Kyu Hwan Choi\REA`, which is **not a seated manager-librarian** and
holds no seat identity. The person's request reached it through the session
that started it, and is recorded here as relayed, not heard · **for
manager-librarian to issue, revise or refuse**, and only then for a librarian
seat. One of four cards (056–059) that carry REA's evidence of 2026-10-13 to
the store. None of them edits an entry, a device module or a limit.

## BEFORE ANYTHING ENTERS: REA is not a source here yet

This section applies to all four cards. 057–059 point back to it.

`D:\Kyu Hwan Choi\REA` is the person's reverse-engineering workspace on the
microscope computer. It is a local git repository with no remote, at HEAD
`f641745` on 2026-10-16. One folder per vendor program: `tweez300/`,
`lunf_direct/` and `nis_laser/` are committed, and its own `CLAUDE.md` tags
each claim `[manual]`, `[binary]`, `[typelib]` or `[inferred]` and says what
was verified live. It is not one of the four prior repositories, and it is not
`dino-autofocus`. **`plan.md` 10.2 names it nowhere, and nothing in this
repository cites it.** That was checked on 2026-10-16 with `git grep` at
`2d9f3f3` for `REA`, `lunf_direct`, `tweez_control`, `nis_laser`,
`LASER_SET_LEVEL`, `g5_regprocs` and `5995` outside `microscope_agent/autofocus/`.
The only hits were unrelated digits.

1. **The person opens it, directly to architecture**, the way `dino-autofocus`
   was accepted on 2026-10-03. Architecture then writes the line in 10.2. A
   relay does not open it, and that includes this card.
2. **Until then these cards are a request and a map of where the evidence
   is.** Nothing enters.
3. **Once it is open, the ceiling is E3.** REA's runs have no `run_id` here,
   so its readings come in as `prior_run:REA@<sha>/<path>`, which
   `SOURCE_GRADE` caps at E3 (10.3 rule 1). What the person saw at the bench
   may be `operator_read:`, also E3, but only if the librarian finds it
   recorded as the person's own words (037's rule: a seat's paraphrase of the
   person is the seat's word). Nothing here reaches E1, because E1 needs a run
   of this system.
4. **REA's live logs are in no commit.** They are gitignored operational
   state:

   | log | lines | sha256 on 2026-10-16 |
   |---|---|---|
   | `tweez300/tweez_control_log.jsonl` | 3 | `b6da468e0c8e27c30a9d3634fbc41fd4678da3d09c4934af708f5c9218675b8e` |
   | `lunf_direct/lunf_direct_log.jsonl` | 474 | `ab6b2cc6fec5f6bb4f18a1dc5cd39145068499ec28db2120220a54593c785083` |

   By 037's rule an item whose source is not committed is not checkable. So
   the person decides whether copies are committed or archived somewhere the
   librarian may read, matched against these hashes. Otherwise only the
   committed documents can be cited, and **those are prose**. 10.3 rule 3 then
   keeps every figure in them out until a machine-readable source is found.
5. **What REA's static work is.** It reads copies of vendor binaries:
   disassembly, strings and COM type libraries. No vendor file was modified.
   A `[binary]` reading names a vendor file and an address. Whether that
   counts as going to the original source (10.3 rule 2) or as an index into
   it is the librarian's ruling, made once and applied to all four cards.

## GOAL

The store says the trapping laser's level can be neither set nor read from
software. REA's work of 2026-10-13 says software **can set it** over the same
TCP interface the store already records for emission, but **cannot read it**,
apart from a setpoint shown in a vendor window. Decide what the store says
now, with its grade and its limits written into the conditions.

## THE ENTRIES THIS TOUCHES

| entry | grade, source | what it says | what REA bears on |
|---|---|---|---|
| `trap_laser_power_has_no_software_path` | E3, `prior_run:agentic-microscope@safety-2026-09-03` | the level is neither readable nor settable; it is set by a hand control | **settable: contradicted.** Readable: not contradicted over TCP. A setpoint, not the delivered power, can be read off the System Manager's window |
| `trap_laser_emission_is_switchable_over_tcp` | E3, `spec:Tweez300UserManual` | its second sentence: *the command set holds no command that sets or reads the laser's power* | true of the **manual's** list, false of the **GUI's own command table** |
| `tweez300_reports_nothing_back` | E3, prior_run | no readback, and six ways a command is ignored all return 0 | not refuted: a 0 is still acceptance, not verification. It gains one fact: this command refuses with **non-zero** codes |

## THE EVIDENCE, AND WHERE IT IS

All of it is in `tweez300/INTERFACE_MAP.md` at REA `69009bf` (blob sha256
`888591bd313c1d05862bb1f1b23b0f25789fc17b153b3a69fd36105d47093428`): section 2,
the table *Present in the GUI's command table but missing from the manual*; the
section 5 table *Main laser power*; and **section 5e**. The client is
`tweez300/tweez_control.py` at `69009bf`.

- **Static** [binary]. `LASER_SET_LEVEL` is in `Tweez300GUI.exe`'s command
  table (`evidence/gui_tcp_command_table.txt`). Its handler, at VA `0xa80070`,
  parses one float and returns −50 if it cannot. It then writes the node
  `Beam.Laser.Power`, which calls the System Manager's COM method
  `IArTw300BeamControl.LaserPowerSet(float)` [typelib]. The System Manager's
  `SetLaserPower`, at `0x86d3c0`, returns **204** outside 0.02 to 1.0 and
  **202** if the laser is not enabled.
- **A float32 boundary.** The GUI passes a 32-bit float, and
  `float32(0.02) = 0.0199999996`, so a literal `0.02` is refused with 204. The
  client sends `0.020000001`, one float32 step up, and the GUI shows it as
  0.02. **0 is not a level**: the only way to remove light is `LASER_OFF`.
- **Live, 2026-10-13.** The laser was in Standby throughout and `LASER_ON` was
  never sent. `LASER_SET_LEVEL 0.0300` returned 0, and the GUI's setpoint
  moved from 0.02 to 0.03. `0.0200` returned 204, twice. `0.020000001`
  returned 0, and the setpoint went back to 0.02.
- **The readback is a setpoint.** It is the text of the System Manager's
  *Tweez 300 - Laser Beam Control* window, read with `WM_GETTEXT`
  (`read_setpoint()`). It shows the setpoint, not the delivered power.
- **Units.** Relative, 0 to 1 of maximum [manual]. This unit is serial 0131
  with an MPB YFL-MP-5-1064-OEM1, so 1.0 is about 5 W (section 5b, read off
  the device's own USB volume).

## WHAT IS NOT SHOWN: write each into the conditions

- **Delivered power was never measured.** A setpoint moving in a window is the
  GUI's view of the device.
- **The laser was never active.** Behaviour under emission, and the Locking
  to Locked approach the manual describes, are untested. So is `LASER_ON`,
  which was withheld on purpose.
- **How the software setpoint and the "hand control" interact is unknown.**
  The old entry is about a hand control. REA does not say whether that is a
  dial on the unit or the GUI's own slider, nor which one wins when both
  move. Ask the person before writing a claim that either one replaces the
  other.
- **One sitting, no log line.** The laser test is not in
  `tweez_control_log.jsonl`, which holds only three camera lines, from
  17:45:15 to 17:45:23. The record of it is the prose of 5e.
- **Where the codes come from is not pinned.** The replies are what came back
  over TCP. Section 5e names 204 and 202 as the System Manager's codes and
  does not say whether the GUI passes them through unchanged or maps them.

## WHAT IT MEANS FOR SAFETY, which this card does not move

- **This widens what software can do to a class-4 source.** A setpoint can be
  changed over a TCP port that has no authentication (059, item b). That is
  the dangerous direction, and the store should say it as plainly as
  `trap_laser_emission_is_switchable_over_tcp` said it for emission.
- **No limit is set, implied or carried.** REA's `laser_limits.json` is REA's
  own gate and binds nothing here; the envelope binds (10.3 rule 4). The range
  0.02 to 1.0 is what the device accepts. It is not a limit.
- Nothing in this repository sends `LASER_SET_LEVEL` or `LASER_ON` because of
  this card. Wrapping either command is a microscope card's decision, made
  with the person.

## WHAT WOULD BE AFFECTED IF THE STORE CHANGES

Read-only, for relay. **Edit none of these.**

- `microscope_agent/src/devices/python_tcp.py:30-35`. The docstring says the
  power *is a hand dial with no software path*, citing the entry. `WRAPPED`,
  from line 71, has no `LASER_SET_LEVEL`, so the module refuses the command
  today. That refusal stays right until a card decides otherwise.
- `microscope_agent/src/tweezers_live_checklist.md:28-29`. Row 0d has the
  person set the power on the hand dial, because *the power has no software
  path*. Row 0e cites the emission entry.
- `microscope_agent/tasks/018`, `037`, `047` and
  `questions/mic-20260918-001/axis_widefield_inline_a4.json` cite the entry.
  They are records pinned to their versions.
- `contracts/schemas/envelope_safety.schema.json:240`. The `$comment` says *a
  written ceiling is the only control there is*. That file is a manager's.
- `plan.md` 2.1 rule 11: *its power has no software path, its hand control is
  the person's, and this rule claims nothing about it*. That is
  architecture's. If software can raise the level, rule 4 (power up last,
  down first) has a command to order. Raise this. Do not edit it.
- In the store: the four `trap_laser_power_at_sample_1064nm_*` entries,
  `trap_heating_detection_bound` (stated as a dial position *because there is
  no path by which the number could have been read back*), and
  `kb/distilled/what_falsifies_the_49_bench_claims.md`.
- `kb/guides/safety_optical_tweezers.md` is rendered from the store and moves
  with the publish.
- `simulation_agent/questions/sim-20260923-101` and `-201`. Records pinned to
  their versions; nothing to do.

## TASK, for the librarian seat, once REA is open

1. Rule each item above as transfer, downgrade or discard (10.2.1), naming
   its slot and the 10.3 rule it passes.
2. **Decide the relation.** Either a new entry (for example
   `trap_laser_level_is_settable_over_tcp`) conflicts with
   `trap_laser_power_has_no_software_path`, or it supersedes it. Both would be
   E3. One is a prior project's memo; the other is later work on this bench's
   own unit, with a live setpoint change. Rule 7 keeps a conflict and rule 8
   keeps a superseded claim. Which one applies is your call: write the reason.
3. **Narrow, don't rewrite,** `trap_laser_emission_is_switchable_over_tcp`.
   Its claim about the manual stays. Its conditions gain one sentence: the
   GUI's command table holds a level command that the manual does not list.
4. **Keep "settable" and "readable" apart.** A setpoint scraped from a vendor
   window is not a readback of power, and it is not over TCP either. If it
   enters at all, it is a separate claim.
5. Write the falsifiers. The claim fails on a re-run in which
   `LASER_SET_LEVEL 0.03` returns 0 and the setpoint does not move. A power
   meter reading that does not follow the setpoint bounds what *setting the
   level* means, without refuting it.
6. Read-only: list the cards that cite the old entry, at their pins, for
   manager-librarian to relay.

## CONTRACT

- A claim about a control path, not a value of a registered observable. The
  level range and codes are identifiers of behaviour. They cross only from a
  machine-readable source (10.3 rule 3), and never as a limit (rule 4).
- Not a safety value. Nothing here touches the envelope or any device code.

## CONSTRAINTS

- Nothing moves before REA is opened (section one).
- Every entry moves `kb_version`. Check the query log for in-flight pins
  first, and publish with the guides.
- Commit under your own seat with `-F <file> -- <paths>`, naming files and
  never `librarian_agent/`. Dead ends go in `failures.jsonl` with `task: 056`.

## REPORT

Each REA item and its ruling. The relation chosen and why. The cards citing
the old entry. The commit and `kb_version`. One sentence: what is not yet on
disk.
