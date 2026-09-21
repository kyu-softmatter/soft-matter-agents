# 031 — carry `valid_until`, and twelve of the fifteen are a date with no event

status: open · issued 2026-09-20 by manager-librarian · **ruling from the
person** · found independently by both librarian execution seats

## THE RULING

**Carry `valid_until` in `kb_query`'s projection.** The person settled it.

Both of you found it and both of you declined to write it because 030 said
the answer's shape is not the seat's. That was the right read of 030 and this
is the answer coming back.

## Why it is the heaviest of the four

It is the fourth instance of `21c5325`'s shape — a field the entry holds and
the projection drops — and the stakes are the highest the store has:

```
15 entries carry valid_until,  14 of them E2
    including all twelve per-objective pixel-size calibrations
kb_get   carries it verbatim
kb_query has no such key at all
```

The schema says why the field exists: *"§5.3 lists E2 as `calibration:<cal_id>`
with a validity period and a condition range BOTH required... a calibration
could claim the second-highest grade in the scale with nothing holding the
claim up."* **So this field is what separates E2 from E5** — and the caller
reading a pixel size through `kb_query` cannot see when it stops being
asserted.

## AND THE FIELD IS HOLLOW IN TWELVE OF THE FIFTEEN

Measured here before issuing, because carrying a field faithfully is worth
nothing if the field is not doing its job:

```
valid_until = {date}          12 entries   all twelve pixel-size calibrations, date 2041-09-19
valid_until = {date, event}    3 entries
```

The schema has both halves on purpose, and one of your own entries argues it
better than the schema does — `particles_show_on_the_green_605_path`:

> BOTH the date and the event are set, and **the event is the one that
> actually invalidates this**: a ten-year date alone would say the
> observation still holds the day after somebody swaps the filter wheel.

**A 2041 date on a per-objective pixel-size calibration is "never expires"
wearing an expiry.** That is the thing the field was added to prevent, and it
is in the store's largest E2 block.

**This is a second task's worth of work and I am not folding it in.** Report
what you find; if the twelve need an event, that is a new task and the person
may need to say what event ends a pixel-size calibration on this bench — a
recalibration, an objective swap, a camera change. Do not invent one.

## TASK

1. **Carry `valid_until`.** One key, the shape `kb_get` already returns.
2. **Present on every row, `null` where the entry has none** — the precedent
   you set for `symbol` in 030 and the one `supersedes` already follows. 022's
   distinction does not apply: an entry with no expiry and an entry whose
   expiry is unknown are not two different things, *once nothing is dropping
   it*. Say so in the code, because that sentence is only true after this
   change.
3. **Self-test in 8b's idiom**, as one of you proposed: key presence on every
   row, and value fidelity against the 15 live examples.
4. **Report on the twelve.** Count, do not fix.

## Scope — do not widen

Both of you measured the other omissions and judged them harmless, and I
agree with the measurements: `subject` on 83 entries restates the handle the
caller asked by and the material distinction lives in `identifiers`, which
already crosses; `supports` is one entry; `schema_version` / `date` /
`curated_by` are bookkeeping that `source` / `source_ref` / `grade` already
cover. **`valid_until` alone.**

## CONSTRAINTS

- Server only. **No entry changes, so `kb_version` does not move** and there
  is nothing to publish. If the twelve turn into edits, that is the next task
  and it moves.
- `실행석` holds `mcp_server.py` and lands this. `사서 실행석3`: this is why
  you are being told rather than asked — you backed out of that file once
  today and recorded it, and I would rather name the holder than have you
  find out by collision twice.

## REPORT

The `kb_query('pixel_size_100x_zoom_1x')` row after the change, with
`valid_until` in it. And the twelve: how many of the fifteen carry an event,
what the three that do say, and whether anything in the store already implies
what ends a pixel-size calibration here.
