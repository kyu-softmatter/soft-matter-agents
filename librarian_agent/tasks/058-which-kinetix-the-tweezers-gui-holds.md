# 058 — which Kinetix the tweezers GUI holds: the person said red, REA wrote down the blue serial

renumbered 055 to 058 on 2026-10-20 by manager-librarian-scope-20261019-4 when it took these four from branch `claude/rea-evidence-cards` (`f0af976c`) into main, on the person's word (Q-20261019-10, `02aaf2ee`): main had already issued 053-055 to other cards. Every card number below was renumbered with it; nothing else changed. Still a draft: landing it is not issuing it.

status: **draft, not issued** · drafted 2026-10-16 by the same side session
as 056, which is not a seated manager-librarian. The request was relayed, not
heard · **for manager-librarian to issue, revise or refuse**. 056's section
*Before anything enters* applies here in full.

## GOAL

The store holds the person's statement of 2026-09-24 that the Tweez 300 GUI
opens the **red-arm** Kinetix, serial `A24M723015`. REA's live camera test of
2026-10-13 is recorded against **`A23H723003`**, which the store maps to the
**blue** arm. The two cannot both hold under the store's current serial-to-arm
mapping. This card does not decide which is right. It puts the conflict on
record, names what each side stands on, and names the reading that settles
it.

## THE ENTRIES THIS TOUCHES

| entry | grade, source | says |
|---|---|---|
| `tweez300_software_opens_the_red_arm_camera` | **E5**, `operator_recall:kyuhwan_20260924_tweezers_camera` | the person chose *the red-arm body* when asked; its conditions say **reading the serial the tweezers software opens settles this and would supersede it at a higher grade** |
| `camera_bodies_are_told_apart_by_serial` | E3, prior_run 2026-09-03 | `A23H723003` is the blue arm and `A24M723015` the red. It is falsified if *the two bodies are moved between arms* |
| `kinetix_red_label_opens_serial_a24m723015` | E1, `measured:run-20260924-002` | with `single_cam_red_noDMD_nocom10.cfg` loaded, label `Kinetix_red` opens `A24M723015`. This is label to serial, **not serial to arm** |
| `tweez300_camera_is_released_so_it_shows_no_image` | E5 | named beside the first in `autofocus/docs/librarian-handoff.md` L-090 |
| `devices.v0.json`, rows `camera_red` and `camera_blue` | staging table | **both** list `exclusive_with: optical_tweezers_gui`. The table keeps no serials (`kept_fields_only`), so the serial-to-arm mapping lives only in the entry above |

A correction to the request as relayed: the request said `devices.v0.json`
lists `A23H723003` as the blue body. It does not; the table drops serials. The
mapping is in `camera_bodies_are_told_apart_by_serial`.

## THE EVIDENCE ON EACH SIDE

**For the blue body, `A23H723003`:**

- REA `tweez300/INTERFACE_MAP.md` at `69009bf`, **section 5d**, the
  paragraph *Tested live (2026-10-13, Kinetix A23H723003)*. Camera `status`,
  `release` and `grab` were driven through the GUI's right-click menu, and 3
  release/grab cycles succeeded. The uncommitted
  `tweez300/tweez_control_log.jsonl` (sha256 in 056) holds three of those
  operations, at 17:45:15, 17:45:20 and 17:45:23.
- The prior project's configuration header, `single_cam_red_noDMD_nocom10.cfg`
  lines 24-28 and 42-43 (here at `microscope_agent/autofocus/configs/micromanager/`).
  It records `Camera-1 = serial A23H723003 (Kinetix_blue)`, measured
  2026-09-03 with the other body free. It loads one camera *so another
  process -- the Tweez 300 GUI -- can hold Kinetix_blue at the same time*.
  That second part is the file's design intent, not a reading, and L-090
  already flags it as a possible conflict. Lines 51-54 add a warning: PVCAM
  enumerates by index, and whether `Camera-1` means the same body while the
  other is held elsewhere is untested. So check the serial, not the label.

**For the red body, `A24M723015`:**

- The person's answer of 2026-09-24, E5. It names an arm, not a serial read
  off the tweezers software.

## WHAT IS NOT SHOWN

- **How REA read `A23H723003` is not recorded.** The serial appears only in
  section 5d's prose. The three log lines carry no serial, and the camera
  driver (`tweez_control.py camera`) works the menu and the window title,
  neither of which shows one. It may have come from the GUI's `Camera Name`
  property, from PVCAM, or from another record. Until that is known it is an
  identifier in prose, and 10.3 rule 3 keeps it from entering on its own.
