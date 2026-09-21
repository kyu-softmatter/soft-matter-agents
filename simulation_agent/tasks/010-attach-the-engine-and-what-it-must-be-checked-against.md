# 010 — attach the engine, and what it may be checked against

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).
The person asked for the engine directly.

## The gate that was closed is open, and it was not the one this seat named

§9.2 rule 4 attaches the engine **only after the pipeline passes with
`mock_backend`**. It passed on 2026-09-20: the first result card in an agent
tree is `23c2838`, `result_run-20260920-003.json`, and it validates.

And the thing this manager called an open environment decision was **already
decided and already written down** — in `pyproject.toml`, in a comment under
`dependencies`. Measured rather than taken from it: HOOMD is not on PyPI
(`https://pypi.org/pypi/hoomd/json` returns 404), it ships through
conda-forge, so `uv sync` gets the pipeline and not the engine. That split is
deliberate, and §9.2 rule 4 is why it costs nothing: a machine with the
validator and the mock does all of M2's verification.

**The engine is therefore a separate install and not this repository's
problem — and on this machine it does not currently work.** `conda --version`
returns `__conda_exe:6: permission denied`, and there is no mamba or
micromamba. Platform is Darwin arm64. **Do not fix that and do not install
anything**: it is the person's machine, the failure is outside every boundary
here, and a seat that repairs someone's shell to get a package has left its
tree. Say so and stop, the way you would at any other wall.

**So write the module against the interface and leave the install to the
person.** The code is testable without HOOMD present — see the last section.

## The seam already exists

`operator.run()` takes `backend=` and defaults to `MockBackend(seed=seed)`, so
**nothing in the operator changes.** What the engine must offer is exactly
what the operator calls:

```
preflight(params)     apply(params)      read()       abort(reason)
mean_squared_displacement(...)           fit_diffusivity(max_lag_time)
block_uncertainty(max_lag_time)          NAME
```

plus the module-level `TERMINAL`, `COMPLETE`, `ABORTED`, `FAILED` the operator
compares `read()` against. `mock_backend` is a **first-class backend** (§4.6),
not a stub, so it is the specification: match its shapes, not your reading of
what they should be.

`block_uncertainty` is not optional and not a detail. `006` measured the fit's
own standard error as **41× too small** because the fit treats a hundred MSD
points as independent when every lag comes from the same trajectories. The
block estimate is what the first result card's error bar rests on. An engine
that returns the fit's error instead would quietly restore the defect the card
was built to avoid.

## What it may be compared against, and what would be circular

**Compare the engine to the analytic Stokes-Einstein, not to the mock.**

The mock's `2.128e-13` against the analytic `2.146e-13` — 0.8 per cent — is
already in `capabilities/simulation.json` as the reason `bd_overdamped`
declares `output_independent_of_input: false`. §5.3 says what that agreement
is worth: it **confirms the integrator and the estimator and says nothing
independent about any diffusivity**. Checking HOOMD against the mock would
compare two implementations of the same closed-form relation and call the
agreement evidence. It is the same circularity one layer out.

**And one seed is not a check.** All three runs on disk return the identical
`2.1277423745663242e-13` — one distinct value across three runs, because the
seed and the parameters are the same. Agreement at one seed says the code is
deterministic. Use several.

**Nothing crosses from a prior repository.** §10.3: no figure is pasted into
code, an extracted value is capped at E3, and safety limits never transfer.
A HOOMD integrator setting you recall from elsewhere is `operator_recall:` E5
at best and has no place in a module.

## Order

1. **Run revision 2 on the mock first.** It has never run — all three runs are
   revision 1, and `009` only landed the revision resolution yesterday. The
   engine has to reproduce the configuration the current plan declares
   (5 µm, 300 s, a 30 s window), not the superseded one (2 µm, 20 s, 2 s).
   Doing this first also gives the mock baseline at those parameters.
2. **Write `src/hoomd_backend.py`** against the interface above.
3. **Test it without HOOMD installed.** The import has to fail loudly and
   early rather than at `apply()`, and everything that does not touch the
   engine — parameter mapping, unit conversion into and out of SI, the MSD and
   block machinery if it is shared — is testable here today. `005` is the
   precedent for what happens when a backend change is not exercised.

## When it actually runs, tell me

`contracts/capabilities/simulation.json` carries `executed_by`
`{module: "mock_backend", ...}` because every run so far was the mock's, and
the `why` names the mock runs that back the independence declaration. **That
field becomes false the moment a HOOMD run lands**, and it is mine to change.
Report the first real run and I will move it — do not edit `contracts/`.
