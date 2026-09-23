# soft-matter-agents

Four agents that design and run soft-matter experiments: a **microscope** and a
**simulation** agent that turn a research question into conditions and execute
them, a **librarian** that owns everything either of them knows, and a
**bridge** that carries cards between the two.

The point is not that a model proposes settings. It is that a proposal has to
survive a deterministic gate before it becomes a plan, and that **a refusal is
a result** — when the evidence for a value does not exist, the system says so
instead of inventing one.

## What holds it together

**Every number carries four parts** — value, unit, source, grade — and the
grade is derived from the source, never self-reported. A value a model made up
has a name (E6) and may not enter a card or the knowledge base.

**Safety is decided by code, not by a model.** People first, then instruments,
then samples. Ambiguity stops rather than proceeds.

**Files are the truth and sessions are volatile.** Agents are separate Claude
Code sessions that never talk except through cards on disk and read-only
queries to the librarian, so every transfer leaves a trace.

**A gate that refuses correct work gets bypassed rather than fixed.** That
sentence has been earned several times over, and most of the design's hard
edges exist to keep refusals aimed at the thing actually wrong.

## How it is laid out

A question enters one executing agent and leaves as a plan that a gate has
already accepted. Both executing agents run the **same five stages**; only
their axis list differs.

```
  [S1] the person's question
  [S2] refine it            LLM alone, forbidden to produce numbers
        |                   -> goal card. Or: already known -> hand to the librarian, stop.
        |                       Or: only a person can answer -> ask once.
   - - - - - - - - - - - - - - - - - - - - - -  the pipeline's sharpest line:
  [S3] axes, in parallel    a question may not enter here unspecified
  [S4] synthesis            trade-offs; the goal card says which way to yield
  [S5] the plan             identifiers, and the card a human approves
   - - - - - - - - - - - - - - - - - - - - - -  S3-S5 = the "system designer"
  [S6] execution            deterministic operator, safety in code
```

| | |
|---|---|
| `microscope_agent/` · `simulation_agent/` | the two that execute. Same pipeline, seven axes vs six |
| `librarian_agent/` | the only knowledge store. Answers read-only, and records what it could **not** answer |
| `bridge/` | carries cards between the two executing agents. Reads their `questions/`, writes their `inbox/`, and touches no number |
| `contracts/` | the only shared code: card schemas, units, the observable vocabulary, `validate.py` |

Each agent directory is self-contained on purpose: taking `microscope_agent/`
plus `contracts/` to the microscope PC has to be the whole move.

## How it is run

**Seats, in three tiers.** One **architecture** seat writes `plan.md`,
`CLAUDE.md` and `contracts/seats.json`. Four **manager** seats write the rest
of `contracts/` and their agent's instructions. Below them the executing
sessions do the work. Instructions go down, reports come up, and **the tiers
hold no extra permission** — the top two touch no instrument.

A seat is assigned by the person, never by another session. Each commit says
which seat made it through the committer identity, and `contracts/seats.json`
is the registry the gate reads.

**Milestones M0–M5 are bodies of work, not an order.** The four agents are
built concurrently; what actually blocks what is a column in `plan.md` §9, and
that column is the thing to read before picking up work.

**Everything lands through the gate.** `validate.py` runs on the tree a commit
would create, and a check that cannot yet decide says UNDECIDED or PENDING
rather than passing.

## Where to look

| | |
|---|---|
| `plan.md` | the design. **The record**, and the only one — start at §0.1 for the fixed decisions and §2 for the principles. It was Korean until 2026-09-20 and briefly a generated rendering of `plan_ko.md`; that split is over and the Korean text stays in history |
| `CLAUDE.md` | the rules binding every session here |
| `ARCHITECT.md` | standing orders for the architecture seat only |
| `contracts/` | the only shared code: card schemas, the unit registry, the observable vocabulary, and `validate.py` |
| `<agent>/README.md` | what that agent is and what it does today |
| `docs/` | a one-screen page for someone who will not open this repository. **Built, not published** — GitHub Pages is off, so this is source and not a site |
| `pyproject.toml` | **two manifests in one file.** `[project]` is the PyPI side; `[tool.pixi.*]` is the conda side, which is where HOOMD, `mcp` and `pymmcore-plus` live. The pixi tables state a different dependency set per platform, because Windows has no HOOMD build |
| `uv.lock` | the exact versions the PyPI side resolves to. Being handed over to `pixi.lock` and kept until that exists |

## Installing

**One command, on every platform.** `pixi` is itself on conda-forge, so there
is no piped installer to trust:

```
conda install -c conda-forge pixi
```

Then, from the repository root, pick the environment for the seat you are:

```
pixi install -e sim     # the simulation agent: adds HOOMD
pixi install -e mic     # the microscope agent: adds pymmcore-plus
pixi install            # everything else: the validator, the contracts, the librarian
```

**If a run says it found no HOOMD, that is the message doing its job.** The
simulation operator runs the mock backend when the engine is absent and says
so out loud rather than falling back quietly — a mock run is a valid run, and
an invisible one is not. What it asks for is one of:

```
conda install -c conda-forge hoomd      # macOS, Linux
pixi install -e sim                     # or, inside this repository
```

**Windows is different and needs its own route.** There is no HOOMD build for
Windows on any channel, so the engine cannot run on the Windows host at all.
It runs in WSL2, which is Linux:

```
wsl --install -d Ubuntu                 # PowerShell as administrator, then reboot
```

and then, inside Ubuntu, the same two commands as above. This splits the
machine rather than the project: **the microscope agent stays on the Windows
host**, where `pymmcore-plus` has a native build and the instrument is
attached, and **the simulation agent runs inside WSL2**. They are two
environments on one computer, and `pyproject.toml` states both.

`conda` itself has a quirk worth knowing here: inside a Claude Code session on
this machine the bare command fails with `__conda_exe: permission denied`,
which comes from the session's own shell snapshot and not from conda. Call it
by absolute path, or from an ordinary terminal.

## Running the gate

```bash
python3 contracts/validate.py                                    # the repository
python3 contracts/validate.py --strict                           # undecided and pending count as failures
python3 contracts/validate.py --expect-fail contracts/examples/rejected
git config core.hooksPath contracts/hooks                        # install the commit gate, once per copy
```

The first must end `0 failed`, and the last must reject every fixture — one
that stops failing means a check stopped working. **Read the counts off the
run and read the tree it names**; several sessions share this working copy, so
a bare run is nobody's commit.

## Status

Ask the run, not this file. Counts written into prose here were wrong three
times in one day, which is why there are none.

---

Public, and in development. The design is deliberately slower than it needs to
be in places where being wrong is expensive. This line said **private** until
2026-09-20, while the repository was public and being read by people the
sentence told to go away.
