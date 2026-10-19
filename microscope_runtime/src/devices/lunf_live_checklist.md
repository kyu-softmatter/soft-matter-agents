# The confocal laser: what to check live, and what each device is left in

Card 036, phase A, written by `microscope-20260924-3`. It sits beside
`lunf.py`, the wrapper it checks. Card 018's shape: every line says what is
tested, why, and the store entry it rests on. A line with no entry says so
and names the gap. Gap names written in `this style (proposed)` are proposals:
nothing has registered them.

**Nothing here has been run.** Phase B happens only after the person has
said, in this seat's window, that the bench is this seat's, and only after
the person's limit for these lines is written. In phase B the order is
read-only first, then the eyepiece mapping with the person, then one line.

## 0. Before the bench: what has to be true, and who makes it true

| | what | who | why |
|---|---|---|---|
| 0a | a limit in `envelope/safety.json` that covers the confocal lines, confirmed physically | the person | `optical_power_max` is the trapping laser's dial range and covers none of these lines. `lunf.COVERING_LIMIT` stays `None` until the person names one |
| 0b | the per-line level set **by hand**, at its lowest, before the bench | the person | software never sets power (`lunf_per_line_power_is_not_transmittable`, E3). So the limit in 0a can't be compared against anything the wrapper commands. It is honoured only by the level the person sets |
| 0c | the fiber shutter at the source open, if light is wanted at all | the person | nothing here reaches that shutter (`laser_shutter_on_the_combiner`, E3). The prior project found that only the vendor software opens it, and that this software holds the digital lines exclusively while it runs. Its route was to force-kill that software, and it called the route a workaround. **Whether this lab uses that route is the person's question, not this wrapper's** |
| 0d | the router can reach `lunf.py` | manager / librarian | the registry's `driver` for `laser_combiner` starts with `split:`, which names no file. And `module_for` sends every `read_back: false` channel to `manual.py`. Reported up |
| 0e | the channel row carries the line map and the blanking polarity | librarian | no entry holds them. The prior project's values were ruled **downgrade** (E3, to the store), not code. Gap: `laser_combiner_line_map (proposed)`, `laser_combiner_blanking_polarity (proposed)` |

## 1. Read-only first

**1a. Nothing else holds the lines.** `lunf.preflight()` asks the transport
whether the digital lines are free, and writes nothing. *Why*: in the prior
project the vendor acquisition software held them exclusively while it ran,
and a write from elsewhere failed. The fact itself sits in no entry of the
store; it was ruled downgrade to E3 there. Gap: `acquisition_software_holds_blanking_lines (proposed)`.

**1b. The light path reads back as an integer.** Read the stand's
`light_path_port` state and record the **integer**, not the label. *Why*:
2.1 rule 11 keys eyepiece safety on the integer. Labels in a loaded
configuration stay downgraded until a frame confirms them, and the lab's own
labels have been swapped once. The element is in the device table, and no
entry says which state goes where.

**1c. The disk's state can be read, or it can't.** Look for a disk-speed or
motor property in the loaded configuration. *Why*:
`csuw1_disk_speed_exposure_constraint` (E3) says an exposure must be an
integer multiple of the disk period, and that a plan needs the period **from
the device**. The prior project found that Micro-Manager exposes **no**
disk-speed or motor device for this unit (ruled downgrade, E3). If that
holds here, the period has no source and the constraint can't be applied. Gap:
`csuw1_disk_period (proposed)`.

## 2. With the person: which light-path states reach the eyepieces

**Nothing is enabled until this is recorded.** The person sets each
`light_path_port` state in turn and says, **at the eyepieces and by looking,
with no laser on**, whether that state sends the image there. Use the
transmitted lamp, never a laser. Record each state's **integer** with the
answer, as a result for the librarian. `lunf.bind_light_path` takes that
record as `{state_integer: entry_id}`, and a state with no entry counts as
reaching the eyepieces. Rests on: 2.1 rule 11. Gap until recorded:
`light_path_port_states_reaching_eyepieces (proposed)`.

## 3. One line, at the lowest setting

Conditions, all of them: the person told before it goes on; the limit
written (0a); the level set by hand (0b); the approved command list naming
this exact enable; the bench handed over in this window; and the path read
back **at that moment**, logged as `light_path_readback` before the enable.
The wrapper refuses if any one is missing, and the tests prove that a clean
path reading alone never enables.

