# Verifying 017 off disk, not off the commit message

Task 017 asks for an entry-by-entry statement of where each entry landed after
the 015 reversal. The seat that executed the reversal (`ed373e0`) wrote its
account from memory of what it had just done and then said so, and asked for
this pass instead. Everything below was read off the tree at `8a9686b` and
re-read at `77882da`; where a count appears it came from a run, and the run is
quoted.

Read by: seat librarian-3, 2026-09-19.

## What 8646426 actually touched, which is not what 017 says

017 opens with "`8646426` touched nine entries and added two", and calls the
set "the eleven". `git show --name-status 8646426 -- librarian_agent/kb/entries`
says **seven modified and two added, nine files**. Nine plus two is where
eleven came from, and the nine already includes the two.

This is not pedantry about a task file. The number is the one thing in 017 that
cannot be checked against anything, and it is the shape `CLAUDE.md` names twice:
read every count off the run, never off prose. Three counts in the repository's
own instructions were wrong within a day of being written. This is the fourth.

The set that the reversal actually reaches is **sixteen entries across two
commits**: `8646426` (7 modified + 2 added) and `ed373e0` (15 modified + 1
added, the fifteen being the same seven plus the eight refractive indices).

## Entry by entry

### ① The identification — E5, and it is not an entry

| | |
|---|---|
| where it lives | `kb/staging/samples.v0.json`, `instances[0].identified_as` |
| grade | E5, `source: assumed:person_ruling_20260919` |
| checked by | **nothing** |

`assumed:` does derive E5 in `SOURCE_GRADE`, so the grade written there is the
right one. But check 43 iterates `kb/entries/` and a staging table is not an
entry, so no check reads this grade, and `kb_index.py` does not index the file,
so no `kb_version` covers it.

**The consequence is not bookkeeping.** 017 says everything in ② hangs off this
grade. A card that applies an Abvigen fact to the bench has to cite the link to
inherit E5 — and check 54 resolves a `kb:` basis against the citing card's
`kb_refs`, which resolve against entries. `kb/staging/README.md` states the same
thing from the other side: nothing cites a staging file with a `kb:` source,
because a `kb:` citation has to resolve to an entry with a grade.

So today a card applying the material or the density to this bottle can cite the
E3 type entry and nothing else. **The E5 exists and is uncitable.** The load
that 017 put on it cannot actually be carried until it is an entry.

It can be one now: an entry needs no `subject` (12 on disk carry none), and
`assumed:` passes check 43 unassisted. What it needs is a `kb_version` move,
which is why this pass did not make it — see the closing note.

### ② Material, diameter, and the eight refractive indices

| entry | grade on disk | verdict |
|---|---|---|
| `tracer_particle_material_and_shape` | E3 `vendor_spec` | restored, type-level |
| `polystyrene_refractive_index_*` ×8 | E3 `peer_reviewed` | untouched in substance |
| the diameter | **no entry exists** | see below |

The eight came through 015 untouched, exactly as 015's report asked: `git show
8646426` does not name one of them. `ed373e0` then touched all eight, and **only
to change `dimensionless` to `1`** — the units fix from 016 part two, not the
reversal. Both statements are true at once and the second is the one a reader
would get wrong: they moved, and nothing about what they claim moved.

**The diameter is the item 017's constraint is now wrong about.** 017 says the
5 µm "gets weak support, not resolution" and that the two-versus-five
disagreement is still live. The person measured it at 19:41 (`48f8239`,
`plan.md` §11-13): 5 µm, CV within 2%, `calibration:` E2. That is above the E3 a
lot number would have given and it does not run through the E5 link at all,
because a measurement is made on the instance. The samples table caught this and
recorded its own correction in place; 017 was written after the measurement and
still carries the old constraint.

**And the entry still does not exist.** The fact lives in `plan.md`, which is a
P14 inversion — knowledge in the architecture seat's design document. It is
blocked on `validity`: the schema requires a non-empty condition range from any
`calibration:` source, and what this measurement is conditioned on is an
instance, which has no interval shape. That is the fourth instance of one
structural limit, after `at the generator` (`trapping_laser_identity`), `the
room` (`lab_ambient_temperature`) and `this cube, this wheel, this light engine`
(`particles_show_on_the_green_605_path`). The third of those says out loud that
it was raised as one problem rather than three; it is now four.

### ③ The two peaks — recorded as contested, which is what 017 said not to do

017: "Keep them (rule 8) and record them as **refuted**, not as contested."

On disk both entries carry `conflict_with: ["particles_show_on_the_green_605_path"]`
and that entry names both back. Run against the store at `kbv-0d3ece9d6234`:

```
kb_conflicts -> ['particles_show_on_the_green_605_path', 'tracer_emission_peak']   {E2, E3}
                ['particles_show_on_the_green_605_path', 'tracer_excitation_peak'] {E2, E3}
   note: "both sides of a conflict are kept and neither is merged away (4.3 rule 6);
          which one applies is decided by the conditions, by the caller"
