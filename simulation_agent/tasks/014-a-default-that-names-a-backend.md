# 014 — a default that names a backend

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).
Found by `simulation-4` with trajectory hashes; confirmed here.

## The line

`src/operator.py`, twice — 641 and 732:

```python
"backend": getattr(backend, "NAME", mock_backend.NAME),
```

**The default names a specific backend.** A backend that does not carry `NAME`
does not produce an error or a blank: it produces the string
`"mock_backend"`, and the run record then says an engine answered that did
not. Both classes carry `NAME` today (`mock_backend.py:39,67` and
`hoomd_backend.py:59,220`) so it is correct right now. It was not correct at
01:31 on 2026-09-22, and nothing about the line prevents the next time.

## It already happened, and the evidence is no longer an inference

`run-20260922-hoomd-s1` says `mock_backend` in **both** `log.json` and
`config.json`. When this card's predecessor noticed it, the argument was that
the numbers disagreed with the label. `simulation-4` then re-ran both backends
at the same seed and compared trajectory hashes:

```
mock,  seed 1   sha=fd4e5d07…      run-20260922-mock-s1    sha=fd4e5d07…  log says mock    consistent
hoomd, seed 1   sha=4ba6f3b9…      run-20260922-hoomd-s1   sha=4ba6f3b9…  log says mock    NOT
                                   run-20260922-hoomd-s1b  sha=4ba6f3b9…  log says hoomd
                                   run-20260922-001        sha=4ba6f3b9…  log says hoomd
```

Seed, `parameters_si`, `plan_hash` and budget are identical across them, so a
mock run would have had to reproduce `mock-s1`'s trajectory and it reproduced
HOOMD's instead, bit for bit. **The same experiment also rules out the other
reading** — that `hoomd_backend` is a wrapper around the mock — because the
two hashes differ. Both halves matter and only one of them is about the label.

And the timing names the cause without needing it inferred: that run executed
at 01:31:54 and both backend files have mtime 01:34:00. **It ran on code three
minutes older than the fix.**

## What to change

**Remove the fallback.** A backend that cannot name itself is refused, the way
the operator already refuses a run it cannot ground. With no default there is
nowhere for the record to be quietly wrong.

This is the shape of `009` one turn further. There the log did not say which
*plan* it opened; here the log says, incorrectly, which *engine* answered. The
run is the evidence itself, so a run record that misattributes its engine
makes §4.6.5's definition of reproducibility — *the same `plan.json` runs
unchanged on the mock and on the real instrument* — **unverifiable**, because
a mock-versus-engine comparison only means something if which one ran is true.

**Do not start while a sweep is running.** `operator.py` is the runner, and
`simulation-2` is mid-sweep through it for the same reason `013` is waiting: a
sweep whose runs come from two code states cannot tell a seed difference from
a code difference.

## The mislabelled run is not yours to correct

`run-20260922-hoomd-s1` belongs to `simulation-2`. **Do not edit it and do not
delete it** — P1, and the deletion policy that landed today does not reach a
run record. What it needs is a `failures.jsonl` row from the seat that owns
it, saying what actually ran; the trajectory hash makes that statable rather
than arguable. Relayed to that seat separately.

Keeping the run is also what makes this card checkable later: `-s1` and `-s1b`
differ in the label and in nothing else, and that pair is the evidence.
