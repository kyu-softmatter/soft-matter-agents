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
- `seat:librarian` holds `mcp_server.py` and lands this. `seat:librarian-3`: this is why
  you are being told rather than asked — you backed out of that file once
  today and recorded it, and I would rather name the holder than have you
  find out by collision twice.

## REPORT

The `kb_query('pixel_size_100x_zoom_1x')` row after the change, with
`valid_until` in it. And the twelve: how many of the fifteen carry an event,
what the three that do say, and whether anything in the store already implies
what ends a pixel-size calibration here.

---

## REASSIGNED 2026-09-20 — the named holder is gone, and item 4 is already done

**`seat:librarian-3` implements this, items 1–3.** `seat:librarian` has left; `ListAgents`
no longer lists it and a message to it bounced. Verified here rather than
taken: `librarian_agent/src/mcp_server.py` is clean at `5c64112` with nothing
uncommitted, so **nobody holds the file.** The constraint above named a holder
to prevent a second collision, and there is no longer anyone to collide with.
Waiting for that ruling rather than deciding it was the right read.

## Item 4 is answered, and it makes the question twelve times smaller

**The twelve are one calibration event, not twelve.** Counted here:

```
valid_until {date} only      12   source calibration:cal-pixel-size-20260919   <- all twelve
valid_until {date, event}     3   three different sources
```

**One `event` fills all twelve.** Ask the person about
`cal-pixel-size-20260919`, not about twelve pixel sizes.

**And the 2041 date was not invented.** The entries' own
`validity_conditions` say it: *"Valid for fifteen years as the operator
stated, anchored to 2026-09-19 because the day the measurement was taken was
not recorded."* So my "never expires wearing an expiry" reading was right
about the effect and **wrong about the cause** — this is not neglect, it is
an empty `event` slot beside a date the operator gave.

What the store already implies, as candidates and not as an answer — the seat
looked rather than reasoned, and none of these is entered:

1. `objective_change_invalidates_trap_calibration` (E3) literally says
   *"Changing the objective silently invalidates ... the GUI's
   pixel-to-micrometre magnification"*. Different subject, closest sentence
   on disk.
2. **An objective change does not end these twelve — it selects among them.**
   Each row carries `nominal_magnification` and `intermediate_magnification`
   as identifiers. What ends one is **a different physical objective at the
   same nominal magnification.**
3. **A camera change ends all twelve at once** — pixel size is sensor pitch
   over magnification, and `camera_sensor_geometry` holds the 6.5 µm pitch.
   That entry has no `valid_until` of its own.
4. A change in the optics between objective and camera. **Nothing in the
   store covers this one.**

## And the argument for the twelve is not the argument for the three

The seat corrected its own case and the correction stands. *"The event, not
the date, is what invalidates"* reaches **the three**. For **the twelve** the
argument is the schema's: E2 requires a validity period, so **the field's
existence is what separates E2 from E5**, and a caller reading a pixel size
through `kb_query` cannot see that the thing holding the grade up exists at
all. Different reasons, same ruling — carry all fifteen.

## One more into the same commit

`mcp_server.py:1935`, self-test 17, added by 030:

```python
plain = kb_query(...)["entries"][0]        # no guard
```

Block 8b, four blocks above, guards the same query with
`if not any_row: bad(...)`. Measured on a synthetic tree: remove the one
entry that answers to `viscosity` and 8b reports *"the projection cannot be
checked"* while 17 raises `IndexError`. **Exactly one entry in the store
answers to `viscosity`**, so one rename or supersede turns a diagnosis into a
stack trace.

And 8b was split in two on 2026-09-19 for this reason, its own comment
saying it *"could not tell two different failures apart and started reporting
the wrong one"*. **Four blocks away, the same lesson was walked into again** —
which is another line for 032: a fix does not reach what the block beside it
already learned. Two lines, and 031 is touching the self-test anyway.

---

## ITEM 4 IS NOW A RULING, 2026-09-21 — fill it, do not count it

The person answered. **The event is the camera being replaced**, and the
**date does not move** — asked whether to re-anchor, they had no preference,
so the recorded 2026-09-19 fallback stands and the entries' own sentence
explaining it stays true.

**Write the same `event` into all twelve.** They share one source,
`calibration:cal-pixel-size-20260919`, so this is one fact and not twelve.

Why the camera and not the objective, which is the part I would have got
wrong on my own: pixel size is the sensor pitch over the magnification, so
**a different sensor ends all twelve at once**, while a different objective
only *selects* among them — each row carries `nominal_magnification` and
`intermediate_magnification` as identifiers, not as conditions.

The text is yours to write and it should say the mechanism, not just the
trigger — the other three events all name *the physical thing this claim is
about being replaced*, and the mechanism is what makes this one checkable.
`camera_sensor_geometry` holds the Kinetix 22's 6.5 µm pitch and is what
these values rest on; name it.

```
valid_until: { "date": "2041-09-19", "event": "<the camera is replaced, and why that ends it>" }
```

**One thing to report and not to fix:** `camera_sensor_geometry` has no
`valid_until` of its own. Twelve E2 entries will now name a camera change as
their terminating event while the entry holding the camera's geometry carries
no expiry at all. That may be right — a sensor pitch is a specification and
not a measurement that ages — but it is worth one sentence from you either
way, because the twelve now depend on it.

This goes in the same pass as items 1–3. It moves `kb_version`, so items 1–3
(server only, no version move) and this (entries, version moves) are two
commits, and **tell me before publishing.**


---

## A correction to this file's own vocabulary, 2026-09-21

Two lines above named sessions by their **window titles**, in Korean, rather
than by seat. Replaced with the registered identities, `seat:librarian` and
`seat:librarian-3`, which is what `seats.json` holds and what check 41 reads.
Confirmed off the commits rather than assumed: `5c64112` is
`seat:librarian`, `5d60856` is `seat:librarian-3`.

Two reasons, and the second is the one that matters. The language rule says
everything in this repository is English with no exception. And **a window
title is not a seat**: it is chosen by whoever opened the session, it can
repeat, and it changes without anything recording that it did — so a task
naming one names something no registry holds and nothing can refuse. That is
the same shape as every other name-nothing-checks found here this week, and
this seat wrote it into its own task file while fixing that shape elsewhere.

*And this note quoted the two titles when it was first written, which left
Korean in the file that had just been cleaned of it. Described instead. The
same question stands over `contracts/validate.py:3714`, which quotes the
Korean section heading the check used to split on — that one is raised and
not decided, because paraphrasing it costs the comment the exact string it is
about, and a quotation of a removed string is not the same act as using one.*
