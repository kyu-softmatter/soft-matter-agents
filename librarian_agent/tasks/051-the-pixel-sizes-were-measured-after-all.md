# 051 — the pixel sizes were measured after all, says the person

status: **done for the 1x rows, the 1.5x question with the person** · **verified on disk 2026-10-15** by manager-librarian-20261007-1. At `b0c5068`, pushed, store `kbv-a3311f82de3e`, not yet published (it rides with 043/046), librarian-20261007-1 made these changes to the five 1x pairs (4x, 10x, 40x, 60x, 100x). Each E2 row lost `refuted_by`. Each `_computed` row lost `refutes`, and its `supersedes` was cleared. Both rows now name each other in `conflict_with`. The E2 rows stay E2 and the `_computed` rows stay E4, and no value moved. The six 1.5x rows stay refuted, each saying that the 2026-10-15 answer did not reach the 1.5x zoom. New source: `src_person_statement_20261015_pixel_sizes_measured`. `src_person_ruling_20260924` gains `withdrawn_by`. L-031 is answered. Read-only, 23 card files cite either row of a pair, and each keeps its pin and the answer it got there. **Open: whether the 1.5x values were measured too.** That has been asked of the person; an answer is a follow-up change. · issued 2026-10-15 by manager-librarian-20261007-1, on the
person's answer to answer-sheet card L-031, given directly in this seat's
window · **for librarian-20261007-1**. It can ride with the 043/046 publish,
or go alone if that publish is far off.

## GOAL

On 2026-09-24 the person ruled that only the 20x at 1x pixel size was
measured and the other eleven were calculated (`src_person_ruling_20260924`).
The store then marked five E2 calibration rows `refuted_by` their E4
`_computed` siblings: `pixel_size_{4x,10x,40x,60x,100x}_zoom_1x`.

**On 2026-10-15 the person withdrew that ruling**, directly in
manager-librarian's window, in answer to L-031. Asked whether all six were
measured at the 2026-09-19 calibration, and why five equal the sensor pitch
over the nominal magnification exactly, the person chose that answer and
said, verbatim: *"2, becuase that is that"*. Read with the question it
answered, that means all six were measured on 2026-09-19, and the five came
out equal to the computed values because that is what was measured.

So **the refutation's only basis is gone.** It stood on the person's
statement, not on an observation, and the same person has now said the
opposite. That is the mismatch this seat named while ruling the oil
indices: in this store a refutation stands on an observation. The pixel-size
refutation never did, and this task corrects it.

## WHAT STILL POINTS THE OTHER WAY

Keep it on record and do not argue it away:

- five of the six values equal 6.5 µm over the nominal magnification
  **exactly**, while the 20x, the one row everyone agrees was measured, reads
  0.32373 against a nominal 0.325;
- a prior-project Micro-Manager configuration, and dino-autofocus's own
  configuration comment, both say only the 20x is a measurement;
- the person's own ruling of 2026-09-24.

Against these stand the calibration record of 2026-09-19 itself (each row's
confirmation that it is a direct measurement), the ruling of 2026-09-21
that they stand and will not be repeated, and now the person's statement of
2026-10-15.

## TASK

1. **Lift the refutation on the five rows, and keep them in conflict.**
   Replace `refuted_by` / `refutes` between each E2 row and its `_computed`
   sibling with `conflict_with` both ways. The conflict is about
   provenance, not value: the two values are identical, so no number moves.
   Rule 8: nothing is deleted. Each entry's conditions gain one sentence
   saying when and why the relation changed, citing this task.
2. **Record the person's statement** of 2026-10-15 as its own source record,
   with the question it answered and the verbatim reply. Both of the
   person's statements stay on record, 2026-09-24 and 2026-10-15, with the
   later one named as withdrawing the earlier.
3. **The E2 rows stay E2** (`calibration:`), and the `_computed` rows stay
   E4. Do not re-grade either. A plan citing either gets the same value; the
   conflict tells it the grade is disputed. The `_computed` rows did not
   become wrong: they are a correct calculation that happens to agree.
4. **Say what would settle it**: a fresh measurement of one of the five on
   this bench (10x is the cheapest). If it reads 0.650 within the precision
   a 20x-style measurement gives, the measurement claim gains an observation.
   If it reads like 20x, off nominal by a few tenths of a per cent, the
   exact equality was a calculation. This is the person's to schedule; you
   only write it down.
5. Update L-031 on the answer sheet to answered, citing this task.
6. Read-only: list the cards that cite either row of each pair at their
   pins, for me to relay. **Do not edit them.** Since 048's fix, a running
   server marks the E2 rows `refuted`. After this change it will not. That
   is a changed answer under a new `kb_version`, which is allowed; the old
   pins keep their old answers.

## RULINGS ON SCOPE (2026-10-15, after librarian-20261007-1 asked)

- **`supersedes` is cleared too.** On the five 1x `_computed` entries, set
  `supersedes` to null. A supersede records that a claim was replaced. On the
  person's word it was not, so leaving it would keep the refutation under
  another name. In each, write one sentence: it was set on 2026-09-24 on the
  person's ruling and cleared on 2026-10-15 when that ruling was withdrawn.
  It was set because the schema had no backward mark, and since 048's
  `status` it has one.
- **The six 1.5x rows stay refuted for now.** The 2026-09-24 ruling refuted
  eleven rows, five at 1x and six at 1.5x. L-031 asked about the objectives,
  and the answer did not address the 1.5x zoom. Each 1.5x E2 value is its
  1x value over 1.5, which an independent measurement rarely gives. So lift
  only the five 1x pairs. Each 1.5x row gains one sentence: the 2026-10-15
  answer did not address the 1.5x zoom. The question has been put to the
  person, and an answer that comes later is a follow-up change.

## CONTRACT

- No value changes. The grade labels stay as they are. Only the relation
  changes, and the record of why.
- Not a safety value, and nothing here touches the envelope.

## CONSTRAINTS

Claim the store's paths if another librarian seat is live. Publish with the
guides. Commit under your own row with `-F <file> -- <paths>`, validate with
the uv form, and push `feature/autofocus-ui`. Dead ends go in
`failures.jsonl` naming `task: 051`.

## REPORT

The five pairs and their new relation. The source record for the person's
statement. The cards citing either row. The commit and `kb_version`. One
sentence on what is still not on disk.
