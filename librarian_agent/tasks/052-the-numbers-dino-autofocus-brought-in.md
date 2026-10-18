# 052 — every number dino-autofocus brought in, entered, named as a gap, or ruled out

status: closed · **verified on disk 2026-10-15** by manager-librarian-20261007-1. librarian-20261007-1 committed the inventory at `314ce381` and pushed it. No entry changed, so the store stays at `kbv-7042c348d4b1`. There are 572 rows in `kb/staging/dino_autofocus_number_inventory.v0.json`: 101 agree with the store, 22 conflict with it (kept), 16 are gaps citing the answer sheet, and 0 entered. The rest are ruled out: 111 no question needs, 98 simulation parameters, 58 method choices, 58 not knowledge, **37 safety, all the envelope's**, 31 template examples, 20 configuration settings, 18 with no traceable origin, 1 E6 (the ~97% synthetic score) and 1 duplicate. The rulings and the safety list are in `kb/sources/src_dino_autofocus_numbers_95eee95.json`. Findings for the microscope seats, relayed: the imported `configs/ti2_*.yaml` and `mock_world.py` treat the path name 605 as a 0.605 µm emission wavelength and use n = 1.518 for the oil. `bench_values.CEILING_12BIT` = 4095 is exported but read by no routine. · issued 2026-10-15 by manager-librarian-20261007-1, on
architecture-20261003-1's request after the import. The person decided on
2026-10-15 to move all of dino-autofocus here and freeze it there.
**Dated after the import commit `8f94789`** (microscope-office-20261015-1,
a subtree merge of dino `main` `95eee95` into `microscope_agent/autofocus/`,
531 files, card 071) · **for librarian-20261007-1, after the 043/046/051
publish**

## GOAL

The code moved whole, and **the ruling condition applies to numbers and
safety values only**. So every number that dino-autofocus carries in code,
configuration or records is now inside this repository with no grade on
it. Each one ends as exactly one of these: a graded store entry, an entry
that already exists (agreeing or in conflict), a named gap, or ruled out
with its reason. A number nobody has ruled reads as knowledge to the next
seat that opens the file. That is the failure this task prevents.

## WHERE TO LOOK, at `95eee95` as imported

Re-derive the list before trusting it. Cite every number as
`microscope_agent/autofocus/<path>:<line>` at `8f94789`.

- `src/dino_autofocus/bench_values.py`: about 14 module constants. Its own
  docstring says each is "unmeasured provisional" unless its comment says
  otherwise, and maps them to dino's question cards L-031..L-033, L-057,
  L-077..L-089.
- `configs/*.yaml`: one per objective (`ti2_{4x,10x,20x,40x,60x,100x}`),
  plus `kinetix_100x_oil.yaml` and `lab_template.yaml`.
- `configs/micromanager/*.cfg`: two Micro-Manager configurations. Pixel-size
  presets in a configuration are that configuration's, not a measurement.
  This is the file whose comment says only the 20x is measured, which is now
  in conflict under 051.
- `docs/runs/`: the 2026-09-30 substrate scan, the 2026-10-02 bench
  properties, and the 2026-10-15 bench to-do. These are dino's own run
  records.
- any other module-level constant that a focus or map routine reads
  (`live.py` and `backbone.py` each have at least one).

**Not in scope, and not entered:**
- `src/dino_autofocus/agents/mock_data/` (moved 2026-10-17 with the console,
  to `console/src/sma_console/agents/mock_data/` at `9267874d`, byte-identical;
  every citation here is pinned at `8f94789`, so it still resolves and is
  left pinned): copies of this repository's own
  cards, used as test fixtures. They are not knowledge and are not a source.
- `tests/`
- `models/`: weights.
- `web/`
- the nested `microscope_agent/autofocus/microscope_agent/`: the flat core
  files dino mirrored. Their originals here are `microscope_agent/src/focus_*`,
  and they carry no numbers by design.

## HOW EACH NUMBER IS RULED

Rule each one under 10.2.1, naming its place and its 10.3 rule. Record the
rulings and the discards in `kb/sources/src_dino_autofocus_*` records, the
way the 17 definitions went in on 2026-10-04.

- **Already in the store.** Cite the entry, and say whether dino's value
  agrees. A disagreement is a conflict and is kept (rule 7). The answer
  sheet (`kb/staging/dino_autofocus_first_questions.v0.json`) already ruled
  dino's first 20 cards. Keep those rulings, and cite them rather than
  re-rule them.
- **A measurement dino recorded.** It enters as
  `prior_run:dino-autofocus@95eee95`, **at E3 at most**. That holds even
  when it was taken on this same stand, because a run recorded in another
  repository is not a run of this system.
- **A vendor or literature figure quoted in dino.** Trace it to the
  document itself and enter it as `spec:` or `literature:`, never as
  dino's. If the trail ends, it does not enter, and the gap says
  `unqualified_source`.
- **A method choice or tuning threshold** (the frame rules, peak criteria,
  the thresholds dino calls provisional): not knowledge. It does not enter.
  List it as a plan's choice, as the answer sheet did for L-077..L-089.
- **A safety value or limit: never crosses.** The focus Z limits stay the
  person's envelope keys. A clearance, an approach margin or a stage limit
  is listed and ruled out, with "safety: the envelope's" as the reason.
- **The DINO model's ~97% on synthetic data, and any other model score:
  E6.** A model's performance on synthetic data is not a measurement of
  this instrument. It does not enter. List it, so nobody quotes it as one.
- **A number with no traceable origin** does not enter. Say so.

## OUTPUT

One table in `kb/staging/dino_autofocus_number_inventory.v0.json`, one row
per number: path:line at `8f94789`, name, value, unit, ruling, and the
entry id or the reason. Then the entries the rulings call for, and one
publish. Report counts by ruling, and every row that touches a safety
value.

## CONSTRAINTS

- Claim the store's paths by message if another librarian seat is live.
  Write only in `librarian_agent/`. The imported tree is read only to you.
- Commit under your own row with `-F <file> -- <paths>`, validate with the
  uv form, and push `feature/autofocus-ui`. Dead ends go in
  `failures.jsonl` naming `task: 052`.

## REPORT

Counts per ruling. The safety rows. The entries added or found in
conflict. The commit and `kb_version`. One sentence on what is still not on
disk.
