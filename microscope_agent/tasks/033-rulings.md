# 033 — rulings on what was used from `C:\agentic_microscope`

Written by `manager-microscope-20260924-1`. **The rulings are
`microscope-20260924-1`'s**, reported up on 2026-09-24 and written here
because that seat's deny list covers `tasks/**`. The hand is this seat's; the
judgement is not.

**Re-ruled after the run, in architecture's terms** (`plan.md` 10.2.1 at
`32e2263`): **there is no fourth word.** An artifact loaded in place still
crosses, so it is ruled piece by piece. The first version of this file
recorded two items as `used`, and that word is withdrawn.

```
transfer  | single_cam_red_noDMD_nocom10.cfg, as the run's loaded configuration | placed by path and sha256 8184073e31e1a7a6..., never copied into the tree | 10.2.1
downgrade | its labels (device, state and preset names)                   | until a frame confirms what each opens | 10.3 rule 1
discard   | its figures, as a source (the PixelSize block, 20x at 0.32373 um) | the store holds pixel size at E2; frame metadata carries the file's figure and is not a source | P14
downgrade | camera serial-to-index mapping (header, 2026-09-03)             | E3 at best; re-read here | 10.3 rule 1
downgrade | Aura line names and 0-1000 scale (header)                      | re-read off the device | 10.3 rule 1
discard   | FocusDirection ZDrive note                                     | safety content; 10.3 rule 4, and the store has it
discard   | LaserLine config group                                         | setConfig is refused; inert today
discard   | Core AutoShutter=1                                             | overridden to 0 as the first call after the load
discard   | header's Aura error-573 diagnosis                              | not used
discard   | "Tweez GUI can hold Kinetix_blue" (header)                     | untested there, not used
```

**Not ruled, because it is not an item that crossed:** the Startup preset,
`LappMainBranch1 State=1`. It is the person's decision (`02d269b`,
*"accept it, load the file as chosen"*), recorded as one, and logged as a
load-time command with its state read back. **Note that it asserts the
unconfirmed Lapp-branch mapping on every load.**

## What the run confirmed, and what it did not

- **Labels, partly confirmed by read-back.** `Nosepiece` read state 2,
  `3-Plan Apo LmbdD0.8 20x`, matching the person's declaration.
  `LappMainBranch1` read 1 (`mirror_in`), matching the preset. **They stay
  downgraded:** a read-back shows the label and the state agree, not what
  the state physically opens
- **Camera serial read**: `Kinetix_red`, PVCAM `Camera-2`, reports
  `A24M723015`, which the header calls red. **Not yet compared with the
  store's `camera_bodies_are_told_apart_by_serial`.** That needs an issued
  caller_id
- **Aura line names read off the device**: `UV CYAN GREEN RED NIR`, with the
  intensity upper limit at 1000 and `100` read back as `100`. That agrees
  with the header, and the reading, not the header, is what the run used
- **The pixel-size stamp read 0.0 at load**, and was not used either way

Totals: 1 transfer, 3 downgrades, 6 discards. The Startup preset is not
counted.
