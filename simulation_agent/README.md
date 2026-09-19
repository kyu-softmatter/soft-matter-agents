# simulation_agent

Turns a computational question into a parameter set that is stable, sampled
correctly and inside budget, and runs it under approval. The microscope agent
does the same job against an instrument; this one does it against an engine,
through the same five stages and a different list of axes.

**The cheapest simulation is the one not run.** S2 has three branches and the
second — *this is already known, hand it to the librarian and stop* — is worth
more here than on the instrument side. There it saves sample; here it saves
compute, and much of dilute Brownian dynamics has already been done by someone
else. An agent that exists to run things is the wrong thing to ask whether a
run is needed, so that branch is written into the stage rather than left to
judgement.

## What is different on this side

**It runs without the experiment.** A person's goal card is enough: a number
that wanted a measurement goes up as an assumption with `degraded: ["bridge"]`
attached, and the job proceeds. That independence is why this is a separate
agent rather than a mode of the microscope one, and it is also the thing to
watch — a seat with a legitimate way to proceed alone can miss a round that
arrived for it.

**A "configuration" here is a declared model.** On the instrument side it is an
optical path; here it is the physics. That makes *the model is not changed*
(§4.2) structural instead of advisory: this agent can only select a model that
`contracts/capabilities/simulation.json` already declares, and declaring one is
a write to `contracts/`, which no execution session can make.

**Six axes, and the hole in the numbering is kept on purpose.** A1 stability,
A2 statistics, A3 finite size, A4 sampling, A5 budget, A7 driving. There is no
A6 — spatial resolution is an imaging question. Renumbering to close the gap
would cost the thing the gap buys: **A7 means the same thing on both sides**,
which is what lets the bridge lay two a7 cards next to each other. The gap is
not a cost, it is the condition of correspondence.

**No orchestrator and no `devices/`.** One engine job has nothing to
coordinate, and symmetry with the microscope side is not a reason to add a
layer (§4.6.8). The operator sees one backend module.

**The refusal to expect is *not inside budget*.** Target accuracy against
compute is where this pipeline usually stops, and §4.2 fixes the shape of that
answer: work out what it would actually take, present that as a counterexample,
attach one relaxation option, and refuse. Emitting a plan that cannot meet the
target is the failure; refusing with numbers is not.

## The discipline that makes a result mean anything

**The convergence and steady-state criterion is declared in the plan, before
the run.** The operator evaluates it; it never chooses one after seeing the
data. Everything else here is ordinary engineering and this is not — a
criterion picked to fit the trajectory turns a converged result into a
restatement of the trajectory.

Three consequences, all of them things it is tempting not to do:

- **A diverged run is not deleted.** Divergence is a result.
- **Under-equilibrated output is labelled, not discarded.**
- **A quantity a criterion compares against is derived, never accumulated** —
  simulated time is the step count times the timestep, not a running sum. A run
  that finished exactly as planned once reported that it had not, because
  floating-point addition left the total a hair short of the boundary. The
  value was right and the decision it drove was wrong, which is what a
  comparison at a boundary always risks.

## Cost is this agent's; the ceiling is a person's

Predicted wall clock and storage are arithmetic over the plan's own parameters,
so this agent computes them. The limits they are compared against are policy
and live in `envelope/safety.json`, which **a person writes** (§10.3 rule 4). A
ceiling derived from what the job turned out to need is not a ceiling, and
§4.2's *does not submit an over-budget job on its own* would have nothing to
mean.

That file holds a list of execution targets with their own ceilings, so the
same plan can be sized for a workstation or a cluster. **It does not exist
yet.** Its shape is fixed by a schema in `contracts/`; until a person fills it
in, the operator resolves a ceiling, finds none, and refuses. That is the
correct behaviour and not a bug to route around — in particular, a limit
written into an instruction file is not a limit.

## Where to look

| | |
|---|---|
| `CLAUDE.md` | the standing orders: the four layers and what each one judges |
| `tasks/` | instructions from the manager seat, and why each was decided |
| `questions/<qid>/` | the goal, the axis cards, the synthesis, the plan |
| `runs/<run_id>/` | config, trajectory metadata, observables, log |
| `inbox/<thread>/` | rounds delivered by the bridge. Read here, written only there |
| `envelope/` | `safety.json`, the person's; `snapshot.json`, this agent's |
| `approvals/` | the person's, and the only folder a person writes into |
| `plan.md` §4.2, §4.5 | what this agent is, in full |

## Where it stands

Run the validator from the repository root and read its last line, which names
the tree it judged. No count is written in this file: several sessions share
this working copy, so a bare run is nobody's commit, and counts pasted into
prose here were wrong three times in one day.