**3a. Dark, then lit, or the check is void** (ruled transfer from the prior
project's bisection tool). Take a frame with every line blanked, then enable
one line and take a frame. The lit frame must be brighter than the dark one.
**If the lit frame is dark, the check is void, not passed**: the fiber
shutter may be closed, the vendor software may hold the lines, or the level
may be zero. Each of these looks like "nothing happened".

**3b. The two shutters, one at a time** (`laser_shutter_on_the_combiner`, E3;
`csuw1_shutter_gates_confocal_excitation`, E3). Two shutters sit in the
chain: one at the source and one at the unit's entrance. With the line
enabled, close the unit's shutter and confirm the frame goes dark, then open
it again. *Why*: the store records where each shutter sits and what it gates.
Only a frame shows that closing one actually stops the light here. Which
shutter an abort closes is the person's policy, not this checklist's.
Today Micro-Manager refuses to write `CSUW1-Shutter`, so the person moves it.

**3c. The disk is spinning before any frame is trusted**
(`csuw1_disk_speed_exposure_constraint`, E3). A stopped disk gives a
**stationary pinhole grid at full brightness**, and nothing looks wrong
until you look at the texture. Check a frame's power spectrum: take the lit
frame minus the dark one, on a central crop, and compare the off-centre peak
with the median. A low ratio means smooth illumination; a high ratio means a
grid. Ruled transfer as a method. The prior thresholds were ruled
**discard**: nobody here chose them. Their two measured regimes were ruled
downgrade to E3, as a starting point for choosing thresholds here.

**3d. Exposure is a whole number of disk periods**
(`csuw1_disk_speed_exposure_constraint`, E3). Only once 1c has given a
period. Without one, record the gap and do not claim that stripes are absent.

**3e. Filter turret 1 is not on the multiband cube.** In the prior project,
state 0 held the multiband cube and blocked the confocal path, while states
1-3 were empty (ruled downgrade, E3). Read the turret's **integer** state
back. No entry holds this yet. Gap: `filter_turret_1_blocks_confocal (proposed)`.

**3f. Power is refused, and the refusal holds on the bench**
(`lunf_per_line_power_is_not_transmittable`, E3). Send a power parameter and
confirm the wrapper refuses before anything is written. The unit tests
already show this against the mock; this line repeats it once with the real
transport.

A blinking line is easier to see than a steady one. That was ruled
**downgrade**, E5: a suggestion, not a requirement.

## 4. What each device is left in: closed, and killed

"Leave every device you opened in a stated state" has to cover the process
being **killed**, not only closed. A killed process runs no `finally` and no
`abort`.

| device | closed normally (`abort`) | process killed | grounds |
|---|---|---|---|
| blanking lines | every mapped line written closed, one row per line, `verification: none` | **each line holds the level last written**, so a line that was open **stays open** | a digital line keeping its level after the writing task is gone is inferred from the prior project's blink test, where each write's task was cleared and the light stayed on until the next write. That it survives the **process** dying is unmeasured: E5. Falsifier: kill the process with a line open and see the light go out |
| per-line power | never written | never written: the level stays wherever it was set by hand | `lunf_per_line_power_is_not_transmittable` (E3). The prior record adds that the level holds whatever was last written, with no read-back |
| fiber shutter at the source | **not reachable**; left as found | **not reachable**; left as found. In the prior project it **stayed open when its controlling program was force-killed**: no link-drop watchdog | prior measurement, ruled downgrade to E3. Only the vendor software's clean close shut it there |
| confocal unit shutter | not written by this wrapper; Micro-Manager refuses it today | unchanged: a mechanical shutter keeps its position | `csuw1_shutter_gates_confocal_excitation` (E3). **The person closes it** |
| spinning disk | not touched: nothing here starts or stops it | not touched | Micro-Manager exposes no disk-speed device (prior, E3). What `disk_survives_kill.py` would have shown is below |

**So a killed process can leave a laser line unblanked, with the fiber
shutter open and nothing in software able to close either.** The barrier
left is the confocal unit's shutter, and the person moves it by hand. A
release after a kill is therefore the person's: close the unit's shutter,
then the fiber shutter by the vendor's own route.

## 5. What `disk_survives_kill.py` establishes

**Nothing measured.** It was committed with the prior project's last
confocal findings and never run: no result, report or later commit exists in
that repository. The script asks one question: does force-killing the vendor
acquisition software stop the spinning disk? After such a kill, the prior
project's confocal frames came back as a stationary pinhole grid at full
brightness. Its record calls "the kill stopped the disk" the most likely
reading, and says the alternative (the disk was never started) is not
excluded. Ruled downgrade, E5, with the kill-then-watch test as falsifier.

Two things carry into a release anyway:

- **A state can outlive its controller on this combiner**. That is measured
  for the fiber shutter (E3), which is why the table above does not assume a
  killed process leaves anything dark.
- **The disk's state is not ours to leave in any state.** Nothing here
  controls it, so a release names it as "as the person or the vendor
  software left it". And every confocal frame is checked for the grid (3c)
  rather than trusted because it is bright.

## What only the person can answer

1. **Which limit in the safety file covers the confocal lines, and at what
   value?** It has to be confirmed physically, the way the trapping laser's
   was.
2. **How will the fiber shutter be opened and the per-line level set?** Only
   the vendor software reaches either. The prior route was to force-kill
   that software to free the lines, which leaves the shutter open with
   nothing owning it.
3. **Which light-path states send the image to the eyepieces?** This is
   established at the bench with the lamp, by integer, before any laser line.
