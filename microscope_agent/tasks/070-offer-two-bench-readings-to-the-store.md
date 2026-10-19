# 070 — offer two bench readings to the store

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261007-1`**, or to whichever microscope seat on the
Office computer the person seats next; `contracts/seats.json` names it. If you
are neither, take nothing from this card and report up.


**Done (closed 2026-10-19).** `microscope-office-20261015-2` took this card under its "whichever microscope seat on the Office computer" clause and committed `findings/microscope-office-20261015-2-20261015.json` at `aa7f0005`, with both items `for_store: true`. The librarian entered `kinetix22_saturates_at_65535_adu_dynamic_range_100mhz_16bit`, `kinetix22_both_bodies_saturate_alike_per_the_person` and `pfs_reports_focus_maintenance_status_and_range_in_three_states` at `62108cef`. The person's go (intake `077a99a2`) is satisfied by that, so no second findings file is written. Take nothing more from this card.

## Why

The bench visit of 2026-10-13 was recorded by `microscope-20261013-1` on the
microscope computer, in
`microscope_agent/findings/microscope-20261013-1-20261013.json` (`1104cc6`).
**Every item there says `for_store: false`**, and the librarian reads that
flag as this side's statement of what it offers. So the camera ceiling cannot
enter the store, and every focus-search plan keeps the
`camera_full_scale_count` gap.

**The person decided on 2026-10-15, in manager-microscope's window, that two
of those items go to the store.**

## What to do

**Do not edit that file.** It is `microscope-20261013-1`'s record, and a
record keeps what its writer said. Write your own:
`findings/microscope-<your seat>-20261015.json`, which card 064 lets
`microscope-20261007-1` write. It holds exactly two items, each with
`for_store: true`:

- **`A_camera_saturation`**: 65535 ADU, at Port `Dynamic Range` and
  ReadoutRate `100MHz 16bit`, 1×1 binning, read off the histogram;
- **`A_pfs_readings`**: the focus-hold device's three states, as read back.

**Each one:**

- **cites the original** by path and commit (`1104cc6`), and its item id
  there;
- says **the person read it on 2026-10-13**, and **decided on 2026-10-15**
  that it goes to the store;
- **copies the values exactly** as the original records them, and adds none.

**Which focus-hold reading the envelope uses** as "not engaged" stays the
person's to write in `envelope/safety.json`. This card offers the readings to
the store; it decides nothing about them. The person added on 2026-10-15
that the two "off" codes differ by in range against out of range. Librarian
task 046 records that as the person's statement; quote it if the original
does, and add nothing of your own.

`A_csuw1_shutter` and the other items stay as they are.

## Boundaries

Write only that one findings file. Validate under the interpreter
`CLAUDE.md` names for the Office computer, then `git diff HEAD -- <path>`,
then `git commit -F <file> -- <path>` under your seat. Push with
`git -c credential.helper=manager push origin feature/autofocus-ui`. Never
force, never amend.

## What comes back

To this seat and to manager-librarian, 3 lines: the commit, and the two item
ids as written.
