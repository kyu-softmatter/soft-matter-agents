# 016 — the seed fallback is 014 one line down

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).
Found by `simulation-4` while fixing `014`, in the same function.

`src/operator.py:679`:

```python
"seed": getattr(backend, "seed", seed),
```

**Same shape as the two lines `014` removed, and `014` looked at this one and
did not see it.** Both backends carry `.seed` today, so it reads correctly —
which is precisely the state `NAME` was in until 2026-09-22, when the first
HOOMD run recorded itself as a mock run.

**What it costs if it goes wrong is worse than the label was.** `config.json`
would record the seed that was **requested** and not the one that ran, and
`config.json` is the basis for reproducing a run. A false backend label is
visible the moment anyone compares trajectories; a false seed reproduces
nothing and says nothing, because the thing you would check it against is the
field itself.

Do what `014` did: no fallback. A backend that cannot say which seed it used
refuses. `014` extracted `backend_name()` and that is what gave the card a
condition testable by behaviour rather than by text — the same is available
here.
