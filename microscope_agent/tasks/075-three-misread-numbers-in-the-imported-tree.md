# 075 — three misread numbers in the imported dino-autofocus tree

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261015-1`, after card 073 lands.** It
touches code files in `microscope_agent/autofocus/`, so
`microscope-office-20261015-2`, translating there under card 074, takes no
file this card names until you report it done. If you are not that seat,
take nothing from this card and report up.

## What the librarian found

Librarian task 052 listed every number in the imported tree: 572 rows, in
`librarian_agent/kb/staging/dino_autofocus_number_inventory.v0.json`
(`314ce381`). The rule for this move is that **a figure in the imported tree
that would act here enters only through the librarian, and binds nothing
until it does.** Three of the figures are misread, and a later caller could
copy them as true:

1. **"605" read as a wavelength.**
   `configs/ti2_*.yaml` `illumination.wavelength` and
   `src/dino_autofocus/engine/backends/mock_world.py` `EMISSION_UM = 0.605`
   treat the path name "605" as a 0.605 µm emission wavelength. The person
   confirmed on 2026-10-15 that 605 is a path name, and the filter is
   FF01-595/31. `mock_world` computes a depth of field from it.
2. **An immersion index from a reseller.** The same configs use
   `n_immersion = 1.518`. The bottle on this bench reads nD 1.5150 at 23 °C
   (store entry `immersion_oil_in_use_label_index_sodium_d_23c`), and 1.518
   is a reseller value the store holds in conflict.
3. **A 12-bit ceiling nobody uses.** `bench_values.CEILING_12BIT = 4095` is
   exported through `focus/__init__` and read by no routine the librarian
   could find. The store's ceiling for Dynamic Range at 100MHz 16bit is
   65535 ADU. A caller that picked the 12-bit constant would misjudge
   clipping by a factor of 16.

## What to do

**Do not replace these with new numbers.** A value that acts here comes
from the store, through a plan, never from a constant in code. For each of
the three:

- **Find every reader.** Report each file and line that reads it, and
  whether that path can reach the instrument or only mock, tests and
  display.
- **Mock, tests or display only:** keep the value, and label it in place
  for what it is: a mock value, not a measurement, with "605" named as a
  path name, not a wavelength, and the store entry that holds the real
  value. Change no behaviour.
- **A path that could reach the instrument:** the value must not be read
  there. Make that path refuse without its value from the plan, the way
  the focus search refuses a gap ceiling. Report it before you change it;
  that change may need its own card.
- **`CEILING_12BIT`:** if nothing reads it, remove its export from
  `focus/__init__` and label the constant as not the camera's ceiling. Keep
  it otherwise, as the record has it.

**And the 37 safety rows.** The librarian listed them under `safety_rows` in
`librarian_agent/kb/sources/src_dino_autofocus_numbers_95eee95.json`: guard
windows, retract heights, pattern ranges and config focus distances, all
ruled the envelope's. **Check that nothing in this repository outside
`microscope_agent/autofocus/` imports or reads any of them.** Add a test in
the tree that fails if `microscope_agent/src/` ever imports from
`dino_autofocus`'s guards or patterns. Watch it fail on a planted import
first, then remove the plant.

## Boundaries

Write inside `microscope_agent/autofocus/` only. No change to
`microscope_agent/src/`, `envelope/` or any limit. Re-run card 072's suite
after; it must stay green. Through the gate, naming each path. Never
`--no-verify`, `--amend` or force.

## What comes back

To this seat, 5 lines at most:

- the commit;
- each number's readers, and whether any reaches the instrument;
- what was labelled or removed;
- the new test, watched failing;
- the suite's counts.
