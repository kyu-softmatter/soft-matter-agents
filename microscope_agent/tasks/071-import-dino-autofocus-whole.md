# 071 — import dino-autofocus whole, with its history

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261015-1`.** If you are not that seat, take
nothing from this card and report up.

## The decision

On 2026-10-15 the person decided that all of `dino-autofocus`, the console
included, moves into this repository **with its history**, into
`microscope_agent/autofocus/`, and that `dino-autofocus` is then frozen as a
read-only record. It is recorded in plan.md 10.2 with the person's words,
and step 4 of plan.md 14's import list is this card.

**Code moves whole.** The import commit is its ruling record; no file in it
is ruled one by one. **The ruling condition applies only to numbers and
safety values**:

- every figure in the tree that would act here enters only through the
  librarian, as manager-librarian's card;
- a guard table inside the imported tree is data of the record and **binds
  nothing**;
- `envelope/safety.json` binds, and the person wrote it at the bench.

## What is already in place

- The freeze point: `dino-autofocus` `main` **`95eee95`**, on GitHub (checked
  2026-10-15 with `git ls-remote`).
- **The validator treats `microscope_agent/autofocus/` as one imported
  subtree** (`441ae7d`):
  - it is declared once for the path check;
  - it is never read as cards or agent source;
  - history checks read only the first-parent line;
  - a root commit in a range is judged rather than crashing.

  On a trial clone this took 802 failures to 0.
- **`.gitattributes`** keeps `microscope_agent/autofocus/configs/micromanager/*.cfg`
  byte-exact, `-text` (`491cea3`), and it has landed before the import, as it
  must.

## What to do

1. **Run the import** from this working copy's root, under your seat identity
   from `contracts/seats.json`:

   ```
   git subtree add --prefix=microscope_agent/autofocus https://github.com/kyu-softmatter/dino-autofocus 95eee95
   ```

   It makes one merge commit, which is yours. Name the source and the freeze
   sha in its message, say it carries the whole of `dino-autofocus` with its
   history, and say that the ruling condition covers numbers and safety
   values only, as above.
2. **The gate judges it.** The merge's paths all fall inside the microscope
   boundary, and the first-parent rule keeps dino's own commits out of the
   check. **If the gate refuses, stop and report the output.** Do not use
   `--no-verify`.
3. **Check the configs survived byte-exact.** For every file in
   `microscope_agent/autofocus/configs/micromanager/`, its sha256 must equal
   the sha256 of the same path in `dino-autofocus` at `95eee95`. Report the
   count and any that differ.
4. **Write the import's ruling line.** The import commit is the ruling record
   for the code (plan.md 10.2, `d53214e`), and `microscope_agent/rulings.jsonl`
   gets **one line** for it, in the shape the file already uses:
   - `ruling`: `transfer`;
   - `item`: all of `dino-autofocus`, by `git subtree`, into
     `microscope_agent/autofocus/`;
   - `slot`: the microscope agent's autofocus;
   - `rule`: plan.md 10.2, numbers and safety values only;
   - `by`, `at` and `recorded_from`, naming the freeze commit `95eee95` and
     your import merge's sha.

   Commit it in its own commit after the merge, because it needs the merge's
   sha. **This one line is the only thing you write in `rulings.jsonl`**:
   card 064 gives that file to the other microscope seat, and this card
   grants one line, no more.
5. Push with `git -c credential.helper=manager push origin feature/autofocus-ui`.
   The push hook judges the pushed range. Never force.

**Change nothing inside the imported tree in this card.** The translation,
the tests and the mirror are cards 072 to 074, after this one lands.

## Boundaries

This card writes `microscope_agent/autofocus/` through the subtree merge,
and the one ruling line in `microscope_agent/rulings.jsonl`, nothing else. Never `envelope/`, `approvals/` or `inbox/`. No change to
`SOFTWARE_MAY_COMMAND` or `NAMED_REFUSALS`. **Run nothing from the imported
tree**: the console and its server start nothing here until a card says so.

## What comes back

To this seat, 5 lines at most: the merge commit, the ruling line's commit,
the gate's verdict and tree lines, the config byte check, and the push.
