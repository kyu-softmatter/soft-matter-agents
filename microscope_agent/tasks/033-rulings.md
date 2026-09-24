# 033 — rulings on what was used from `C:\agentic_microscope`

Written by `manager-microscope-20260924-1`. **The rulings are
`microscope-20260924-1`'s**, reported up on 2026-09-24 and written here
because that seat's deny list covers `tasks/**`. The hand is this seat's; the
judgement is not. The first four lines are the ones card 033 §3 expected,
which the seat confirmed; the rest are the seat's own.

```
downgrade | camera serial-to-index mapping (header, 2026-09-03)   | E3 at best; re-read here | 10.3 rule 1
downgrade | LightEngine line names and 0-1000 scale (header)       | re-read off the device   | 10.3 rule 1
drop      | PixelSize block                                         | the store holds it at E2; P14
drop      | FocusDirection ZDrive note                              | safety content; 10.3 rule 4, and the store has it
drop      | LaserLine config group                                  | setConfig is refused; inert today
drop      | Core AutoShutter=1                                      | overridden to 0 as the first call after the load
drop      | header's Aura error-573 diagnosis                       | not used; Aura is never commanded
drop      | "Tweez GUI can hold Kinetix_blue" (header)              | untested there, not used
used      | the configuration file as a load artifact               | loaded in place as the person's choice, not transplanted | 10.2.1, person's word
used      | Startup preset LappMainBranch1 State=1                  | the person's decision "accept it"; logged as a load-time command, read back after
```

## Two lines are not in the three-way form, and that is noted, not changed

The seat reported the configuration file as **`transfer`** with **"no
slot"**, and the Startup preset as **`accepted`**. The standing rule is that
a transfer names the A1–A7 slot it lands in, and **an item that cannot name
a slot is dropped**. Read literally, the first line rules itself a drop.

**Neither item crosses into this project's design.** The file is loaded
where it sits, as the person's choice for one run, and nothing from it is
rearranged into an axis, a module or a constant. The three-way ruling is for
what gets carried across, and this is used in place. So both are written
above as **`used`**, a fourth word, with the seat's reasons kept word for
word.

**Whether `used` belongs in the vocabulary is the seat's call and then
architecture's**, not this seat's. If the seat means `transfer`, it must name
a slot. If it means something the three words do not cover, that is a gap in
the form, and it should be raised rather than absorbed. Until then, **count
these two as neither transfers nor drops.** The totals: 2 downgrades, 6
drops, 2 used in place, 0 transfers.
