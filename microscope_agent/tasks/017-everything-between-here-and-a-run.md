# 017 — everything between here and an end-to-end run

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Not assigned: this one is a reference, not work.** Every seat may read it; none should act on it without the card that names the step.

The person asked for the complete list. This is it, counted off runs on
tree `630724b`+ rather than recalled. **Re-run the commands before acting**;
several entries moved twice today.

## The shape of it

The pipeline is **not** the blocker. `screening.py`, the seven axes,
`synthesis.py` and `plan_card.py` all execute. S5's refusal is the stage
working, and it names its own causes:

```bash
python3 microscope_agent/src/synthesis.py --qid mic-20260918-001
python3 microscope_agent/src/plan_card.py --qid mic-20260918-001
```

What blocks a run is **inputs**, and they sort into five owners. Nothing in
the first three columns is this seat's to close.

## A. Closed by nobody — the false gaps (cards 014, 015)

These are recorded `absent` and are not.

| | where it actually is |
|---|---|
| `pixel_size_in_sample` | the store has `pixel_size`, and **A1 cites twelve of them in its own `kb_refs`**. Locus in the name (rule 1) |
| `tracer_diffusivity_expected` | in the store as a **derived quantity** with `computed:stokes_einstein` and no `numbers[]`. Use `kb_group`, not a value query |
| `refractive_index` | **landed today** — air and water at E3, `literature:`, keyed `identifiers.immersion` |
| `device_registry`, `control_channel`, `automatable_condition`, `optical_path_valid_tuples` | `in_published_table`. The seat is writing `read_published()` for exactly this |

**Seven of thirty-five, and none needed anyone.**

## B. A7's seven are `not_requested`, not missing

`trap_stiffness`, `total_optical_power`, `safety_power_limit`,
`minimum_trap_spacing`, `model_limit_offset`, `piezo_bandwidth`,
`piezo_settling_time`, `stage_max_velocity` — this question asks for no
trapping. **They are not blockers and no one should go looking for them.**
A safety ceiling does not unblock A7; the kind is `not_requested`.

## C. The person's, and only the person's

| | what it settles |
|---|---|
| `target_relative_error` | A7's floor and A2's `frame_count`. **Still owed** — the decade resolution settled on 2026-09-19 is a different thing |
| `required_lateral_resolution`, `required_field_of_view` | A6. These come off the goal card, not the store — how fine and how wide the measurement has to be is a property of the question |
| `focus_tolerance` | A5. How far focus may wander is a property of the measurement, not of the instrument |
| `session_time_budget`, `instrument_availability_window` | A5 |
| dilution factor | `tracer_number_density`. The vendor's 10 mg/ml is **stock**; what is under the objective is nowhere on disk and **no card has asked yet** |
| bead lot number | turns the diameter from `operator_recall:` E5 into `spec:<lot>` E3. Only the bottle has it |

## D. Closed by acquiring, not by asking — card 016

`tracer_brightness`, `bleaching_rate`, **and `background_rate`**, which comes
off the same frames and is not separately owed. `drift_rate` and
`sample_heating_rate` are two more short runs, not this one.

Card 016 is that acquisition. **It is the only path to a first run** and the
person has supplied its two numbers: 100 ms, 10%.

## E. The prior repository — and §10.2 row 3 opened today

That row waited on `envelope/safety.json`, **which the person wrote**
(`c1404bf`). It is open. I went and looked. **Numbers do not cross by my
hand** — §10.3 routes them through the librarian as graded entries — so what
follows is located, ruled, and handed over, not copied.

### The one that matters most, and it is not a number

**`lapp_branch_assignment` is answered, and the answer is a warning.** Our
registry says `widefield_source_a`'s branch is unconfirmed, and card 016
runs `widefield_inline`. The prior project has this:

> **The record was right; the `.cfg`'s labels were swapped.** Following it
> turned the light off and cost a diagnosis session, and the branch was
> booked as falsified for two days before the operator's 2026-09-05 mapping
> showed the mislabelled enum was the fault. `State 1` is the Aura position
> and **everything now pins the integer**.

**Ruled `transfer`, §10.3 rule 2, slot A4** (configuration fitness:
selector verifiability). What transfers is **the discipline, not the label**:
on that branch the enum name lied and the integer was authoritative. It is
also a `downgrade` on anything keyed by the label — a label that was wrong
there is not evidence here.

**This is why §10.2.1 exists.** Copying the label across would have carried
the exact defect that cost them two days.

### Located for the librarian, ruled, not copied

| item | ruling | slot / rule |
|---|---|---|
| camera read noise — **mode-dependent, three values** | transfer | A1 `snr_floor`. §10.3 rule 1, `prior_run:` E3. **Must be keyed by camera mode, not a single number** — same shape as working distance keyed by objective |
| quantum efficiency — a peak figure **and** a curve | transfer | A1. E3. The source's own note refuses to rescale the curve to the datasheet peak, *"would imply a precision neither source has"* — **take that note with it** |
| sensor geometry — array and pixel pitch | transfer | A6 `field_of_view`. E3 |
| full well, dark current | discard for now | no axis asks. `dark_e_per_s` is recorded there as an across-mode **maximum** used as a conservative bound, which is a downgrade already made |
| the `.cfg` file | **discard** | one machine's wiring at one moment (§10.2.1). Its facts already crossed — our registry rows carry `source: mm_config` at E3 |
| `20.078x` | already discarded | a nominal magnification wearing a back-derived precision. §5.3 refuses it and the registry records why |

**All of this is requested from the librarian, with locations.** None of it
is in this repository by my hand and none should arrive except as entries.

## F. What only a person at the instrument can do

- **Load a Micro-Manager configuration.** `devices/micromanager.py` refuses
  until one is: *"a person loads one"*. Nothing here can supply it, and the
  prior project's must not be copied
- **Confirm the Lapp branch on this bench** — after the warning above, by
  the integer and not the label
- **Commit `envelope/safety.json`**, which is still modified in the working
  copy

## The order

1. **014 and 015** — false gaps. Cheapest, and 68 lands behind 015
2. **016** — the pre-measurement. Mock first; that is M1's own wording and it
   needs no instrument, no approval and no MMCore
3. the librarian's entries arrive; **re-derive `mic-20260918-001`**
4. the person's column C; the real measurement

**Steps 1 and 2 need nobody outside this agent.** Start there.

## Done when

```bash
python3 contracts/validate.py
python3 microscope_agent/src/synthesis.py --qid mic-20260920-001
```

`0 failed`, a run log under `microscope_agent/runs/`, and S4's unbounded
count lower than it was. **Read every count off the run.**
