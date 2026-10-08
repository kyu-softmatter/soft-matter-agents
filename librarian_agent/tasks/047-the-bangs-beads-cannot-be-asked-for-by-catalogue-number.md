# 047 — the Bangs beads cannot be asked for by catalogue number

status: closed · **verified on disk 2026-10-07** by manager-librarian-20261007-1. Done at `c3e1c84` and published at `6018bd1`. The two single products now carry `catalog_number` (FSFR004, FSFR005) and answer to it. Product lines carry `catalog_numbers_listed`, which is not addressable, and answer to the vendor's line name under `product`: a line is not passed off as one product. The emission and excitation names became the registered ones. Three names were left, and listed: two diameters, which are an open registry collision, and one stock concentration with no registered name. No other seat's card cites the old names. · issued 2026-10-07 by manager-librarian-20261007-1, found
while verifying 042 · **for librarian-20261004-1, after 044 and 045**. No live
question needs the Bangs beads today, so this is the lowest of the three.

## GOAL

042 made the 5 µm Abvigen bottle findable by its catalogue number. The same
defect remains on another product. Eight Bangs entries keep their product
under `identifiers.catalogue_product`. `kb_entry.schema.json` makes
`catalog_number` addressable and not `catalogue_product`, so a card asking
for `FSFR004` gets `absent` while the store holds the bead. Two of the eight
also put the product in a quantity name, `bangs_fsfr004_diameter` and
`bangs_flash_red_emission_wavelength`. That is the registry's first rule,
broken the same way 042 fixed. Registered subject-free forms already exist
for the emission peak and the excitation peak.

At filing: `bangs_flash_red_emission_peak`, `bangs_flash_red_excitation_peak`,
`bangs_flash_red_plain_ps_material`, `bangs_fluorescent_ps_contains_sodium_azide`,
`bangs_fluorescent_ps_stock_concentration`, `bangs_fluorescent_ps_storage`,
`bangs_fsfr004_nominal_diameter`, `bangs_fsfr005_nominal_diameter`.
Re-derive the list.

## CONTRACT

- Do it the way 042 did, and say whether you chose the same mechanism.
  **One catch 042 did not have**: some entries name a product *line*
  (`FSFR001-FSFR007`), not one catalogue number. A range is not a catalogue
  number. Decide how a line is addressed without pretending it is one
  product, and say how.
- Rename the product-bearing quantity names to registered ones where one
  exists. Where none exists, leave the name and list it. Registration waits
  until a question asks for the name.
- Search other seats' cards and envelopes for the old strings, by reading
  only, and report the hits.
- No claim changes and no grade moves. A rename is not a supersede (rule 8).

## CONSTRAINTS

Claim the store's paths by message first. Publish once, with the guides.
Commit under your own row and validate with the uv form. Dead ends go in
`failures.jsonl` naming `task: 047`.

## REPORT

The entries edited and how a single product and a product line are each
addressed. The renames and who cites the old names. The names left as they
are. The commit and `kb_version`. One sentence on what is still not on disk.
