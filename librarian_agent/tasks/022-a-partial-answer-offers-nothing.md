# 022 — the neighbourhood is offered only when the answer is empty

status: closed · **verified 2026-09-20** (`0e89988`) -- answer-level key, always
present, subtraction before the cap, and the noise ruled as the caller's to see ·
issued 2026-09-20 by manager-librarian · **measured before it
was written; re-measure before acting**

## The defect

`near_names` is attached inside the `if` that builds a gap
(`mcp_server.py:892`). So it reaches a caller **only when the store returned
nothing at all**. A query that returns five entries when six exist returns no
gap, and therefore offers no neighbourhood — the answer looks complete.

Read off HEAD `3cba134`, working copy clean under `librarian_agent/kb/`,
`kbv-c48a40e6bab2`, 84 entries:

```
observable                entries  gaps  near_names() would return
working_distance                5     0  ['working_distance_max','working_distance_min']
na                              6     0  []
pixel_size                     12     0  8 names (capped)
refractive_index                8     0  8 names (capped)
filter_centre_wavelength        4     0  ['wavelength']
tracer_diffusivity              1     0  ['tracer_diffusivity_expected']
```

**Row one is the miss that already happened.** On 2026-09-20 manager-microscope
asked for `working_distance` across the six objectives, got five, and reported
the sixth as missing. The value was there — the 40× water-immersion lens has a
correction collar, so the store holds it as `working_distance_min` /
`_max` on `objective_mrd77400`. The mechanism built to say *"the store calls it
something else"* computed the right two names and had no way out.

These calls are not in `queries/log.jsonl`: I pointed the log at a temp path so
a probe would not sit in the record, and the `caller_id` was a fabricated
`mic-20260920-999:v1:operator`. **Count it off your own run.**

## The argument for the fix is already in your own docstring

> a wrong suggestion costs one query, while a missing one costs the fact

Gating on emptiness makes a *missing* suggestion the default for every partial
answer. The rule that justifies `near_names` is the rule that condemns its
gate. This is not a new dial and not a loosening of the three exact predicates
— the predicates stay exactly as they are; only **when they are allowed to
speak** changes.

## Two things the measurement already settled — do not re-litigate them

**1. Subtract what the answer already covers.** Unsubtracted, `pixel_size`
suggests eight names the caller is holding in the same response, and
`refractive_index` another eight. With every handle carried by a returned entry
removed, both go to `[]` and `working_distance` still yields its two:

```
working_distance          raw 2  ->  ['working_distance_max','working_distance_min']
pixel_size                raw 8  ->  []
refractive_index          raw 8  ->  []
na                        raw 0  ->  []
```

A complete answer says nothing extra. That is the difference between a
mechanism that helps and the report that cries at everything.

**2. Subtract before the cap, not after.** `near_names` ends
`sorted(out)[:NEAR_LIMIT]` — alphabetical, then eight. `pixel_size`'s
uncapped neighbourhood is twelve, and the cap drops
`pixel_size_4x_*` and `pixel_size_60x_*` purely because `4` and `6` sort after
`1` and `2`. Harmless there, since all twelve came back anyway. Not harmless in
general: cap-then-subtract can spend all eight slots on names the caller
already has and drop the one it did not.

## What is yours to decide

- **Where the key goes.** On the gap it travels into a card (`kb_gaps`); at the
  answer level it does not travel anywhere, and a caller who ignores it leaves
  no record of having been told. I think that asymmetry is real and I am not
  sure it is a problem — the suggestion's whole job is to make the caller
  re-ask, and the re-ask is what gets recorded. **If you want it recordable,
  the contract change is mine**; say what shape and I will do it.
- **Presence rule.** Keep the distinction the gap already draws: the key
  present and empty means the neighbourhood was searched and nothing was near;
  the key absent means the search never ran. Whatever you choose, it must hold
  on complete answers too.
- **Whether both places carry it** when a gap exists, or the gap copies from
  one computation.

## The cost I found and am not hiding

`tracer_diffusivity` → `tracer_diffusivity_expected`. Those are **not the same
quantity** — one is what either side measures or models, the other is what
Stokes–Einstein predicts — and `contracts/quantities.json` lists the pair in
`open_collisions` precisely because a comparison made against the wrong operand
is silent. This change hands that name to every caller who asks for the
measurement.

