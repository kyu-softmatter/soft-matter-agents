# 004 — three things that need the architecture seat

Written on 2026-09-20 with no architecture session running and every other
design seat closed. Each of these was finished or counted by `manager-bridge`
and needs one insertion into a file that seat owns. **On disk rather than in a
message**, because the notification that works and leaves no record is the
failure this repository counted all through 2026-09-19.

---

## 1. §11-16 is counted, and the answer is *never*

The question was whether `inequalities[].interval` and `constraints[]` ever
appear in the same card for the same parameter, and whether the values agreed.
Counted over 13 axis cards:

- `inequalities[]`: **37 entries — 34 `abstained`, 3 `returned`.**
  `inequalities[].interval` is used **zero times**. The three `returned` carry
  `allowed_set` (2) and `precondition` (1), which is §5.3.2 working.
- `constraints[]`: **6 parameters, all in the 4 simulation axis cards.**
- **Cards where both cover the same parameter: 0.**

**So this is not a §11-11 row.** There has never been a second copy, and
§11-11 counts copies with nothing comparing them. What is there is one schema
slot no card has used beside one that four cards use — and §5.3.2 made
`interval` one of the three things a `returned` inequality may carry, so the
unused slot is the *intended* home going forward while `constraints[]` is
where the simulation side puts them today. A convergence question, not a
duplication one. It needs no check. §11-16 should be closed as counted.

Verified and **fine**, so nobody re-reports it: `axis_bd_overdamped_a3.json`
carries `box_length` twice in `constraints[]` — `min 9 µm` from
`box_length_min_images` and `min 100 µm` from `box_length_min_dilution`. Two
lower bounds from two physical reasons on one parameter, which §4.5.3 calls
normal; the intersection takes 100. It looks like a duplicate from a distance.

---

## 2. A §8 row for KB entry units

`degC` is in the store and nothing looks. Counted twice, four hours apart, and
the second count is the one that matters: the librarian seat fixed `numbers[]`
fast — **60 KB numbers, 0 unregistered** — but **8 of the 42 `validity`
conditions that carry a unit are in `degC`**, all eight the polystyrene
refractive-index entries.

That is the librarian manager's own argument arriving as evidence. They said a
KB entry is not a card and gave `validity` intervals as the example; extending
check 2 is therefore the wrong shape, because its line reads `N numbers use
declared units` and folding the store in would make that sentence quietly mean
something else while still not reaching `validity`.

Suggested declaration, number architecture's:

> NN. **A KB entry's units are registered, wherever they appear.** Every unit
> in an entry's `numbers[]` and in its `validity` conditions resolves in
> `units.json`. The store is not covered by check 2, which reads cards, so an
> entry can hold a unit no card would be allowed to carry and the first card
> citing it inherits one. `degC` is the case that forced it: `units.json` does
> not merely lack it but argues against ever adding it — the registry is
> multiplicative, `si_factor` and `dim` express a scale and a dimension and
> neither expresses an **origin**, so a `degC` scaled like a `K` is wrong
> silently. Temperature is carried in kelvin and the Celsius reading goes in
> the note, as `lab_ambient_temperature` already does. `validity` is checked
> and not only `numbers[]` because the first fix reached the numbers and left
> eight conditions behind.

`manager-bridge` implements on the row, with fixtures, and not before —
implemented-and-not-declared is a check 42 FAIL and the gate runs the whole
validator, so it stops every session.

---

## 3. A §7 line for `contracts/history_fixtures.py`

The §11-7 history fixtures are written and firing 3/3 and cannot be committed:
check 13 needs the path declared in **both** §7 of `plan.md` and
`ALLOWED_PATHS`, and §7 is architecture's. (§7 was in `plan_ko.md` when this
was written; the design document came back to an English `plan.md` on
2026-09-20 and 003 records the move.) Full design, the held file's location and the suggested §7
text are in **`bridge/tasks/003`**.

---

**None of these is urgent and none is blocking anyone.** They are finished
work waiting on one seat, which is a different state from work in progress,
and the difference is worth a file because nothing else on disk records it.