```

The service tells the caller to pick. That is the definition of contested, and
017 ruled these are not contested.

The word *disproved* is on disk — in `validity_conditions`, as prose, inside a
4090-character field. **The store has no machine-readable way to say refuted.**
`kb_entry.schema.json` offers `conflict_with` and `supersedes`; neither fits.
Superseding is wrong (nothing replaced the number), and conflict is wrong by
017's own ruling. The gap is in the schema, which is manager-owned, so nothing
was invented here.

What a caller sees today, asking the store for the product's emission
wavelength:

```
kb_query("abvigen_product_emission_wavelength")
  -> tracer_emission_peak | E3 | vendor_spec | no gap | overlap "unstated"
     claim: "The tracer particles emit at 680 nm, as specified by the supplier"
```

E3, no gap, no warning in any short field. `conflict_with` is returned and so is
the prose, so the information is reachable — but the three fields a caller reads
first all still say the pre-015 thing.

### The four that are neither ① nor ② nor ③

| entry | grade | note |
|---|---|---|
| `tracer_particle_density` | E3 `vendor_spec` | restored, type-level; unit `g/cm^3` still unregistered |
| `tracer_stock_concentration` | E3 `vendor_spec` | restored, type-level; unit `mg/ml` still unregistered |
| `tracer_storage_conditions` | E3 `vendor_spec` | restored; `degC` → `K` (275–281), the offset-unit pattern followed correctly |
| `tracer_number_density_from_diameter` | E3 `vendor_spec` | relation restored; entry-level `unit: 1/ml` **unregistered, and nobody has counted it** |

Added rather than restored: `bottle_label_states_no_product` (E3,
`operator_read`), `particles_show_on_the_green_605_path` (E2, `calibration`),
`abvigen_published_data_is_unreliable` (E3, `prior_run`, no `grade_tag`).

`tau_d` was touched by neither commit and stands at E4 `computed:diffusive_time`.
015 said it would inherit whatever the diameter became; it is a formula and
carries no diameter value, so nothing was owed and nothing changed.

## The rename is half done, and the half that is missing is the half 015 named

015 item 3 was "deal with the names", and its argument was that `tracer_` in a
name asserts these are ours in a string nothing checks. `ed373e0`'s message
reports the handles as `abvigen_` and says they stay. Counted off the tree:

```
7/7  entry_id   still says tracer        <- not renamed
6/7  claim      still says "the tracer particles"
6/7  numbers[].name / symbol  say abvigen_product_*
5/7  subject.id                say abvigen_product_*
7/7  identifiers.applies_to    names the type
```

The files were never renamed — `git show --name-status 8646426` reads `M` on all
seven, not `R`. What moved was `numbers[].name`, `symbol`, `subject.id` and a new
`identifiers.applies_to`. The entry id and the claim's first words, which are what
`kb_get` answers to and what a caller reads first, still assert the particles are
ours. `tracer_particle_material_and_shape` says in its own body that "a query for
our tracer should not land here" while being named `tracer_particle_material_and_shape`.

This is not a slip in the work; it is a slip in the report of the work, which is
the failure the seat itself asked this pass to catch.

## Counts, each off a run

**Unregistered units: three, not two.**

```
registered in contracts/units.json      45
numbers in kb/entries                   55   across 74 entries
unregistered in numbers[].unit           2   g/cm^3 (tracer_particle_density)
                                             mg/ml  (tracer_stock_concentration)
