# 066 — enter the formulas the drag calculators name

Written by a design session (root, committing as `design`) on 2026-11-11, on
branch `calculator-skills`. You read this; you do not edit it.

**For a librarian session** (cwd `librarian_agent/`). If you are not a
librarian session, take nothing from this card and report up.

## Why

`contracts/calculations.json` (plan.md §4.5.2.2) is a table of calculators.
A calculator is code that computes one bound before a run. Its formula is
the store's, named in `formula_entries`, and it is never written into the
code.

The pilot row covers one question: the drag of a trapped bead against its
height above the coverslip. It requires five new calculators, and they name
seven entries the store does not hold yet. Until those entries exist, the
calculators abstain, kind `no_input`, naming the entries. This card asks you
to enter them. It is the "find only the values that are needed" the person
asked for, written down as a list.

## The entries the table names

The names are the table's requests. If a different id is right by your
rules, enter it under that id and report the mapping up. The design session
then changes the table, so that no calculator cites a name the store does
not hold.

| id the table names | what it holds | where it is |
|---|---|---|
| `wall_drag_parallel_faxen_series` | The parallel wall correction to Stokes drag, as a series in R/ℓ with ℓ the centre-to-wall distance, and the range where it is accurate to 1 % (ℓ/R ≳ 1.4). A formula entry that keeps no dimension. | Tolić-Nørrelykke et al., Rev. Sci. Instrum. 77, 103101 (2006), Eq. 40 and Appendix D. doi:10.1063/1.2356852, open as arXiv physics/0603037. |
| `stokes_drag_sphere` | γ0 = 6πηR, the bulk drag on a sphere. A derived quantity, unit N·s/m. | A textbook source of your choosing. It is the relation `tracer_diffusivity_expected` already stands on. |
| `video_blur_variance_factor` | The factor by which a finite exposure lowers the measured variance of a trapped bead, as a function of exposure over relaxation time, and the range in which its stated approximation holds. | Wong & Halvorsen, Opt. Express 14, 12517 (2006), Eq. 7 and the Padé form. doi:10.1364/OE.14.012517, open as arXiv physics/0607156. |
| `power_spectrum_fit_relative_error` | The statistical error of the corner frequency and diffusion coefficient fitted from a position power spectrum, as a function of record length. | Berg-Sørensen & Flyvbjerg, Rev. Sci. Instrum. 75, 594 (2004). doi:10.1063/1.1645654. The open copy that was found is a scanned image. If you cannot read the expression, record the gap as `inaccessible` and do not work around it. |
| `effective_focal_shift_oil_objective_into_water` | How far a trapped bead moves per unit of nominal focus travel, trapping in water through an oil objective: 0.808 ± 0.005 at 100x/1.4 oil and 1064 nm. | Deufel & Wang, Biophys. J. 90, 657 (2006). doi:10.1529/biophysj.105.065458, open in PMC. A paper's value about another instrument, so E3 at best. Its conditions must say it is not this instrument's factor. |
| `optical_trap_heating_rate_water_1064nm` | Heating of water at the focus of a 1064 nm trap per watt: 7.7 ± 1.2 K/W and 8.1 ± 2.1 K/W for two silica bead sizes. This is the `sample_heating_rate` the existing heating bound reads. | Peterman, Gittes & Schmidt, Biophys. J. 84, 1308 (2003). doi:10.1016/S0006-3495(03)74946-7. |
| `water_viscosity_temperature_coefficient` | How fast water's viscosity falls with temperature near room temperature. `water_viscosity_293k` states "roughly two percent per kelvin" in its claim, but no entry holds the number. | `src_water_properties`, already in the store, or its primary source. |

## How

- **Under your own rules.** One source at a time, in your ingest order:
  source record, distilled note, entries, index, ingest log. One claim per
  file, with `validity_conditions` written for each.
- **Where to look, not what to enter.** The literature review at
  `docs/drafts/literature_trap_drag_vs_height_above_a_wall.md` tells you where
  each item is. It is a summary, so enter nothing from it. Every entry comes
  from the source itself (rule 5).
- **Read level.** Where the review read only an abstract, read the paper
  before entering.
- **No instrument values from papers.** A paper's number is about that paper's
  instrument. The focal-shift factor and the heating rate are references for
  an order of magnitude here. The axis uses them to say what has to be
  measured.

## Done when

- **Entered or recorded.** Each of the seven is entered, or recorded as a gap
  with its kind and where it was looked for.
- **Store current.** The index is rebuilt and `python contracts/validate.py`
  ends `0 failed`.
- **Reported.** Send a design session the entry ids, and any name you changed.
- **Committed.** Commit under `librarian`, through the tool, on branch
  `calculator-skills`, once the person has said to commit.
