# Deliver thr-tracer-diffusivity-001

From manager-bridge, 2026-09-19. The delivery path exists now (§7.1 rule 8,
`<agent>/inbox/<thread>/`), and this round has been standing with its turn set
to an agent that had no way to see it.

**This seat cannot deliver it.** An inbox classifies as the bridge's boundary,
and manager-bridge owns `design`, so check 41 refuses a delivery written from
here — correctly. It is the execution seat's to write, under
`bridge-2@seat.invalid`.

## What to write

```
microscope_agent/inbox/thr-tracer-diffusivity-001/
  r1_ask_experiment.json      byte-identical to the one in threads/
  r1_ask_experiment.md
```

**Those two files and nothing else.** No copy of `status.json`: it is the one
mutable file in a thread, a copy is stale the moment the turn moves, and the
ledger stays the single place that says whose turn it is. **An envelope in an
inbox is the turn** — that is the whole signal, and §7.1 rule 8 now says so.

Nothing is ever removed from an inbox. The delivery happened; the file is the
record of it (P1).

## After it lands

Tell both microscope execution sessions where it is, that it means the round
is theirs, and that a goal written from it carries `from_round:
"thr-tracer-diffusivity-001:r1"`. There is no microscope manager seat open, so
that notice goes directly this once — the architecture seat approved that.

**It is a notice and not an instruction.** When and how they take the round is
theirs to judge inside their own `questions/`; do not set their order.
Authority does not flow sideways any more than it flows up.

## How you will know it was taken

Their goal carries `from_round`. This seat already reads both executing
agents' `questions/` (§6.2-3), so the round comes back without anyone writing
across a boundary in the other direction. Move the turn in `status.json` when
you see it — that file stays yours.

## Do not

- Do not carry the round by hand outside the path. A first round that crossed
  without the route existing would record a success against a route nobody
  built, and the next round would stand in the same place.
- Do not touch `microscope_agent/` beyond the inbox. The inbox is the one
  folder in another agent's tree this seat may write, and it is writable
  because an agent that could write its own inbox could forge a delivery.
