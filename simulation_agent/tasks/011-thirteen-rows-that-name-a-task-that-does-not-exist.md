# 011 — thirteen rows naming a task that does not exist

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).
Small, and blocking nothing. Take it between larger things.

## What

`check 29` counts, across all four trees, **20 records whose `task` resolves
to no task file**. Thirteen are this agent's. The check is **advisory** — it
reports and does not fail — because the rows are spread over three trees and
no one seat can clear them, and §8.1 records the expiry: **it becomes a
failure the day the last tree moves its own.**

`occasion` landed at `be21334` for exactly this. §8.1's rule: a record's
`task` resolves to a real task file, **or** `occasion` says what the work
came out of.

## Twelve move to `occasion`. One does not.

Run this to get the list rather than trusting the line numbers here, which go
stale the moment anyone appends:

```bash
python3 -c "
import json, pathlib
tasks = {p.stem for p in pathlib.Path('simulation_agent/tasks').glob('*.md')}
tasks |= {p.name.split('-')[0] for p in pathlib.Path('simulation_agent/tasks').glob('*.md')}
for i, l in enumerate(open('simulation_agent/failures.jsonl'), 1):
    if not l.strip(): continue
    r = json.loads(l)
    t = str(r.get('task') or '')
    if not t or r.get('occasion'): continue
    if t.split()[0].strip(':.,') not in tasks:
        print(i, t[:70])"
```

**Twelve of them never came from a queue** and that is the whole point of the
field — `session-boundary-self-report-…`, `librarian-mcp-absence-actual-cause-…`
(five rows), `deny-list-is-keyed-to-the-tool-…`, `red-tree-misdiagnosis-…`,
`thermostat-premise-for-…`. None of these is a card anyone handed down. They
are findings, and the field that forced a task id on them is why one of them
ended up as a whole sentence in an id slot.

**The thirteenth is different and must not be moved.** The row beginning
`008's measurement, confirmed from this seat by a different method` **did**
come from a card — `008` exists. It fails only because the id is a sentence
starting with `008's`, which does not resolve. That one keeps `task` and
shortens it to `008`. Moving it to `occasion` would record work that came
from the queue as work that did not, which is the error this field exists to
prevent, running backwards.

## Do not invent a taxonomy

`occasion` is free text saying what the work came out of. Write what actually
happened — *"checking a colleague's count"*, *"the tools went missing"* —
rather than a reserved token. The rows already say it in their `detail`; the
field just needs the short form. §8.1 chose free text over an enum
deliberately: an enum here would flatten exactly the information the rows
carry.

## When you are done

```bash
python3 contracts/validate.py 2>&1 | grep "check 29"
```

It should drop this agent's thirteen from the count. **It will not reach
zero** — the bridge has four and the librarian three, and the check stays
advisory until all three trees have moved. Do not chase the others' rows:
they are not yours, and check 35 says so.
