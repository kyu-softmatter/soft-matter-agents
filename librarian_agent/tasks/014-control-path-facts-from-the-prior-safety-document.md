# 014 — control-path facts and open questions from the prior SAFETY.md

status: open · issued 2026-09-19 by manager-librarian · authorised by the person

## GOAL

The person opened `agentic-microscope/SAFETY.md` (416 lines, 11 sections) and
ruled on what crosses. It splits three ways and only two of them come here:

- **Control-path facts** — how a device is driven, what it reports back, what
  it does not. §10.2's *hardware control path* row is **open** (✔) and says in
  its own rule that it **does not wait for `envelope/`**, because wrapping a
  control path needs no safety limit. **Bring these.**
- **Open questions** — things the prior project knew it had not measured.
  These are absences, so they are gaps and not entries (see 011). **Bring
  these as gaps**, not as claims.
- **Safety limits** — numeric limits, forbidden devices, permitted ranges.
  §10.3 rule 4: **not transferable.** The person writes `envelope/safety.json`
  after confirming physically, and the prior document is reference material
  for them, not a source for us. **Do not bring these, in any form.**

## What is there

Sections, so you can find them rather than take them from me:

| § | what it is |
|---|---|
| 0 | return code 0 means the GUI accepted the command, not that it happened; the Tweez 300 TCP interface has **no readback of any kind** |
| 1 | the Class-4 1064 nm trap laser, **Aresis Tweez 300** — the person confirmed this model name today |
| 1b | LUN-F XL confocal lasers, reachable only as blanking on NIDAQ digital lines |
| 2 | objective/coverslip collision, called the worst irreversible risk |
| 3 | the piezo stage, and a device described as forbidden |
| 4 | camera ownership — PVCAM hands a Kinetix to one process at a time |
| 5 | the two turret shutters are in series |
| 6 | sample exposure; light off by default |
| 7 | data-integrity hazards that look like results |
| 8 | the running procedure |
| 9 | open safety questions |

## Two places the split is subtle — rule these, do not skip them

1. **§3's forbidden device.** That a particular analogue line is cabled to the
   piezo is a **control-path fact**. That it is *forbidden* is a **policy**,
   and policy is `envelope/safety.*`, which §4.3.2 says is not knowledge.
   The first may cross; the second may not. If you cannot state the first
   without the second, that is a signal, not an obstacle — say so.
2. **§7's `PixelType` reporting 12-bit for 16-bit data.** This reads like a
   data hazard and is a **device fact about what a driver reports**. It is
   also exactly the shape this repository keeps finding — something written
   down that says one thing while the system does another — so it is worth
   crossing on its own merits.

## §10.2.1 applies to every item, and you know this drill

Each item is ruled **transfer / downgrade / discard** before use, and a
transferred one **names the slot it went into and the §10.3 rule it passed**.
The slots available are A1–A7, the orchestrator's four functions, O1
preflight, a contract field, and a KB entry — the 2026-09-18 correction that
this seat raised. An item that cannot name one is discarded, and
`hardware/*.py` observations about the prior project's own code have no slot
here.

Numbers cap at **E3** (§10.3 rule 1), vendor values cite the device document
rather than the old repository (rule 2), and **nothing comes out of prose**
(rule 3).

## TASK

1. Enter the control-path facts. The device table already has `automatable`
   and `read_back` columns — the Tweez 300 is a `read_back: false` row, and
   §0 is the evidence for it.
2. Record the open questions as gaps. §9 names the Z retract direction as the
   most consequential, and the trapping height as unknown.
3. Rule each item and say which of the three it was. A discard is a result.

## CONSTRAINTS

- **The laser's entry is 013 and comes first** — the person's own statement,
  `operator_read:`, with `Aresis Tweez 300` now confirmed as the model. Do not
  file the laser from the prior document instead; §10.3 rule 2 sends a vendor
  value to the device document, and the person's direct statement outranks a
  second-hand one either way.
- **Do not carry a single numeric limit**, not even as context inside a claim.
  If a control-path fact seems to need one to make sense, the fact is written
  wrongly — rewrite it without.
- Adding table rows moves the snapshot hash and the microscope re-copies.
  Publish from a committed tree and tell me.

## REPORT

Counts by ruling — transferred, downgraded, discarded — and for each transfer
its slot and rule number. Then the one thing I want named explicitly: **what
you found that is a safety limit and left behind.** A discard list nobody
writes down is a discard list nobody can audit, and this is the category where
that matters most.
