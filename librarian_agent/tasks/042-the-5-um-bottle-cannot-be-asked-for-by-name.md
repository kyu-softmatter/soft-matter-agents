# 042 — the 5 um bottle cannot be asked for by its catalogue number

status: closed · **verified on disk 2026-10-07** by manager-librarian-20261007-1, from librarian-20261004-1's report of the same day. Done at `75b5753` and published at `d6f892d`, `kbv-1f5ae4042d26`, both by librarian-kyuhwan-macbook-20260930-1. None of the nine entries keeps `catalogue_product`, nine entries carry `catalog_number: AFR-0500-COOH`, and none uses the four product-bearing quantity names this task named. **Two leftovers, neither a miss**: `abvigen_product_particle_density` (`tracer_particle_density`) and `abvigen_product_stock_concentration` (`tracer_stock_concentration`) still carry the product in their quantity names, which this task's contract said to leave until a question asks for them. And eight Bangs entries, a different product outside this task, still keep the product under `identifiers.catalogue_product`, so they cannot be asked for by catalogue number. That second one is the same defect as this task's and has no task yet. · issued 2026-10-01 by
manager-librarian-kyuhwan-macbook-20260930-1, from what
librarian-kyuhwan-macbook-20260930-1 found while doing 041 · **for
librarian-kyuhwan-macbook-20260930-1, after 040**: no live question needs
the 5 um bottle today

## GOAL

A card asking `observable=AFR-0500-COOH` gets `absent`, and today's cards did
exactly that. The store does hold the product's type facts. Nine entries keep
the product under `identifiers.catalogue_product`. `kb_entry.schema.json`
lists `catalog_number` as addressable and does not list `catalogue_product`,
so the product is in the store and cannot be found by its own name. The F8801
entries from 041 use `catalog_number` and are found. Make the 5 um entries
findable the same way.

The same entries also put the product into their quantity names:
`abvigen_product_excitation_wavelength`, `_emission_wavelength`,
`_storage_temperature_min` and `_storage_temperature_max`. That breaks the
registry's first rule. The commit that files this task also registers the
subject-free forms: `excitation_peak_wavelength`, `emission_peak_wavelength`,
`storage_temperature_min` and `storage_temperature_max`.
`contracts/quantities.json` records each pair under `open_collisions`. Both
fixes edit the same entries, so they are done once and published once.

## TASK

The nine entries with `catalogue_product`, checked at filing:

- `tracer_particle_density`
- `tracer_storage_conditions`
- `tracer_emission_peak`
- `tracer_particle_material_and_shape`
- `tracer_stock_concentration`
- `tracer_excitation_peak`
- `tracer_number_density_from_diameter`
- `particle_suspension_a_identity`
- `abvigen_published_data_is_unreliable`

Re-derive this list before trusting it.

## CONTRACT

- **Make the product addressable without changing what any entry claims.**
  Whether that means renaming the key, adding `catalog_number` beside it, or
  something else is your call. Say which you chose and why. Measure what
  `observable=AFR-0500-COOH` returns afterwards, through `Store` and not
  `kb_query`, and report it.
- **Rename the four `abvigen_product_*` quantity names to the registered
  ones** wherever they appear as `subject` ids or `numbers[].name`. The other
  four `abvigen_product_*` names (`_diameter`, `_number_density`,
  `_particle_density` and `_stock_concentration`) are not registered. Leave
  them, and list them in the report: whether they get registered is the
  registry's call, made once a question asks for them.
- **Check who cites what you rename.** Before you edit, search the cards and
  envelopes of the other agents for the old strings, by reading only. Report
  the hits. Do not edit those files; they belong to other seats.
- Edit in place or supersede, under the store's own rules for a change that
  does not change the claim. No grade moves. `particle_suspension_a_identity`
  stays E5.
- Once the renames land, the `open_collisions` entry for these pairs can be
  closed. That edit is in `contracts/`, so tell me when your commit is in and
  I will close it.

## CONSTRAINTS

- **This moves `kb_version`.** Check the query log for in-flight pins and
  confirm with the execution seats before you publish. Run the full publish
  steps, guides included.
- Name files, never `librarian_agent/`. Run `git var GIT_COMMITTER_IDENT`
  first. Commit under your own seat with the environment-variable form, and
  pass the message with `git commit -F <file>`. When the validator ends
  `0 failed`, push. That is the person's standing instruction.
- Dead ends go in `librarian_agent/failures.jsonl` naming `task: 042`.

## REPORT

- The entries edited.
- How the product became addressable, and what the query returns now.
- The renames, and who cites the old names.
- The four names left as they are.
- The commit and the publish's `kb_version`.
- One sentence on what is still not on disk.
