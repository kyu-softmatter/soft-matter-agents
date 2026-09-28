# 039 — ten HOOMD papers, distilled into the store

status: **open** · issued 2026-09-28 by
manager-librarian-kyuhwan-macbook-20260925-1, at the person's request in that
seat's own window: *"these are major papers that did research with HOOMD --
distil them well and keep them"* · **assigned to the librarian session the
person points at this file**

## GOAL

The simulation agent designs and runs HOOMD experiments. When it plans one,
the question "has this regime been simulated, how, and what was found" should
come back from the store as graded claims with their conditions -- not from a
model's memory of the literature, which is E6 and enters nothing. The person
has chosen these ten as the reference works for that. Distillation here means
what `plan.md` means by it: **decomposition into claims**, not summary.

## TASK

The PDFs are on this MacBook, in `~/Downloads/`, named exactly:

| # | file |
|---|---|
| 1 | `Fang et al. 2020 - Two-step crystallization and solid-solid transitions in binary colloidal mixtures (1).pdf` |
| 2 | `Frechette et al. 2025 - Active-noise-induced dynamic clustering of passive colloidal particles (1).pdf` |
| 3 | `He et al. 2020 - Colloidal diamond (1).pdf` |
| 4 | `Hofmann et al. 2026 - A general model for frictional contacts in colloidal systems (1).pdf` |
| 5 | `Kelidou et al. 2024 - Active string fluids and gels formed by dipolar active Brownian particles in 3D (1).pdf` |
| 6 | `Kim et al. 2026 - Self-assembly of colloidal diamond via the depletion interaction (1).pdf` |
| 7 | `Lee and Park 2026 - Microscopic origins of second normal stress difference in a colloidal gel under startup shear (1).pdf` |
| 8 | `Pretti et al. 2019 - Size-dependent thermodynamic structural selection in colloidal crystallization (1).pdf` |
| 9 | `Shee et al. 2025 - Tuning steady shear rheology through active dopants (1).pdf` |
| 10 | `Vyas et al. 2026 - Two-dimensional non-equilibrium melting of charged colloids (1).pdf` |

Several are over 20 pages or 20 MB; read them in page ranges, and read the
supplementary methods where the paper has them in the same file -- that is
usually where the simulation is actually specified. If a file is missing, ask
the person; do not look for another copy online without saying so.

For **each paper**, three layers, as the store already does them:

1. **One source** in `kb/sources/`, in the form of
   `src_sultanova_2009_optical_polymers.json`: full citation, DOI, and
   **publication status checked, not assumed** -- a 2026 paper may be a
   preprint, and `grade_tag` is `preprint` until it is peer-reviewed. Add
   `method_as_stated`: what was simulated and how, as the paper states it --
   HOOMD version, integrator, pair potentials and their parameters, time step,
   thermostat or ensemble, particle count, box and boundary conditions, run
   length. Add `not_entered` for what you read and chose not to file, and why.
2. **One distilled note** in `kb/distilled/`, in the house form of
   `water_viscosity.md` -- the claim, under what conditions, what it does not
   cover, the limit worth remembering -- plus a short **how it was simulated**
   section, since that recipe is most of what the simulation agent will reuse.
3. **Entries** in `kb/entries/`, one claim per file, for what a simulation
   plan here would actually query: the parameters that define a regime (a
   packing fraction, a Péclet number, a size ratio, an interaction strength),
   stated transition or boundary locations, and method choices the paper
   reports as mattering. The distilled note carries the rest. Ten papers can
   produce hundreds of entries; **fewer entries that each hold is the right
   outcome**, and a paper that yields only a source and a note is acceptable.

## CONTRACT

- **A simulation result is a claim about a model, not about colloids.** Every
  entry from a simulation says in its claim and its `validity_conditions` which
  model it holds in -- the potential, the dimensionality, the ensemble. Where a
  paper has both experiment and simulation (at least paper 3 does), file them
  as separate entries and say which each is.
- **Numbers only from text and tables.** A value read off a rendered figure by
  a model is E6 and enters nothing -- that is the rule the Sultanova source
  already states. If a result exists only as a curve, the note may describe it
  in words and the entry does not get the number.
- **Everything is E3**, `source: literature:<ref>`, `grade_tag`
  `peer_reviewed` or `preprint` as checked.
- **Reduced units stay reduced.** Most of these papers work in units of the
  particle diameter, kT and the Brownian time. Do not convert them to SI with a
  diameter the paper did not state; a number whose unit is not in
  `contracts/units.json` is a request to this seat, not a new spelling.
- **An unregistered quantity or unit is an ordering, not a refusal.** List
  each one you needed in the report, with the entry waiting on it, and this
  seat registers it. Do not invent a spelling to get past the validator.
- **HOOMD versions differ.** Papers from 2019 to 2026 were written against
  older releases than the HOOMD 7.2.0 this repository pins. Record the version as stated; do not
  translate a script into today's API inside the store.

## CONSTRAINTS

- **Nothing copyrighted enters the repository.** No PDF, no figure, no passage
  of text -- identifier, stated conditions and numbers only, as every existing
  literature source does. The PDFs stay where they are.
- **Not while a fan-out is pinned.** These move `kb_version`. Before
  committing, confirm with the simulation and microscope execution sessions
  that nothing is in flight; then publish once, at the end, not per paper.
- Commit **per paper**, so a paper that does not survive checking is local.
  Name files, never `librarian_agent/`. Run `git var GIT_COMMITTER_IDENT`
  first -- this working copy pins another seat as committer -- and use the
  environment-variable form with your own seat. Write the message to a file
  and use `git commit -F`.
- Dead ends -- a claim you tried to file and could not -- go in
  `librarian_agent/failures.jsonl` naming `task: 039`.

## REPORT

Per paper: the commit, and how many sources, notes and entries it added. The
list of unregistered quantities and units, each with the entry waiting on it.
The `kb_version` after the publish. And the one sentence: what is not yet on
disk.