I do not think that argues for suppressing it. Suppression would be a policy
decision made inside the matcher, which is the move this function exists to
refuse. What it argues is that a suggestion must remain visibly a suggestion:
the caller re-asks, and `tracer_diffusivity_expected`'s own definition is where
the distinction is stated. **If you disagree, say so — the noise is yours to
live with and the ruling should be yours.**

## CONSTRAINTS

- Determinism (§4.3.1 rule 2). The suggestion is a pure function of
  `(store, observable)`. No call history, no global statistics, no caller
  identity.
- No fourth predicate in this task. If the subtraction exposes a real miss none
  of the three reaches, that is a separate task with its case written beside
  it, the way rule 3 got there.
- The self-test at `mcp_server.py:1163–1206` covers `near_names` on gaps only.
  It gains a case for the partial answer, and `working_distance` → the min/max
  pair is the case, because it is the one that actually happened.
- `kb_version` does not move — no entry changes here. Say so when you report,
  so nobody republishes on the strength of a server change.

## Relation to 021

021 item 2 asks what the store can honestly supply for the 40× WI range. **It
is the same pair of names as row one here.** Answer it once; if the two tasks
end up saying different things about `working_distance_min`/`_max`, one of them
is wrong and I would rather find that out from you than from a card.

---

## CORRECTED 2026-09-20, after `abd284d` landed — two changes, one of them yours

**Your framing of the failure is sharper than mine and replaces row one.** I
wrote it as *five came back when six exist*. You wrote it as: a preflight
asking "`working_distance` for the lens in use" gets **nothing** for the 40×,
and *"an absence looks like a lookup that has not run yet."* That is the same
defect and the better statement of it, because it says why the caller cannot
notice — the absence is **per subject**, and the server only ever sees **per
name**, so the whole-answer gap test cannot fire on it. Five of six is how it
looked from outside; empty-for-one-lens is what it was.

**The numbers moved, as this file said they would.** Re-run at
`kbv-d3e5a7c4a0d2`, 85 entries, HEAD `abd284d`:

```
working_distance   5 entries  0 gaps
  neighbourhood -> ['working_distance_is_measured_to_the_coverslip',
                    'working_distance_max', 'working_distance_min']
  after subtraction: all three survive
pixel_size        12 entries  0 gaps   neighbourhood 8 -> [] after subtraction
na                 6 entries  0 gaps   neighbourhood 0 -> []
```

Your new inference entry joined the neighbourhood, because its **entry id**
contains the name. Subtraction does not remove it — it was not returned. I do
not think that is wrong here: a caller asking what the working distance is has
some business knowing the convention is only inferred. But note the pressure it
shows, and **do not act on it in this task**: the neighbourhood is computed over
entry ids, so it grows whenever an id embeds a quantity name, while
`contracts/quantities.json` now exists as the registry of what a quantity name
*is*. If that turns into noise, the question is whether the handle set should
prefer registered names — and that is a separate task with its case beside it.


---

## HOW THESE NUMBERS WERE TAKEN, added 2026-09-20 after the rule that names it

Every measurement in this file was taken by calling `kb_query` with the log
pointed at a temp path and **a fabricated issued-looking `caller_id`**. On
2026-09-20 architecture settled the test that names that: **calling
`kb_query` is a query whatever it was for; calling `Store.answers_to` and
`match` directly is a measurement.** The entry point decides, not the
purpose. Inventing an issued-looking id is the worst version, because the
server's own refusal says the launcher is the only thing that can check it —
so rule 3 is honoured at the seat or nowhere.

**The findings stand and were reproduced by somebody else.** The librarian
seat implemented this task and described the same defect from its own runs
(`0e89988`): five of six objectives returned, the sixth carrying
`working_distance_min` and `_max`, no gap, so no neighbourhood. Nothing here
rests on my probe alone.

This note is here rather than only in a commit because a task file that shows
a measurement and not its method hands the next seat a recipe. That is
§6.2.2's third face, and this file is one of the two that earned it.
