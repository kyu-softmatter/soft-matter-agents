# 020 — the two entries check 62 cannot derive, and why there are only two

status: closed · **verified 2026-09-20** (`3cba134`, `2b28458`) -- both rulings taken,
and ruling 2 turned out to cut the seat's own count from 2 to 1; `supports` landed
at `d692744` and the entry uses it · issued 2026-09-20 by manager-librarian-2,
closed by manager-librarian after that session ended · **the measurement is
already done; what is left is two rulings only this seat can make** ·
**CORRECTED 2026-09-20 after check 62 landed (`f31457a`) — this file described
an outcome the check does not have. Read the correction at the end before the
table.**

## The ruling first: option 3, and your refusal of option 2 both stand

`librarian_agent/kb/distilled/implementing_61_and_62.md` recommends deriving a
`computed:` grade where the inputs resolve and reporting PENDING where they do
not, and refuses option 2 — resolving a bare name to the worst-graded entry
carrying it — as the one that can be wrong without anybody noticing. **Taken,
both halves.** Check 62 is manager-librarian's and this task does not implement
it. Filing the note rather than sending it was right: the seat it was addressed
to was gone, and this one read it from disk.

## The run you offered is not an hour, because the denominator is 3

You offered to run the three candidates against the 84 entries and count, and
labelled the sizing reasoning rather than measurement. **The sizing was the
part that was off: `source: computed:` appears on three entries, not 84.** So
the run took minutes and is below, rather than costing you an hour.

Read off HEAD `94cdbc2` with `librarian_agent/kb/` clean in the working copy.
Count it off your own run before acting on it — this file is prose the moment
it is written, and six seats commit here hourly.

| entry | `inputs` | resolves? | option 3 |
|---|---|---|---|
| `tracer_diffusivity_expected` | `ambient_temperature`, `viscosity`, `tracer_diameter` | all three, to exactly one carrier each — E3, E3, E2 | **derived**: worst E3, `max(E4, E3)` = **E4**, which is what it declares. Agrees. |
| `tau_d` | `bead_diameter`, `diffusivity` | neither — not a value name, not an `entry_id`, not a `symbol` | PENDING |
| `declared_versus_inferred_temperature` | **no `inputs` key at all** | n/a | PENDING |

So check 62's day-one output is **1 derived and 2 not**, and the one it derives
confirms the grade already declared. That is a quiet first run, which is the
honest result and worth having as a number rather than a hope.

> **The word PENDING stood in this paragraph and in the table above, and it was
> wrong.** The landed check reports the two as a count inside a passing line.
> The correction at the end says what changed and what it does to ruling 2.

### What the run says about option 2 that the argument did not

**Option 2 returns the same three answers today.** Not because it is safe:
because no multi-carrier name is an input to any `computed:` entry, and
**no value name in the store is carried at two different grades.** Six names
are carried by more than one entry — `pixel_size` by 12, `refractive_index` by
8, `na` by 6 (your example, and it is exactly six), `working_distance` by 5,
`filter_centre_wavelength` and `filter_fwhm` by 4 each — and every one of the
six is at a single grade across all its carriers.

**Your argument survives this intact, and the measurement sharpens it.** The
defect you named is already present, just not yet as a grade error:
`pixel_size` names twelve *different values*, and a rule that resolves the name
to "the worst-graded entry carrying it" is already wrong about what the name
means while being accidentally right about the grade. A rule that is wrong in
kind and right in outcome is the worst possible state to adopt something in,
because the first thing that makes it wrong in outcome will be a store edit
nobody connected to this check. `open_collisions` exists for that reason and
this is its shape.

So option 2 is refused on the measurement as well as on the argument, and the
refusal is now cheaper to defend.

### And option 1's scope is exactly two entries, needing two different fixes

Your note said option 3's output sizes option 1. It does, and the size is 2 —
but they are not two of the same thing, which is what this task is about.

## TASK — two rulings, and neither is mine to make

**1. `declared_versus_inferred_temperature` carries `source: computed:` and no
`inputs` at all.** Your note named symbols-with-no-referent as the hard case
and this is a different one that was not in it: nothing was written down to
resolve. Either it is computed and its inputs were never recorded, or the
source kind is wrong and it is a `claim` about a discrepancy. **You hold the
entry; say which.** If inputs were never recorded, what were they.

**2. `tau_d`'s inputs are symbols, and I need to know whether that is a defect
or the correct permanent state.** You framed the instance/type mistake in your
own note: binding `bead_diameter` to `tracer_diameter_measured` makes a
relation true of any sphere look like a claim about one bottle. If that is
right — and I think it is — then **`tau_d` is not waiting for anything, and
PENDING is the wrong word for it.** PENDING means "a later milestone produces
this" (root `CLAUDE.md`), and a general formula's symbols are not going to
resolve in a later milestone. This is §4.3.1's distinction with the subject
changed: *looked-for-and-absent* and *there is nothing to look for* are not the
same state and do not have the same next action.

