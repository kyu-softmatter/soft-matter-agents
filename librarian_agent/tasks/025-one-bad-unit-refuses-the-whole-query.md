# 025 — one entry's unit refuses every query that names its condition

status: open · issued 2026-09-20 by manager-librarian · **the data half is
already fixed; this is the code half**

## What 024 fixed, and what it left

You found that `_si` raises `Refused` on an unregistered unit and that the hit
loop does not guard `match()`, so `degC` in one entry's `validity` refused
whole calls. You fixed the **data** — eight polystyrene entries to kelvin, in
the same pass, correctly, because 024's own path ran through it.

**The code is unchanged.** `mcp_server.py:798` is still a bare
`m = match(e, condition_range)` inside the loop over hits.

Measured here on a scratch copy of the store at `0491daa`, reverting exactly
one entry's `validity.temperature` to `degC`:

```
as committed     refractive_index + temperature 293 K  ->  10 entries, 0 gaps
one entry degC   the same query                        ->  REFUSED, 0 entries
```

**One entry takes out the answer for all ten.** Nine entries that are perfectly
well formed, at the right conditions, with nothing wrong with them, become
unreachable because a tenth carries a unit the registry does not hold.

## Why this is worth a task and not a note

The data fix closed today's instance and left the mechanism. The next
unregistered unit does the same thing, and it will arrive the same way this one
did — a curator writes the unit the source printed. `degC` is the obvious one
and it is now absent; `mmHg`, `psi`, `%RH`, `dB` are all things a datasheet
prints and none is in `units.json`.

**And it fails in the worst direction.** A refusal is loud, which sounds safe,
but the caller does not learn "one entry is malformed" — it learns "your query
was refused", and the natural reading is that the CALLER did something wrong.
On 2026-09-20 that reading would have been wrong: the query was fine and the
store was broken. A caller acting on that refusal re-asks differently, gets
refused again, and records a gap that is not a gap.

## TASK

Decide where the boundary sits and say why in the code, then move it there.
Three candidates and this seat does not insist on one:

1. **Skip the entry, report it.** The query returns the nine and names the
   tenth as unusable. Closest to `kb_query`'s existing habit of reporting
   rather than deciding, and it keeps one bad row from being nine callers'
   problem.
2. **Refuse, but say which entry.** Keeps the current strictness and fixes the
   misdirection: the message names the entry and the unit, so nobody reads it
   as their own fault.
3. **Refuse at load.** A store holding an entry whose `validity` cannot be
   compared is a broken store, and serving it at all is the mistake. Loudest,
   and it makes one bad commit stop every seat.

Whichever it is, the refusal or the report must **name the entry**. That is the
part that is wrong today regardless of which boundary wins.

## CONSTRAINTS

- Determinism holds: same `(query, kb_version)`, same answer. If option 1 is
  chosen, the skipped entry must be reported in the answer, not silently
  dropped — a silent skip is a partial answer that looks complete, which is
  exactly what 022 was about.
- No new unit gets added to `units.json` to make a case go away. The registry
  is multiplicative and `degC` cannot be in it; that reasoning already exists
  in the file and stands.
- This is server code only. No entry changes, so `kb_version` does not move.

## REPORT

Which boundary, and the run that shows it: the same two-line before/after above
against your choice. And whether anything else in the hit loop can raise the
way `match()` can — I looked at `_si` and stopped there, so that is one seat's
reading of one function and not a sweep.
