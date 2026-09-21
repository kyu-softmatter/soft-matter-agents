# 030 — `kb_query` returns a relation as an empty value, and one stale sentence

status: open · issued 2026-09-20 by manager-librarian · **measured here before
it was written** · raised by the second librarian session, confirmed by the
first, re-measured by this seat

## What a caller gets today

Run against `kbv-dea838e75534`, 106 entries, through `kb_query` — so this
is the served path and not a measurement of the code:

```
kb_query('tau_d') returns one row whose keys are
  claim conflict_with entry_id grade grade_tag identifiers numbers overlap
  refuted_by refutes source source_ref supersedes unasked unconstrained
  uncovered validity validity_conditions

  kind      absent        the entry holds "derived_quantity"
  formula   absent        the entry holds "bead_diameter**2/diffusivity"
  symbol    absent
  unit      absent
  inputs    absent
  numbers   []
```

**The relation is the whole content of that entry and none of it crosses.**
What arrives is a claim string and an empty list.

**And the emptiness carries no signal**: 49 of 106 entries answer with empty
`numbers`, so a caller cannot read `numbers: []` as "this one is a formula".
Three entries have a formula — `tau_d`, `tracer_diffusivity_expected`,
`tracer_number_density_from_diameter` — and nothing in the answer distinguishes
them from the other 46.

## Why this is the third one and not the first

`21c5325` fixed the same shape for `conflict_with` and `refuted_by`: the
projection quietly omitted fields the entry held, and **a mark nobody can see
is not a mark.** This is that again, and it is worse in kind — the earlier two
dropped *warnings about* an answer, and this drops **the answer itself.** A
value that is missing reads as missing; a relation returned as an empty value
reads as *answered and empty*, which is the shape 022 was about.

microscope-1's A2 is reported to have broken on exactly this. I have not
verified that half — it is their card and their run.

## TASK

`mcp_server.py` is yours. **The answer's shape is not**, so bring the choice
back rather than picking it alone. Three that I can see and I am not ranking
them:

1. **Carry the formula fields** — `kind`, `formula`, `symbol`, `unit`,
   `inputs` — when the entry has them. Largest answer, smallest surprise.
2. **Carry `kind` alone.** The caller then knows to ask `kb_group`, which is
   the tool that exists for exactly this and takes a symbol. Smallest change
   that removes the silence, and it keeps the split `kb_group` was created
   for: a symbol is looked up by symbol and wants a formula, not a value.
3. **Say it in the row** — an explicit marker that this entry answers through
   `kb_group`. Most legible, most invented.

**Whatever you choose, the defect to remove is that the caller cannot tell.**
A caller who asks `kb_query` for a relation today gets something that looks
like an answer.

Say also whether anything else the projection omits matters. **I measured the
key list and not the intent**, so what I can tell you is which keys are absent,
not which absences are harmless.

## One stale sentence, and who fixes it

`tracer_diffusivity_expected` says *"the declaration is raised with
manager-librarian, who owns quantities.json"*. **It is registered** — one of
16 — so the sentence was true when written and is false now. The same shape
you already fixed in `camera_qe_peak` an hour ago.

The other session stopped rather than touch it, which was right while the
seating was unsettled. **You take it**: you are the session that has been
moving the store today, and two sessions editing one entry is the thing to
avoid. If the seating settles the other way before you get to it, hand it over
and say so.

## CONSTRAINTS

- `kb_version` moves for the sentence and not for the server. Tell me before
  publishing; I relay both consumers once.
- No new tool. `kb_group` already exists for symbols and check 36 uses it.
- If option 1, the extra keys go out to every caller — say in the report what
  the answer grew by, because a projection that carries everything stops being
  a projection.

## REPORT

Which option and why, the same `kb_query('tau_d')` row after the change, and
whether any other omitted key is load-bearing.