- **Which arm each body sits on today** rests on a prior-project mapping of
  2026-09-03. If the bodies were swapped since then, the person's *red arm*
  and REA's `A23H723003` agree, and it is the mapping that is stale.

So there are three readings, and the store should hold all three until one
is settled:

| reading | then |
|---|---|
| the GUI holds `A23H723003`, which is on the blue arm | the person's statement named the wrong arm; the E5 entry is refuted |
| the GUI holds `A23H723003`, and the bodies have changed arms | the serial mapping is stale; `camera_bodies_are_told_apart_by_serial`'s own falsifier has fired |
| REA's serial is wrong | the E5 entry stands, and REA's 5d needs correcting at its source |

## WHAT SETTLES IT, for the person to schedule

No light, and no acquisition. The second reading opens a camera.

1. **Read the serial the GUI holds**, off the GUI itself. INTERFACE_MAP 5c
   names a root property, `Camera Name`; the Photometrics plugin re-opens its
   camera by serial. A person reading it is `operator_read:`, E3, which
   outranks the E5 and is what the entry's own conditions ask for.
2. **Or check which camera stays free.** With the Tweez GUI holding its camera,
   load `single_cam_red_noDMD_nocom10.cfg` in Micro-Manager. If `Kinetix_red`
   opens and reports `A24M723015`, the GUI does not hold the red body. A run
   of this system doing this would be a device's report of itself, which can
   be E1. It is a microscope seat's to plan, with the person.
3. **Read each body's label at the bench** to settle which arm each serial is
   on today. That confirms or falsifies `camera_bodies_are_told_apart_by_serial`.

## WHY IT MATTERS, AND WHAT WOULD BE AFFECTED

`single_cam_red_noDMD_nocom10.cfg` keeps only `Kinetix_red`, and it is the
configuration the person chose for the first real acquisition. If the GUI
holds the blue body, that configuration can run while the tweezers GUI is up.
If it holds the red, the two collide, and the GUI must release first.

Read-only, for relay. **Edit none of these.**

- `librarian_agent/kb/staging/devices.v0.json`. `camera_red` and `camera_blue`
  both carry `exclusive_with: optical_tweezers_gui`. Once the body is known,
  one of the two is wrong. Leave both until it is.
- `microscope_agent/src/tweezers_live_checklist.md:26`. Row 0b names a gap,
  `tweez300_camera_body`, which **is not in the store** (no gap record found,
  2026-10-16). Recording it is part of this task.
- `microscope_agent/tasks/047-sim-to-real-the-asymmetric-double-well.md:30-36`
  and `:57-62` pick the recording camera by this answer, and say *confirm it
  by serial at the bench before relying on it*.
- `microscope_agent/tasks/037` (line 0b), and
  `microscope_agent/src/session_033.py:397`, which cites the serial mapping.
- `kb/guides/safety_camera_red.md`, `safety_camera_blue.md` and
  `safety_optical_tweezers.md` are rendered from the store and move with the
  publish.
- `microscope_agent/autofocus/docs/librarian-handoff.md:183` (L-090) and
  `:222`. They hold the same question from the dino side, with the same
  conflict marked.

## TASK, for the librarian seat

1. **Before REA is open, this much can be done**: mark the conflict between
   `tweez300_software_opens_the_red_arm_camera` and the cfg header, which is
   already readable: it sits in this repository since the dino import, and
   its parent project, agentic-microscope, is open. Rule it as 10.2.1 rules a
   configuration loaded in place: its labels are downgraded, and its design
   intent is not a reading. Write the gap `tweez300_camera_body` with what was
   searched.
2. Once REA is open: rule its 5d serial (10.2.1). It is an identifier in prose
   with an unrecorded reading, so **downgrade** looks right unless the REA
   session that wrote it can say where it was read. Ask through
   manager-librarian. Don't guess.
3. **Do not refute the E5 entry on REA's word or the cfg header alone.**
   Refute or supersede it only on reading 1 or 2 above. Record which three
   readings remain open.
4. Read-only: list the cards citing any of the three entries, at their pins.

## CONTRACT

- Identifiers and a relation, no values. A serial is addressable, and an
  entry that names one should carry it in `identifiers`.
- Not a safety value.

## CONSTRAINTS

As 056's. Dead ends go in `failures.jsonl` with `task: 058`.

## REPORT

The conflict as recorded, and the gap. The ruling on REA's serial. Which
reading is open. One sentence: what is not yet on disk.
