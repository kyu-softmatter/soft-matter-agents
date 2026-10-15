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

**Revised on 2026-10-15 from what microscope-office-20261015-1 found on a
scratch clone before touching anything shared.** Running `git subtree add`
in the shared working copy fails three ways:

- a remote cannot be fetched by a short sha;
- `git subtree add` builds its merge with `read-tree` and `commit-tree` and
  never calls `git commit`, so **the pre-commit gate does not run**, which
  is `--no-verify` in effect, leaving no trace;
- it refuses while any other seat has an uncommitted edit, which is the
  normal state here. And its closing `git reset` moves the branch to a
  commit built on the HEAD read at the start, so **a commit another seat
  lands in those seconds would be dropped**.

So the merge is built and judged outside, then brought in with
`--ff-only`.

1. **Build the merge in a scratch clone** of this working copy, at its
   then-current HEAD. Use a **short path**, such as `D:\sma-scratch9`,
   because a long one fakes missing-file failures under Windows' path limit.
   Ask the person for that directory if it does not exist. Run, with your
   seat's committer identity from `contracts/seats.json`:

   ```
   git subtree add --prefix=microscope_agent/autofocus https://github.com/kyu-softmatter/dino-autofocus 95eee9582a820ebf09896cf53db2e28cd3ed5397
   ```

   Use the **full** freeze sha, and write the message with `-F <file>`. The
   message says:
   - the source and the freeze sha;
   - that it carries the whole of `dino-autofocus` with its history;
   - that the ruling condition covers numbers and safety values only;
   - **that the pre-commit hook did not run, because `git subtree` made the
     commit with `commit-tree`, and that step 2 and the pre-push hook are
     what judged it.**
2. **Judge it there, before it touches anything shared:**
   - `validate.py --commit-range HEAD^1..HEAD`, and a full run, both under
     the interpreter `CLAUDE.md` names for this computer;
   - **0 failed** on both, and every path of the merge under
     `microscope_agent/autofocus/`.

   If either refuses, stop and report the output.
3. **Bring it into the shared copy without moving anyone's work:**
   `git fetch <scratch> <sha>`, then `git merge --ff-only <sha>`.
   - `--ff-only` refuses if HEAD has moved since step 1, so no seat's commit
     can be dropped. Then start again from step 1 at the new HEAD.
   - The merge touches only `microscope_agent/autofocus/`, so other seats'
     edits stay where they are. If git refuses because a local change would
     be overwritten, stop and report: never stash, reset or check out
     another seat's work.
4. **Re-run the validator in the shared copy** and quote its `verdict:` and
   `tree:` lines.
5. **Check the configs survived byte-exact.** For every file in
   `microscope_agent/autofocus/configs/micromanager/`, its sha256 must equal
   the sha256 of the same path in `dino-autofocus` at `95eee95`. Report the
   count and any that differ.
6. **Write the import's ruling line.** The import commit is the ruling record
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
7. Push with `git -c credential.helper=manager push origin feature/autofocus-ui`.
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
