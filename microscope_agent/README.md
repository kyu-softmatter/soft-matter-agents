# microscope_agent

Turns a measurement question into an instrument configuration and an
acquisition that is detectable, sufficient, and inside what the sample and the
hardware will survive — then runs it under approval. The simulation agent does
the same job against an engine; this one does it against a bench, through the
same five stages and a longer list of axes.

**The instrument can destroy the thing it is measuring, and itself.** That is
the whole of the difference. P0 orders people, then instruments, then samples
and data, and on this side every one of those three is reachable by a command
this agent could emit. So safety here is interlock rather than judgement: the
decision is made by deterministic code and ambiguity stops instead of
proceeding (§2.1).

## What is different on this side

**A configuration is an optical path, and not all of them produce anything.**
Configurations carry a role. `imaging` declares observables; `perturbation`
drives the sample and declares nothing, because the trap light is blocked from
every detection path. A perturbation configuration is **composed onto** an
imaging one rather than screened against the observable — without that split
the contract asks the optical trap for an observable it cannot have (§4.5.3).

**Seven axes, and A6 exists because its absence was the evidence.** A1 signal
and noise, A2 statistics, A3 sample integrity, A4 configuration suitability,
A5 time stability, A6 resolution and field, A7 driving and motion. A6 appeared
when imaging became a first-class modality; while only the trap was assumed,
nobody missed it — **the hole in the axis list was the shape of the bias, and
that is why the list is fixed in `plan.md` rather than derived per question.**

**A7 is the only axis that asks what we do rather than what we see**, and one
inequality is why it is a single axis: `v_max ~ k·x_max/γ`, the escape
condition, ties the drive strength to the motion directly. Splitting drive from
motion would copy that inequality into two axes, and two copies of one
inequality always drift apart (§4.5.3 rule a).

**An orchestrator and a `devices/` folder, unlike the simulation side.** A run
here touches a stage, a nosepiece, a disk, shutters and two cameras, with an
ordering that matters: power up last and down first, z retracts before a turret
rotates, nothing acquires while the optical-path lock is held. That
coordination is what the orchestrator is for, and `devices/` holds the backends
behind one fixed interface — including `manual.py`, because **a device whose
state cannot be read back is not automated here whatever it was elsewhere**,
and a manual sheet blocks automatic commands to that device group entirely.

**The sample is consumed by the measurement.** It cannot be remounted, so
"repeat" is capped at one before any axis reasons about statistics, and a
mistake is not recoverable by running it again. This is a property of the
question rather than of the agent, and it changes what an abstention costs.

## Read-back is where this agent is most likely to be wrong

§2.1 rule 8 says a safety signal **can refuse and cannot permit**, and this
instrument is full of signals that look like permission:

- The tweezer's interface has no read-back of any kind, and returns `0` to a
  command it ignored — six distinct ways, all indistinguishable from success.
- A Micro-Manager write to the nosepiece runs **no objective escape**: z does
  not move, and the incoming objective arrives at the height the outgoing one
  was at. Rotating at the stand does run it. The software path does not.
- The same rotation silently invalidates two trap calibrations, neither of
  which is readable back.

So the first bound this fan-out ever returned was not a range at all. It was a
**precondition**: *establish the loaded state by acquiring an image, not by
reading a selector back; a plan that treats a returned position as a
verification is refused.* That is what an axis is for on this side.

## Abstention is the normal output, and it is not a backlog

Most bounds here abstain, and the store is nearly empty about this instrument.
That is recorded rather than smoothed: an axis states an interval or abstains
with a reason and a named missing input, and silence is refused (§4.5.2.1).
An axis that invented a number to avoid abstaining would be the failure.

Three kinds of gap close three different ways, and the card has to say which:

- **A person decides it** — a target accuracy is not a measurement and does
  not arrive by looking harder.
- **An acquisition produces it** — `tracer_brightness` and `bleaching_rate`
  for a new sample exist nowhere and cannot; one bare-particle run closes
  both, and it does not spend the one sample mount.
- **The store has it under another name** — an empty query is not evidence of
  absence, which is why `absent` may only be claimed after the neighbourhood
  was searched.

## What it inherits, and under what conditions

`agentic-microscope` is the one prior repository the person opened, and this
agent is where most of it lands — control paths, device rows, the objective
table. Nothing crosses as itself: each item is ruled **transfer**, **downgrade**
or **drop**, a transferred item names the A1–A7 slot it went into and the §10.3
rule it passed, and an item that cannot name a slot is dropped (§10.2.1).

**Safety limits never cross.** That project's laser readings sat in its own
safety document, load-bearing, and were retracted as a measurement error —
struck through rather than deleted, so the next reader meets the retraction
where they meet the number. Copying brings the number and leaves the
retraction behind, and that is the argument §10.3 rule 4 is made of.

## Where to look

| | |
|---|---|
| `CLAUDE.md` | the standing orders: the pipeline, the rulings, what the operator still owes |
| `tasks/` | instructions from the manager seat, and why each was decided |
| `questions/<qid>/` | the goal, the screening, the axis cards, the synthesis, the plan |
| `runs/<run_id>/` | config, frames metadata, observables, log |
| `inbox/<thread>/` | rounds delivered by the bridge. Read here, written only there |
| `envelope/` | `safety.json`, the person's; `snapshot.json`, this agent's |
| `approvals/` | the person's, and the only folder a person writes into |
| `src/devices/` | one backend per device group behind a fixed interface, `manual.py` included |
| `plan.md` §4.1, §4.5, §4.6 | what this agent is, in full |

## Where it stands

Run the validator from the repository root and read its last line, which names
the tree it judged. **No count is written in this file**: several sessions
share this working copy, so a bare run is nobody's commit, and counts pasted
into prose were wrong three times in one day.
