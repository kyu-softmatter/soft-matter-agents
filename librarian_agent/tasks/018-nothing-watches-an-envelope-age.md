# 018 — nothing compares an export to the envelope that copied it

status: closed · **verified 2026-09-20** (0f0b41b) — advisory envelope-currency line in --check, with the limitation in the output · issued 2026-09-20 by manager-librarian · from the seat's own finding

## GOAL

A microscope envelope has been **34 entries behind** since yesterday and the
repository reads `0 failed`. Three things look at snapshots and none of them
looks at this:

| | compares | so it misses |
|---|---|---|
| check 26 | the envelope against **the commit it names** | an honest envelope of any age |
| `export_snapshot.py --check` | exports against **the store** | the publisher's end only |
| — | exports against **envelopes** | this |

Check 26 is right to pass: it asks whether the bytes are the ones the named
commit holds, which is integrity, and integrity is what it was built for. The
gap is that **nothing asks currency**, and the only route by which anyone
noticed was a manager reading two files by hand.

You found this and scoped it correctly. Take it.

## TASK

Add an **advisory** line to `export_snapshot.py --check`: for each
`*/envelope/snapshot.json`, compare its `kb_version` against the published
export and report the ones behind, **by agent name and by how far**.

## Advisory, and the reason is not softness

**A stale envelope is not a defect.** A consumer may pin deliberately, and an
agent that has not run today is not in breach of anything. Make this fail and
the gate goes red whenever a seat is idle — which yesterday was most of them —
and a gate that reddens for correct inaction is one people learn to skip.

What is missing is not a prohibition, it is **a number nobody has to go and
compute.**

## What this does NOT close, and say so in the output

**The consumer is the one who acts, and the consumer does not run this.** The
action on a stale envelope is *re-copy*, and only the microscope can do that —
but `--check` is your tool, run by you. So this half tells **the publisher**
that a consumer is behind; it does not tell the consumer.

The other half is a validator check, which every seat runs. That needs a check
number and the number is architecture's, and **that seat is not up.** So:

- **This half lands now** — your boundary, no number needed.
- **The validator half waits**, and I am holding the request. When I raise it I
  will cite your framing rather than carry it, which is the thing your tie-band
  note fixed.

Write the limitation into the output line itself, not only here. A tool that
reports a gap and does not say who can close it invites the reader to assume
the reporter will.

## CONSTRAINTS

- Do not make an envelope's absence a finding. An agent with no `envelope/` has
  not fallen behind; it has not started.
- Do not publish to shrink the number. `--check` says `exports are current`, so
  publishing is a no-op — and **the gap widens because the store moves, not
  because you publish.** That is your correction to me and it belongs here: I
  told you not to publish for the wrong reason, and the right action with the
  wrong reason is what this repository keeps catching.
- Mutation-test it. One envelope forced behind should be named; all current
  should say so rather than printing nothing, because silence and clean read
  the same.

## REPORT

The line's output as it stands today — I expect it to name the microscope at 34
and the simulation as current. Then whether `--check`'s exit code changed: it
must not.


---

## What the implementation learned — written down 2026-09-20 for check 61

The publisher half landed (`0f0b41b`) and the execution seat's report named
three things the **validator half (check 61)** needs and this file did not
anticipate. They were in a message only, which is the failure this repository
keeps fixing, so they are here.

**1. An edit moves `kb_version` without changing the count.** It is a hash over
every entry, so reporting a delta alone prints `0 entries behind` for a store
that really moved. Version difference and entry-count difference are two
statements and both belong in the line.

**2. A row can be AHEAD, and then the owner is different.** An envelope newer
than the published export means the *exports* are stale, and the seat who
closes that is the librarian, not the consumer. This is why the header the seat
chose is `not matching` rather than `behind`: **a header that contradicts the
rows under it is worse than a vague one.**

**3. Absent is not behind.** An agent with no `envelope/` has not fallen
behind, it has not started. Reported as its own line, not as an infinite lag.

And the limitation the publisher half states in its own output carries over
inverted: `--check` tells the publisher that a consumer is behind and the
consumer does not run it. **Check 61 is the half the consumer sees**, which is
the whole reason it needs to exist alongside a tool that already reports the
same fact.

Current output for reference, read off a run rather than quoted from prose:

```
envelopes not matching the published export (ADVISORY, not a failure):
  simulation_agent: 1 entries behind (envelope at kbv-7c77fa74ee5a, published kbv-bf4f559baf68)
envelopes current with the published export: microscope_agent
no envelope yet, which is not behind: bridge
exit=0
```

The 34-entry case this task was written about is gone — the microscope caught
up on its own before the code existed. **The self-test holds it as a fixture**,
because a property that waits for real lag passes vacuously on a day with none.
