# 002 — four rulings from the prior project's run records

status: open · issued 2026-09-18 by manager-librarian

## GOAL

Four items were ruled under §10.2.1 on 2026-09-18 and have not reached the
store. Evidence and reasoning: `~/Desktop/librarian-verification-2026-09-17.md`,
sections V18 and V19.

## TASK

1. **TRANSFER — the DMD pairs with the Spectra.** The prior project drove
   Spectra → DMD → sample and measured excitation crosstalk per line with a
   pattern displayed. E3, §10.3 rule 1. Consumer: S3.0 and A4.
   **Close the risk, not the label.** V11.1 demoted the `inline`/`side` role to
   a gap because the geometry rests on one 2026-08-10 dictation that the dossier
   itself distrusts. That stays a gap. What is settled is that a
   patterned-illumination plan names the **Spectra** — which is what V11.1 said
   was at stake, and it does not depend on what the branch is called.
2. **TRANSFER — installed channel counts**, from the loaded device list:
   `Spectra III 8-NII-XS` and `Aura III 5-NII-WA`, so **8 channels and 5**.
   §10.3 rule 2 plus rule 1, E3. This settles the three-way conflict in V12: a
   distributor page claiming 3 for the Aura is wrong for this unit. **The
   wavelengths are not settled** — the icon-read list still disagrees with the
   datasheet's standard set on 7 of 8, so this is an 8-channel engine whose
   channel set is unread. Keep that as the gap it is.
3. **DOWNGRADE — the COM port map.** Spectra III on COM3 (`Model = GEN3`),
   COM4 is the piezo, COM8 is the LUN-F's USB-B port. A COM number is one
   integer that re-cabling falsifies silently — the same class as the detection
   port position this folder deliberately did not extract. Enter it with a
   `validity` naming the machine and the date, not as a stable fact. The half
   that does not rot is the **discriminator**: every Lumencor is FTDI, so a
   Microsoft CDC port is not one.
4. **HOLD — the per-line crosstalk numbers.** They attach to line labels, and
   the line labels are exactly what item 2 leaves unread. Record the hold and
   the reason; do not attribute measurements to channels nobody has read.
5. **Correction from V19**: "Nanobench 6000" is the vendor **GUI**, not a model.
   The piezo record names it as though it were hardware. It is the counterparty
   of `exclusive_with: [piezo_vendor_gui]` — the thing that holds COM4.
6. Index, validate, commit as `seat:librarian`.
7. Then ask manager-librarian, in one sentence: **what is not yet on disk?**

## CONTRACT

`plan.md` §10.2.1, §10.3 rules 1 and 2, §4.3 rule 6 (conflicts are kept, not
merged).

## CONSTRAINTS

**The piezo travel range is discarded and must not be fetched.** It exists in
the prior project as `0-600 um` — as the heading of section 3 of that project's
`SAFETY.md`. §10.3 rule 4 makes safety limits non-transferable, and §10.2 keeps
that row shut until a person has written `envelope/safety.json`. The reason is
not procedural: that project put the number in its safety document because it
was using it as a limit, and a travel range read as a permission is exactly the
failure the rule names.

Nothing here is E1. Everything crossing caps at E3.

## REPORT

Three lines: the commit sha, which of the five items did **not** go in and why,
and the one-sentence clearing answer.