unregistered in entry-level unit         1   1/ml   (tracer_number_density_from_diameter)
```

`1/ml` has been on disk since `4ffafb0` at 11:59 and appears in no census. Every
count so far — manager-bridge's twelve, 016's table of twelve, `ed373e0`'s
"twelve down to two" — iterated `numbers[]`. The entry-level `unit` field is the
one KB rule 4 *requires* a `derived_quantity` to carry, so the single entry kind
obliged to name a unit is the kind the count never looked at. The blind spot is
structural, not arithmetic.

**Entries that were true, well sourced and about the wrong object: two.**

The manager predicted "closer to two than to seven" and that is right, but the
sense changed. Under 015 the count would have been seven, all wrong by
attachment — true of a product that was not ours. Under 017 the attachment is
restored and six of the seven are true of a product that is ours, merely reaching
this bench at E5 instead of E3. What remains wrong is the two peaks, and they are
wrong in the opposite direction: correctly attached to the right product, and
false about it, because the supplier's published figure is false. **Two entries,
and the lesson that caught them is the one that was written an hour before it
applied: a correctly graded entry is not a safe one.**

## What is still true about the bottle

Four things, and only the first two are measurements of it:

1. it fluoresces under Aura3 green and is visible through the 605 band — E2;
2. its label does not state a product identity, and was looked at — E3;
3. its particles are 5 µm, CV within 2% — E2, measured, **not yet an entry**;
4. it is the Abvigen product — E5, the person's judgement, **not yet an entry**.

Two of the four things known about the bottle are not in the store. Both are
blocked on the same thing: what a `calibration:` or an instance-level claim puts
in `validity`.

## What acted on 015 outside librarian_agent/

017 names `81e9fb8` and `dd5ee3c` and asks whether there are others. There are
four more, all on the same thread and all already corrected:

| commit | seat | what |
|---|---|---|
| `81e9fb8` | manager-simulation | withdrew the product from simulation task 004 |
| `dd5ee3c` | the person | recorded the withdrawal in `plan.md` |
| `e799d73` | the person | `plan.md`: the withdrawal is withdrawn |
| `e1fb69c` | the person | `plan.md`: the un-withdrawal is confirmed, not relayed |
| `48f8239` | the person | `plan.md` §11-13: the diameter closes by measurement |
| `6f6cf3d` | manager-simulation | simulation task 004's evidence section reversed back |

**No card anywhere carries the withdrawn identification.** Searching the whole
tree for `AFR-0500`, `abvigen` or `Abvigen` outside `librarian_agent/` returns
`plan.md`, `contracts/quantities.json`, `contracts/seats.json` and two simulation
*task* files — no `questions/`, no `inbox/`, no thread artifact. The simulation
card was being written while the withdrawal happened and its manager caught it in
the task file before it reached a card.

**The delivered snapshot is clean.** `microscope_agent/envelope/snapshot.json`
pins `kbv-eed5128749c3`, 49 entries, `built_from_commit: aac5f38` at 11:14 —
before `4ffafb0` at 11:59 entered the data sheet. It has never held a tracer
product entry and holds neither peak. Nothing needs recalling.

**But `contracts/quantities.json` is now waiting on a task that will not run.**
Its `not_yet_registered.pending_015` defers six ids with the reason "They come
back when 015 settles what they are about and what they are called." 015 is
superseded. 017 settled both questions — they are about the type, and they are
called `abvigen_product_*` — and the six names in that list are the pre-rename
ones, so not one of them exists in the store any longer. The same deferral is
written into check 44's body ("waits on task 015, which owns six ids this file
deliberately does not bless yet"), which means the contract step that would stop
`quantity` subjects resolving against themselves is blocked on a withdrawn task.
Both files are manager-owned; both were raised rather than edited.

## What this pass did not do, and why

No entry was written and `kb_version` did not move. Two librarian execution
sessions were live in one working copy while this ran, and the store's own
`failures.jsonl` records what a mid-flight version move cost the last time: 19
`kb_refs` across two agents went PENDING over a one-entry difference. The two
entries this pass argues for — the E5 link and the measured diameter — are
therefore named here with their blockers rather than created, and both blockers
are schema questions that belong to the manager.
