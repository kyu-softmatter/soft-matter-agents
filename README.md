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

## Where to look

| | |
|---|---|
| `plan.md` | the design, in Korean. Authoritative. Start at §0.1 for the fixed decisions and §2 for the principles |
| `CLAUDE.md` | the rules binding every session here |
| `ARCHITECT.md` | standing orders for the architecture seat only |
| `contracts/` | the only shared code: card schemas, the unit registry, the observable vocabulary, and `validate.py` |
| `<agent>/README.md` | what that agent is and what it does today |

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

Private research repository. The design is deliberately slower than it needs to
be in places where being wrong is expensive.
