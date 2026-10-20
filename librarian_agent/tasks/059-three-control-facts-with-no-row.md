# 059 — three control facts from REA with no row in the store

renumbered 056 to 059 on 2026-10-20 by manager-librarian-scope-20261019-4 when it took these four from branch `claude/rea-evidence-cards` (`f0af976c`) into main, on the person's word (Q-20261019-10, `02aaf2ee`): main had already issued 053-055 to other cards. Every card number below was renumbered with it; nothing else changed. Still a draft: landing it is not issuing it.

status: **draft, not issued** · drafted 2026-10-16 by the same side session
as 056, which is not a seated manager-librarian. The request was relayed, not
heard · **for manager-librarian to issue, revise or refuse**. 056's section
*Before anything enters* applies here in full.

## GOAL

REA established three things on 2026-10-13 that no entry speaks to, one way
or the other. They are not contradictions, and they are of three different
strengths. (a) was verified live, (b) is a live observation of the
computer's own state, and (c) was **never run on the instrument**. Decide for
each whether it enters, as what, and with which limits. Or record why not.

## (a) The tweezers GUI can hand its camera over, by driving its own menu

**Evidence.** REA `tweez300/INTERFACE_MAP.md` at `69009bf`, **section 5d**,
and section 5 item 2. The client is `tweez300/tweez_control.py camera
status|release|grab`.

- **Static** [binary, disassembly of a copy of `Tweez300GUI.exe`]. The item
  is `ReleaseGrabCameraMenuItem` on the right-click menu of the GUI root.
  There is no TCP command, node or COM method for it. The GUI enables it at
  run time only if the camera plugin's capabilities have bit 8 set.
  Photometrics returns `0xA9` while the camera is open, and IDS uEye and
  DirectShow do not, so on this bench it exists for the Kinetix. It refuses
  while calibration is active, while any view records, and while a ROI is
  active. While released, the GUI refuses camera operations and its window
  title ends `- RELEASED.`. The plugin's `GrabCamera` re-opens by serial.
- **Live, 2026-10-13.** `status`, then `release` and `grab`, each returned
  `changed: true`, and 3 consecutive release/grab cycles (6 operations) all
  succeeded after the driver was hardened. Early attempts were flaky. The
  uncommitted log holds three of these lines (056, point 4).

**Not shown.** That another program then opened the released camera. 5d
records the toggle and the GUI's own state, not NIS or Micro-Manager taking
the body. Nor does it show which body was released (058).

**How it works, and why that matters for safety.** It is UI automation: it
moves the real mouse and clicks the GUI. P0 rule 5 forbids automatic commands
while a person has hands on the instrument, and a mouse moving under a
person's hand is the same hazard at the computer. REA's own rule is to run it
only when nobody is using the PC. Write that into the conditions.

**Store rows it bears on.** `tweez300_camera_is_released_so_it_shows_no_image`
(E5): the person's *"we always release the camera"*. This gives the release a
software route. In `devices.v0.json`, `camera_red.exclusive_reason` says
*whoever opens first locks the other out*; the release is the hand-over that
sentence leaves out. `optical_tweezers.note` sends whatever is reachable only
through the GUI to a manual instruction sheet; this item is reachable through
the GUI, by automation.

## (b) The tweezers command port listens on every interface, with no authentication

**Evidence.** REA `tweez300/INTERFACE_MAP.md` at `69009bf`, **sections 5e
(last bullet) and 5f**.

- `Tweez300GUI.exe` binds TCP `0.0.0.0:2070`, although its status pane shows
  `127.0.0.1/2070`. The protocol has no authentication, and it carries
  `LASER_ON` and `LASER_SET_LEVEL` (056). Windows had created inbound *Allow*
  rules for the GUI on the Public profile, any port and any remote address,
  and the computer has Public-profile network links.
- **Changed 2026-10-13, by the person in an elevated shell**: one inbound
  Block rule for TCP local port 2070 on all profiles, and both Public Allow
  rules disabled. Afterwards, read-only: one block rule, no enabled inbound
  Allow for the GUI, and loopback control unaffected (a local connect to
  `127.0.0.1:2070` succeeded and the setpoint read back).
- The hardware interlocks, key switch and shutter are independent of the
  network and were never at stake. Laser level and emission were.

**Not shown.** That the port is unreachable from another machine: a
connection from this PC to its own address bypasses the firewall and proves
nothing. Upstream network filtering was not examined. The GUI still binds
every interface, so the protection is the firewall alone. A policy reset or a
Windows "Allow access?" prompt answered yes brings the exposure back, and a
second GUI instance listens on 2071.