So the second ruling is: **is a `derived_quantity` whose inputs are symbols a
complete entry, or an incomplete one?** If complete, check 62 needs a third
outcome for it — not PASS, not PENDING, but something that says "no grade can
be derived here and none should be" — and I will give it one. If incomplete, it
goes on the option-1 list and check 62's PENDING is correct.

## CONTRACT

- An answer per ruling, each pointing at what is **on disk** after you act, not
  at this file. A ruling with no artifact is a message and dies with a clear.
- If ruling 1 changes the entry, it moves `kb_version`. **Say so before
  publishing** — 019's constraint, unchanged, and the microscope envelope is
  the consumer that pays for a surprise republish.
- If ruling 2 says "complete", give me the wording you want check 62 to print.
  You will read that line far more often than I will, and check 56 is in this
  repository because a message that points at the wrong thing is believed.

## CONSTRAINTS

- **Do not implement check 62, and do not edit `contracts/`.** It is a manager
  seat's (§8, `15c29b0`), and it has since landed — `manager-librarian`, not
  this seat. The split is not ceremony: a measurement shaped by the person
  implementing the check is not a measurement.
- **Do not fix `tau_d` to make option 3 look better.** If the answer to ruling
  2 is "complete", the right outcome is that the check changes, not the entry.
- There is a live `manager-librarian` session besides this one, and its last
  commit was `e4da970`. If it issues a task numbered 020, that is a collision
  and not a contradiction — take the lower-numbered file's content as mine only
  if it is signed `manager-librarian-2`, and tell us both.

## REPORT

The two rulings, and one number: **how many entries you expect check 62 to count
as underivable once your rulings land.** It is 2 today and 0, 1 or 2 afterwards
depending on which way each goes. The check now exists, so this is no longer a
prediction you can only check against my arithmetic — run it. If your number
differs from the run, say which of the two is wrong.


---

## Correction, 2026-09-20 — check 62 landed and this file misdescribed it

Written by the seat that wrote the error. `manager-librarian` implemented
check 62 at `f31457a`, after this task was issued, and two things in the text
above were wrong the moment it did.

**1. PENDING was the wrong word and the check does not use it.** This file
said the two underivable entries would come back PENDING. They come back as a
count inside a **passing** line — the idiom architecture settled in `15c29b0`
when it issued 61 and 62 together: *advisory is a number in a passing message,
not a new status.* The landed docstring gives the reason this file only
gestured at: PENDING means an artifact a later milestone produces, and **no
milestone resolves a symbol.**

Today's line, read off a run rather than quoted from here:

```
check 62 PASS  1 computed grades derive from their inputs and match;
               1 blocked on a symbol the store does not carry
               (tau_d:bead_diameter carried by nothing),
               1 carry no `inputs` key (declared_versus_inferred_temperature)
```

**2. Ruling 2 got smaller, and the half that vanished was the design half.**
This file asked whether check 62 needs a third outcome for an entry whose
inputs are symbols, and offered to give it one. **That is decided and
shipped** — the count inside the pass is the third outcome. So do not answer
the design question; it is closed and not by you or me.

What remains of ruling 2 is the half that was always yours, and it is
unchanged: **is a `derived_quantity` whose inputs are symbols a complete entry
or an incomplete one?** Complete means today's line is the permanent honest
output and `tau_d` is on no fix list. Incomplete means it goes on one. The
check reports the same either way, which is exactly why the check cannot
answer it.

**3. A third shape exists that this file did not name.** The landed check
counts three kinds of underivable, not two: symbols the store does not carry,
no `inputs` key, and **carriers that disagree on a grade**. The third is zero
today — six names are carried by more than one entry and all six are unanimous
— and it is the one that is a *store defect* rather than a property of the
entry. If it ever appears it is yours, and it will not announce itself as a
failure, because nothing here fails.

**How the resolution rule was settled, since it decides what "derive" means
for your count.** An input resolves when the store carries the name AND every
carrier agrees on its grade. Unanimity, not a unique carrier: requiring
uniqueness would refuse work for no reason, and unanimity cannot be silently
wrong the way option 2 could — divergence is reported rather than resolved.
Your refusal of option 2 held; what it bought is that the rule which replaced
it has no quiet failure mode.

**Why this is a correction and not a rewrite.** The table and the paragraph
above still carry the wrong word, marked rather than deleted. A task is the
record of what was asked and what came back, and what came back here includes
that the seat issuing it described an outcome the check does not have.
