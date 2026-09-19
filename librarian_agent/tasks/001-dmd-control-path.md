# 001 — the DMD's control path is recorded backwards

status: closed · issued 2026-09-18 by manager-librarian · **closed 2026-09-19** (closing commit not recorded here)

## GOAL

`kb/staging/devices.v0.json` says the DMD is controllable via `pymmcore-plus`.
It is not. A preflight that opens it that way fails, and `automatable: full` is
true only of a core nobody has pinned.

## TASK

1. Correct the `dmd` channel. What the prior project's **run record** says
   (`~/Desktop/agentic-microscope/kb/decisions/2026-09-07-dmd-on-v71-and-blue-flip.md`,
   measured on the microscope PC):
   - `pymmcore-plus` refuses it — `MMCore requires 75; device adapter has 71`.
   - Raw `pymmcore` **pinned to device interface 71** loads it, and
     `DMD_dualcam_LUNF.cfg` then loads complete at **31 devices, DMD included**.
   - So the README claim "the one device that does not load" is true **of
     pymmcore-plus** and false in general. Record which, not just that.
2. Add the fact the registry never had: the DMD is **spectrally neutral**. It
   sets intensity and pattern across all wavelengths and selects no wavelength.
   A plan expecting it to pick a colour is wrong. Transmission loss through it
   is unconfirmed — a gap, not a zero.
3. Ruling and provenance, per §10.2.1: **transfer**, §10.3 rule 1, so **E3** —
   a run taken elsewhere is not a run taken here. Consumer: O1 preflight and
   the orchestrator.
4. Rebuild the index if `entries/` changed, run `python3 contracts/validate.py`,
   commit as `seat:librarian`.
5. Then ask manager-librarian, in one sentence: **what is not yet on disk?**

## CONTRACT

`plan.md` §10.2.1 (transfer / downgrade / discard, and name the rule passed),
§10.3 rule 1 (E3 cap), §4.3.2 (knowledge is yours, policy is not).

## CONSTRAINTS

The `agentic-microscope` repository is open; the other three are not. Read
narrowly — the one decision file above answers this task. Do not touch
`envelope/` or anything safety-shaped.

## REPORT

Three lines: the commit sha, whether the spectral-neutrality fact went in as a
claim or a gap, and the one-sentence clearing answer.
