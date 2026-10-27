# 021 — the numbers nothing uses, shown beside the plan the person signs

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 019. If
you are not that seat, take nothing from this card and report up.

**Held until the rule lands.** The list this card shows is computed by one
rule in `contracts/`, which manager-microscope writes with its fixtures
(plan.md 15.1 item 10, `574499c9`; what counts as using a number is
worded field by field at `9e9c480b`). It is not there yet. This seat releases
the card with one added line that names the rule's path, its fixtures' path
and the commit it landed in. Build to that commit. Start nothing here before
that line exists.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

A plan card's `numbers[]` holds the values the run sets and also values the
plan only reasons with, such as a record length or a bleach window. Refusing
the second kind would refuse correct plans, so plan.md 15.1 item 10 lists
them instead. The list is shown beside the plan the person signs, so an
intensity that nothing sets is seen before signing and not found later in
the frames.

`microscope_agent/questions/mic-20260920-001/v4_plan_microscope_mic-20260920-001.json`
is the case. Its `numbers[]` holds `illumination_line_intensity_permille`,
and none of its actions names it. The acquisition action names only
`exposure_time` and `frame_count`. Which fields count as using a number is
the rule's to settle, so the rule's fixtures say what this card's list
holds, not this paragraph.

The list is a function of the plan card alone. No binding, snapshot, device
or run log plays a part. So it exists before the plan is signed, and the
console computes it from the very card whose fingerprint the dialog shows.
**The console does not read it from the run log.** A plan that needs signing
does not run until it is signed, so at the sign dialog no derivation event
exists yet.

## What to do

1. **The copy.**
   - In `src/sma_console/agents/sma_files.py`, beside `plan_hash`, add
     `unused_numbers(card)`. It is a copy of the rule in `contracts/`.
   - Its docstring cites the rule's path and the commit it was copied at,
     the way `plan_hash` cites `card_sha`.
   - It reads only the plan card it is given. The console imports no code
     from the tree and runs none; it reads the tree as data.
   - Its output is the rule's, unchanged, in the rule's order. As proposed,
     each number comes out as `name`, `value`, `unit` and `from`, where `from`
     is its place in `numbers[]`. The release line says if that changed.
   - The dialog takes each number's `source` from the card's own entry at
     `from`, not from the copy's output.

2. **One card, one list.**
   - `QuestionDetail` gains `unused_numbers`. `get_question` computes it
     from the same plan dict that `plan_hash` hashes, in the same `replace`.
     So the list and the fingerprint are always of one card.
   - Give it three states, told apart:
     - no plan: nothing;
     - a list, possibly empty;
     - "could not be worked out", with the copy's reason in words, when the
       copy cannot apply the rule to the card.
   - The mock store gives it the same way, and `to_dict` and `from_dict`
     carry it. So does the question detail the API returns. Regenerate
     `web/src/api/schema.ts`; do not hand-edit it.

3. **The sign dialog** (`web/src/features/questions/sign.tsx`).
   - Add a section after "Devices this plan touches", headed **"Numbers in
     this plan that nothing sets"**.
   - One line per number: `name: value unit (provenance)`. Use
     `provenanceWord` for the provenance, as `devicesTouched` does, so a
     guess still reads "guessed".
   - With an empty list, say: "Every number in this plan is one the run
     sets, hands to a step, sizes itself by, or checks against." It puts
     item 10's meaning of "used" (`9e9c480b`) in plain words, and a
     condition on a selector's device is not in it.
   - When it could not be worked out, say: "The numbers nothing sets could
     not be worked out from this plan: " followed by the reason. Mark it as
     an alert.

4. **Signing does not change.**
   - The list is shown and decides nothing. No number is refused, no
     control is disabled, and the Sign request sends what it sends today.
   - Neither `/sign-check` nor `signing/approval_writer.py` reads the list.
     When an approval is written changes only on the person's word, and
     this card asks for no such change.

5. **Tests, each watched failing first.**
   - The copy run on the rule's fixtures, read from the tree's
     `contracts/` through `repository_root()`. Each fixture's expected list
     equals the copy's output. A missing fixture file fails the test; it
     does not skip it.
   - Break the copy once by hand: stop counting one of the fields the rule
     counts, see a fixture fail, then restore it. Name that fixture in your
     report.
   - In a `tmp_path` tree, add a number to a plan that no action names. The
     detail's list gains it and the fingerprint moves, both from one read.
     Then name it from an action: the list loses it.
   - A plan the copy cannot read gives the "could not be worked out"
     state, with a reason, and no exception reaches the route.
   - The web dialog in each of the three states. For each, the Sign
     control is enabled exactly as it would be without this section.
   - The mock's shipped microscope plan shows its list in the dialog.

## What not to do

- Read no run log, derivation event or snapshot, and no file other than the
  plan card the dialog shows.
- Write nothing into a plan card. A list written into the card was
  considered and not adopted, because it would sign a second copy of what
  the card already says.
- Compute nothing about what the runtime will write to a device. That needs
  bindings, which are the runtime's and the librarian's.
- Change nothing under `signing/` and nothing about when Sign is offered.
- Install nothing. Your commit carries `console/` only.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest -p no:cacheprovider` passes.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat, with the fixture you watched fail.
