# 066 — the source records the drag skills pin

Written by a design session (root, committing as `design`) on 2026-11-11, on
branch `calculator-runner`. You read this; you do not edit it. It replaces the
card of the same number on branch `calculator-skills`.

**For a librarian session** (cwd `librarian_agent/`). If you are not a
librarian session, take nothing from this card and report up.

## Why

`contracts/skills.json` (plan.md §4.5.2.2) declares skills. A skill is code
that computes one bound, and a session runs it only through a dispatcher.
A skill is self-contained, and it is proven against its source by worked
cases. **Your entry is the source record.** The skill's manifest pins it by
the hash of the entry file as committed, and the commit gate compares that
hash. If you later change an entry, the commit says so, and the skill is
re-read against it.

The pilot question is the drag of a trapped bead against its height above
the coverslip. Its six planned skills name the entries below. Until those
entries exist, the skills cannot land: a skill lands only with a case worked
from its source.

## The entries the table names

The names are the table's requests. If a different id is right by your
rules, enter it under that id and report the mapping up. A design session
then changes the table.

| id the table names | what the skill needs from it | where it is |
|---|---|---|
| `wall_drag_parallel_faxen_series` | The parallel wall correction to Stokes drag, as a series in radius over centre height, with the bulk drag it multiplies. **As a separate number**, the centre-height-to-radius ratio above which the source states the series is accurate, and to what accuracy. | Tolić-Nørrelykke et al., Rev. Sci. Instrum. 77, 103101 (2006), Eq. 39, Eq. 40 and Appendix D. doi:10.1063/1.2356852, open as arXiv physics/0603037. |
| `video_blur_variance_factor` | The factor by which a finite exposure lowers the measured variance of a trapped bead, as a function of exposure over relaxation time. **As a separate number**, the ratio up to which the source states its approximation holds. | Wong & Halvorsen, Opt. Express 14, 12517 (2006), Eq. 7 and the Padé form. doi:10.1364/OE.14.012517, open as arXiv physics/0607156. |
| `power_spectrum_fit_relative_error` | The statistical error of the diffusion coefficient fitted from a position power spectrum, as a function of record length and corner frequency. | Berg-Sørensen & Flyvbjerg, Rev. Sci. Instrum. 75, 594 (2004). doi:10.1063/1.1645654. The open copy that was found is a scanned image. If you cannot read the expression, record the gap as `inaccessible` and do not work around it. |
| `effective_focal_shift_oil_objective_into_water` | The definition of the effective focal shift, and a paper's value for one oil objective (0.808 ± 0.005 at 100x/1.4, 1064 nm). | The definition: Neuman, Abbondanzieri & Block, Opt. Lett. 30, 1318 (2005), doi:10.1364/OL.30.001318. The value: Deufel & Wang, Biophys. J. 90, 657 (2006), doi:10.1529/biophysj.105.065458. A paper's value is about another instrument, so E3 at best, and its conditions must say it is not this instrument's factor. |

Two more entries serve the legacy heating bound, not a skill:

| id | what it holds | where it is |
|---|---|---|
| `optical_trap_heating_rate_water_1064nm` | Heating of water at the focus of a 1064 nm trap per watt: 7.7 ± 1.2 K/W and 8.1 ± 2.1 K/W for two silica bead sizes. | Peterman, Gittes & Schmidt, Biophys. J. 84, 1308 (2003). doi:10.1016/S0006-3495(03)74946-7. |
| `water_viscosity_temperature_coefficient` | How fast water's viscosity falls with temperature near room temperature. `water_viscosity_293k` states it in prose, but no entry holds the number. | `src_water_properties`, already in the store, or its primary source. |

## What each formula entry must carry, beyond a normal entry

A skill is proven by cases, and a case needs numbers from the source. For
each formula entry:

- **The locus.** The equation number, table or figure, so a case's `worked`
  text can point at it.
- **At least one worked value from the source, where the source gives one.**
  This is an input set with the result the paper states: a table row, a
  quoted check value, or a limiting value the text gives. Record it with its
  locus.
  - If the source gives no worked value, say so in the entry.
  - The microscope session then writes a case from a limit the formula itself
    fixes, and marks any other case `not_run`.
- **A source's judgement as its own number.** The accuracy the series is
  stated for and the ratio it holds above are a choice the source made. They
  are not a law. Enter them as separate numbers, so the skill takes them as
  inputs.

## How

- **Under your own rules.** One source at a time, in your ingest order:
  source record, distilled note, entries, index, ingest log. One claim per
  file, with `validity_conditions` written for each.
- **Where to look, not what to enter.** The literature review at
  `docs/drafts/literature_trap_drag_vs_height_above_a_wall.md` tells you
  where each item is. It is a summary, so enter nothing from it. Where it
  read only an abstract, read the paper.
- **After an entry is committed, it is pinned.** Tell a design session the
  entry ids and the commit. The design session records each file's hash in
  the manifest. From then on, a change to that entry shows at commit as a
  check 99 failure until the skill is re-read against it. That is intended.
  Change an entry when it is wrong, and say so.

## Done when

- **Entered or recorded.** Each of the six is entered, or recorded as a gap
  with its kind and where it was looked for.
- **Store current.** The index is rebuilt and `python contracts/validate.py`
  ends `0 failed`.
- **Reported.** Send a design session the entry ids, the commit, and any
  name you changed.
- **Committed.** Commit under `librarian`, through the tool, on branch
  `calculator-runner`, once the person has said to commit.
