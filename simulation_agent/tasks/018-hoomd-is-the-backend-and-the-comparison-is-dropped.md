# 018 — HOOMD is the backend, and the comparison is dropped

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).
**The person asked for this directly**: compute with HOOMD only, and the
mock-versus-engine comparison is not needed.

## What changes

`src/operator.py:556`:

```python
backend = backend or mock_backend.MockBackend(seed=seed)
```

**HOOMD becomes the default.** A run that names no backend gets the engine.

**And `010`'s comparison requirement is withdrawn.** That card told you to
check the engine against the analytic and never against the mock, and the
reasoning still holds for the analytic half — the engine is checked against
`D = k_BT/(3*pi*eta*d)`, which is what the three-seed and ten-seed sweeps did.
What is dropped is running the mock alongside to compare. There is no longer a
mock arm.

The sweep already said the comparison had stopped paying: at ten seeds each,
mock is 0.99973 ± 0.241 % and HOOMD 0.99964 ± 0.210 % against the analytic.
They agree to 0.01 per cent and neither is distinguishable from the closed
form. The three-seed run made mock look three times wider; ten seeds showed
that was sampling noise. **A comparison that cannot separate its two arms is
measuring the seed count.**

## What does NOT change, and this seat cannot change it

**The mock stays in the tree.** §4.6.5's first clause is not about
comparison:

> `mock` is a first-class backend. **The whole pipeline has to run with no
> hardware and no HOOMD**, and M2–M3's validation is done on the mock.

`pyproject.toml` rests on that sentence and says so: HOOMD is on no PyPI index
under any name, so `uv sync` gives the pipeline and not the engine, **and that
is acceptable only because the mock runs**. Removing the mock would mean a
fresh clone resolves a lockfile for a repository that cannot execute anything
— which is the person's own "easy to set up on another computer too"
requirement, broken.

So: **stop computing with the mock, keep the mock able to compute.** If what
was wanted is the stronger thing — the mock gone — that is §4.6.5 and §7 and
architecture's, and it is asked rather than assumed. Raised separately.

## Order

`015`, `016` and `017` are in the same two files and are one line each. Do
them first or fold them in, but **say which in the commit** — a default change
and a fallback removal landing together with no note reads as one change to
whoever bisects it later.

**And record what the first default-HOOMD run was**, because
`capabilities/simulation.json`'s `executed_by` already names hoomd_backend and
was moved on the evidence of runs that asked for it explicitly. The first run
that gets the engine *by default* is a different fact and this card would
rather it were written down than inferred.