**What kind of fact this is.** That the GUI binds every interface with no
authentication is a fact about the vendor software. It is knowledge, and a
hazard, and it belongs beside `trap_laser_emission_is_switchable_over_tcp`.
That the firewall blocks it is a **state of this computer, which can change
with no signal**: if it enters at all, it needs a `valid_until` event. What
the firewall should be is policy, and it is the person's. The tweezers page,
`kb/guides/safety_optical_tweezers.md`, may be the right place for the hazard. Don't carry the
computer's network addresses into the store; they are in 5f if the person
wants them.

**Store rows it bears on.** None directly. Callers on loopback are
unaffected: `microscope_agent/src/run_trap_plan_20260925.py:49-52` and
`shutdown_20260925.py:41` connect to `127.0.0.1:2070`, and
`tweezers_live_checklist.md` row 1c records port 2070, observed 2026-09-24.

## (c) A route through NIS itself, written and never run on the instrument

**Evidence.** REA `nis_laser/README.md` at `74e5817` (blob sha256
`adcce9de3657140f02a3fb31ec1b878bd001263f37529c9c47ae37a9498dde3c`), and
`nis_laser_server.py`. A server runs inside NIS (`start_server.mac`) and calls
the MultiLaser macro functions exported from `g5_regprocs.dll`, which work
only inside the NIS process. Clients reach it on TCP `127.0.0.1:5995`. Reads
are `status`, `lasers`, `shutters` and `light_path`. Light-adding writes are
gated, and each one reads the light path at that moment against a list of
eyepiece-free positions. That is P0 rule 11's shape. Every write returns
NIS's own read-back, which is NIS's view and not a measurement.

**Not shown, and this is all of it.** It was tested against a fake NIS only:
14 offline tests. The first live run, read-only, has not happened. Open
questions: whether background mode works under NIS's Python, whether names
are wide strings, whether `line_on` unblanks the line or only flags it for
acquisition, how NIS's power numbers map to volts, and which shutter is the
fiber's and which the CSU-W1's. One line of the README is already stale:
it says going around NIS *could not set power*, which `lunf_direct` (057)
overturned the same day. Its other two reasons stand: the direct route needs
NIS closed, and it cannot reach the fiber shutter.

**So nothing about the bench enters from (c).** At most, the store can say
that the vendor documents a MultiLaser macro interface. That would be sourced
to the NIS documentation itself (10.3 rule 2), not to REA. Hold the rest as a
candidate route, with a gap naming the read-only run that would make it a
fact.

## WHAT WOULD BE AFFECTED IF THE STORE CHANGES

Read-only, for relay. **Edit none of these.**

- (a): `microscope_agent/src/devices/python_tcp.py` has no camera path, and
  none fits its TCP scope. A release route would be a new driver and a
  microscope card's design. Also `tweezers_live_checklist.md` row 0b,
  `devices.v0.json` `exclusive_reason` on both camera rows, and
  `tasks/047`'s plan to record while trapping.
- (b): nothing in code. `kb/guides/safety_optical_tweezers.md` if the
  hazard enters, and any future card that lets something off this computer
  reach the tweezers.
- (c): `microscope_agent/src/session_036_laser.py`, whose route force-kills
  NIS to free the lines. (c) and `lunf_direct` are two alternatives to that,
  and choosing among them is the person's. `plan.md` 4.6.6, *heterogeneous
  control channels*, is architecture's, and would need a line if an
  in-process macro server becomes a channel kind.

## TASK, for the librarian seat, once REA is open

1. (a): rule it (10.2.1). It is a candidate claim that the GUI's camera
   release has a software route by UI automation, verified to toggle and not
   verified to free the body for another program. Write the mouse condition
   in.
2. (b): split the vendor-software fact, which may enter, from the
   computer-state fact, which enters only with a `valid_until` event or not
   at all. Raise the guides question with manager-librarian.
3. (c): enter nothing about the bench. Write a gap for the read-only first
   run. If the vendor's macro documentation is to be cited, go to it.
4. Read-only: name any card the new rows would change, at its pin.

## CONTRACT

- No values of registered observables. Ports and addresses are identifiers;
  the port enters only where a claim needs it.
- Not a safety value. Firewall settings are the person's and are not
  knowledge to be written into the envelope by anyone else.

## CONSTRAINTS

As 056's. Dead ends go in `failures.jsonl` with `task: 059`.

## REPORT

(a), (b) and (c) each: entered, held or excluded, with the reason. Any gap
written. One sentence: what is not yet on disk.
