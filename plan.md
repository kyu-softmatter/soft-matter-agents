# plan.md — four-agent research system, redesign

> Status: draft v0.2 (2026-09-16) · Scope: **design principles and boundaries only**. Implementation detail is not settled here.

---

## 0. Where this document sits

- This document fixes only **what will be built and what will not**. Function names, libraries and prompt wording are not decided here.
- Rule for changes: when an implementation conflicts with a principle (§2), **the implementation is what gets fixed**. Changing a principle means editing this document first and leaving the reason in the same commit.
- Language convention: **everything inside the repository is written in English** — code, schemas, comments, commit messages, agent instructions (`CLAUDE.md`, skills).
  **The design document is the one exception, and as of 2026-09-20 the shape of the exception changed**: the document of record is `plan_ko.md` (Korean), and `plan.md` is **the English rendering generated from it**. Work happens in `plan_ko.md`. Where the two disagree, the Korean wins — the same shape as JSON beating Markdown (P3), and for the same reason: **one document of record means one place to fix.** `plan.md` carries `generated-from: plan_ko.md sha256:<hex>` in its head, and `contracts/hooks/pre-push` recomputes that hash and refuses the push when it no longer matches. The hook does **not** translate — that needs a model and P0 puts no model in a gate, so what deterministic code can do is compare and refuse. **Why it changed**: the repository is public and most people opening this document for the first time do not read Korean. Moving the document of record into English instead would mean **the person doing the design loses their own language** — so the record is written in the language it can be written most precisely in, and the read side is generated.
- The four prior repositories (`agentic-microscope`, `Brownian-Dynamics-Agent`, `librarian-agent`, `sim-exp-bridge`) were **deliberately not consulted**. §10.2 states when consulting them becomes permitted.
- Mirrors and summaries of those repositories fall under the same ban — neither their contents nor **their filenames** are used in this design. The rule lives in `CLAUDE.md`.

### 0.1 The settled foundational decisions

| # | Decision | What it says |
|---|---|---|
| D1 | Repository shape | **A single monorepo.** The four agents are packages inside one repo, and the contracts (schemas) and unit conventions are version-controlled in one place. |
| D2 | Execution runtime | **Centred on Claude Code sessions.** Each agent = a directory + `CLAUDE.md` + directory-scoped skills + subagents + hooks. Only the deterministic parts drop down into thin scripts. |
| D3 | Inter-agent communication | **File/git-based asynchronous cards.** Schema-fixed JSON (plus Markdown for people) is exchanged, and the commits become the audit log. |
| D4 | Execution permission | **A staged gate**: proposal (autonomous) → validation (code) → approval (human) → execution (logged). Dangerous actions are separated by tier (§6). |
| D5 | Standalone operation | **Each agent works on its own.** A person can call any one of them directly, and with the others absent it proceeds in reduced mode and records in the card what was missing (§3.1). |
| D6 | Internal pipeline | **The two executing agents use the same five-stage pipeline**: question refinement (S1–S2, LLM alone) → **system designer** (S3–S5: parallel independent per-axis analysis → synthesis and trade-offs → output) → approval → **system operator** (S6: preflight → dispatch → watch → record) → backends (HOOMD-blue / hardware). §4.5–4.6. |
| D7 | Unit of record | **The card's record is physical units** (µm·s·pN·K·k_BT). Dimensionless numbers are **derived**, and which group to use is not a fixed list but is **looked up in the librarian's KB or defined on the spot** (§5.7). Reduced-unit conversion happens only inside a backend. |
| D8 | Approval granularity | **Two kinds of approval card**: a single plan (`plan_approval`) and a condition range (`scope_approval`). A scope approval must carry an expiry and a count ceiling, and it destroys itself the first time a deviation appears (§6.1). |
| D9 | Librarian interface | **The librarian is implemented as an MCP server.** Subagents query it directly without a file round-trip. **Only read tools are exposed outward**; distillation and archiving happen only inside the librarian's session (§4.3.1). |
| D10 | One knowledge store | **All knowledge is owned by the librarian.** No other agent keeps a knowledge store of its own; what it needs it holds only as a copy (a snapshot) (P14, §4.3.2). |
| D11 | Session boundary | **One agent = one Claude Code session.** They are always split four ways, and one session does not simply change scope. The session boundary is the permission boundary (§6.2). |
| D12 | Instruction and reporting tiers | **Three tiers.** Architecture (writes the structure) → manager (revises each agent's design) → the four agents (do the work). Instructions go down and reports come up. A tier does not add permission — the top two are Tier 0 (§6.2, §6.2.1). **Worktrees were introduced on 2026-09-18 and reverted the same day** (§6.2.1). |

### 0.2–0.4 What the contracts found in the design

The three subsections are one series. Every time a contract was written, a lie in the design surfaced, and the place it surfaced is recorded per milestone — M0 (§0.2), M1 (§0.3), the M4 wire (§0.4). The numbers are fixed because references point at them.

### 0.2 M0 — the card contracts

Writing a contract exposes the design's lies. Five came out of M0, and every one of them was folded back into this document:

1. **P2 said three-tuple while §5.3 said four.** The grade is an input to the §6 gate and to checks 21 and 22, so §5.3 was right and P2 was stale.
2. **§5.2 had no `card` and no `qid`.** The validator has to pick a schema **without trusting the filename**, and it has to group by question.
3. **An approval binds to the plan's hash, and without excluding `status`** the approval invalidates itself the moment the state moves to `APPROVED`.
4. **There was nowhere to put approval cards.** A `scope_approval` spans several questions, so `questions/<qid>/` cannot hold it → `approvals/`, and the writing party is separated by folder.
5. **There was no rule for a number moving between cards.** A moved number points at its source card through `origin`, and the validator confirms it **by comparison, not by recomputation**. Re-deriving an already-validated value somewhere with fewer inputs is not validation.

### 0.3 M1 — the microscope execution layer

Actually trying to fill in `capabilities/` produced three more:

1. **The contract could not express an optical trap.** `capabilities.schema.json` requires **at least one** observable per configuration, and a trapping configuration has no detector — the trap light is blocked on every detection path, so it produces nothing on its own and is layered on top of an imaging configuration. Expressing it would have meant inventing an observable that does not exist. Fixed by giving a configuration a **role** (`imaging` / `perturbation`) (§4.5.3).
2. **There was a schema and nobody checked it.** The validator collects as cards only the JSON that carries a `card` field, so `capabilities/*.json` sat there having passed no check at all — a contract nothing checks is not a contract but decoration (P4). Capabilities are now checked the way check 1 checks a KB entry.
3. **The rule "the two tables are the same table" had no check.** §4.6.7 merely declared it, and nothing stopped the two files from diverging. Made into check 38.

1 and 3 surface **only at the moment the table is filled in**. While it stays a skeleton, neither of them is wrong.


**The fourth (2026-09-18) — `degraded` was asserting the opposite of the fact.** The first three surfaced **while writing** a contract; this one is a case where **the contract was already right and the code filled that field with the inverse of its meaning.** So neither the schema nor a check could stop it.

`screening.py` put the librarian into `degraded` only when it could not pin `kb_version`. But that function reads `kb/index.json` **directly, as a file.** When the store reads cleanly the result is `degraded: []`, and that is a claim that **"the librarian answered"** — when no gap detection, no conflict detection and no external search happened. **And M1's completion condition is exactly that field** (§9.1). The cards made that day were reporting the condition as already met.

**The validator could not catch it, and why it could not is the point of this entry.** Nothing in the card distinguishes a file existing on disk from a service having answered. The microscope session found it **by reading.**

**The same shape lives elsewhere.** Every seat holding code that reads the store directly is a candidate — anywhere a successful file read looks like a running service.

**A check that catches half is not added.** "If `degraded` is empty then one of `kb_refs` or `kb_gaps` must be filled" catches exactly one card in the ordinary sweep (a `plan_approval`, a legitimate exception since a person writes it), but under `--expect-fail` it **attaches a second failure reason to seven flat fixtures.** Then the original check can break and the card keeps failing, which is the state §11-7 exists to prevent. And the real case — code that fills `kb_gaps` faithfully while wrongly emptying `degraded` — passes that check untouched.

**The honest check is to compare against the log, and that is now possible.** The MCP server stood up for real on 2026-09-18 (`a9df017`), and every response is recorded in `queries/log.jsonl` with its `caller_id` (§4.3.2). Then `degraded: []` becomes a claim that **the log must carry an entry under that `caller_id`.** That the log file does not yet exist is itself the statement that **every card up to today is on the degraded path**, and that is the first baseline to compare against.

### 0.4 M4 — the bridge wire

Writing the bridge's wire contract produced six more. Not one line of bridge code exists yet:

1. **The gate was boolean.** `answerability` and `unit_consistency` could only be true or false, so the bridge had to write something the table had not yet said as either "cannot produce" or "possible" — both of which manufacture a fact that does not exist. Fixed to three values, and that split **refusal (which carries a counter-example number) from holding (which passes the turn to a person).**
2. **Producibility was self-reported.** Check 21 asks whether a grade follows from its source, and the bridge gate had no equivalent — if the envelope wrote `producible: true`, that became the fact. Now the validator recomputes it from the vocabulary and the capability table, and **refuses when the card claims more than the table does.**
3. **The envelope's hash proved only itself.** `payload_hash` says "the envelope agrees with itself", and a bridge that altered a number could alter the value and the hash together. Only when `r<N>_hashes.json` records the sending side's **original card** along with its revision does "the card received = the card sent" become a check at all.
4. **`status.json` and `r<N>_hashes.json` are not cards.** They have no numbers, no grades and no `qid`. But the validator collects only JSON carrying a `card` field, so those two could hold a schema and still pass no check — the same failure as §0.3-2. They are split off by an `artifact` field so that check 1 checks them and `--expect-fail` counts them too.
5. **The bridge's Markdown cannot echo the payload's numbers.** The envelope's `numbers[]` is empty, so check 9 refuses every number in the Markdown. It looked like an awkward constraint at first and is exactly right — a carrier that rewrites a value makes the same quantity live in two places (P3).

6. **One declaration had two parsers.** `capabilities/microscope.json` declares in the composite form `{"id": ..., "requires_composition": [...]}`, check 38 read that, and check 8's derivation compared strings only. **An observable the table says is producible derived as `no`.** And that `no` blocked the bridge completely — with a derivation of `no`, check 8 demands a refusal card, a refusal card demands a counter-example number, and there is no counter-example when the table says it is producible. There was no card that could be written, and forcing one **puts an impossibility nobody established into the ledger.** The bridge seat reported it and it was fixed by sharing the normalisation.

   Two rules come out of this. **One declaration, one parser** — two consumers that do not share a normalisation will diverge eventually, and the one that diverged does not raise an error, it **quietly says something false.** And **do not derive impossibility from silence** — the `populated` table was turning "nobody attached this name" into "cannot be produced", so one card failed for two reasons and one of them was a false statement. A name absent from the vocabulary is now `undeclared`, not `no`.

1 and 2 did not surface in M0. **While not a single envelope exists, the gate cannot be the wrong shape** — check 8 was `N/A` until then. 6 is the other side of that: it surfaced the moment an envelope existed, and **what was blocked was not the gate but the side trying to write a card that could pass it.**

---

## 1. What is being built

In one sentence: **a system that, once "what to measure or compute" is settled, designs the conditions under which it can actually be obtained, executes them under approval, and hands them to the other side (experiment ↔ simulation) in a form that can be verified.**

This system does not choose research topics. It only does **the work of translating a given goal into executable conditions.**

**The measurement target is not fixed.** Which experiment will arrive is an open question, and **proposing the system configuration that suits that experiment is the goal.** So the microscope agent's output is not "parameters for a settled configuration" but **"which configuration to measure with, plus the parameters within it."** It is not designed on the premise of a particular modality (optical trap, widefield fluorescence, confocal, DMD structured illumination, …).

### 1.1 Success criteria (in a measurable form)

- **S1** A goal thrown out in one sentence by a person → a machine-readable execution plan. Every number in the plan carries a unit and a source.
- **S2** The validator passes the plan. Count of numbers without a source = 0.
- **S3** An approved plan is executed, and the plan can be reconstructed from the execution log alone.
- **S4** A result from one side is compared on the other side as **the same observable**. Unit and non-dimensionalisation conversions are checked by code, not by prose.
- **S5** Asking the same question a second time is faster through KB reuse, and does not contradict the first answer.
- **S6** When a goal admits more than one possible configuration, **the reason for the chosen one and the discarded ones is left in the plan as numbers.**

### 1.2 Failure criteria (if this shows up, the design is wrong)

- A number comes into being that exists only in prose and that nobody checks.
- The round trip passes three rounds while the observable's definition shifts subtly each round.
- A person repeats the same safety confirmation by hand on every execution.
- A failed execution or run quietly disappears.
- A safety judgement enters an LLM path.
- Where a number came from is written down but **how much it can be trusted** is not.

---
## 2. Design principles

| # | Principle | Why | If broken |
|---|---|---|---|
| **P0** | **Safety comes first — people, then instruments, then samples and data.** Where it conflicts with every other principle, **P0 wins.** A safety judgement is always made by deterministic code, and ambiguity stops (§2.1). | This system causes irreversible physical action. Other principles can be got wrong and redone; this one cannot. | A person is hurt or an instrument is destroyed. Every design decision after that is meaningless. |
| **P1** | **Files are the truth, sessions are volatile.** All of an agent's state is on disk. | Sessions drop and context gets summarised. | Nobody knows today the condition that was agreed yesterday. |
| **P2** | **Every number is a four-tuple (value, unit, source, grade).** Without a source it is not a number; without a grade there is no knowing how far to trust it (§5.3). | A physical quantity means nothing without a unit, cannot be reproduced without a source, and cannot be gated without a grade (§6). | A figure a model made up plausibly becomes an experimental condition. |
| **P3** | **Prose is for explaining, contracts are for machines.** When the same number is in both Markdown and JSON, **the JSON is the record.** | A sentence that cannot be checked becomes false with time. | The document and the actual execution diverge. |
| **P4** | **The model only judges; the code checks.** The validator is deterministic. | Make a model grade its own output and the pass rate goes straight to 100%. | The gate becomes decoration. |
| **P5** | **A refusal is a first-class output.** An impossible request is refused with "why it is impossible" and **a counter-example number.** | Forcing work that cannot be done produces quietly wrong data. | An unrealisable plan travels all the way down to the instrument. |
| **P6** | **One agent = one responsibility = one directory = one permission set.** | Auditing is possible only when permission and responsibility share a boundary. | The bridge optimises conditions and the librarian designs experiments. |
| **P7** | **Dependencies run one way.** The librarian calls nobody (pull-only). The bridge creates no content (transport-only). | Circular calls produce infinite round trips and no located responsibility. | Nobody knows who decided that number. |
| **P8** | **Execution passes through the gate.** Proposal → validation → approval → execution. The gate cannot be skipped. | Instruments and samples are not reversible. | One typo becomes hardware damage. |
| **P9** | **Logs are append-only.** A correction is a new revision (`r1`, `r2`, …), never an overwrite. | What changed and when is the experimental record. | Bias cannot be traced. |
| **P10** | **Scope shrinks by default.** A new capability has to pass "is this needed for the question in front of us" to get in. | This is the reason the previous structure grew. | It becomes a general-purpose workflow engine again. |
| **P11** | **Each agent is complete on its own.** Collaboration only adds capability; it is not a precondition for working. | An experiment cannot wait for a simulation, and a simulation cannot wait for instrument time. | One stops and four stop. |
| **P12** | **The output tree is flat, per question.** Every file of one question in one folder, no per-stage folders, rounds and revisions as filename prefixes (§7.1). | Outputs accumulate without limit and are not deleted (P9). People look things up by "that question". | Three months later you are grepping through your own experimental record. |
| **P13** | **Code is disciplined by dependency direction, not by file count.** Agent code gathers in one `src/`, dependencies run one way, sibling imports are forbidden (§7.2). | A ceiling on file count does not discipline a design, it gets pushed aside by it — which already happened once in this document (4 → 5). What holds the structure is the dependency graph. | Fixing one device breaks another. |
| **P14** | **Knowledge lives in one place only.** The librarian is its sole owner, and every other agent holds only a **copy** carrying a source id and a hash. A copy cannot correct itself (§4.3.2). | The same fact in two places soon becomes two different values. Nobody knows which is right. | Each agent plans with a different viscosity. |
| **P15** | **Do not manufacture false precision.** A computed value's significant figures follow the worst precision among its inputs, and once an estimate is mixed in it speaks **in orders of magnitude only** (§5.8). | The default purpose is exploring a system nobody understands. An estimate written to three digits is not information, it is an illusion. | A condition is chosen with a value whose order of magnitude is unknown, and it looks like a precise decision. |
| **P16** | **Learning reorders candidates; it does not delete them.** A lesson rests on an actual record (E1·E2) and lives with a falsification condition and a case count (§8.2). | A deleted candidate accumulates no data and is disadvantaged forever. That is how bias fulfils itself. | The system repeats whichever configuration worked the first few times and calls that learning. |

### 2.1 The safety rules (P0)

P0 is not a slogan but **a list of enforced rules**, all of them enforced by code. **The count is not written here** — three were added on 2026-09-19, and until that day this sentence said "seven". Count the list.

1. **Safety is an interlock, not a judgement.** An action that can endanger a person or an instrument is not placed on an LLM judgement path (§4.6.1). Every safety limit lives in `envelope/` as a machine-readable value under Tier 3 protection.
2. **Ambiguity stops (fail-closed).** When state cannot be read back, when the evidence grade is insufficient, or when the validator cannot decide, the default is **stop, not proceed**.
3. **Irreversible actions take E1–E3 evidence only.** When a value resting on `E4` (computed) or `E5` (estimated) enters as a parameter of an irreversible action, it is not covered by a `scope_approval` and **an individual human approval is forced** (§5.3, §6.1).
4. **Power goes up last and comes down first.** A command raising a light source or laser output is at the very end of a parallel set; a command lowering it is at the very front. An abort begins with cutting output (§4.6.8).
5. **While a person has hands on the instrument, automatic commands are forbidden.** With a `manual` instruction sheet open, the orchestrator issues no command at all to that device group. The lock releases only when a person's confirmation closes the sheet — this is lockout/tagout in software (§8, check 23).
6. **A safety-related failure is not papered over by a retry.** Retries happen only the number of times the plan states, and a failure on a safety interlock gets zero.
7. **Nobody may exceed a safety limit.** Not the plan, not a `scope_approval`, not an individual human approval may exceed the safety limit in `envelope/`. Changing the limit itself is Tier 3 (forbidden), and requires a person to confirm physically **outside** the system and then edit the document.
8. **A safety signal can refuse and cannot permit.** Even when an interlock or a state read returns a value that reads as "fine", **that is not used as grounds for proceeding.** One value covers several worlds — a configuration that sensor cannot handle, a state where something that should be present is missing, and a genuinely safe state **all read as the same value.** Information flows one way: if the signal says "danger" that is a fact and **it stops**; if the signal says "fine" that means **that sensor did not see a danger**, not that there is none. This is the place rule 2 (stop when it cannot be read back) does not cover — here it *is* read back, and the value read is asymmetric. **Permission always has to come from something else**: a limit in `envelope/`, a human approval, or a deterministic check that says the configuration is allowed.
9. **An opt-in guard is not a chokepoint.** If a safety check only runs because **the caller chose to call it**, it is not protection but **a convention.** If another path touching the same device can reach it without passing that check, that path is the reality and the check is decoration. **A guard goes where there is no way around it** — where the command actually leaves, which is the driver side (P4, §4.6.1). And where the way around cannot be closed, **write down that it cannot be**: on 2026-09-19 this repository met the same thing three times — a deny list that resolved against the session root and blocked nothing, a `--no-verify` that walks past the gate without a trace, and the case that produced this rule. **All three had protection written down with a door open beside it.** §6.2 flipping that day to "what enforces is the commit gate, and the settings file states" is one instance of this rule.
10. **Loading saved state is a command that turns output on.** When a configuration, template or project file carries output state, loading it **turns output on with no output command.** Rule 4 (power up last, down first) is bypassed entirely — because there is no command to order in the first place. So **a configuration that gets saved is saved with output off**, and loading is treated as an output-raising action and placed inside rule 4's ordering. Whether a state-restore path can carry output differs per device, so **the device registry has to say so** (§4.6.1).

**Safety is not item 1 on a priority list; it is a constraint outside the list.** The moment it goes on the list it looks exchangeable.

---

## 3. System overview

```
                        the person (researcher)
                   goal ↓        ↑ approval / refusal
        ┌──────────────────────────────────────────┐
        │                                          │
  ┌─────┴─────────────┐                  ┌─────────┴─────────┐
  │ microscope agent  │                  │ simulation agent  │
  │ condition design  │                  │ parameter design  │
  │ + execution       │                  │ + execution       │
  └─────┬─────────────┘                  └─────────┬─────────┘
        │  plan / result cards                      │  plan / result cards
        └──────────────┐          ┌─────────────────┘
                       ▼          ▼
                  ┌──────────────────────┐
                  │ bridge               │  transport · unit-mapping checks
                  │ (may author nothing) │  round / hash management
                  └──────────────────────┘

        ▲ pull                                        ▲ pull
        └──────────────  librarian (knowledge) ───────┘
              entries / distilled / sources — the system's only knowledge store
              exposed as an MCP server (read-only, stateless)
              (never speaks first, answers only on request)

  ※ the person can call any of the four boxes directly (D5, §3.1).
```

- **Horizontal axis**: experiment ↔ simulation. They touch only through the bridge. Direct reference is forbidden.
- **Vertical axis**: the person's goals and approvals come down; plans, results and refusals go up.
- **Librarian**: the knowledge layer both sides pull from. It never becomes a caller.
- **Direct-call paths**: all four agents have an entrance a person can use alone. Going through the bridge is **an option and not the default** (D5).

### 3.1 Standalone operation and reduced mode (D5, P11)

Nothing stops for want of a collaborator. Instead, **what it worked without is written into the card.**

| Agent | Called alone | What is missing | What the card records |
|---|---|---|---|
| microscope | the person supplies the goal card directly → condition design → approval → measurement | without the librarian, constants cannot be pulled from the KB; without the bridge, there is no comparison against the other side | `degraded: [librarian]`, the affected numbers are `assumed` or `spec` |
| simulation | the person supplies the goal card directly → parameter design → smoke run → the real run | the same | `degraded: [librarian, bridge]` |
| librarian | the person queries and distils directly (the knowledge store used alone) | nothing — the librarian is complete as a standalone tool | — |
| (MCP server down) | each agent proceeds on `envelope/snapshot.*` alone | the latest knowledge, external search | `degraded: [librarian]` |
| bridge | the person places both sides' cards by hand to make the round trip | there is no automatic trigger | `trigger: human` |

Rules:
1. **Nobody presumes the other exists.** When a call to the other side fails, it proceeds as **reduced mode plus a statement**, not as a refusal.
2. **Reduced mode is not hidden.** The validator passes a card carrying a `degraded` list, but forces that list to propagate all the way to the result card.
3. **A standalone result is a first-class result.** A plan or result made without a thread passes the same schema and the same gate (`thread: solo-<id>` in §5.2).
4. **There is exactly one hard dependency: `contracts/`.** No agent reads another agent's directory, so checking out one directory plus `contracts/` is enough to run.

---
## 4. Agent specifications

Each agent has **what it does / what it does not do / inputs / outputs / permissions / failure modes / standalone operation / definition of done**. "What it does not do" is the core output of this redesign.

### 4.1 Microscope agent (`microscope_agent/`)

**Responsibility in one sentence**: translate a given observation goal into conditions actually measurable on this instrument, and carry out the measurement under approval.

**What it does**
1. **Configuration choice**: find the candidate **system configurations (modalities)** that can yield the observable in `contracts/capabilities/`, and eliminate impossible configurations with numbers. **What to measure with is the first decision, and it comes before parameter search** (§1).
2. **Back-calculating the requirement**: target uncertainty/resolution → the statistics needed (sample count, measurement length, repetitions).
3. **Condition search**: propose conditions inside the operating envelope — source power, detector settings, frame rate/exposure time, measurement length, field of view and magnification, stage position and **travel speed**, temperature, sample concentration, and the parameters belonging to the chosen configuration (**number of traps and power per trap**, pinhole, DMD pattern, camera selection, and so on).
4. **Stating the trade-offs**: SNR ↔ photodamage, temporal resolution ↔ noise, resolution ↔ field of view, statistics ↔ drift, and the trade-offs **between configurations**. The chosen point is written together with **the points and the configurations discarded.**
5. **Writing the execution plan** → passing the validator → requesting approval → execution → raw data plus execution log.
6. **Recording deviations afterwards**: the difference between planned and actual conditions, per run (drift, actual power, temperature variation, and so on).

**What it does not do**
- It does not decide what to research. Goals come only from a person or from the bridge.
- It does not update the envelope or the calibration constants on its own. It reflects only the output of a separate, explicit calibration procedure.
- It does not change hardware state without approval (§6 Tier 2).
- It does not claim paper-level conclusions. It reports as far as the observable and its uncertainty.
- It does not delete a failed run or quietly re-run it (P9).
- **It does not build a knowledge store of its own.** A new fact coming out of a measurement leaves as a result card, and entering it into the KB is the librarian's job (P14).

**Inputs**: a goal card (person) or an ask_experiment card (bridge), `envelope/*.json`, librarian entries
**Outputs**: `questions/<qid>/plan_microscope_<qid>.json` (the record, **configuration + parameters**) plus `.md` (for people), `runs/<run_id>/{raw/, log.json, deviations.json}`, a result or refusal card

**Permissions**: Tier 0 autonomous / Tier 1 low-risk single measurement inside the envelope / Tier 2 human approval / Tier 3 forbidden (§6)

**Failure modes and responses**
| Situation | Response |
|---|---|
| The required condition is outside the envelope | **Refusal card**: state which value exceeds which limit and by how much |
| The target uncertainty is physically impossible | Compute the measurement time it would need, present it as a counter-example, then refuse |
| A needed calibration constant is not in the KB | Stop; propose calibration as prior work (do not fill it with an estimate) |
| Deviation during execution exceeds tolerance | Stop per the stop criteria, report the partial result together with the deviation |

**Standalone operation**: complete on a person's goal card alone, with no librarian and no bridge. A constant that could not be pulled from the KB goes up as `assumed` and leaves `degraded: [librarian]`. Since it is the only agent touching the instrument and the envelope, the §6 gate applies unchanged in standalone mode.

**Definition of done**: the result card passes the validator, and every number in it is traceable by `run_id`.

---

### 4.2 Simulation agent (`simulation_agent/`)

**Responsibility in one sentence**: translate a given computational goal into a parameter set that is stable and converges inside budget, and run it under approval.

**What it does**
1. **Parameter design**: integration timestep, total steps/physical time, particle count and density, interaction parameters, temperature, friction/diffusion coefficient, box size and boundary conditions, seed count, equilibration time, save interval.
2. **Constraint checks (in code)**:
   - Integration stability: timestep ≪ the shortest characteristic time
   - Finite size: box size vs the relevant correlation length
   - Sampling: save interval vs the observable's timescale (avoiding aliasing)
   - Statistics: seed count and trajectory length vs the target statistical error
   - Budget: expected wall clock and storage vs what is allowed
3. **Declaring the equilibration/steady-state criterion in advance.** It is not chosen after the run.
4. **Execution plan → validation → (approval if needed) → smoke run → the real run → results plus convergence evidence.**

**What it does not do**
- It does not change the model itself. Changing a potential form or a physical model is a separate decision requiring human approval.
- It does not quietly back-fit parameters to match experimental data. Fitting happens **only when it is explicitly the requested task**, labelled as fitting.
- It does not delete a failed or diverged run. Divergence is a result too.
- **It does not build a knowledge store of its own.** New facts leave as result cards (P14).
- It does not submit an over-budget job on its own.

**Inputs**: a goal card or an ask_simulation card, `envelope/budget.json` (resource limits), librarian entries
**Outputs**: `questions/<qid>/plan_simulation_<qid>.json` plus `.md`, `runs/<run_id>/{config, trajectory_meta, observables, log.json}`, a result or refusal card

**Permissions**: Tier 0 autonomous / Tier 1 smoke runs and small verification runs / Tier 2 over-budget jobs and model changes / Tier 3 forbidden

**Failure modes and responses**
| Situation | Response |
|---|---|
| The target accuracy is impossible inside budget | Compute the resources needed, present them as a counter-example, enclose one relaxed-goal option, then refuse |
| Equilibration not reached | Do not discard the partial result; report it labelled "not converged" |
| Seed-to-seed variance larger than the target | Compute the additional seed count and propose it as follow-up work |

**Standalone operation**: complete on a person's goal card alone, with no input from the experimental side. Numbers that needed an experimental comparison go up as `assumed` and leave `degraded: [bridge]`. Running independently of instrument scheduling is the reason this agent is kept separate.

**Definition of done**: the result card carries the observable, the statistical error and convergence evidence, and the run can be repeated from the config hash.

---
### 4.3 Librarian agent (`librarian_agent/`)

**Responsibility in one sentence**: hand the other agents the knowledge they need **now**, with its source, and where there is none, fetch it from outside, distil it and keep it.

**Three storage layers**
```
kb/
  sources/    source identifiers (DOI/URL/local path), access date, licence notes.
              No reproduction of full text -- identifiers and local quotations only.
  distilled/  human-readable distillation notes: what is claimed / under what conditions / what the limits are.
  entries/    one atomic claim = one file, machine-readable.
              {claim, numbers[(value,unit,source)], validity_conditions,
               confidence, source_ref, date, supersedes}
```

**Confidence uses §5.3's E-grades as they are.** No separate librarian-only scale — two scales soon become two truths.

**The ordering inside E3** (citation priority): `peer_reviewed` → `textbook` → `vendor_spec` → `preprint`. All four are grade E3 and are separated only by tag — when two sources state the same value differently, cite in this order but **keep both and tie them with `conflict_with`.**

The reason preprint is last is one thing: it has not been peer-reviewed. The reason a vendor spec sits below a textbook is different — a vendor measures under conditions favourable to its own instrument.

**A general search result cannot become an entry.** A source outside those four kinds (a blog, a forum, a summary page, a model's answer) is used **only as a clue about what to look up**, and is entered only when following it reaches one of the four. If it does not, it is not entered.

**When it genuinely is not there, ask the person.** A value not found in the four kinds is not filled in by estimate; it goes into `gaps` and then the person is asked to confirm, **stating where it was looked for.** If the person supplies an answer it is entered with that source; if not, the value stays an E5 estimate and the plan carries that fact with it.

**E6 (a model's guess) cannot enter the KB.** It is used only inside a conversation, and labelled when used.

**What it does**
1. **Context-based supply**: given the request context (observable plus condition range), return only the relevant entries. It does not dump unrelated knowledge.
2. **When there is none, it answers "none".** It does not fill a blank with a guess. It then proposes an external search.
3. **External search → distillation → storage**: after confirming the source, store it across the three layers. Distillation is not summarising but **decomposition into claims.**
4. **Conflict preservation**: conflicting claims are not merged arbitrarily; both are kept, marked `conflict`, with the difference in conditions recorded.
5. **Updating**: when a new measurement overturns an existing entry, link them with `supersedes`. The old entry is not deleted.

**What it does not do**
- It does not set experimental or simulation conditions. It supplies numbers; it does not choose them.
- It does not interpolate, extrapolate or average values. That is the judgement of the agent using them, and that judgement is recorded in the plan.
- It does not speak to another agent first (P7, pull-only).
- It does not bypass access restrictions on paid or copyrighted material. Inaccessible is recorded as inaccessible.

**Input**: a query `{observable, condition_range, requester, purpose}`
**Output**: `{entries: [...], gaps: [...], grade_summary}` — **a response whose gaps are non-empty is the normal case.**

#### 4.3.0 A store and a service are different things (§9)

**The librarian is two things: a knowledge store, and a service on top of it.** The store has existed since M0 in a form a person curates; the service is M3. On 2026-09-17 the execution order changed and M3 became first (§9), but **the distinction itself is independent of order** — curation stays a person's job even once the service exists.

| | Store (from M0) | Service (M3, first in execution order) |
|---|---|---|
| What | `kb/entries/`, `kb/sources/`, `kb/distilled/`, `kb/index.json` | MCP server, context queries, producing `gaps`, distillation, external search, conflict detection, snapshot export |
| Who writes it | **a person curates it by hand** (`curated_by`) | the librarian agent. But **entering an entry happens only inside the librarian's session** — what the service exposes is reading only (§4.3.1) |
| Who reads it | agents read the files directly and cite with a `kb:` source | calling `kb_query`. **Direct reading does not go away** — the store is readable even with MCP dead |
| Record | the entry files. `index.json` is generated | the same |

**The grade system works with the store alone.** `kb_version` is a content hash over all entries, and when a card cites `kb:<entry_id>` the validator confirms the grade **against the store** (checks 21 and 25). That is: "I cited a literature value" was self-reported without the store, and with the store it becomes checkable.

**What is actually lost without the service** is not values but **the discovery of blanks**: what is not in the KB (`gaps`), which claims contradict each other (`conflict`), and whether an answer exists outside. So a card that did not reach the librarian carries `degraded: ["librarian_agent"]`, and its meaning is not "there is no literature value" but **"we do not know what was missed."**

**That state is not temporary.** In the original order it was the interregnum during M1–M2, but after the reordering it remains **the state at every moment the MCP server is down** (§3.1). So the completion conditions of M1 and M2 force a pass through that state once each (§9) — a branch nobody has walked is not a branch that exists.

#### 4.3.1 Interface — the MCP server (D9, M3)

The librarian is implemented as an **MCP server** (`librarian_agent/src/mcp_server.py`). Subagents have to be able to query it directly, without a file round-trip, for S3's fan-out (configuration × axis, up to 21) to have a practical speed.

**The tools it exposes are read-only:**

| Tool | What it does | Who uses it |
|---|---|---|
| `kb_query(caller_id, kb_version, observable, condition_range, purpose)` | relevant entries + `gaps` + `grade_summary` | S2, S3 subagents, the operator |
| `kb_get(caller_id, kb_version, entry_id)` | one entry, verbatim | anyone **inside the question** |
| `kb_conflicts(caller_id, kb_version, topic)` | pairs of conflicting claims | S3 |
| `kb_group(caller_id, kb_version, symbol)` | one dimensionless group's defining expression, inputs and validity | S3 (§5.7), check 36's comparison path |

**This table is the record, and the server's wire names are matched to it.** On 2026-09-18 a proposal came up to keep a second copy of this table in `contracts/`, and I accepted it and then reversed — the argument was "an execution seat has to read `mcp_server.py` to learn the signatures", and **the premise was wrong because this table already writes the arguments down.** Had it stayed, the same table would have diverged in two places, which is exactly the shape §11-11 counts. If the server's wire names take an MCP-conventional prefix and diverge from this table, **it is not that there is no contract but that the server departed from it**, and the side that moves is the server.

**Why a fourth is needed** (the answer to §11-5): a dimensionless group **is looked up by symbol.** `kb_query` searches by observable and condition range and returns a value, but when S3 and S4 ask about `k*` or `τ_D` what they want is not a value but **the defining expression** (§5.7), and a condition range is not the query term. `kb_get` requires already knowing the `entry_id`, and the route from symbol to id exists only in the index. The remaining option is making `kb_query` return either a value or a definition depending on its arguments, and **a tool whose return shape changes with its arguments produces a branch in every caller.** One more tool is cheaper. Check 36 needs the same lookup, so this tool becomes its comparison path.

**No write tools are exposed.** External search, distillation, and writing or retiring entries happen only inside the librarian's session. If a subagent can write to the KB, an undistilled value becomes the record immediately.

**`condition_range` is a map of intervals.** It is written in the physical units of record (D7):

```
condition_range = {
  "temperature":   {"min": 291, "max": 295, "unit": "K"},
  "bead_diameter": {"min": 0.5, "max": 2.0, "unit": "um"}
}
```

What it is matched against is an entry's validity conditions, and **they have to be the same shape.** So M3's first task is not the server but the schema: today `validity_conditions` is prose (`minLength: 10`), and **prose cannot be compared.** A machine-readable `validity` goes beside it and the prose stays for people — of the two, `validity` is the record (P3). An existing entry with prose only does not match a condition query until `validity` is filled, and comes back as `unconstrained`. That is better than passing it quietly.

**Four comparison rules.** The librarian does not choose values; it says **only whether something is covered** (§4.3, "what it does not do"):

1. **Covered, so return it.** When an entry's `validity` contains the whole query interval, `overlap: "full"`.
2. **Merely overlapping, so say it overlaps.** On a partial intersection, return `overlap: "partial"` together with **the part not covered.** Do not clip and do not extrapolate — that judgement belongs to the user of the value, and that judgement is recorded in the plan.
3. **Silence is two things with different consequences, so it has two names.** When the query asked and the entry has no opinion on that quantity, it is `unconstrained` — that entry does not constrain that axis, so it is harmless. **When the entry constrains and the query did not mention that quantity, it is `unasked`** — that is the dangerous one, meaning the caller may be using the value outside a condition it never considered. Neither counts as satisfaction: reading silence as satisfied is the same as having no validity conditions at all. **Until 2026-09-18 this rule called the dangerous one `unconstrained`**, so a caller implementing the contract faithfully would have looked for the warning in the harmless set and read "nothing to worry about" — a case where a rule's intent is inverted exactly by one name. **The implementation was right and the specification was wrong** (`match()` in `a9df017` had already separated the two). And the `unconstrained` on the `overlap` side **becomes `no_overlap`** — the same word in two positions within one response, as an overlap value and as a field name, is the collision §4.5.2.1 records, and `no_overlap` carries its own subject inside the word.
4. **Units convert only when the dimensions match.** `units.json` is the record (§5.7), and where dimensions differ it does not convert, it refuses.

**The shape of `gaps`.** §4.3 requires them raised "stating where it was looked for". That requirement is the field:

```
gap = {
  "observable":      "bleaching_time_constant",
  "condition_range": { ... },
  "kind":            "absent" | "condition_mismatch" | "inaccessible" | "unqualified_source",
  "searched":        ["kb/entries", "external:crossref", "external:vendor_docs"],
  "nearest":         [ {"entry_id": "…", "overlap": "partial", "uncovered": { ... }} ],
  "kb_version":      "kbv-…",
  "asked_by":        "<caller_id>",
  "asked_at":        "…"
}
```

`kind` has four values because **what to do next differs in all four cases**:

| kind | Meaning | What to do next |
|---|---|---|
| `absent` | there is no claim at all about that observable | external search, and if still nothing, the person |
| `condition_mismatch` | a claim exists but does not cover this condition | find literature at other conditions, or have the user record the extrapolation as an assumption |
| `inaccessible` | a source was found but cannot be accessed (paywalled, restricted) | the person. **Do not bypass** (§4.3) |
| `unqualified_source` | there was a clue but it did not reach one of §4.3's four kinds | do not enter it. Leave the clue in `searched` so the next person does not walk the same path again |

**A gap with an empty `searched` is not a gap.** Not having looked and there not being one are different, and this field separates them. `nearest` does the same job — "there is nothing similar" and "there is one but at a different temperature" lead to different next actions.

**`grade_summary` is a convenience value.** It merely summarises the grade counts and the worst grade among the returned entries; the record is each entry's own `grade`. **A card does not cite `grade_summary`** — citing the summary loses which number had which grade.

**State is isolated per `caller_id`.** The server does not have to be fully stateless — it only has to get the isolation unit right. But **that unit must not be `qid`.** The leak happens precisely between siblings sharing one `qid`.

**A caller that is not an axis needs a form too** (2026-09-19). The tool table above lists **S2, S3 subagents, the operator and S4** as consumers, while the format was only `<config>:<axis>` — **S2, S4 and the operator have no axis, so they could not construct a conforming id.** Then `degraded: []` on a card issued by those three **cannot be supported in principle**, and an attempt to check it ends as "covers axis cards only and nothing else". This subsection wrote down four consumers and gave one format, so it is the shape §11-11 counts — one fact living in two places and diverging. The simulation manager found it while designing check 45.
**S4 is not in this table — §4.5.4 forbids it to query** (corrected 2026-09-19). This table listed S4 as a consumer of `kb_conflicts` and `kb_group`, and §4.5.4 rule 4 says "it does not query for new facts. S4 **only combines**." **Two subsections were saying different things** — the sixth shape today, and unlike the previous five: it is not one sentence meaning two things but **two subsections in conflict.**

**§4.5.4 wins, because it carries its reason and its alternative** — *once synthesis starts querying, S3's parallel independence becomes meaningless and one final agent ends up re-judging everything alone*, and *if more knowledge is needed, go back to S3, and that is a new revision (P9)*. This table merely enumerated consumers, with no reason. **The side holding a reason beats the side holding a list.**

**So `s4` came out of the `caller_id` grammar too — which I had put in the same day.** Widening to non-axis callers, I took this table as the grounds, and that table happened to be the wrong side. A seat that does not query does not appear in the log, so it needs no id.

**`kb_get`'s "anyone" was narrowed to "anyone inside the question" as well.** A manager looking around is not any card's evidence, and permitting it makes **the log an access record rather than evidence.** That is why the simulation manager did not call the tools even though they came up in its session today — a manager has no axis and no qid, so it would have had to **invent** an id, which is exactly the thing this subsection's clause exists to prevent.

**A consequence: synthesis does not decide its own `degraded`; it inherits it from the input axes.** It does not query, so it cannot know on its own. If even one axis is in reduced mode the synthesis is too, and the propagation runs axis → synthesis → plan (check 10). The example chain already behaves that way — **the rule is catching up with the observation.**

**Which cards need a `caller_id` field is decided by this too**: goal (S2 queries) and result (the operator queries) have one, and **synthesis does not.**

**The bridge has a form too — and omitting it is the fifth instance of the same defect** (2026-09-19). The same day "four consumers listed and one format given" was fixed, and **the fixed grammar counted four again and left the bridge out.** The reason the bridge is not in this subsection's table is not that it does not use the librarian but **that the requirement is written in §4.4 rule 5** — if the same observable at the same conditions has already crossed, do not open a round, point at a knowledge item. When a consumer list lives in one subsection and one consumer is declared in another, whoever edits the list does not count them (§11-11).

**The bridge's isolation unit is not a question but a thread and a round.** `bridge:<thread>:r<N>`. There is a reason it cannot hang off `<qid>` — **one thread moves between two `qid`s** (one on each side). And the `bridge:` prefix exists so that a parser separates them without knowing the namespace.

**So this table is the only home for consumers.** §4.4 says the librarian is needed but **does not declare itself a consumer**; it points here. Two lists means only one of them gets fixed.

**And a window is open between declaration and passage**: `axis.schema.json`'s pattern still accepts only the axis form, so `s2`, `operator` and `bridge:…` are **declared and refused by the server.** The format is this subsection's, so the declaration had to come first. **And closing it needs three places — my writing "two" was one short**: adding the format is this subsection, letting a card carry it is the manager's schema, and **letting the call pass is the librarian's server.** On 2026-09-19 the server refused an id the schema accepted — because the server held its own copy of the pattern, and while consolidating two copies into one the day before, **the third copy, the one that decides whether a call succeeds, was missed and it was written down as "now one place".** It is closed now, with the server reading `common.schema.json#/$defs/caller_id` — closing the class rather than the instance.

**Two of the three being right still refuses the call, and that state is invisible in the log** — a refused call leaves no line in `queries/log.jsonl`, so the only symptom is "that seat stays degraded". So `degraded: ["librarian_agent"]` has **two causes**: the tools being absent (the window was launched wrongly; a restart fixes it) and the tools being present and refusing (the contract does not match; a restart does not fix it). Same marking, different cause. **Since a refused call leaves not even a line**, the queries from those seats have no trace at all during that time — which is why knowing the window is open matters.

**Closing that window revealed that two copies had already diverged** (`71da178`). The `caller_id` pattern existed in the `axis` and `screening` schemas separately, and **the screening one had no `(:v[0-9]+)?`** — the first screening card carrying the `:v1:` §4.3.1 requires **would have been refused by a schema nobody was thinking about.** It simply had not blown up because no screening card existed yet. The pattern is now in one place, `common.schema.json`. It is the shape §11-11 counts, except this time it was caught **before** it blew up.

**The axis form was left alone.** That is about not moving again what was just moved; adding three is enough.

**The revision component exists because that argument goes one step further** (2026-09-18). The reason the unit must not be `qid` is that "the leak happens between siblings sharing one `qid`", and without a revision **a re-run's a1 and the original a1 are the same context on the server.** What the same subsection allows is "one subagent continuing follow-up queries inside **its own** context", and **a re-run's a1 is not the same subagent** — it is a different fan-out, and it exists because something was wrong.

**And without this, §4.5.5's rule gets a mechanical bypass.** "Revision 2 may cite revision 1 as a record and may not use it as an input" **is checkable at the card level**, but if the server carries the context across, revision 1's context enters revision 2's computation **with no card citing anything.** The leak merely moves from between siblings to **between two moments of the same axis.** The simulation manager raised it.

**Revision 1 states `v1` too.** Omitting it creates the implicit rule "absent means 1", and that class of thing bit five times today (§7.1 rule 3). The price is check 33's string enforcement and the existing cards moving together.

```
caller_id = <qid>:v<N>:s2                  e.g. mic-20260916-001:v1:s2
          | <qid>:v<N>:<config>:<axis>     e.g. mic-20260916-001:v1:confocal:a3   (only S3 fans out)
          | <qid>:v<N>:operator            e.g. mic-20260916-001:v1:operator
          | bridge:<thread>:r<N>           e.g. bridge:thr-tracer-diffusivity-001:r2
          | selftest:<what is being tested> e.g. selftest:query-log-roundtrip   (not a round)
```

Five rules:

1. **Isolation**: session context is kept per `caller_id` only. It does not reference another `caller_id`'s queries or responses. A subagent continuing follow-up queries inside its own context is permitted — state is harmless as long as it does not see a sibling.
2. **Determinism**: the same `(query, kb_version)` always gives the same answer. **The answer must not depend on call history.** Hold that condition and a content-addressed cache is not a leak path; in a 21-way fan-out it is in fact necessary.
3. **An id is issued, not chosen.** The `caller_id` is injected by the S3 fan-out runner. A subagent cannot set or change its own — that would let it impersonate a sibling's id, and an instruction embedded in retrieved literature could do it too.
4. **Verification traffic uses its own namespace.** `selftest:` overlaps no `qid` and no thread, so a reader of the log **can tell a line produced by a test from a line produced by a real round.** If they overlap there is no way to tell — the log does not record the calling process. On 2026-09-19 the librarian seat's self-test held a `Store()` defaulting to the real `queries/log.jsonl`, and **because that test did not call the tools**, no test lines got mixed into the real log. It was one line's difference, and had they mixed, the very log that was evidence for `degraded: []` would have been left holding test lines. A `selftest:` id is not an exception to rule 3 — **it impersonates no round, so there is nothing to be issued.**
5. **Global aggregates do not affect answers.** Statistics such as popular entries or query frequency may be recorded, but the moment they enter a ranking or a response body they become a sibling-to-sibling communication path.

**Determinism includes the ordering.** The order of returned entries is a total order on `(grade, rank within E3, entry_id)` — better grade first, within the same E3 `peer_reviewed → textbook → vendor_spec → preprint` (§4.3), and ties broken by `entry_id` lexicographically. This ordering is **the only place §4.3's citation priority actually operates.** Until now that ranking existed only as a sentence and no code read it.

**The KB version is pinned for the duration of a fan-out.** S3.0 pins `kb_version` and every query carries it. If the librarian **changes the store mid-fan-out** (adding, editing or retiring), each sibling sees a different KB, determinism breaks, and the difference itself becomes a side channel. As a side effect **the whole question becomes reproducible** — re-run with the same `kb_version` and the same constraints come out.

**When the store moves mid-fan-out, stay rather than chase the pin** (2026-09-18, microscope manager). The instinct is to re-pin and that is wrong. Three grounds:

1. **Chasing does not converge.** Re-pinning once left the card recording the target **stale four minutes later**, and the store moved twice more after that. A fan-out that re-pins every time the librarian commits does not finish.
2. **The server serves old pins, so staying is honesty and not convenience.** The response carries `answered_from`, and the pin points at **a state the server can still reproduce.** While the server was refusing, staying was impossible, which is why chasing looked like the only option.
3. **Check 33 requires sibling agreement.** Answering only the remaining axes at today's version puts them out of step with the finished ones, and dragging the finished ones up to match is precisely that treadmill.

**So the PENDING check 25 raises on that directory is a state and not a defect** — it is the fact that "this fan-out answered against the store as it was then", and `answered_from` proves it. This judgement has the same shape as §9.3's common-ancestor problem: whether to treat what one side accumulated as prior work or as a baseline. Here **the place it stayed is the baseline.**

**There are five gap `kind`s — the fifth is `in_published_table`** (2026-09-19). The service's first real use found it: `kb_query` answered `absent` for `device_registry`, `control_channel` and `read_back`, and **all three are in the caller's own `envelope/` snapshot under `tables.devices`** — one is a table name and two are column names in that table, and that snapshot is published by the librarian itself and fixed by sha256.

**`absent` is not merely unhelpful; it is false in the direction that costs.** That kind's next action is "look outside, and if still nothing, the person", so it **sends you out of the building to find what is already in your hand.** And the sharpest form of it is P14 pointed at itself — knowledge lives in one place and the librarian owns it, and **the librarian answered "it is not here, look outside" about its own file.**

**What this subsection wrote down as the reason for four kinds was "the next action differs in all four", and that criterion produces the answer here.** This case's next action — **read `tables.<name>` in your own snapshot and compare the sha256** — is unlike all four. So it is a fifth.

**The name says where it is, not what it is not.** `not_an_entry` carries no next action. And the gap has to carry **which table** — asked about a column, returning no table name makes the caller guess. The alternative of putting the guidance only in `nearest` was refused: **what a machine branches on is `kind`**, and putting the next action in a field nobody reads leaves the caller still doing `absent`'s work.

**When a name does not resolve, the gap carries the nearest names the store does know** (2026-09-19). Of nine empty-handed results, **eight were the store failing to recognise its own knowledge in the caller's words** — asked for `numerical_aperture` while the store holds it as `na`, asked for `objective` while it holds `objective_mrd70040…`. Five are closed by `in_published_table`; three are closed **by nothing.**

**Matching is authority; suggesting is not.** This is where it parts from fuzzy matching. Folding strings inside `answers_to()` means **a wrong name gets an entry back as though it were right**, and then the caller's word overwrites the store's word. Putting near names in the gap returns **nothing** and says only "I know these names" — the caller has to ask again in the store's words, and **both of those asks stay in the log.** Same shape as `in_published_table`: **a gap says where to go, it does not go for you.** This is why the librarian seat refusing whitespace normalisation the same day does not conflict with this.

**And this opens a deeper question** (to be raised in §11). `kb_query`'s argument is named `observable`, and in the first real use **not once was it asked with a registered observable** — what was asked was one table, two columns, and an entry_id. An entry's `subject` already has four kinds (device, configuration, observable, quantity), while the query's argument carries **the name of one of them.** The fifth kind fixes the answer side; this is **the question side.** They are not mixed.

**Old pins are served, not refused.** The reproducibility this subsection promises — *re-run with the same `kb_version` and the same constraints come out* — requires it. And since the pin exists **so that siblings see the same KB even when the store changes mid-fan-out**, refusing the pin in that situation produces exactly the failure the pin was preventing. The server refused until 2026-09-18 (`4033b4d` fixed it), and one judgement had been standing on that refusing behaviour — **a decision grounded in a bug's behaviour has to be revisited when the bug is fixed.** An uncommitted version is not servable, though: a hash of a working tree has nowhere to go back to.

**The verb being "add" bit on 2026-09-18.** `kb_version` is **a hash over all entries**, so editing and retiring move it just as much. That day **fixing one `tau_d`** staled 19 places across cards, one of which had two of seven axes in flight. The sentence the librarian execution seat raised is the point — **a rule written with one verb gets read as a rule about that verb.**

**MCP is transport, not memory.** An entry received is recorded by the caller in its own output as `kb_refs` (P1, §8 check 25). Even with the server dead, what a plan rested on has to remain in the files.
**What was not received is recorded too.** `kb_refs` records the entries received, but **what was asked for and not received** was recorded nowhere. The service's output is not values but the discovery of blanks (§4.3.0), and if that blank is not on disk then what the service did is not recorded — turn the server off and the discovery goes with it. So a card also writes `kb_gaps` (§5.2), and a rule comes with it: **every `assumed:` (E5) number on a card that reached the librarian must point at an item in `kb_gaps`** (check 39). An estimate is legitimate only when somebody looked and it was not there. If the librarian was not reached, that fact stays in `degraded` and this rule does not apply — **not having reached it and having looked and not found are different.**

**A failed call is reduced mode, not a refusal.** Where the librarian cannot be reached it proceeds carrying `degraded: [librarian]`, and a value that could not be filled goes up as `assumed` (E5) (§3.1).

#### 4.3.2 The librarian owns all knowledge (D10, P14)

**No other agent keeps a knowledge store of its own.** All knowledge that is newly produced or needs consulting passes through the librarian. Three things are distinguished for this:

| | What | Where | Ownership |
|---|---|---|---|
| **Knowledge** | what is true — measured facts, calibration results, literature, device characteristics | `librarian_agent/kb/` | **the librarian, solely** |
| **Record** | what happened — questions, plans, run logs, raw data, **the query log** | each agent's `questions/`, `runs/`, and the librarian's `queries/` | that agent, append-only |
| **Policy** | what is permitted — safety limits, interlocks | `envelope/safety.*` | **the person**, Tier 3 (§2.1 rule 7) |

**Policy has two shapes, because what a limit attaches to differs.** A simulation's limit attaches to **an execution target** (`targets` — what, and how far, in this run). An instrument's limit does not attach to a target; it attaches to **a control channel** — the output-producing `laser_combiner`, `optical_tweezers`, `widefield_source_a/b`, `dmd`, and the moving `piezo_stage`, `stand_ti2e`. **An instrument has no such thing as an execution target.** So requiring `targets` on both sides makes the microscope policy unwritable, and until 2026-09-18 it literally was. The schema splits the two shapes by `agent`. Which channel binds which parameter and where that meets the plan's `conditions[]` is **the microscope seat's to decide** — it is a fact only that seat knows, and a seat that does not know inventing it is what §10.3 rule 4 prevents.

Two cases where the boundary is confusing:

- **"This laser's maximum power is X"** → a fact. The librarian's (E3, spec).
- **"We do not go above Y"** → a policy. `envelope/safety.*`'s, and not knowledge, so the librarian does not touch it.

**Knowledge needed at execution time is held as a snapshot.** Values preflight has to consult every time, such as the device registry and calibration, sit in `envelope/snapshot.*` as **a copy exported from the librarian's KB.** The copy carries entry ids and hashes and the validator compares it against the record (§8 check 26). The copy cannot be edited by hand — if it needs fixing, fix the KB and export again.

**Two tables fall under this — the device registry and the valid optical-path table.** Both say "what this instrument looks like", so they are knowledge, and therefore not owned by `envelope/`. Export arrives in M3, so **during M1–M2 the two tables live in `librarian_agent/kb/staging/{devices,optical_paths}.v0.json` and the executing agents read them by the direct read §4.3.0 permits** (§11.1). When they are exported as snapshots in M3, **only the place they are read from changes; the owner does not.** The one thing `envelope/` owns itself is a single policy — `safety.json`.

The reason a snapshot exists is P0 rule 2 (fail-closed). **A safety judgement must not depend on a live server call.**

**The librarian's records are outside `kb/` too.** Who asked what and why stays append-only in `librarian_agent/queries/log.jsonl` and does not enter the knowledge store. Of the three categories in the table above this is a **record** — not what is true but what happened, the same position as an executing agent's `runs/` sitting beside the store rather than inside it. And since what `kb_version` hashes and what a card cites with `kb:` is entries only, putting something uncitable inside blurs that boundary.

**This log is not a new concept; it closes an asymmetry that already existed.** `kb_query` takes a `caller_id` and a `purpose`, and `kb_gap` carries `asked_by` (§4.3.1) — that is, **a failed query was attributed and a successful one was not.** An entry received stays in the card's `kb_refs`, but who asked and why disappeared outside the card.

**And this log does not touch answers.** §4.3.1 rule 4 (global aggregates do not affect answers) is kept **structurally rather than by comment**: only writing and offline auditing exist, and **no function reads the log by caller, observable or count.** If the answering path has nothing to call, a sibling communication channel cannot come into being (P4: not restraint, but absence).

There is one more side effect. Recording the answer beside the query makes **§4.3.1's determinism checkable for the first time** — two lines with different returns for the same `(query, kb_version)` is a place where the guarantee broke. Until now that guarantee existed only as a sentence.

**The librarian publishes and the consumer pulls.** The librarian's session cannot write into another agent's directory (D11, §6.2) — so `src/export_snapshot.py` only **publishes** to `kb/exports/snapshot_<agent_id>.json`, and each agent's session copies it into its own `envelope/snapshot.json`. The copies grow to two, but both are compared against the record by entry hash (check 26) so the values cannot diverge, and **one copy is cheaper than piercing a boundary.** And the copy passing through each session's hands is the point rather than a side effect — when, and at which KB version, an agent took it into its envelope stays in that agent's commits.

`kb/` is the only other directory another session may read. Knowledge is designed to be shared (P14), and **only reading** is shared — writing is the librarian's session alone. It is the single exception to §3.1 rule 4 ("no agent reads another agent's directory"), and the rule's conclusion stands: check out without `kb/` and it still runs in reduced mode.

**New facts leave as result cards.** An executing agent does not write new knowledge from a measurement into its own directory. It exports a result card and **only the librarian** turns it into a KB entry. **This is the only path by which a value an executing agent measured enters the KB.**

**But it is not the only path for E1 and E2 — on 2026-09-19 this subsection said so and was wrong.** A **calibration** a person performed directly on the instrument does not arrive as an executing agent's result card. §12's `pixel_size` row had opened that path from the start (`calibration:` source, an expiry, E2), and this sentence's "only" was covering it, and the same absolute statement was in `librarian_agent/CLAUDE.md` rule 9 as well. **Calibration is a second path**: its source is `calibration:` and **an expiry is mandatory**, and that expiry stands in for the traceability a result card would give. E1 still has exactly one path. **What separates them is not who said it but whether a calibration event occurred**, and a value a person stated from memory is not a calibration, so it stays `operator_recall:` E5. The librarian manager found it by asking the person back (§8.1).

**Permissions**: Tier 0 KB read/search · Tier 1 external search (read) · Tier 1 KB write (new entry) · Tier 2 retiring/superseding an existing entry · Tier 3 bulk reproduction of source text, bypassing access restrictions

**Standalone operation**: complete as a knowledge store a person writes to directly — querying, distillation, conflict resolution and retirement all work with no other agent. It is the only one of the four with zero collaboration dependency.

**Definition of done**: every number in a response is traceable through `source_ref`, and the blanks that could not be filled are stated in `gaps`.

---

### 4.4 Bridge agent — simulation ↔ reality (`bridge/`)

**On the name.** The two sides this agent joins are **simulation and the real experiment**, and the relation is symmetric. There are two reasons not to use a name like `sim2real` — the direction reads one way, and the `2` implies **conversion.** This agent does not convert (§4.4 rule 2: it checks, it does not convert).

The identifier stays `bridge`. Changing the name would move the directory, the `author` enum, the validator's regexes, the ledger schema, four `CLAUDE.md` files and the example thread together, while **what is gained can be gained in the description.** So the description alone states both sides: simulation ↔ reality, bidirectional.

Strictly, **a round has a direction** (`ask_simulation` / `ask_experiment`), and what is bidirectional is the relation of the whole thread. Per round it is half duplex — which is also why a `duplex`-style name would have been slightly too much.

**Responsibility in one sentence**: move one side's plan or result into a question card the other side can act on, and manage the rounds. **It authors no content.**

**What it does**
1. **Transport**: plan/result card → wrapped in an `ask_simulation.json` / `ask_experiment.json` envelope and delivered.
2. **Unit and dimensionless-number checks**: confirm that both sides' cards use the same physical units and that derived dimensionless groups do not contradict each other (§5.7). Reduced units never appear in a card, so **there is no mapping conversion at all** — the bridge does not convert, it only looks at the consistency of two representations. The first round has nothing to compare against (`no_counterpart`), and **from the second round on, the same answer means a comparison that was not made** (check 8).
3. **Producibility check**: can the other side produce the requested observable? **The verdict is derived from the vocabulary (`contracts/observables.json`) and the other side's capability table; the envelope does not self-report it** — the same as what check 21 does to grades. The answer is one of three: `yes` (some configuration in that table produces it) · `no` (the vocabulary excludes that side, or no configuration in the `populated` table produces it) · `undeclared` (the table has not said yet, or **the vocabulary does not define the name**). A `no` becomes a refusal card before a round trip is wasted, and **`undeclared` is a hold, not a refusal** (§11-1).

   **Production requiring composition is also `yes`, and the composition requirement stays in the table.** An observable the capability table declares as `{"id": ..., "requires_composition": ["trapping"]}` has producibility `yes`, and **the envelope carries only the configuration names** (`producing_configs`). The reason the envelope does not echo the composition requirement is the same as §4.4-5 — the side planning the configuration reads the same table directly, so there is nothing to copy across, and one fact living in two places is two facts by next week (P3). The receiving side planning without the composition is stopped by its own S3.0 looking at the same table.
4. **Round state machine plus integrity**: `r<N>_hashes.json` records **the original card in the sending side's directory** by id, revision and hash. `payload_hash` alone says only "the envelope agrees with itself", and a bridge that altered a number could alter the value and the hash together. If the original later moves to a new revision, comparison becomes impossible, and the validator then counts not a pass but **"rounds compared against the original: 0".**
5. **Duplicate blocking**: if the same observable at the same conditions has already made the round trip, replace the new round with a KB reference and record that substitution in `status.json`'s `substitutions`. Opening a round twice on the same (direction, observable) within one thread is a failure (check 8). **Without the librarian this rule does not work** — there is no store to point at, so a bridge in reduced mode reopens the round instead of substituting. `degraded: [librarian_agent]` is where that cost is written.
6. **Call the person when it repeats**: when the same `(reason_code, parameter)` pair appears **twice** within one thread, do not open another round; escalate to the person. **There is no fixed round ceiling** — a number cuts off round trips that are making real progress, and round trips going in circles are already waste before they reach that number. A cycle like A→B→A→B is caught by the repeated pair as well. **Repetition is recorded in `status.json`'s `blocked_pairs`**, and if the thread's refusal cards show the same pair across two rounds with nothing in the ledger, that is a failure — a repetition nobody records is a ceiling nobody enforces.

**What it does not do**
- It does not add, correct or round a number. It moves it without changing a character.
- It does not optimise conditions or suggest "better" parameters.
- It does not write conclusions or interpretations.
- It does not answer on behalf of either agent. An answer always goes out under that agent's signature.
- It does not open a round on its own. Opening a round is triggered by a person or by a plan-completion event.

**Input**: one side's plan/result card
**Output**: `threads/<thread>/{r<N>_ask_*.json, r<N>_ask_*.md, r<N>_hashes.json, status.json}`. The last two are **thread ledgers, not cards** (§5.1).

**Permissions**: Tier 0 (transport, checking, refusal), all of it. **Nothing at Tier 1 or above** — the bridge executes nothing.

**Failure modes and responses**
| Situation | Response |
|---|---|
| The observable is not producible on the other side | Immediate refusal card, with a list of substitutable observables attached (the list comes from each agent's declared capability table) |
| The unit mapping is unclear | Hold the round, escalate a request for a mapping definition to the person |
| The observable is **not yet declared** in the vocabulary or the capability table | **Hold** the round. The turn is the person's and `status.json` records what has to be answered. This is not a refusal — undeclared is not impossible (§11-1) |
| Hash mismatch | Stop the round. Automatic recovery forbidden |

**The turn can never be the bridge's.** `status.json`'s `turn` is one of the two executing agents or the person — the bridge moves cards, so it is not the side that owes anything, and the librarian only answers and holds no turn. When `state` is `open` the turn belongs to an agent; when it is `held`, `escalated` or `closed` it always belongs to the person. Only a person can take a thread out of those three.

**The envelope's Markdown does not echo the payload's numbers.** The envelope's `numbers[]` is empty (the bridge makes no numbers), and check 9 requires every number written in the Markdown to be in that card's `numbers[]`. So the human-readable envelope cannot restate values; it points at the payload. That is the intended result — a carrier echoing a value makes the same quantity live in two places, and next week it is two values (P3).

**Standalone operation**: a round stands even with a person placing both sides' cards by hand (`trigger: human`). The two executing agents do not have to be alive at the same time — asynchronous is the default (D3).

---
### 4.5 The executing agents' internal workflow (microscope and simulation, in common)

The two executing agents use **the same five-stage pipeline**. The only difference is §4.5.3's axis list.

**Terminology**: **S3–S5 together are called the `system designer`.** It is the whole part that takes a goal card and produces a validatable plan, made of per-axis analysis (S3) → synthesis (S4) → output (S5). Inside the repository the English spelling `system_designer` is used (§0, language convention). The front end (S1–S2) is **the work of settling the question**, and the system designer is **the work of solving that question into executable conditions**; this boundary is the most important dividing line in the pipeline — entering the system designer with the question unsettled is forbidden.

```
[S1] the person's question
  │
[S2] refine the question                              LLM alone · forbidden to produce numbers
  │   → question_<agent>_<qid>.md   (for people)
  │   → goal_<agent>_<qid>.json     (the record = §5.1's goal card)
  │   purpose → observable → consistency check → intent
  │   ├─(a) something to be measured/computed ────┐
  │   ├─(b) already known → hand to the librarian → stop early (no experiment)
  │   └─(c) only a person can answer (purpose included) → ask back once
  │                                               │
┌─ system designer ────────────────────────────────┴─────────────
│
│ [S3.0] configuration screening                      Python (deterministic)
│   │   keep only the configurations in capabilities/ that can yield this observable
│   │   zero of them means a refusal here · at most 3 configurations are kept
│   │   → configs.json
│   │
│ [S3] configuration × axis, parallel and independent ←── librarian pull   LLM + Python
│   │   one subagent per (surviving configuration) × (axis A1–A7)
│   │   cannot see a sibling's output
│   │   each produces a "constraint (permitted interval)" — it does not decide
│   │   → axis_<config>_a1.json … axis_<config>_a7.json
│   │
│ [S4] synthesis · resolving trade-offs                LLM + Python
│   │   per-configuration intersection → a configuration with an empty set drops out
│   │   compare the survivors + priorities → one configuration + one operating point
│   │   forbidden to produce new numbers, forbidden to query new facts
│   │   → synthesis.json
│   │
│ [S5] output
│       → plan_<agent>_<qid>.json  (the record) ──validator──> VALIDATED
│       → plan_<agent>_<qid>.md    (generated from the JSON, for people)
│
└────────────────────────────────────────────────────────────────
```

**The system designer's contract** — the reason these three stages are bound under one name is that their input and output are fixed as one:

| | Content |
|---|---|
| Input | one goal card (S2's output) plus librarian entries. It reads nothing else. |
| Output | `plan_<agent>_<qid>.json` plus `.md`, or a refusal card. The intermediates (`axis_*.json`, `synthesis.json`) stay in the same folder as an audit record. |
| Permissions | Tier 0 only. **The system designer executes nothing** — execution is a separate stage after approval (§6). |
| Forbidden | changing the question itself. If the goal is judged wrong, it goes back to S2 as **a refusal plus a question**, not as a plan. |

#### 4.5.1 S2 — refining the question (LLM alone)

1. **Grasp the purpose — why is this being asked.** It comes before the observable, because the purpose determines the precision mode, the priorities, the stop criteria, and even "is this the right observable". It is written in `purpose`.
2. **Narrow the observable — what is being measured.** Translate the purpose into a single observable.
3. **Check purpose against observable**: if the requested observable is a poor proxy for that purpose, **propose a better one.** Do not change it — there is no authority to change the question (the system designer contract in §4.5), so it goes up as an ask-back (c).
4. **Classify ambiguity into exactly three branches**:
   - **Something to be measured/computed** → down to S3.
   - **Something already known** → hand it to the librarian and **stop here.** Not running an experiment is a normal output too.
   - **Something only a person can answer** (target accuracy, priorities, the identity of the sample) → ask back **once only.** Do not multiply round trips.
5. **Convert into a form the next stage understands**: fill the goal card's fields with purpose, observable definition, target accuracy, constraints and priorities.
6. **Decide the precision mode**: follow the `purpose`'s default (the table below), and if choosing otherwise, write the reason (§5.8, §8 check 32).
7. **Save**: Markdown for people plus the JSON of record, under the same `qid`.

**Purpose classification (`purpose`)** — each drags in a different default:

| purpose | What is being attempted | Default `intent` | What that purpose changes |
|---|---|---|---|
| `screen` | survey what the system is like | explore | fast and rough. Sample preservation and turnaround come before accuracy |
| `characterize` | quantify a property | explore | accuracy first. Sweep a wide condition range |
| `compare` | compare across conditions or samples | explore | **sameness of conditions comes before absolute accuracy.** Systematic error cancels in a comparison, so the arms are not optimised separately but **fixed at one condition** |
| `verify` | confirm a known value or model | **confirm** | does not start until the target uncertainty is stated |
| `troubleshoot` | diagnose an instrument or sample fault | explore | large safety margins, fast turnaround. The aim is exclusion rather than a conclusion |
| `feed` | produce the input for another experiment or simulation | set by the other side | the format and uncertainty the other side requires become the constraint (bridge, §4.4) |

The `compare` row is the most substantive item in this table. When comparison is the purpose, optimising each condition individually makes the systematic error differ per condition and **the comparison itself becomes meaningless.** Not knowing the purpose, S4 will optimise each of them as a matter of course.

**Only a person can answer the purpose.** If it is blank, do not guess; ask back (c). An observable can be inferred and a purpose cannot — the same observable can belong to any of the six purposes.

**Core constraint**: S2 is the LLM alone, so **it cannot produce numbers.** Figures such as target accuracy and condition ranges enter the goal card only if a person gave them or the librarian gave them with a source. Where it cannot be filled, leave it blank and pass "decide this value" to S3 (P2, P4).

Why separate it: scatter an unrefined question in parallel and N subagents each solve **a different question.** Those results cannot be synthesised.

#### 4.5.2 S3 — per-axis parallel independent analysis (system designer · LLM + Python)

- **Input**: the goal card + **its own single configuration** (whichever S3.0 left) + the librarian entries it requested itself. **A sibling's output is not an input.**
- **Output**: a **constraint** on (its own configuration, its own axis) — "looking only at this axis in this configuration, this is the permitted interval".
- **It does not decide.** Choosing the operating point is S4's job. This is the practical device that preserves independence — if each picks a point, N different plans come out and synthesis becomes impossible.
- **It declares its method**: `method: deterministic | llm_estimate`. A deterministic output takes a `computed:` source; an LLM estimate takes an `assumed:` source (§5.3). That label becomes the confidence weight in S4.
- **It may abstain**: `verdict: feasible | infeasible | abstain` plus the numbers behind it. With no grounds for a judgement, it abstains rather than guessing (P5).
- **It runs once.** Recursive calls forbidden, with a count ceiling (cost control).
- **In explore mode it answers in orders of magnitude.** It gives the permitted interval as a decade rather than a figure, and does not put three significant digits on a calculation with an estimate in it (§5.8).

Structural guarantees of independence — blocked by structure, not by request:
1. Subagents run as **separate calls**, and each writes output only to its own file.
2. They have no read permission on a sibling's file path.
3. The validator treats a cross-reference between `axis_*.json` files as a failure (§8 check 11).
4. Librarian queries are isolated by `caller_id`, and the id is issued by the fan-out runner (§4.3.1). The librarian cannot become a detour between siblings.

##### 4.5.2.1 What an axis subagent is handed

The four above block things **between** siblings. This subsection governs the space between an axis and **its own computation.** It was brought across from `agentic-microscope`'s verdict packet on 2026-09-17, and **its shape there does not fit us as it stands** (§10.2.1).

**Why it does not fit, first.** Their subagents **take proposals that already exist and run them against a gate**, so there is a "list of findings to judge". Our S3 does not judge proposals; it **makes intervals** (§4.5.2). There are no findings yet, so there is no list of findings. What crosses over is not the list but **the failure the list was preventing.**

**The failure it prevented: silence reads as headroom.** Their wording was "a margin with no finding reads as headroom". On our side the same failure looks like this — **if an axis produces no interval for two of the five inequalities it owns, that silence reads as "this axis does not constrain there".** Not constraining and not having been able to compute are different, and S4 cannot see the difference. So:

- **Enumerate every inequality it owns**, and for each produce either an interval or an abstention. §4.5.3 assigns inequalities per axis, so this list is **derived and not declared by the axis.**
- **Separately carry what it ran and got no interval from** — whether the input was missing, or the inequality does not bind under those conditions. Those are different statements, and omitting them makes both "no constraint".
- **Silence is refused.** If something is on the list with neither an interval nor an abstention, that axis's output is not accepted.

**Separate computation from interpretation — this crosses over unchanged.** On their side the quantitative half is produced by code and the subagent **does not recompute that margin.** It draws on the design side the line §4.6.1 draws on the execution side. Our `method: deterministic | llm_estimate` merely labels one output; it does not split the two halves. **An inequality that can be produced deterministically is produced by code, and the subagent takes only those with no closed form.** Recomputing produces the same quantity in two places, and when they diverge there is no knowing which one entered the plan (the same failure as §0.4-6's "one declaration, one parser").

**Vocabulary must not be readable two ways.** They used `accept`/`refuse` and **at the first real convening two agents used the two words in exactly opposite senses** — one used `refuse` to mean "the finding stands", the other used `accept` for the same thing. "Accepting" a finding can mean granting the finding or letting the proposal through. **Our `verdict: feasible | infeasible | abstain` does not have this collision because its subject is the configuration** — it stays. What is kept is the rule: **judgement vocabulary must carry its subject inside the word, and when it changes, the old word is not deleted but left with "why this is now refused".** Delete it and the next person picks the same word again.

**An axis output has four states and they are not collapsed.** Collapsing two of them on their side led to **a gate returning FAIL while saying "it produced no result".** Our four: `returned` (an interval came) · `abstained` (the axis stated it has no grounds) · `not_run` (that axis does not apply to that configuration, §4.5.3) · `failed` (it was called and nothing came back). **Collapse `abstained` and `failed` and an axis that abstained under P5 looks the same as a dead one, and the first is normal while the second has to stop the plan.**

**Subagents are given no write tools.** Only reading is opened — not restraint, but inability (P4). Each agent directory's `.claude/settings.json` enforces it. All five of their roster files were `tools: Read, Grep, Glob`.

**Refuse on read-back.** A verdict with no supporting numbers · an interval for an inequality not on its own list (the axis trespassed on another's) · silence on something that is on the list · an abstention with no reason. **One refusal and the round's output is not used** — a refused output is not an absent output, and synthesising without it **records a review that did not happen.**

#### 4.5.3 Configurations and axes — two orthogonal dimensions

**Axes are written to be modality-neutral.** Since the measurement target is open (§1), an axis must be **a question any optical measurement has to be asked**, not "something about the optical trap".

| | Microscope | Simulation |
|---|---|---|
| A1 | signal and noise (SNR, detection limit, background, artefacts — on a spinning disk the **exposure time must be an integer multiple of the disk period** or striping remains) | integration stability (timestep vs the shortest characteristic time) |
| A2 | statistics required (sample count, record length, repetitions) | statistics required (seed count, trajectory length) |
| A3 | sample health (photodamage, bleaching, heating, concentration) | finite size (box vs correlation length, boundary conditions) |
| A4 | configuration fitness (device combinations, optical-path exclusivity, automatability) | sampling (save interval vs the observable's timescale) |
| A5 | temporal stability (drift, PFS state, resettling after a configuration switch, total elapsed, scheduling) | resource budget (wall clock, storage) |
| A6 | spatial resolution, field of view, optical sectioning (NA, magnification, pixel size, pinhole, axial resolution). Because of the objective turret and the 1.5× zoom, **magnification is a discrete set** | — |
| A7 | **driving and motion** (power, trap count and splitting, multiplexing limits / stage and trap speed, acceleration, settling, escape) | driving protocol (shear rate, force ramp) |

A6 became necessary once imaging became a first-class modality. It did not exist while only the optical trap was assumed, and **its absence was itself the evidence of the bias.**

**A7 — the limits on the side that perturbs the system.** The first six axes ask "what is being seen"; A7 alone asks "what is being done":

- **Drive quantities**: source and laser power, **trap count `N` and splitting** (power per trap ≈ total/`N`, so the per-trap stiffness falls with it), the multiplexing scheme's channel count and update rate, the minimum separation at which traps start to interfere.
- **Motion**: the piezo stage (range, bandwidth, settling time, whether closed-loop), the motorised stage (speed, acceleration, backlash, repeatability), **the travel speed of a trap position.**
- **The coupling limit — escape**: move a trap too fast and drag beats the trap force and the particle is lost. To an order of magnitude, `v_max ~ k·x_max/γ`. This single inequality **binds a drive quantity (`k`) and a motion quantity (`v`) directly.**
- **Settling time** sets when measurement begins → it becomes an input to A5 (temporal stability).
- **Safety coupling**: total power hits P0's safety limit before it reaches A3 (the sample) (§2.1). The interval A7 produces is always a subset of the safety limit.

**A7 — the simulation side.** The driving protocol (shear rate, force ramp) is owned by A7, not A1. A1 produces an upper bound on the **timestep** at a given shear rate (`dt ≪ 1/γ̇`), but that takes γ̇ as an input; it does not produce **the permitted interval for γ̇ itself.** Without A7, the drive quantity enters the plan as a number no axis reviewed. The inequalities A7 owns:

- **Quasi-staticity**: ramp duration ≫ the system's relaxation time. Break it and you measure the ramp rather than the state.
- **Reaching steady state**: the strain that has to accumulate before steady state under shear. Total step count is also constrained by A2 (statistics) and A5 (budget), but "how much do we have to strain it" is a question on the driving side.
- **Model validity**: is the drive strength inside the range where the overdamped assumption holds.

**A6 does not exist for simulation, and the number is left empty.** An axis number has to mean the same thing on both sides for the bridge (M4) to put `axis_*_a7.json` side by side and compare. Pulling simulation's driving axis up into A6 would make A6 mean resolution on one side and driving on the other. **A hole in the numbering is not a cost but the condition for correspondence.** So the axes are seven for the microscope (A1–A7) and six for simulation (A1–A5, A7).

**An inapplicable axis abstains; it does not fall off the list.** In an equilibrium simulation, A7 leaves a card abstaining with "no driving requested". It is not cut out of `capabilities/` — cutting it out means **nothing records the fact that a constraint was absent** (P1).

**Why driving and motion are not split into two axes** — this is where the criterion for splitting an axis comes from:

> **(a) Variables appearing together in one inequality are owned by one axis.**
> **(b) No axis requires another axis's *output* as an input.**

Several axes each producing an interval on **the same parameter** is normal — exposure time is constrained by A1, A3, A5 and A6 all at once, and taking that intersection is exactly S4's job. The problem is elsewhere:

- Break (a) and **the same inequality is duplicated across two axes.** If a driving axis and a motion axis each write the escape condition `v_max ~ k·x_max/γ`, the two will necessarily diverge. One inequality belongs in one place.
- Break (b) and **an axis that has to see a sibling** comes into being, and S3's independence (§4.5.2) collapses.

A contrasting example: for a spinning disk, `exposure time = n × disk period` has both variables as **directly settable parameters**, so A1 can own that condition alone and produce intervals on both variables together. The other axes each produce their own intervals on exposure time and S4 takes the intersection — nothing breaks.

When creating a new axis, put it through (a) and (b) first.
**A configuration (modality) is the second dimension, orthogonal to the axes.** S3's fan-out is (configuration × axis); the axes are fixed but **the configuration list differs per question** — S3.0 draws it deterministically from `contracts/capabilities/`. If the observable is "particle trajectory", the optical trap and brightfield tracking remain as candidates; if it is "local concentration field", confocal and widefield fluorescence do.

**Not every configuration yields an observable.** An optical trap has no detector — the trap light is blocked on every detection path, so it is not visible to a camera, and it is therefore used **not as a replacement for an imaging configuration but layered on top of one.** Configurations split into two roles:

| Role | What | What it declares in `capabilities/` |
|---|---|---|
| `imaging` | produces observables | the observable list |
| `perturbation` | perturbs the system and produces nothing itself | which configurations it can be layered with |

S3.0 screens only `imaging` configurations by observable. A `perturbation` configuration is layered onto the selected imaging configuration when the goal requires that driving, and that combination too has to be **a valid tuple in the optical-path table.** Without this distinction the contract demands of an optical trap an observable it does not have (§0.3-1).

**Cost control**: after S3.0, at most **3** configurations are kept. 3 configurations × 7 axes = 21 subagents, equal to `max_subagents_per_question` in `validation_limits.json`. That ceiling is not decoration — if four configurations all survive it is 4 × 7 = 28 and it actually binds.

**The only discriminators usable for cutting are ones evaluated at the capability level.** Until 2026-09-17 this subsection said "over the limit, cut by the goal card's priorities", and that was **a rule presuming information it does not have.** None of the goal card's four priority items (`physical_feasibility`, `target_accuracy`, `evidence_grade`, `cost`) **can be evaluated at S3.0** — all four require numbers S3 produces, and this cut is what decides whether to run S3 at all. The microscope session found it while implementing S3.0.

So the rule is:

1. **Cut with discriminators decidable from `capabilities/` alone** — `requires_contrast` (a configuration that does not match the contrast the sample provides is not a candidate), and switching cost once there are values for it. These are true or false without S3.
2. **If it still exceeds the ceiling, do not cut — stop.** Ask the person once through §4.5.1 (c) — which configurations to look at is answerable by whoever knows the purpose.
3. **Do not drop a candidate without grounds** (P16). An untried configuration never accumulates the record that would justify trying it, so one cut arbitrarily is disadvantaged permanently. That is exactly the path by which bias fulfils itself, and the failure P16 named.

**If the ceiling binds often, that is not a ceiling problem.** If questions where all four configurations survive are common, then whether seven axes have to run independently per configuration needs revisiting — raising the ceiling raises the cost, and multiplying the ask-backs consumes the person. Write it in §11 before editing this subsection.

The axes are **a fixed list** and do not change per question. Some axes abstaining as "not applicable" is normal. Adding or removing an axis means editing this document (P10).

#### 4.5.4 S4 — synthesis and trade-offs (system designer · LLM + Python)

1. **Per-configuration intersection (Python, deterministic)**: for each configuration, take the intersection of the per-axis permitted intervals. A configuration whose intersection is empty is dropped, together with **which two axes conflict at what values.** If every configuration drops, it ends as a refusal card (P5).
2. **Configuration choice + applying priorities (LLM)**: compare the survivors, choose one, and choose a point inside that configuration's intersection. Use the priorities the person put in the goal card; if there are none, use the default policy — **physical feasibility > target accuracy > evidence grade > cost** — and write that fact into the card. **Safety is not on this list**: it is not something to trade but a constraint already filtered (§2.1). All else equal, choose **the one with the better evidence grade.**
**The comparison rule in explore mode**: **a difference under 10× is not a difference.** When a configuration comparison falls within the same order of magnitude, treat it as a tie and break it by evidence grade → safety margin → whichever has been tried less (P16) → cost. Choosing a configuration on a marginal numerical edge is using information that is not there.


   **The concession order is carried in by the goal card** (settled 2026-09-19, §11-9). There is no fixed order and no default.

   - **Five axes climb the ladder**: A1 (signal and noise) · A2 (statistics required) · A5 (temporal stability) · A6 (resolution and field of view) · A7 (driving and motion). **A4 (configuration fitness) is off the ladder** — an optical path either exists or does not; it is not something to concede. **A3 (sample health) has a floor** — P0 orders people → instruments → samples and data, so it is not fully tradeable.
   - **The order cannot override a `hard` constraint.** Being first does not buy something physically impossible. The order is **a tiebreak among possible things**, not a permission.
   - **A concession is recorded by name.** Which axis was conceded by how much, to gain what, stays in the trade-off record (3 below).
   - **If the card carries no order, S4 does not guess.** Where things are close and there is no order, escalate to the person through §4.5.1 (c). Choosing to have no default was intended to produce exactly this outcome — asking once is cheaper than inventing an order that does not exist.

   **And the order has to be in the goal card, because it is used at S2.** Written **before** any axis produces a number, it cannot be a post-hoc justification. Allowing it to be set later means **choosing the order that justifies the configuration already chosen.** It is the same argument as §9.3's "write down what counts as better before starting" for the A/B, and it prevents the same failure.
3. **Trade-off record**: leave the chosen configuration and point, **the discarded configurations and points**, and the reasons for discarding, as numbers (S6). An axis that leaned on an `llm_estimate` marks that dependence.
4. **Forbidden**: it makes no new numbers and queries no new facts. S4 **only combines.** If the conclusion is that more knowledge is needed, the right move is back to S3, and that is a new revision (P9).

Why forbid it: once the synthesis stage starts querying, S3's parallel independence becomes meaningless. One final agent ends up judging everything alone again.

#### 4.5.5 S5 — outputs and identifiers (system designer)

- `plan_<agent>_<qid>.json` — the record. It carries every mandatory item in §5.4. It has to pass the validator to be `VALIDATED` (§5.5).
- `plan_<agent>_<qid>.md` — **generated from the JSON.** Edit it by hand and the system does not read it (§5.6).
- Every file of one question sits **flat in one folder**, `questions/<qid>/` (§7.1).
- `qid` convention: `<agent>-<YYYYMMDD>-<NNN>` (e.g. `mic-20260916-001`, `sim-20260916-003`). Every output of one question shares the qid, so one grep gathers the whole history.
- A re-run reuses the qid and increments `revision`. Earlier outputs are not deleted; they sit alongside under a **`v2_`** prefix (P9, **§7.1 rule 3**).
- **Revision 2 may cite revision 1 as a record and may not use it as an input.** The gate no longer objecting and it being all right are different questions, so the simulation manager deliberately left it open. What §4.5.2 forbids is **reading between siblings within one fan-out**, so it does not catch revision 1, which is a different fan-out. But **feeding revision 1's numbers into your own computation** inherits exactly the reason the re-run exists — that something was wrong. So what is permitted is **comparison**: writing "revision 1 was X and this one differs because Y". It is the same line as check 12 treating transport **as comparison rather than re-derivation**, and that line is what makes P9's reason for keeping revision 1 hold — it is kept as something to compare against, not as material.
- Filenames are written in English per §0's language convention (`question_…`, `goal_…`, `plan_…`).

#### 4.5.6 Stopping conditions at each stage

| Stage | Where it can end |
|---|---|
| S2 | the answer is already known → hand to the librarian and stop · only a person can answer → ask back and wait |
| S3 | every axis `infeasible` → refusal |
| S4 | the intersection is empty → refusal (naming the conflicting axes with numbers) |
| S5 | validator failure → stays `DRAFT`, revision increments |

Early termination is a first-class output. **The cheapest experiment is the one that does not have to be run.**

---
### 4.6 The execution layer — system operator (S6)

It takes an approved plan, breaks it into per-module work and dispatches it, watches the execution, and records the results. **It does not change the plan.**

```
      plan_<agent>_<qid>.json (the record, APPROVED)  +  plan_….md (context)
                        │
┌─ system operator ─────┴────────────────────────────────────────
│
│ [O1] preflight       per-module state query · re-confirm limits · dry-run
│   │                  one failure and it stops here (instrument untouched)
│   │
│ [O2] dispatch        plan.json → mechanically derived module commands (Python)
│   │                  lowest-risk modules first, sources and power last
│   │
│ [O3] watch           compile stop_criteria into monitors, abort immediately on violation
│   │                  no LLM in the abort decision
│   │
│ [O4] record          log.json (append-only) + deviations.json → result card
│
└───────────────────────┬────────────────────────────────────────
                        │  fixed interface: preflight / apply / read / abort
        ┌───────────────┴───────────────────┐
   [simulation]                        [microscope]
   src/hoomd_backend.py            src/orchestrator.py
   src/mock_backend.py                single entry point · parallel · locks · sync · abort fan-out
     (one HOOMD-blue job)               │
                                        └─ src/devices/ (each knows only its own device)
                                           dev_body · dev_camera1 · dev_camera2
                                           dev_fluor1 · dev_fluor2 · dev_dmd
                                           dev_confocal_laser · dev_confocal
                                           dev_piezo · dev_motor_stage · dev_tweezer
                                           manual · mock
```

**The boundary between designer and operator is the approval gate.** The designer has Tier 0 only (it executes nothing), and the operator is the only component holding Tier 1–2 (§6). An approval is valid only for a specific `(plan_id, revision)`, so if the plan changes the operator refuses to execute (§5.5).

#### 4.6.1 What Python does and what the LLM does

| | Python (deterministic) | LLM |
|---|---|---|
| Normal path | command derivation, unit conversion, dispatch order, interlocks, monitors, aborting | **not involved** |
| Exception path | detecting the anomaly and the abort itself | interpreting a situation the plan did not anticipate, writing the deviation report, proposing follow-ups |

**Rule: the LLM does not synthesise instrument or simulation commands.** Every command is derived mechanically from values in `plan.json`, and every command in the log carries a `from` field pointing at the field it came from (§8 check 14).

The reason is simple — in an irreversible action, a probabilistic output only adds risk (P4, P8). Where the LLM is needed is "writing up, so a person can read it, what happened that the plan did not anticipate", and even then the abort is already finished by Python.

#### 4.6.2 Why both the JSON and the Markdown are read

- `plan_….json` = **the commands.** Every parameter comes only from here.
- `plan_….md` = **the context.** It holds why this condition was chosen and what was discarded. It is used in an exceptional situation to judge "does this deviation break the plan's intent".
- **There is no case where the Markdown beats the JSON.** If the two disagree, it stops before executing. §8 check 9 is a check at writing time, and the operator confirms once more at execution time (P3).

#### 4.6.3 Module and device decomposition

**Simulation — five logical modules**

| | Module |
|---|---|
| MOD1 | initial configuration generation (placement, density) |
| MOD2 | integrator setup (timestep, thermostat) |
| MOD3 | observable measurement (save interval, computation) |
| MOD4 | checkpointing and storage |
| MOD5 | job submission and resources |

**Microscope — modules are divided by actual device, not by logical unit.**
Each device has different control software and different I/O terminals (§4.6.6). Grouping them logically makes the operator assume **an integrated interface that does not exist.**

**Devices are two layers: the control channel (the device) and the elements inside it.** One microscope body has ten independently moving elements. Without looking at element granularity, neither interlocks nor optical paths can be expressed.

| Device (control channel) | Elements | What has to be filled in at M3 |
|---|---|---|
| **microscope body** | objective turret · condenser turret · filter turrets 1 and 2 · shutters 1 and 2 for the filter turrets · dia lamp · PFS · fluorescence source branch · 1.5× zoom (on/off) · output direction | whether each element has its own channel or shares one body SDK, each turret's position list and switching time, the PFS operating range and reacquisition time |
| **confocal (spinning disk)** | dichroic selection 1 and 2 · filter wheels 1 and 2 · **the spinning disk (rotation speed, in/out position)** · **the laser shutter** · the detector | each wheel's position list and switching time, the disk speed range and stabilisation time, in/out switching time, shutter response time, acquisition format |
| cameras ×2 | — | which output direction each attaches to, trigger scheme, whether they can be used simultaneously |
| fluorescence sources ×2 | power · wavelength · shutter | which branch each corresponds to, whether the shutter is on the source side or the body side |
| DMD | pattern · sync | pattern upload path, sync scheme with camera and source |
| confocal laser | power · line (wavelength) · interlock | power control channel, interlock signal |
| piezo stage | xyz | range, speed, bandwidth, settling time, whether closed-loop |
| motorised stage | xy(z) | speed and acceleration limits, backlash, repeatability |
| optical tweezers | power · trap count/splitting · trap position | **the ceiling on trap count and the splitting scheme**, the trap travel-speed limit, the stiffness calibration path |

There are about twenty-five elements, and **far fewer control channels.** So the file-splitting criterion is not the device but **the control channel** (§4.6.5).

"What has to be filled in" is **confirmed and then put into the librarian's KB.** What was extracted from a prior repository on 2026-09-17 is in `kb/staging/devices.v0.json` (§11.1), and the empty cells are filled as they are confirmed on the instrument. The reason it does not go in `envelope/` is §4.3.2 — device characteristics are knowledge. They are not filled in by guess now (P2).

Modules and devices receive **only their own parameters.** There is no direct device-to-device communication; ordering, synchronisation and interlocks are held by the operator — the same reason as S3's parallel independence.

#### 4.6.4 What it does not do

- **It does not fix the plan.** If it cannot be executed as written, it stops and returns it to the designer with the deviation. That is a new revision (P9).
- **It does not execute an unapproved plan.**
- **It does not paper over a failure with a retry.** Retries happen only the number of times the plan states, with that fact left in the log.
- **It does not interpret results.** The operator's output ends at the result card; interpretation is the next stage's work.

#### 4.6.5 The backend boundary

- One fixed interface: `preflight() / apply(params) / read() / abort()`. HOOMD-blue or a camera looks the same shape to the operator.
- **`src/devices/mock.py` is a first-class backend.** The whole pipeline has to run with no hardware and no HOOMD, and M2–M3's validation is done on the mock (§9).
- **A backend holds no policy.** Judging limits is the envelope's and the operator's work; a backend relays commands and returns state. Put a condition judgement in a backend and the envelope exists in two places.
- Swapping the backend does not change the plan. The same plan.json runs unchanged on the mock and on the real instrument — that is the practical definition of reproducibility (S3).
- **The file-splitting criterion is the control channel.** If one body SDK handles ten elements, one file `dev_body.py` takes those ten. Split a file per element and several files hold the same SDK handle, and at that moment the single entry point (§4.6.8) breaks.

#### 4.6.6 Heterogeneous control channels (the microscope's actual conditions)

The nine kinds of device currently attached to the microscope — the body, two cameras, two fluorescence sources, the DMD, the confocal laser, the confocal, the piezo stage, the motorised stage, the optical tweezers — and the roughly twenty-five elements inside them (§4.6.3) are **each operated through different software or different I/O terminals.** What that fact forces on the operator's design:

1. **There has to be a device registry — and it is knowledge.** Per device, record:
   `{id, elements: [...], control: sdk | daq | gui_manual | file_watch, automatable: full | partial | none, read_back: bool, sync: hw_trigger | sw_sequence | none, lock_group: ..., limits: {...}}`
   What goes in `limits` is **what the device can do** (travel, maximum speed, exposure range), not **what we permit.** The latter is policy and belongs to `envelope/safety.json` (§4.3.2). Put both in one field and the safety limit gets updated along with the device specification.
   Optical-path constraints are not here but in the optical-path table (§4.6.7).
   The registry is owned by the librarian — in `kb/staging/devices.v0.json` during M1–M2, and in `envelope/snapshot.json` from M3 (§4.3.2).
   **The planning stage (S3 axis A4) and the execution stage (O1 preflight) look at the same table.** Wherever it lives, that is the condition.


**A sample registry sits beside it as its own table — and it names an individual, not a product (2026-09-19).**

**Separating individual from type is the whole of this judgement.** A measurement is made of an **individual** and a specification is written about a **type.** What had its fluorescence band measured today is not a catalogue product line but **what is in the tube on this bench**, and if that bottle later turns out to be a different product, **the observation is still true of the bottle and becomes false of the product.** So the first item cannot be `AFR-0500-COOH` — what is on the bench right now is **a particle with no catalogue identity.**

So it splits three ways: the **individual** (the registry's item), the **type** (an ordinary KB entry, `spec:<catalog>` E3), and **the claim joining them** ("this bottle is that product") — which carries its own grade. As of 2026-09-19 that is E5, and it becomes E3 when a person reads the label. **Putting all three in one cell is what architecture did with pixel size this morning: grading a value before settling what it is about.**

**Its place is the librarian's `kb/staging/`, beside the device table.** Not the same table — the device table's columns are all `driver`, `automatable`, `read_back`, and **all false for a sample**, so the same reason that kept a thermometer out of the devices applies here (§5.3.3). The reason it is the librarian's is the same as §4.6 saying of the device registry "it is knowledge" — **what is in this laboratory is knowledge, and knowledge lives in one place** (P14). Two reasons it is not the microscope's run record: one sample is used by **two agents** (the simulation models it), and a bottle outlives a run.

**The grounds for creating it are not subject resolution.** It passes the criterion the librarian manager set — *does this registry have a reason to exist beyond resolving a subject* — because **a run record has to say what was on the stage.** The value of that criterion is that it answered three cases differently on the same day. The quantity passed; the place **did not pass and ended as a reserved word (`ambient`) instead of a registry**; the sample passed. **Creating a registry in order to satisfy a check is inversion, and it was refused three times that day.**

**And the strongest evidence that this registry is needed was produced by a check itself.** Check 44 refused the sample entries' subject and the librarian seat deleted them rather than gaming it — which was right. **But the claim did not disappear**: those entries' names became `tracer_particle_density`, `tracer_emission_peak`. **The subject, having been refused, moved into a string nothing checks.** The refusal did not remove the problem, it **made it invisible**, and sixteen entries stood on top of it.

2. **A device that is not automated is not pretended to be.** A device operable only through a GUI is handled by `src/devices/manual.py` — the operator **issues an instruction sheet and takes a person's confirmation.** The sheet and the confirmation record stay in `runs/<run_id>/manual_steps.md`, and **without the confirmation it does not move to the next module.** Pretending a half-automatic system is fully automatic makes the entire log false (P2, P9).

3. **An optical path is a state vector, not pairwise exclusion** (§4.6.7). The initial design's `exclusive_with` cannot express this instrument — it is replaced below.

4. **Synchronisation is held by the operator.** Record separately which combinations are bound by a hardware trigger (for example source, DMD and camera) and which by software ordering. Let devices talk to each other directly and the ordering does not stay in the log.

5. **Different control channels have different failure modes.** An SDK throws an exception, a DAQ **quietly outputs the wrong voltage**, and a GUI tells you nothing. So every device has to be able to read its own state back through `read()`, and **a device that cannot be read back is treated as `automatable: none`.** Automation that cannot be confirmed is not automation.

#### 4.6.6.1 The order for standing up real control (2026-09-20, settled by the person)

Measuring `tracer_brightness` requires the instrument to actually move, and `src/devices/` today holds only `manual.py` and `mock.py`, while **the `control` cell of all ten registry channels is empty.** §10.2's "hardware control path" row is open for that cell, and the gate (the four interface functions) is satisfied. **What that row records decides the order: wrapping a control path needs no safety limit.** So the wrapping and the person's writing of `envelope/safety.json` **go in parallel** — what waits is only **the moment the real thing moves.**

**1. The scope is the three brightness-path channels.** `widefield_source_a` (excitation) · `camera_red` (605-band collection) · `stand_ti2e` (objective and filters). **All three are `automatable: full` and `read_back: true`.** It was chosen by counting, and the result lines up with §10.2.1's "one at a time" by itself — **the two channels without read-back are not on this measurement path at all.** Wrapping all ten at once creates control paths nobody uses, and **untested code is a class this repository has counted several times.**

**2. The `control` cells are extracted from a prior repository.** That is exactly what §10.2's row points at — the driver call style, the channel, the read-back path. **It passes a §10.2.1 ruling and only structure crosses: no figures cross** (§10.3). The ruling is written into `microscope_agent/rulings.jsonl` with its `by` (§7.1 rule 9).

**3. The two without read-back are automated with the blind spot stated — and where that meets §2.1 is written here.**

`laser_combiner` and `optical_tweezers` accept commands and are not confirmable. The person chose **to automate them and nail the blind spot into the run record.** **§2.1 rule 2 says stop when it cannot be read back, and rule 8 says no signal means no permission.** Both meet this choice, so the boundary is written narrowly:

- **The command goes out. Nothing treats that channel's state as confirmed.** The run record carries `verification: none` for that channel, and if that is empty the run does not stand.
- **No safety judgement is built on that channel's state** — rule 8 exactly. Permission comes only from a limit in `envelope/`, a human approval, or a deterministic check.
- **An irreversible action still requires a confirmed limit** (check 57). A trap can be commanded, but **that does not make its being off something the system can confirm.**

**And there are two failures that block an irreversible action — the paragraph above covered only one.** The seat holding check 57 pointed it out:

    - **The limit is unconfirmed** (`confirmation: carried_over`) — how far it is permissible to demand has not been settled.
    - **The limit is confirmed and nobody can read back whether it was respected** (`verification: none`) — the demand is legitimate and **what happened is unknown.**

    **One check does not carry both — architecture gave 57 both in a message and that was wrong.** The inputs differ: 57 reads **the envelope and the plan's `actions[]`**, while the second reads **the run record**, and a run may not exist yet. Who fixes it and how differ too — the first is **a person did not measure**, the second is **a machine cannot see.** If one check carries both, then on failure **it cannot say which rule was broken.** The seat holding 57 followed the document and not the message, and even wrote "not handled here" into the docstring. **The second is check 66.**

    **And splitting them revealed this: there is nothing for the second to hold on to.** This subsection put that rule on the run record's `verification`, and **`run_log.schema.json` has no such field** (confirmed 2026-09-20, zero mentions). It is the shape where **a rule is written and nothing carries it**, and the class counted most often today. 66 brings the field and the check together. And the second is precisely §2.1 rule 8 — with no read-back there is **no signal at all, and an absent signal does not permit.** A confirmed ceiling gives **an upper bound on what may be demanded**, not **what happened.**

    **Therefore: a confirmed limit binds the demand, read-back confirms what happened, and an irreversible action needs both.** That result lands directly on the person's third choice — `laser_combiner` and `optical_tweezers` **accept commands, and no irreversible action through those two runs**, whether or not the limit is confirmed. It opens the day a read-back path exists. **Setting a trap is not itself irreversible, so nothing is paralysed** — what is blocked is the irreversible subset.
    **The remaining risk is accepted, not resolved, and it is written that way.** `optical_tweezers` is a laser and falls under P0's first line. This choice is **a person accepting rule 2 for that channel**, and the condition for reversing it is the day a read-back path exists — on that day this paragraph is edited first.


#### 4.6.7 An optical path is a state vector — and that is what a "configuration" is

Writing out every **discrete selector** that determines an optical path gives: output port, fluorescence source branch, filter turrets 1 and 2, the shutters for filter turrets 1 and 2, the objective turret, the condenser turret, the 1.5× zoom, the dia lamp, and on the confocal side dichroics 1 and 2, filter wheels 1 and 2, **the spinning disk in/out**, and **the laser shutter.**

**The spinning disk's in/out splits the same hardware into two modalities** — with the disk out, the same path is widefield. In the configuration list these are two separate items, and the switching cost is the disk in/out time.

**Optical-path state = the tuple of these selectors.** The combinations number in the thousands and only a few are physically valid.

**It cannot be expressed as pairwise exclusion (`exclusive_with`).** The real constraint is not "A and B cannot be simultaneous" but **"only this tuple is valid."** The filter turret positions, the dichroic selection and the output port all have to agree for light to reach the detector, and that does not decompose into pairs.

So there is **a whitelist of valid optical paths.** For the same reason as the device registry it is knowledge, so the librarian owns it: in `kb/staging/optical_paths.v0.json` during M1–M2, and in `envelope/snapshot.json` from M3 (§4.3.2):

```
{ id, selectors: {output_port, fluor_branch, filter_turret_1, filter_turret_2,
                  objective, condenser, zoom_1_5x, dia_lamp, shutter_1, shutter_2,
                  dichroic_1, dichroic_2, filter_wheel_1, filter_wheel_2,
                  spinning_disk_position, laser_shutter},
  sources: [...], detectors: [...], observables: [...],
  switch_cost: {time, perturbation} }
```

**And one item in this table is exactly §4.5.3's "configuration (modality)".** `contracts/capabilities/` maps `observable → configuration`, and **the optical-path table** maps `configuration → selector state`. **The table S3.0 consults when choosing candidates and the table the orchestrator uses for interlocks are the same table.** Keep two and they diverge eventually, and the moment they do there is a configuration that "is possible on paper and where no light actually arrives". Since they are split across two files, **the validator checks that the configuration id sets match** (§8 check 38).

**Composition requirements attach on the observable side.** Some observables come only with a perturbation configuration layered on — the position distribution of a trapped particle exists only with the trap on. That is not expressed as a **new path id** like `transmitted_with_trap`. This table's `composable` block already says which configuration composes with which, so a new id writes the same statement into a second table and **the two tables diverge.** Instead, `capabilities/`'s `produces` items may be `{id, requires_composition}` rather than a string, and check 38 verifies that the requirement does not contradict this table — the named configuration has to be a `perturbation`, and its `composes_with` has to point back. **"Composes with any configuration" is a sentence a table can hold and an instrument cannot.**

Why `switch_cost` enters the plan: an optical-path switch is not free. A turret rotation takes seconds and leaves vibration and a focus change. A plan that changes configuration twice within one question has to account for that cost in A5 (temporal stability).

**Declaring it is not enough.** An optical path can be changed by a person's hand, so O1 preflight confirms each selector's actual position at execution time through `read()`. If a selector cannot be read back, that path is `automatable: none` and goes to a `manual` instruction sheet (§4.6.6 rules 2 and 5).

#### 4.6.8 The microscope orchestrator — one parallel entry point

On the microscope side there is **one parallel Python script that operates all the hardware** (`src/orchestrator.py`), and the per-device scripts (`src/devices/dev_*.py`) are **subordinate to it.**

**What the orchestrator holds** — what a device script never touches:

| Responsibility | Content |
|---|---|
| Parallel execution | **one worker = one control channel** = one file in `src/devices/`. Two cameras are two channels so there are two workers; the body's ten elements are one channel so inside it is sequential — the turrets share one machine, so that is also physically true. |
| Device locks | no simultaneous commands to one device. One exclusive lock per device. |
| Optical-path locks | **compiles** the optical-path table's valid tuples (§4.6.7) **into lock groups.** No acquisition begins during a switch. |
| Ordering | a command **raising** output is last in a parallel set; a command **lowering** it is first. |
| Synchronisation | the arm-and-fire ordering of combinations bound by a hardware trigger. |
| Timeouts | a ceiling on every operation. The `manual` channel waits on a person, so it gets its own ceiling. |
| Abort fan-out | on abort, propagate to all devices simultaneously. If some fail, keep trying the rest and record every outcome. |
| State snapshots | gather `read()` before and after each stage and leave it in the log. |
| Time base | pin a common `t0` and put every worker's events on the same clock (§4.6.9). |

**Constraints on a device script**:
1. **It knows only its own device.** It does not import another `dev_*.py` (§8 check 16).
2. **It implements four functions only**: `preflight() / apply(params) / read() / abort()`.
3. **It does not handle parallelism, ordering or locks itself.** Doing that on the device side scatters the interlocks across several places.
4. **It stores no state.** The record of state is the device itself, and the only copy is the orchestrator's snapshot.
5. **It holds no policy** (§4.6.5). Judging limits is the envelope's and the operator's work.

**This instrument's concrete interlocks** (P0, §2.1):

1. **Blocking starts with the shutters.** An abort closes filter-turret shutters 1 and 2 and **the laser shutter** first, and then lowers power. Ramping a lamp or a laser down is slower than a shutter, so the fastest blocking means is used first.
2. **Retract z before rotating a turret.** While the objective or condenser turret rotates, a lens can collide with the sample and the coverslip. This is not a condition but **an interlock** — whatever the plan demands, no rotation command goes out without the z retraction.
3. **PFS is turned off before a switch and re-engaged after settling.** Left on while a turret or the optical path changes, it loses focus and hunts. The reacquisition time is included in A5's settling time.
4. **No acquisition during a switch.** While the optical-path lock is held, no camera or detector begins an acquisition. The spinning disk begins acquisition **only after its speed is stable** — frames taken while accelerating do not match the period.

**Do not mistake what the parallelism is for** — this is the single most important line:

> The orchestrator's parallelism exists **to overlap waiting** (source warm-up, stage motion, temperature stabilisation, camera readiness). **It does not exist to obtain timing precision.**
> Combinations needing precise simultaneity (source, DMD and camera, and **spinning-disk rotation with camera exposure**) are bound by a **hardware trigger.** Trying to hit microseconds with software parallelism produces quietly wrong data.

**Single entry point rule**: every command going out to the instrument passes through the orchestrator. Allow a bypass call and the log splits and the interlocks become meaningless. `devices/manual.py` and `devices/mock.py` also sit under the orchestrator behind the same interface.

**There is no orchestrator on the simulation side.** One HOOMD job is a single backend, so there is nothing to coordinate in parallel. A layer that is not needed is not created for symmetry (P10).

#### 4.6.9 How parallel workers share one clock

Splitting workers by channel produces an immediate problem — **how to put events from different workers on the same time axis.** Matching frames from two cameras needs this answer.

There are three means of alignment, **in priority order:**

| | Means | Where it works |
|---|---|---|
| 1st | **a common hardware trigger's counter** | devices bound to the same trigger. The frame index is the time and there is no jitter |
| 2nd | **the device's hardware timestamp** plus clock alignment | devices with their own clock. Read both clocks at the same instant at the start and end of the run, and record offset and drift |
| 3rd | **a software monotonic clock** (an offset against the orchestrator's `t0`) | everything else |

**Rule: do not compute physics from a software timestamp.** OS scheduling jitter enters at the millisecond scale, so third-priority times are used **only for log ordering and causal sequence.** Values with physics riding on them, such as the time difference between two frames or a correlation function, come only from the first and second (§8 check 37).

**The two-camera case** is the archetype of this rule. The two workers run independently but are bound to **the same hardware trigger**, and each worker writes the trigger counter alongside its frames. Alignment is done by **counter match**, not by the soft clock. This is the actual implementation of §4.6.8's "parallelism is for overlapping waiting, not for timing precision".

**Time recording in the run log**: the orchestrator leaves `{t0_wall(UTC), t0_mono}` together at the start of the run, and every event afterwards is written as a `t_mono` offset. A device with a hardware timestamp writes `t_dev` alongside, and the clock-alignment measurements stay in the same log. It has to be possible later to trace which time was of which grade.

---
## 5. The shared contracts (`contracts/`)

### 5.1 Kinds of card

| Card | Who writes it | What it is |
|---|---|---|
| `goal` | the person | **why it is being asked** (`purpose`) plus what is wanted: observable + target accuracy + constraints + priorities + `intent`. The output of S2 refinement (§4.5.1). |
| `plan` (execution plan) | microscope, simulation | how to obtain it. All conditions + cost + stop/success criteria. |
| `plan_approval` | the person | which plan revision may be executed. |
| `scope_approval` | the person | which **condition range** may be executed without individual human approval. Expiry and count ceiling mandatory (§6.1). |
| `result` | microscope, simulation | what came out. Value + uncertainty + deviation + run_id. |
| `refusal` | anyone | why it cannot be done. A counter-example number is mandatory. |
| `ask_*` (envelope) | the bridge | the transport envelope carrying a plan/result to the other side. **It holds no numbers** (§4.4). |

**A card's `observable` carries the name only.** The definition is read from `contracts/observables.json`. Until 2026-09-18 `plan.schema.json` had `required: [name, definition]` with `additionalProperties: false`, so **every plan was forced to restate the definition**, and all three plan cards carried a sentence different from the vocabulary's. One fact in two places is two facts by next week — it already was.

The grounds are this repository's own precedent: it is **the same failure one layer up** as stopping an envelope from echoing the payload's numbers (check 9, §4.4-5), and "a carrier that echoes puts the same quantity in two places" applies to definitions too. And there is one more gain — today there is **no path at all** for an `estimator` to cross to the other side, whereas with the card carrying only the name and both sides reading the same vocabulary, **the estimator crosses by reference.** That is stronger than a copy (the reason §11-1 made `estimator` part of identity). The sentence a person reads is pulled from the vocabulary by the generated `.md` (P3). The bridge manager raised it.

Turning a received `ask_*` into a goal is **the receiving agent's S2.** The bridge does not write what is being asked — when the carrier writes the question, it is no longer transport (§4.4).

`status.json` and `r<N>_hashes.json` are not in this table. They are **thread ledgers, not cards**: no numbers, no grades, and no `qid` (one thread joins two questions). They record only whose turn it is, what repeated and what was substituted. The validator separates the two by an `artifact` field instead of `card`, and §0.3-2's conclusion — a contract nothing checks is decoration — applies here too.

### 5.2 Common fields

```
card,                              the kind -- what the validator picks a schema by
id, schema_version, qid,
thread, round, revision,
author (agent id), created_at, status,
numbers:     [ {name, value, unit, source, grade} ... ],
assumptions: [ {rationale_id, statement, numbers: [...], falsifier, gap_ref, authorised_by} ... ],
kb_refs:     [ {entry_id, grade, kb_version} ... ],
kb_gaps:     [ {observable, kind, searched, kb_version} ... ],
degraded:    [ agent_id ... ]
```

- `card`: the kind is written inside the card. **Do not trust the filename** — files get moved and names get changed.
- `qid`: the key binding one question's outputs (§4.5.5). The file path already says it, but the moment a card leaves the path (bridge transport) the path is gone.
- `thread`: a standalone run uses `solo-<qid>`. Only cards belonging to a bridge round trip have a real thread id.
- `numbers`: **the only place a card holds numbers.** Other fields do not write numbers directly; they point by name. Write the same number in two places and next week there are two values (P3).
- `assumptions`: the list of grounds for E5 numbers. Every `assumed:` number has to be explained here (§8 check 4). `authorised_by` records the fact that a person **instructed a value to be carried outside the range its source covers** (D3) — using a curve's endpoint at a wavelength beyond it, or applying a spec read at one condition to another. **An instruction does not raise the grade**: being told to use it is not evidence for the value, and the moment authority can lift E5 to E3 the grade scale becomes an authority scale and measures nothing. What this field lives on is **the E5/E6 boundary** — once an extrapolation is written as a number, what a person instructed and what a model invented look identical, and E5 may enter a card while E6 may enter nothing. So **a model cannot fill this field.** If it could, it would be the laundering path by which E6 enters a card. And this field does not attach to a KB entry — an entry states what is true under the conditions its source covers, and stretching that is a property of the plan that stretched it.
- `kb_refs`: the entries received from the librarian and **their grades at that time.** The grade of a `kb:` source is validated here (checks 21 and 25).
- `kb_gaps`: what was asked of the librarian and **not received** (§4.3.1). The opposite side of `kb_refs`, and it being non-empty is normal too. Every `assumed:` number points here (check 39) — an estimate nobody looked up and an estimate looked up and not found are not the same value.
- `degraded`: records that it proceeded without an absent collaborator (§3.1). Empty is normal and non-empty is normal. **Only hiding it is abnormal.**

### 5.3 The number four-tuple: value, unit, source, grade (P2)

Every number is `{value, unit, source, grade}`. **The source says where it came from and the grade says how far it can be trusted.** They are different information and both are needed.

**Evidence grades (E-grades)** — one scale shared by the whole system. Cards, KB entries and decision grounds all use the same ruler.

| Grade | Name | What | Example |
|---|---|---|---|
| **E1** | direct measurement | a value this system measured **at these conditions** | the actual reading of that run |
| **E2** | calibration-derived | the output of a calibration procedure. A validity range and an expiry are mandatory | the control-value vs actual-value curve |
| **E3** | literature / specification | peer-reviewed literature, textbooks, vendor specifications | solvent viscosity η(T), camera QE |
| **E4** | computed | a defining expression applied to E1–E3 inputs | `τ_D`, `k*` |
| **E5** | estimate | an assumption with its grounds written down | "the bleaching time constant is about this" |
| **E6** | model guess | a value the LLM invented | — **forbidden to enter a card or the KB** |

**The grade is derived deterministically from the source.** It is not self-reported (§8 check 21):

| source | Grade |
|---|---|
| `measured:<run_id>` | E1 |
| `calibration:<cal_id>` | E2 (expiry and condition range mandatory) |
| `kb:<entry_id>` | inherits that entry's grade |
| `spec:<device_id>` | E3 |
| `operator_read:<who>_<date>` | E3 — a value the operator **read** off the instrument |
| `literature:<ref>` | E3 — published but not a vendor spec. While `spec:` covered vendors, textbooks and papers had no prefix |
| `prior_run:<project>@<sha>` | E3 — **a run over there is not a run over here** (§10.3 rule 1). The ceiling for a measurement brought from a prior repository; measured again here it rises to E1 |
| `operator_recall:<who>_<date>` | E5 — a value the operator **stated from memory** |
| `computed:<formula_id>` | **max(E4, worst input grade)** |
| `assumed:<rationale_id>` | E5 |

**What an inference rests on, when it is not a quantity: `supports` (2026-09-20).** `inputs` names
quantities and a grade composes from them. Some entries rest on things that are not quantities at all,
and those were being written as prose in `validity_conditions` -- the same shape as the CV that read as
200 per cent, and the reason a distinction living only in prose is one nothing can act on. `supports` is
mutually exclusive with `inputs` and takes two forms:

- `{entry}` — another entry in this store. **It caps the grade**, the way an input does.
- `{external, who_could_confirm}` — a premise this repository does not hold and names who could settle
  it. **One of these removes the cap entirely**, because a chain whose weakest link is outside the store
  has no worst input to inherit from: there is nothing here to be worse than.

**So `computed:` caps against whatever is nameable, and stops capping when something is not.** That is
not a weaker rule; it is the rule declining to manufacture a bound out of an absence. An entry resting
on an external premise is not ungraded — it is graded by 5.3's ordinary route and says out loud that a
premise underneath it is unverifiable here, with a name attached to who could verify it.


**A target has no row in this table. And no new one is made (2026-09-19).** A **target accuracy** a person stated rides in a card as `target_relative_error` and the like, but **it has neither a source nor a grade.** The reason is the same split as §4.6 — just as the device registry's `limits` is **what the device can do** while `envelope/safety.json` is **what we permit**, a measured accuracy is a **claim** about the world and a target accuracy is a **decision** about what we will accept. **A decision is right by being made.** A grade is a scale for how far a claim can be trusted, so it has nowhere to attach on a decision.

`operator_recall:` looks closest but is **the wrong kind**: that is an operator stating **a fact about the world** from memory, and it is E5 because memory is unreliable about facts. Grading a target E5 would be saying **the person may be misremembering their own target.** `assumed:` is wrong for the same reason — it records a person's target as an assumption.

**The proposal to create a `decision:` source kind is refused.** This table is a function from source to grade, and P2 says the grade is derived from the source. **Putting in a source that yields no grade punches a hole in that invariant** — and that hole would be writing "this is not a source" as a source kind. For the same reason a ceiling does not live that way, a target does not either. The bridge manager raised all three together.

**The line is drawn not at "numbers that look like targets" but between a person's target and everything computed from it.** The **statistics requirement** derived from a one-decade target is not a decision but **a claim about what statistics demand**, so it stays as a `numbers[]` item with a `computed:` source and a grade. The target losing its grade does not make the computations under it lose theirs — the opposite: when a decision steps outside the grade scale, **the grades of the claims flowing from it get sharper.** The microscope manager drew it.

**For the same reason the `operator_set:` source kind is withdrawn (2026-09-19).** It existed for a few hours that day because there was no prefix for recording a person stating a target, and once targets were settled as having no source, **not one number in this repository could be written with it.** Leaving it is dead vocabulary, and worse than dead — **the name `operator_set` reads as "put a person's decisions here" and inverts the judgement immediately above.** The argument that refused `decision:` (a source yielding no grade is a hole in P2's invariant) does not apply here. `operator_set:` yields E5, so the function is intact, and **what breaks is not the invariant but the meaning.** The seat that created it asked whether to withdraw it.

**E5 holds two things in one cell, and when they conflict they are not the same thing (2026-09-19).** `operator_recall:` is **a claim about the world** — it may be wrong, but it is saying something. `assumed:<rationale_id>` is **a placeholder put down in order to proceed** and claims nothing about this setup. The reason they share a grade is that **the grounds for believing both are weak**, not that they are the same kind.

**So when these two disagree, it is not a conflict.** One is a claim and one is a blank, and **a blank is not objecting.** §11-13 first wrote "both are E5 and neither beats the other", and that sentence was one layer short — by grade they are symmetric, by kind they are not. It is the same place as today's target accuracy: **the grade is the wrong axis for some distinctions.**

**Resolution rule**: when a claim and a placeholder hold different values for the same quantity, **move to the claim.** Keeping the placeholder is **planning with a number nobody ever asserted**, and if the two sides then diverge from that state, the harm §11-13 records — calling two diverged experiments one comparison — happens with no grounds. After moving, the grade stays E5 and the gap stays open. **The uncertainty is not removed but shared**, and that is the honest state.

**And do not merge a target with a margin.** On 2026-09-19 `axis_bd_overdamped_a2.json` carried `target_relative_error 0.1` as `assumed:a_statistics` E5, and that is **a margin the axis chose for itself while there was no target.** The target a person stated is a different fact, and **only one of the two had just arrived.** The reason not to merge them is not the value but the cost — statistics go as 1/ε², so 10% and 30% are **nine times the samples**, and the end the axis tightened to on its own is the expensive one. Today it is free because A5 says "too small a job for this axis to bite", but the moment a real budget exists, **an unreviewed 0.1 is where the computation flows.** It is written down so a later reader does not see `0.1` and think a person chose it.

A dimensionless group is not a new source kind. It uses `computed:` with a **`derived: true` mark** (§5.7) — the grade rule is the same, so no row is added. The mark is needed because the validator has to recompute the defining expression (check 17).

Why the operator was split in two: at the stage this system attaches, **the largest information source is the person**, and dropping everything they say to `assumed` (E5) undervalues facts that were actually confirmed, while raising it all to `spec` (E3) promotes memory to documentation. **Having seen and having remembered cannot take the same grade.** Only the speaker knows which it is, so it is separated by source kind.
Why `computed` does not become E1 even from E1 inputs: **the expression itself is an assumption.** Stokes–Einstein assumes sphericity, bulk and no slip, and those assumptions remain in the computed value however good the inputs are. So a computation drops one step, and where the inputs are worse it follows the worse side.

**A policy takes no grade — because it is a decision, not a claim.** P2's four parts (`value`, `unit`, `source`, `grade`) attach to **a claim about the world.** A ceiling in `envelope/safety.*` is not a claim about the world but **something we have decided not to do**, so it has only `value` and `unit`. The simulation manager settled this on 2026-09-18, and the bridge manager, while separately building a schema that demanded `{value, unit, source, grade}` on every ceiling, **read it and deleted its own** — one rule with two schemas is the shape §11-11 counts.

**Attaching a grade goes wrong in two directions.** One is that a reading appears — "this ceiling is only E5, so it is soft" — and P0 says exactly the opposite: safety is decided by deterministic code and ambiguity stops. The other is worse: with a grade attached, **the ceiling can be raised by improving the source.** A ceiling is not a fact that better evidence revises upward.

**E5 is permitted and counted.** How many E5s are in one plan is that plan's reliability, and there is a ceiling (§11-2). E6 may enter nothing.

**A nominal designation is not a number.** Values such as a `20x` objective, a `1.5x` zoom, or filter position `3` are **identifiers exact by definition** with no uncertainty. These are stored not in `numbers[]` but as **string identifiers.**

The reason is that the failure mode is concrete. Leave a nominal magnification as a number and somebody back-calculates it from the pixel-size calibration — `6.5 µm ÷ 0.1xx µm/px = 20.0xxx` — and **a calibrated quantity gets stored wearing a nominal name.** The false precision is the symptom; the disease is two different facts sharing one name:

| | What | Where |
|---|---|---|
| `objective: "20x"` | a nominal designation. Exact, no uncertainty | string identifier |
| `pixel_size` | a **measured** value per objective × zoom × binning combination | `numbers[]`, `calibration:` source, with an expiry (E2) |

What axis A6 actually reads is **pixel size.** Magnification is a derived convenience, and the moment it becomes the record the back-calculation starts.

**A `spec:` value is a quotation.** If the catalogue says `NA 0.80`, it is carried across as `0.80` — digits are **neither added nor removed.** Change the notation and it is no longer a quotation, and later there is no knowing which way it was changed.

**An interval is a quotation too.** If the catalogue gives a working distance as `0.2–0.16 mm`, pressing it to one end as a single value is editing, not quoting. There are cases where fixing the conditions fixes the value to one — fix the coverslip thickness and the correction-collar setting is fixed and so is the working distance — but that is not the interval disappearing, it is **a conditional single value**, and **that condition has to be written in `validity`.** Leave only the endpoint with no condition and the next person cannot know why the interval vanished, nor that the value is wrong once the condition changes. (On 2026-09-17 this document broke its own rule here: the objective table it handed over pressed `0.2–0.16 mm` into `160 µm`.)

**A permitted range and a value in use are different facts.** "The coverslip thickness this lens accepts" and "the thickness this lab actually mounts" answer different questions. Merge them into one field and both answers are lost — what still holds when the lens is changed, and what breaks when sample preparation changes. The first is `spec:` and the second is `operator_read:`.

**A number read off a figure is not a source.** Vendors sometimes give transmission **only as a curve** with no numeric table. If a model reads pixels off the rendered curve and builds a table, that is not a quotation but **an inference, and E6** — it may enter neither a card nor the KB. A person reading the same graph is `operator_read:` (E3), but **only to the precision the graph supports** (§5.8, §8 check 28). And the trick of using the curve's endpoint as a stand-in for values beyond it holds only when the curve is flat at that end — if it is still falling steeply, the endpoint is neither a bound nor an approximation.

**Decisions take grades too.** Decisions such as choosing a configuration, choosing an operating point, or aborting are recorded as `{by: code|llm|human, evidence_grade: E1…E5, reversible: yes|no}`. That combination determines §6's tier and §2.1 rule 3 — the grade is not decoration but **an input to the gate.**

### 5.3.3 `at` is not resolved now — and it says so (2026-09-19)

**No place registry is built now. Instead, an unresolved `at` is made to say so.**

The asymmetry the librarian manager pointed at is half the answer: **every `at` that resolves today points at a driven channel, and every one that does not points at something nobody drives.** That is not a coincidence — for driven things **the device table already answers "where"**, and for undriven things there is no table that answers. So `at` is doing two jobs right now, and only one of them has its own registry.

**The workaround of putting a thermometer in the device table is refused.** The device table is **a registry of the things software talks to**, and all ten channels have `driver`, `automatable`, `read_back`, `lock_group`. A wall thermometer read by eye has none of them, so putting it in makes **every column of that table false about it.** The librarian manager confirmed and refused it.

**The reason not to build it now is not that there are two cases — it is that the comparison is not needed yet.** Where a vocabulary lives is the moment a **machine compares** "measured in the room but needed at the sample", and the three gaps waiting on that comparison **have no values yet.** They are blocked for want of values, not for want of a vocabulary. When the sample arrives next week those values appear, and **that is the moment the vocabulary is needed.** Building it before is designing a fifth kind from two cases, and if it sets as a free string it is **worse than nothing — because it looks resolved.** That schema already warns that `quantity` is "the weakest of the four, a de facto registry rather than a declared one".

**So what to do now is make the unresolved `at`s countable.** An `at` that does not resolve to a registered subject **is marked as such**, and a check reports the count. It must not pass quietly as a free string — **a field that resolves only half the time makes you look at the resolved half and forget the rest** (the librarian manager's sentence). This repository learned the same thing three times today: `drop 0` was invisible until `rulings.jsonl` existed, false gaps were invisible until check 49, and the target's unit would have been invisible had the commit moving its container not closed it. **A deficiency nobody counts looks like a deficiency that is not there.**

**Transition condition**: stand the place vocabulary up **before** the sample-dependent gaps close. The grounds for counting then are not a guess but the list of unresolved `at`s accumulated in the meantime.

**And the librarian owns it when that happens.** This is where the librarian manager got stuck, and there is a precedent — §4.6 says of the device registry **"and it is knowledge"** and gives it to the librarian. The optical-path table is the same. A place is the same kind of fact: **a fact about this setup**, not the contract vocabulary (`observables.json`) that decides what an agent may compute. Per P14, knowledge lives in one place.

### 5.3.2 What a bound stands on is not only numbers — what A4 and A6 revealed (2026-09-19)

**`interval.basis` accepts `kb:<entry_id>` too.** Its description today is "names in numbers[]", and so **a bound standing purely on knowledge the service supplied is inexpressible.** A4 is that case: `numbers[]` is empty and the grounds are five `kb_refs` that came back E3. Now that the librarian is serving, this kind becomes common. **No new vocabulary is created** — `kb:<entry_id>` is a source prefix §5.3 already defines, and the same thing is not called by two names. The field's shape is `string`, so this is a widening and not a migration. And this reference **actually resolves**: a check can confirm that the `entry_id` is in that card's `kb_refs`, so it is **not** in the class of 47, 48, 50 and 51 that "read a declaration and not an understanding".

**A permitted set and a precondition are different fields. They are not made one.**

- **`allowed_set`** — an enumeration, not an interval. A4's selector combinations (strings) and A6's magnification (a discrete set, being objective turret × 1.5× zoom, §4.5.3) both go here. **Intersection is defined**: set∩set and set∩interval are exactly what S4 already does. The reason not to reuse `interval` is already in the schema — `interval` requires `unit` as **mandatory**, and a unit is meaningless on a set of string selectors.
- **`precondition`** — it does not constrain a value; it **requires something of the plan.** A4's `selector_verifiable` is that: none of the three selectors is verified by read-back and the three fail differently, so §2.1 making an unverified state non-proceedable gives the conclusion "the mounted state is settled by the acquisition". **S4 propagates this rather than intersecting it.**

**Put both in one field and S4, trying to handle two kinds with one operation, mishandles one.** And that is the class that bit this repository five times — **when one sentence means two things, the reader picks one** (§7.1 rule 3). Here the reader is S4, and if it picks wrong the precondition quietly disappears.

**`state: returned` requires exactly one of three** — a numeric interval · an `allowed_set` · a `precondition`. Today it requires only `interval` and has `additionalProperties: false`, so the other two **cannot be put in.** The microscope manager counted all 28 intervals in the repository and raised it.

### 5.3.1 A target travels — and the travelled copy is compared (2026-09-19)

**The proposal to keep the target only in the goal card and reference it below is refused.** What a `plan_approval` fixes is **the plan, not the goal.** If the target lives only in the goal, then editing the goal's target while an approved plan exists makes **that plan's accuracy target move with it, leaving no record.** An approval is about the plan at that moment, so what the plan stands on has to be frozen then.

**This is not an exception but an instance of something already here.** It is the same reason `kb_version` is pinned and old pins are served from git history (§4.3.2) — a card's inputs have to freeze at the moment the card was made, and a pin that resolves to "whatever it is now" is not a pin. A plan pointing at a goal that can move is another name for that defect.

**What §11-11 counts is not copies but copies with no comparison.** Check 12 was already doing that comparison, and what that table demands is not that copying stop but **that what was copied keeps being compared.** So the target rides in goal, plan and result in the same inline slot, and **check 52 verifies that the travelled copy matches the goal's** — because what check 12 did for free on `numbers[]` is lost the moment the target leaves that container. It is the same argument as the unit subsection, and it goes into the same check: **the change that opens a hole closes it.**

**And travelling only goes forward. It cannot go back — because a contract change cannot rewrite an approved output (2026-09-19).**

The bridge manager actually migrated one example plan and watched four refusals, one of which was not a schema problem:

```
check 7 FAIL  plan_hash does not match the plan (status excluded)  [plan_approval.json]
```

**A card an approval has fixed can neither gain nor lose a field.** The hash moves and the approval no longer covers that card (§5.5). So a contract migration **cannot touch** an approved plan — not "must not touch" but **cannot, unless a person approves again.** This is not a fact about targets alone, and **not a fact about approvals alone either: every schema change that alters the shape of a card some recorded hash has pinned meets the same wall.** This subsection's first wording, "pinned by an approval", was one layer narrow — **it does not matter who wrote the hash.** Signing person or delivering bridge, a recorded hash is a recorded hash. `bridge/threads/<thread>/r<N>_hashes.json` freezes the original card exactly as an approval does and **exists without one**: on 2026-09-19 `sim-20260917-001` was actually frozen in it, and migrating it in place moves `card_sha` and check 8 fails. The two pins **share an exit too — the next revision.** So going forward only is not two rules sharing a motive but **one rule about recorded hashes.**

**And when a pin breaks, the finding has to name the cause's location.** When a ledger pin breaks the finding is attributed to the ledger, and that is right — what no longer holds is the ledger. But **the ledger is in the bridge tree and the card that moved is in someone else's tree**, and the message says *do not fix it, stop the round.* The bridge seat reads a red light in its own tree, hears "do not fix", and **does not hear where the cause is.** It is check 50's principle seen from the other side — there the problem was aiming at the side that can act, and here **the side that can act cannot be identified from the finding alone.** Check 8 names the original path and revision. **Naming the cause is routing, not repair**, and the instruction not to fix stands unchanged. The bridge manager raised it, and what did the investigating was manager-simulation checking its own tree directly — rather than trusting an investigation result it was sent.

**So the shape is one this repository already uses** — `seats.json`'s `enforced_from` and the validator's `before_enforcement()`. **New cards go inline; cards an approval has pinned keep the old shape for as long as that approval stands.** Then the removal condition becomes not "nine cards have been migrated" but **"none of the unmigrated cards is still pinned"**, and that is **a condition that can become true without asking a person to re-approve what they already approved.** The former cannot.

**`success_criteria` is widened with it.** A criterion names its threshold as a `number` and check 6 resolves that against `numbers[]`, and when the threshold is a decision there is **nothing to point at.** `$defs/criterion` gains `target: <metric>` as an alternative to `number`, requiring **exactly one**, and check 6 resolves both — `number` against `numbers[]`, `target` against that card's `targets[]`. It is the shape of **inheriting check 6's guarantee rather than loosening it**, the same argument as the unit and comparison subsections.

**That this was learned by counting is the value of the judgement.** There were five `targets[]` references, and **the numbers themselves were across nine cards in three trees**, in goal, plan and result. The bridge manager **tried the migration on its own example card first**, hit check 12, and knew it **before** the two execution seats edited their own trees. That is why `contracts/examples/` exists.

### 5.4 What a plan must have

- `purpose` — why this measurement is being made (`screen`/`characterize`/`compare`/`verify`/`troubleshoot`/`feed`, §4.5.1)
- `intent` — `explore` | `confirm`. How the target is expressed and how comparison works divide here (§5.8)
- `observable` — what is being measured or computed. **One id from `contracts/observables.json`**, with the definition, `estimator` and window requirement read from that entry. It is not that the name suffices but that **the name is the reference to that entry**, and a card restating the definition splits the copy (§5.1). Until 2026-09-18 this line read "the definition too; the name alone is insufficient" — **it was never wrong.** It was written when there was no vocabulary to point at, and then there was no way other than writing the definition into the card. It survived after the vocabulary existed and became **the grounds forcing a second copy**
- `system_configuration` — **by which configuration it is obtained**: device set, optical path and modality (microscope), or model and engine (simulation)
- `alternatives_rejected` — the configurations eliminated in screening and synthesis, and **the numbers behind the elimination**
- `conditions` — every condition parameter, as a tuple
- `envelope_check` — which limits it was compared against, and the result
- `cost` — expected time and resources
- `stop_criteria` — when it stops (declared before execution)
- `success_criteria` — what counts as success (declared before execution)
- `assumptions` — the list of `assumed` numbers and their grounds
- `open_risks` — what is knowingly being accepted

**Declaring the stop and success criteria in advance** is the single most important line in this design. Chosen afterwards, they are not a result but a description.

### 5.5 The state machine

```
goal
  └─> plan(DRAFT) ──validate(code)──> plan(VALIDATED) ──person──> plan(APPROVED)
           │                              │                         │
           └──> REFUSED                   └──> REFUSED              └─> RUNNING
                                                                        ├─> DONE   ─> result
                                                                        └─> FAILED ─> result(partial) + deviations
```
- A correction is not a state rollback but **a revision increment** (`revision: 2`), and a new revision starts again from DRAFT.
- There are two routes to `APPROVED`: a `plan_approval` exists for that `(plan_id, revision)`, or the plan falls inside the range of a valid `scope_approval` (§6.1). If the plan changes, the `plan_approval` is void.
- **An approval binds to the plan's hash, and that hash is computed over the card with `status` removed.** State moves along this state machine on the same file (DRAFT → VALIDATED → APPROVED), so hashing the whole card would make **the approval invalidate itself the moment it is issued.** Everything but `status` is bound, so changing a single condition breaks the approval.

### 5.6 The record rule

The JSON is the record; the Markdown is a human-facing output generated from it. Edit the Markdown by hand and the system does not look at it (P3).

---

### 5.7 Units and dimensionless numbers (D7)

**The record is physical units.** Every number in a goal/plan/result card is written in laboratory physical units — length µm, time s, force pN, temperature K, energy k_BT or pN·µm, viscosity Pa·s.

**Temperature being Kelvin only was forced, not chosen.** `units.json`'s registry is built on `si_factor` and a dimension vector `dim`, so it **expresses scale and dimension but not origin.** Offset units (Celsius, Fahrenheit) therefore cannot be registered and must not be — give `degC` an `si_factor: 1.0` and it takes scaling like Kelvin, wrong and silent. **The larger half of a missing unit is a missing source**: a person says 20 °C, the card carries 293 K, and nowhere in the number does it say the reading arrived in Celsius. That goes in the number's `note` beside the rounding — a value read to the nearest degree makes 293.15 a five-digit claim, so it is written 293 (§5.8). It surfaced on 2026-09-17 while the librarian seat was making the `lab_ambient_temperature` entry.

**`derived` does not mean "was computed".** On 2026-09-18 this confusion got a check approved and then reversed. What `derived` means is **"this number defines a named symbol that has to agree globally"**, which is why check 36 runs `derived` → `symbol` mandatory → compare for conflicts against other definitions and the store. A number with a `computed:` source carrying `formula` and `inputs` being **not** `derived` is normal — it was computed but it does not define a symbol. Across the repository `derived` and `symbol` already pair exactly (zero cases of one without the other). And the 2026-09-18 census showed the documented meaning and the actual usage had diverged **to an intersection of zero** — all six `derived: true` cases **carried units** (five `s`, one `N*s/m`), and of the fourteen numbers in cards with the dimensionless unit `1`, **not one** was `derived`. All six authors read it as "a computed, named quantity". So the meaning was not split; **it was matched to the usage.** Dimensionlessness is read not from this field but as a unit, from `units.json`'s `1` (`dim: {}`).

**And why it was not split is written down — because without that the same proposal comes back** (it came twice on 2026-09-18). `formula` and `symbol` do different jobs: `formula` says **"recompute me"** (check 17) and `symbol` says **"I mean one thing everywhere"** (check 36). So `derived` pairs with `symbol` and **not with `formula`** — there are **eighteen** numbers that have an expression and are not named quantities (`diffusivity`, `exposure_time_chosen`, `box_length_min_dilution`, `exposure_ceiling`, …), and requiring the flag on `formula` **refuses correct work at three boundaries at once.** So putting that paired condition in as a check makes it **pass vacuously.**

**Put a rule on top of an undefined term and the rule catches the wrong thing.** Adding that check would have dropped 15 normal cards as "derived with no symbol", nine of them the simulation's real cards. The microscope manager counted them all before implementing and stopped.

**And `kind: dimensionless_group` is being used for "named quantity".** `kb:tau_d` has that `kind` while its expression is `bead_diameter**2/diffusivity`, which is **time**, and its `unit` and `dimension` are empty. This is checkable — **an entry declared dimensionless must have its expression's dimensions cancel** — and the validator's `eval_formula` already knows dimensions. There is currently one genuinely failing case in the store, so it is not vacuous. A named quantity that is not dimensionless needs its own `kind`, and that is a decision on the entry-schema side.

**Recomputing for yourself a quantity the store already holds is not estimation but circumvention.** On 2026-09-17 a simulation card minted `tau_a = radius²/D` as E5, while `kb:tau_d` held `diameter²/D` as **E4** with a validity matching that configuration exactly. A factor of four apart, with the worse grade. The rule is simple — **cite a quantity the KB covers; do not compute it yourself.** A self-computed value always has an equal or lower grade (§5.3's `computed` inherits the worst input), and on top of that the same quantity survives under two names.

**But no check caught this, and the cause was not the vocabulary but the flag.** The number looked like this:

```json
{"name": "tau_a", "formula": "particle_radius ** 2 / tracer_diffusivity_expected",
 "inputs": ["particle_radius", "tracer_diffusivity_expected"],
 "source": "computed:stokes_diffusion_of_one_radius", "grade": "E5",
 "derived": null, "symbol": null}
```

**Three fields say "this is a derived value"** (`formula`, `inputs`, a `computed:` source) **and a fourth decides whether it gets checked.** Check 36 begins with `if not num.get("derived"): continue`, so it never looked. Had `derived` been set, it would have been **an immediate FAIL** as "derived with no `symbol`". Check 39 did not catch it either, and that side is by design — the card is `degraded: ["librarian_agent"]` so it is exempt. It did not pass by declaring a gap that does not exist; **there was no obligation to declare a gap at all.**

**So a cheap check falls out, and this one does not guess**: a number that has a `formula` or `inputs`, or whose source is `computed:`, and that has no `derived`, is **self-contradictory on its face.** It is **internal consistency** requiring no judgement about whether two quantities are the same quantity, so it refuses no correct work. It is the pair of §0.4-6's "one declaration, one parser" — here **there are four declarations and only one turns the check on**, and filling only the other three slips through quietly.

Three things are different and must not be mixed:

1. **A false gap is checkable.** If a `gap_id` points at an entry that actually exists in the KB, it is not a gap. **That is not the cause of this case** — this card was in reduced mode and had no obligation to declare a gap — but it is a real hole in check 39, and check 39 already reads the gap list, so there is a place for it.
2. **Two names for the same quantity are not checkable.** `r²/D` and `d²/D` are **different expressions** — a factor of four apart, and that they mean the same physical quantity does not follow from the expressions. Deciding it deterministically makes the rule guess, and a guessing check refuses correct work.
3. **So this is caught by registration rather than by a check.** That is why the vocabulary exists (§11-1) — register a quantity with its definition and `tau_a` and `tau_d` **appear side by side in one list**, and a person sees it. That was already decided for observables, and derived quantities need the same place.

In the meantime one cheap **signal** is possible: when the **dimensions and the input symbol set** of a number a card derived overlap those of a KB entry, raise it as `UNDECIDED` for a person to see. Not `FAIL` — whether two quantities are the same is not adjudicable, and turning the unadjudicable into a refusal would be inventing the vocabulary rather than waiting for §11-1.

**A dimensionless number is derived.** It is computed from physical values by a defining expression, and the validator **recomputes it and confirms the match** (§8 check 17). It is recorded in the card with a `derived:` mark, and since a derived value is not the record it cannot be edited by hand.

**The list of dimensionless groups is knowledge, not a contract.** Since the measurement target is open (§1), the useful groups cannot be fixed in advance, and trying to fix them embeds physics knowledge in `contracts/` and makes knowledge live in two places (a P14 violation).

| | Where | What |
|---|---|---|
| **Convention** | `contracts/units.md` | ① permitted units per quantity ② **the form a dimensionless-group entry must have** |
| **Knowledge** | `librarian_agent/kb/entries/` | one group = one entry. `{symbol, defining expression, validity, source, grade}` |

How it works:

1. **Look it up first.** S3 and S4 query the librarian for the group they need (`kb_query`, §4.3.1). If it is already distilled, the defining expression and the validity come together.
**A window-dependent quantity requires the plan to carry the window**, and since 2026-09-17 **check 40 looks at that.** Until then this sentence was only a rule, and two example plans were in fact passing with no window — it surfaced the day `window_required` first entered the vocabulary. This document confirmed for the second time that day that a rule with no check is not kept.

2. **If it does not exist, define it on the spot.** The appropriate group differs per question, so an ad-hoc definition is permitted under three conditions:
   - **Write the defining expression into the card.** The validator has to be able to recompute it from the physical values (check 17).
   - **The grade is E4.** A defining expression is itself an assumption (§5.3).
   - **Do not reuse a symbol.** If the KB holds the same symbol with a different definition, it fails (check 36). One symbol with two meanings collapses comparison silently.
3. **What was used goes to the librarian as a proposal.** An ad-hoc definition travels with the result card to the librarian, who distils and enters it — the same path by which E1 and E2 values enter the KB (§4.3.2).

Below are the initial candidates for M1's KB seed (on the basis of optical-trap colloid measurement). **It is an example, not a list:**

| Symbol | Definition | Meaning |
|---|---|---|
| `k*` | `k d² / k_BT` | dimensionless trap stiffness |
| `τ_D` | `d² / D₀`, `D₀ = k_BT / 3πηd` | diffusion time (bulk Stokes–Einstein) |
| `τ_k/τ_D` | `1 / k*` | trap relaxation time — one `k*` governs both |
| `f_wall` | a function of the wall distance `h/d` (Faxén) | the near-wall drag correction factor |

Rules:

1. **Fix the reference quantities at bulk values.** `γ` is the bulk Stokes drag and `D₀` the corresponding diffusion coefficient. **The wall correction is not absorbed into `τ` but attached separately as `f_wall`.** Absorb it and the time unit changes every time the stage position changes, and nothing can be compared.
2. **`τ` is computed from `(d, T, η(T))` and all three carry sources** (P2). `η` depends strongly on temperature, so writing `η` and omitting `T` is a failure.
3. **Do not use a mass-based time unit.** `τ_LJ = σ√(m/ε)` does not enter the physics of overdamped BD and has no experimental counterpart. A reference point with no counterpart produces quietly wrong comparisons.
4. **Reduced-unit conversion happens only inside the backend** (`src/hoomd_backend.py`). plan.json holds no reduced values — if a plan is tied to a particular engine's unit system, swapping the engine invalidates the plan (the same reason as §7.2 rule 2).
5. **Polydisperse and multi-species particles**: pick **one** reference length `d` (the nominal diameter of the main species). Other sizes are written as ratios `d_i/d`.

`contracts/units.md` is not a mapping table. It holds only ① the permitted units per quantity and ② the mandatory form of a dimensionless-group entry, and **not the defining expressions themselves.** That is why the groups that will attach to imaging modalities (resolution vs pixel size, bleaching time constant vs exposure, and so on) are not written down now.

### 5.8 Precision modes — explore and confirm (P15)

A goal card carries `intent: explore | confirm`. S2 sets it from the `purpose`'s default (§4.5.1), and a person can override it.

| | **explore** — the default | **confirm** |
|---|---|---|
| Purpose | find out about a poorly understood system by measuring | re-confirm a known value |
| Target expressed as | **an order of magnitude** — "is it the 10⁻² s decade or the 10⁻¹ s decade" | a target uncertainty — "±5 %" |
| S3 constraint expressed as | a decade interval | a numeric interval |
| S4 comparison | **a difference under 10× is indifferent**; the same decade is a tie | numeric comparison |
| E5 tolerance | generous (the ceiling is high) | strict |
| Failure | cannot even narrow the decade | falls short of the target uncertainty |

**No false precision**: a computed value's written precision cannot exceed **the worst precision among its inputs.** With even one E5 input mixed in, the result is written only as an order of magnitude. `τ_D = 0.0431 s` becomes a lie the moment one estimate enters the inputs, and `τ_D ~ 10⁻² s` is true. The validator counts significant figures (§8 check 28).

**Why the default is explore**: most of the experiments this system attaches to are looking into a system nobody understands, and confirmation is the exception. Make confirm the default and S3 demands a precision that does not exist every time, and the end of that is three significant figures on an estimate. Confirm mode turns on only when **a person writes down what is to be confirmed and to what accuracy.**

---


#### 5.8.1 A tie is a verdict about values, and that verdict carries a grade too (2026-09-19)

**P15's 10× band is a rule for comparing two values, not a rule for comparing two bodies of evidence.** The grounds are in `librarian_agent/kb/distilled/the_tie_band_does_not_measure_evidence.md` (librarian-3, `kbv-7c77fa74ee5a`) — cited rather than copied.

**The real case**: the simulation holds `bead_diameter` 2 µm as `assumed:a_sample` E5 across six cards, and the store holds `tracer_diameter` 5 µm as `calibration:` E2. Since `D ∝ 1/d`, the diffusion coefficients are 2.5× apart, which is inside 10×, so it is **a tie.** In the morning both sides were E5 and that tie was honest in both senses. **The distance between the values has not changed in the slightest, and whether a conclusion can stand has changed entirely, and the band sees none of it.**

**And the band works against its own purpose.** P15 exists so nobody chases a factor of 1.4 in a system nobody understands, and here it **endorses keeping 2 µm** — the difference is inside the band, so the bridge reports no disagreement and no card has to be rejustified. **The real disagreement is not in the values**: one side has evidence and the other has a placeholder, and **the axis the band measures is the only axis on which the two sides actually agree.**

**The answer is not to narrow the band, and not a new threshold. It is to apply to comparison a rule §5.8 already has.**

If a computed value inherits **the worst input** in its chain, **so does the verdict of a comparison.** Therefore:

> **A tie verdict carries a grade, and that grade is the worse of the two values compared.** A tie between E2 and E5 is **an E5 tie.**

No new number is chosen — §5.8's existing rule simply had not been applied to comparison. And this closes the misleading failure exactly: **it is a tie reported with no grade that misleads**, and a graded tie says what it is worth. *"No disagreement at E5"* reads correctly and *"no disagreement at E2"* is a far stronger statement.

**Why the band is not narrowed** is also right in that note: P15 breaks on comparisons where both sides are equally weak — which most are today. **What was missing was not a smaller number but a second question beside the first**, and the answer to that second question is the single line above.

**This does not say 2 µm is wrong.** 5 µm is an E2 about **this bottle**, and a model may run at a diameter that is not on the bench — **as long as the choice is recorded as a choice.** What changed is that `assumed:a_sample` went from **a reasonable placeholder while nothing better existed** to **a decision made in the presence of a measurement.** That decision is fine, and it **has to be made rather than inherited.**

**Binding it into one rule has not been earned yet.** That note gives `declared_versus_inferred_temperature` as a second case — one entry meaning different things on the two sides of a comparison. But **the two are not the same class**: this one is **grade asymmetry** and that one is **subject-and-kind asymmetry**, and the latter is the place §5.3.3's `at` and check 44's `subject` handle. **Binding them into one rule requires counting, and two is thin for counting** (§8). The grade side derives from §5.8 and so it stands now. Binding is revisited when a third case appears.
## 6. The permission model

| Tier | Example actions | Gate | Record left |
|---|---|---|---|
| **0 autonomous** | reading, computing, condition search, writing cards, KB search, refusing | none | the card |
| **1 low-risk execution** | camera preview, a single measurement inside the envelope, a simulation smoke run, external literature search, writing a new KB entry | validator passed + inside the envelope + inside budget | the run log |
| **2 human approval required** | changing source power, moving the stage, long measurements, submitting over-budget jobs, changing the physical model, retiring a KB entry | a `plan_approval` (matching revision) **or** a valid `scope_approval` (§6.1) | the approval card + the run log |
| **3 forbidden** | manually editing safety limits or calibration constants, deleting or overwriting raw data, changing firmware/driver settings, concealing a failed run, bypassing copyright | — | the attempt itself is recorded |

**Implementation direction (D2)**: Claude Code hooks' `PreToolUse` intercepts tool calls falling under Tier 2/3, and for Tier 2 confirms that a `plan_approval` for that `(plan_id, revision)` or a valid `scope_approval` is on disk. It does not rely on the model's self-report (P4).

### 6.1 The two kinds of approval card (D8)

| | `plan_approval` | `scope_approval` (operating permit) |
|---|---|---|
| Subject | one `(plan_id, revision)` | a condition range plus a device set |
| Mandatory fields | — | expiry, execution-count ceiling |
| Range limit | — | **a subset of the envelope only.** The range cannot exceed the envelope |
| Effect | one execution of that plan | demotes plans inside the range to Tier 1 (no human call) |

**Conditions that destroy a scope_approval** — all checked by code (§8 check 19):

1. the expiry passes
2. the execution-count ceiling is reached
3. the relevant calibration is renewed or expires
4. **a `stop_criteria` violation or an over-tolerance deviation occurs even once in an in-range execution** → invalidate immediately and escalate to the person
5. the envelope changes (the superset of the range moved)

**What a scope cannot cover** — always needing an individual `plan_approval`:

- optical-path reconfiguration (moving to a different configuration in the optical-path table, §4.6.7)
- operating a device on a `manual` channel
- a measurement that is irreversible for the sample
- a plan bringing in a new device
- changing the physical model (simulation)

**Intent**: the person drops out of approving normal repetition and is called **only when something abnormal occurs.** A gate pressed fifty times a day is not a gate — it only builds the habit of stamping.

**The simulation-side scope** is defined as a resource-budget range (total core-hours, storage). Inside budget it is Tier 1; over it, individual approval.

**Grade raises the tier** — the same action gets a higher gate when the evidence is worse:

| Situation | Result |
|---|---|
| A parameter of an irreversible action depends on E4/E5 | promoted to Tier 2, cannot be covered by a `scope_approval` (§2.1 rule 3) |
| A plan covered by a `scope_approval` | its evidence must be **E1–E3 only** |
| An E2 source's expiry has passed | plans using that value cannot execute; calibration has to come first |
| A plan's E5 count exceeds the ceiling | validator failure (§8 check 3) |

**Permission ceilings per component**: the system designer (S3–S5) is Tier 0, and **only the system operator (S6) holds Tier 1–2.** Backends hold no permissions and are called only through the operator (§4.6).

**Agents with no gate**: the bridge holds Tier 0 only. The librarian holds up to Tier 1. Only the two executing agents touch hardware and compute resources.

### 6.2 The session boundary is the permission boundary (D11)

**One Claude Code session per agent.** Four are always launched separately, and one session does not simply change directory scope. Above those four sit two more positions where instructions and reports move up and down (D12).

**There are nine positions** — one architecture, four manager, four execution. Manager and execution pair up per agent.

| Tier | Seat | Committer identity | Permission ceiling | Where it may write |
|---|---|---|---|---|
| architecture | architecture | `architecture@` | Tier 0 | `plan.md`, `CLAUDE.md`, `README.md`, `.claude/`, `contracts/seats.json` |
| manager | microscope manager | `manager-microscope@` | Tier 0 | `contracts/` (except `seats.json`), `microscope_agent/CLAUDE.md` and `.claude/` |
| manager | simulation manager | `manager-simulation@` | Tier 0 | as above but for `simulation_agent/` |
| manager | librarian manager | `manager-librarian@` | Tier 0 | as above but for `librarian_agent/` |
| manager | bridge manager | `manager-bridge@` | Tier 0 | as above but for `bridge/` |
| execution | microscope | `microscope@` | Tier 2 (with approval) | `microscope_agent/` |
| execution | simulation | `simulation@` | Tier 2 (with approval) | `simulation_agent/` |
| execution | librarian | `librarian@` | Tier 1 (external search, KB writes) | `librarian_agent/` |
| execution | bridge | `bridge@` | **Tier 0 only** | `bridge/` |
Every address is `…@seat.invalid`. `.invalid` is reserved by RFC 2606 and can never route, so a seat address is a **label**, not a mailbox. The author stays the person and only the committer is the seat — git's separation of the two is exactly for this.

**One identity per session. Two sessions sharing an identity are not a seat but a hole.** It was caught twice on 2026-09-17. Two sessions sitting at the root were both the design seat by definition, so check 41 passed their mixture, and hours later four sessions shared one `manager@seat.invalid`, making **check 41 decorative for that whole tier** — three commits stand under that identity and git does not know which session made any of them. The symptom was the same both times: **the check passed, and its passing was the defect.**

**Execution seats may grow (decided 2026-09-17), and when they do the same trap waits.** With two microscope execution sessions, two sessions share one `microscope_agent/` — the same shape as four managers sharing `contracts/`. The rules are the same:

1. **Mint a new identity per session** (`microscope-2@seat.invalid` and so on). Paths may be indivisible while identities are divisible, and a divided identity **gives attribution even where it cannot refuse** — which session made a commit still has an answer. That is different from having no attribution at all.
2. **Divide paths when they actually divide.** Do not pretend to divide — a `paths` narrowed by guesswork refuses correct work, and a refused seat uses `--no-verify`.
3. **What guards a shared surface is not a check but the worktree merge** (§6.2.1). Two people editing the same file surface as a conflict at merge. So the merge-awareness in checks 35 and 41 is not a convenience but **the only defence of the shared surface.**

**A tier does not add permission.** The two positions above are Tier 0 — they do not touch the instrument, do not make approvals, and execute nothing. What a tier gives is not permission but **order**: structure is set above, each agent's design revisions are made by its manager, and the work is done below. If above can do more than below, that is not a tier but a bypass — and where a bypass exists, the gate below soon goes unused.

**Why the design seat was split in two.** As one, that seat held structure (§0, §2, §6), contract implementation (`contracts/`) and each agent's instructions **at the same time.** On 2026-09-17 two sessions sat in it and edited the same files, and the prescription §6.2.1 left then was "divide the owned paths before opening a second". The tiering is that division: architecture writes **what the rules are**, and the manager carries those rules **into the contracts and the instructions.** Divided by path, check 41 can now tell the two apart — before, both were "the design seat" by definition and there were no grounds for refusing a mixed commit.

**A position outside the agents is necessary.** The moment rule 3 says "an agent session does not write `contracts/`", there has to be a separate position that writes the contracts and this document. That is the two positions above, and since they are not agents they do not touch the instrument. Without naming them, an M1 session starts editing the contracts the moment it is blocked, and then the contract gets fitted to the implementation — exactly the wrong direction.

**What enforces the boundary is the commit gate (checks 35 and 41). `.claude/settings.json` states it, and its path denials are enforced only in a session sitting at the repository root.** This subsection said the exact opposite until 2026-09-19 — that the settings enforce and check 35 catches at commit. **An outward-facing path denial is inert in a session rooted at an agent**: a path pattern resolves against that session's root, so `Write(microscope_agent/**)` from a session sitting in `bridge/` means `bridge/microscope_agent/**`, and **such a path cannot exist.** Every entry naming a sibling directory, `contracts/` or `plan.md` is the same. This is the defect class §7 wrote at length about for `.mcp.json` — the resolution point must not be the session's cwd — and **here there is no equivalent of `$(git rev-parse)`. Permission patterns are literal, and an absolute path becomes identical across checkouts, which is the answer §7 already refused.** So there is no portable expression for this position. bridge-85 found it and the bridge manager reproduced it.

**So the deny list aims at what it can reach.** In a session rooted at an agent, **paths inside its own tree resolve normally.** And as it happens, the two things most in need of write protection in this system are inside it: **`envelope/safety.json`** (P0 rule 7 — a person confirms the limit physically and writes it; a model writing it is this system's worst failure) and **`inbox/**`** (§7.1 rule 8 — the bridge writes it; an agent writing its own inbox forges a delivery). Neither is **in** the deny list today, and instead there are ten inert entries. Outward-facing entries stay but are marked **as a statement of intent rather than enforcement** — delete them and the intent is gone; leave them unmarked and the next person reads them as protection.

**And the rule is ownership, not a list: inside your own tree, deny what another seat owns.** Writing it as two was short — the bridge manager, applying it to its own case, found four more, and those four are in **all four agents.** `CLAUDE.md`, `README.md`, `tasks/` and `.claude/` are the manager's, and **all of them are inside that agent's tree, so they resolve in that seat.** Nothing was being denied. That is: **an execution seat could edit the instructions coming down to it, its own instruction file, and the files constraining it.** `tasks/` is the home of downward instructions per §6.2-2, and **a seat that can edit its own instructions has not been instructed, it has a preference** — the same argument as the reason `excludes` exists (§6.2.1), surfacing again one tier down.

    | Owner | Paths inside an agent's tree |
    |---|---|
    | the person | `envelope/safety.json` (P0 rule 7) · `approvals/` (§7.1 rule 5) |
    | the bridge | `inbox/` (§7.1 rule 8) |
    | the manager | `CLAUDE.md` · `README.md` · `tasks/` · `.claude/` |

The reason to write it as ownership rather than as a list is so that **when a new agent appears the answer follows.** Copy a list and the copies diverge (§11-11).

**Denying `.claude/` does not block the manager because the manager sits at the root** (D12). A manager session does not load `<agent>/.claude/settings.json`, so that denial **binds the constrained seat and not the constraining one** — §6.2.1's requirement that a constrained party must not own the file holding its constraints holds here structurally rather than by accident. **Seat a manager inside an agent directory and this inverts.** On that day, this paragraph gets fixed first.

**A bridge session has no instrument tools and is denied writes to run directories** — it must execute nothing, so it must be unable to execute. **Reading `contracts/` is denied in no seat.** §6.2 rule 3 established `contracts/` as **the place everyone reads and nobody writes**, so a rule blocking reads is not broader than the intent but **contrary to it.** On 2026-09-19 an execution seat's `sed -n … contracts/validate.py` was denied — a path the matcher had built by resolving against the session cwd. The result is bad not because access was blocked but because **the blocked seat starts guessing instead of reading**, and that day was exactly that price: a contract is a contract because the consumer does not have to read the producer's source (§4.3.1), and when the consumer cannot read **the contract itself**, guessing is all that is left. So denials attach only to `Write` and `Edit`, and if a `Bash(...)` pattern catches a read, that pattern is wrong. **Check 53 catches it** — an entry in an agent setting's `deny` beginning with `Bash(` or `Read(` is refused. Write only the rule and there is nowhere for the next person adding a denial to be caught.

    **But how far this rule reaches is written honestly.** That 2026-09-19 denial **did not come from this repository's settings** — the microscope manager confirmed that all the entries in the four agent settings are `Write`/`Edit`. It came from a user-level setting or the harness, and **this document does not reach there.** So the rule is about settings inside the repository, and what a seat meeting an externally imposed denial should do is **report, not guess** — being unable to read something you need to read is the same position as §6.2 rule 3's **report a defect in the contract.**

**A tool denial, unlike a path denial, is not inert**: a tool name does not resolve against a root. This distinction is the most important one in this subsection — within the same file one kind enforces and the other does not.

**If sessions ever come to sit at the repository root, `<agent>/inbox/` has to come out of the bridge's deny list first.** It is inert today so the conflict is invisible, but the moment it resolves, `Write(microscope_agent/**)` blocks **the one outward write this seat is required to make.** It is written as a condition — build an exception list now and the same fact lives in two places with nothing to compare (§11-11).

**The design seat has its own boundary too.** The root `.claude/settings.json` is the design session's, and it denies writes to the four agents' **output paths** (`envelope/`, `approvals/`, `questions/`, `runs/`, `src/`, `kb/`, `threads/`). Each agent's `CLAUDE.md` and `.claude/` belong to the design seat and are not denied — the same split as check 35's `DESIGN_OWNED`. **The position that specifies has to be unable to implement** for "specify, do not implement" to be a setting rather than a habit.

**Naming a path is not naming a change (2026-09-19).** `git commit -- <paths>` builds its temporary index from **the worktree state of those paths** — not from what you staged. So **if another seat is mid-edit on a file you named, that edit rides out under your identity.** It actually happened: `4cc39a0` carried three `$defs` into `common.schema.json`, of which `target` was manager-bridge's (the §5.3.1 judgement) and went into manager-microscope's commit. The bridge manager noticed seconds later, trying to commit its own, when the hook listed that file as excluded.

**There is one more layer: the worktree overrides the index, so your own staging is ignored too.** Pick hunks with `git add -p` and then `git commit -- <file>` and **the whole file goes.** Confirmed by reproduction — with one line in the index and two in the worktree, what got committed was two.

**No check catches this.** The gate looks at the tree the commit would create, and that tree is fine. Check 41 does not catch it either — `contracts/` is a path the four managers **own jointly**, so it is no boundary violation. It is unreachable in principle by a path rule, and check 41 attributes that hunk to the committing seat forever.

**And there are two directions, only one of which was written down (2026-09-20).** The above is **my commit carrying someone else's work in progress.** The mirror is **my uncommitted edit being erased by someone else's whole-file write**, and it was nowhere. The librarian manager wrote the same docstring **twice** — while the first draft sat uncommitted for a few minutes, another session wrote `validate.py` wholesale and the edit vanished. **No warning, no check that catches it, and nothing in `git status`.**

**And the two habits push against each other.** What closes direction 1 is **a diff before committing**, and the only thing that narrows direction 2 is **committing fast**, which widens direction 1. The window between them was measured for real the same day — **three minutes.** The librarian manager ran `git diff`, confirmed one hunk and that it was all its own, committed three minutes later, and **three went in** (`779269b`). **What the habit closes is the moment of checking, not the moment of committing.** So §6.2.1's rule is right and **partial**, and that it is partial was not written down.

**One false sentence remains in that commit's message** — *"the three failures … is not in this commit's index"*. True when written and false at commit time. The judgement not to revert is right: without that change checks 13, 48 and 55 all fail, and **a broken gate costs more than a wrong attribution.** The seat raised it itself.

**So the rule is this: before committing a shared file, run `git diff -- <that file>` and see that every hunk is yours.** And **this position is closed by habit and not by a check** — at commit time there are no grounds on disk for deciding "whose hunk is this", and making seats pre-declare their changes would make that declaration a new row in §11-11. It has the same shape as §2.1 rule 9, so **the fact that it does not close is written beside the rule.**

**And the habit did not survive an hour — in both directions, between the two seats that wrote the rule.** `manager-microscope` swept up the bridge's `$defs/target` in `4cc39a0`, and `manager-bridge` swept up the microscope's entire check 53 in `d5af7b1`. **The second happened after the rule was written, and by the seat that wrote it.** The manner matters: it ran `git diff --stat` **in the same command as the commit** and read `+84` after landing. Its own change was twelve lines. **Stating a rule and executing it are different acts and only the first was done.** It is the failure mode of every control closed by habit, and this instance recorded **a half-life under one hour** between the two seats best placed to keep it.

**The two commits are not fixed.** They are immutable, their content is right, and rewinding moves someone else's work twice. Instead it is written here: **`4cc39a0`'s `$defs/target` is manager-bridge's, and `d5af7b1`'s check 53 is manager-microscope's.** Check 41 attributes both wrongly forever, and **that is structurally invisible to every check** — because `contracts/` is the four managers' joint property and no boundary was crossed.

**The structural answer is already in §6.2.1 and the manager seats are not using it: a worktree per seat.** What a worktree buys is not tidiness. **It makes `git commit -- <paths>` actually mean what everyone already believes it means** — the paths I changed. Today it means **a different sentence**: "the current worktree state of those paths", and the two sentences coincide only when nobody else is editing the same file. Eight sessions guarantee that coincidence breaks. And since removing worktrees was **a person's decision** (2026-09-18) and not a technical obstacle, restoring them is a person's decision too — architecture raises it as §11-17. The `.mcp.json` absolute-path problem that was breaking isolation then **has since been solved** (`$(git rev-parse --show-toplevel)`), so that obstacle is gone.

**And the advice above was only half right.** `-- <paths>` protects you from someone else's work on **other files** and does **nothing** about the same file. On the morning of 2026-09-19 architecture confirmed this method by reproduction, but what it tested was **only the different-file case**, and it stated the result for the whole — concluding more broadly than the test covered, which is the class two seats each hit that same day. The microscope and bridge managers raised it together.

**Work a person assigned directly is not a rule violation, and it has to be written as such.** On 2026-09-19 the microscope execution seat received round r1, while the sentence *"receiving a round is assigned by a task card"* entered that agent's `CLAUDE.md` **afterwards**, and what that seat had received was **a person's direct instruction** (the one route §6.2.2 recognises). The rule is right and the work was right, and **on disk there stands one "round taken with no card" that the next session reads as a violation.** So **work a person distributed directly is written up retroactively as a card or stated as an exception** — either way a record is needed, and the reason is the same as §6.2 rule 2: **a path that worked and left no trace** is, to the next person, a path that does not exist. The microscope execution seat raised it itself.

**And this dictates how a session is launched.** Claude Code reads `.claude/settings.json` **only from the working directory**, not from subdirectories. So launching a microscope session at the repository root means `microscope_agent/.claude/settings.json` is **not loaded** and the root's design-seat settings apply. The boundary does not loosen — **the wrong boundary applies, and writing to its own directory is denied** — a session seated wrongly is loudly blocked rather than quietly passed. Each agent session is launched **with its own directory as the working directory.**

**That decision splits MCP approval as many ways as there are directories (2026-09-19).** Claude Code keys projects by **working directory**, so one repository becomes several things to approve — checking showed **seven** entries related to this repository in `~/.claude.json`, all with `enabledMcpjsonServers = []`. More worktrees means more of them.
    **And the root `.mcp.json` is inherited while the approval is not.** That the two behave differently was written nowhere, so a session with the server registered and no tools had no way to know why. **The fix is to approve by server name rather than by path** — one line of `"enabledMcpjsonServers": ["librarian"]` in the user-level `settings.json` covers all seven paths and any future ones at once. `enableAllProjectMcpServers: true` is not used: it approves any server in any repository without asking. **Settings are read at session start, so a running session is unaffected.**

    **The most expensive part is that approval is not inherited, and the failure is silent.** A seat without the librarian's tools gets no error and **proceeds on the degraded path, which for these agents is a legitimate way to finish** — so **a quiet day is indistinguishable from an ordinary one.**

    **The cards are not silent, though, and that distinction matters.** `evidence` defaults to degraded and clears only when the server answers, and check 45 reads it from the other side, so **no card ever comes out falsely saying "the librarian answered".** The damage stops at a seat idling or proceeding degraded. So this is **a scheduling problem, not an evidence problem** — **a failure that is silent but cannot contaminate the record is a different class and is handled differently.**

    **"Then why not launch everything from the root" is not the answer, and a second reason appeared today.** The first is above — a root cwd reads as a top-tier seat and that position is *specify, do not implement*. **The second: inward denials are relative patterns.** `envelope/safety.json`, `approvals/**` and `inbox/**` resolve from an agent directory and **actually guard three things inside that tree that belong to others.** From the root they become paths that do not exist. This subsection wrote that *outward denials are inert in a session rooted at an agent*, and **moving to the root inverts that and makes the inward denials inert** — the guards on the person's two folders and the bridge's one drop **at the same time.** So the fix is **one approval per session, not a change to the directory structure.** The simulation execution seat found it and its manager confirmed and raised it. A running session is not fixed with `cd` (the rule above).

On 2026-09-17 this was actually wrong. All five sessions were at the root and the root had no `.claude/` at all, so **no session had ever loaded a boundary.** The two overwrites above are the result.

**`deny` is half the boundary.** Denial rules catch `Write` and `Edit` and not `sed -i` or a python heredoc, and in this repository every session used the latter. The other half is the gate at commit time (§8) — whatever the tool was, it looks at the set of paths that reached the index. The settings make the right thing easy; the gate stops the wrong thing.

Four things follow:

1. **Permission isolation is enforced per process.** Each agent directory's `.claude/settings.json` opens only the tools permitted to that session. A bridge session has no instrument tools at all, and a librarian session has no hardware path. The model is not restraining itself; **it cannot, for want of the means** (P4).
2. **A message may notify and may not be the only copy.** Until 2026-09-18 this rule read "sessions do not talk directly", and **that day it was false** — six sessions instructed and reported by inter-session message all day, including the seat that wrote the rule. The observation is right and the rule was not: a message is **notification** and the disk is **the record.** A downward instruction is a file in `<agent>/tasks/` and the message points at that path. An upward report goes to its own home among cards, `failures.jsonl` or §11, and the message points at it. **What exists only in a message is context, and context disappears with a reset** (P1, §6.2.3). A case of nearly losing exactly that came up the same day — a manager had nowhere to write its own instruction and had to raise the very fact that there was nowhere to write it, by message. **Peers have no place to reach each other on disk** — `<agent>/tasks/` belongs to that agent's manager, so a manager cannot write into a neighbouring manager's lane. There are two routes and both are used: **put the obligation inside a file the other party must touch when doing that work** (on 2026-09-18 the librarian manager did this by writing the migration obligation into an enum's description — whoever moves that value will read it), and where that is impossible, **go up and come back sideways.** The latter adds a round trip and in exchange **architecture sees the fact and records it** — a decision passed directly between peers reaches no document.
3. **Nobody writes outside their own directory.** `contracts/` is read by everyone and written by nobody, and another agent's directory is neither read nor written. The bridge alone exceptionally **reads** cards from both agents' `questions/` and transcribes them into its own `threads/`, and **delivers by writing into the receiving side's `<agent>/inbox/`** (§8 check 35, §7.1 rule 8). **Until 2026-09-19 this rule had no delivery direction** — the read exception was one-way, the bridge reading from an agent, so although §5.1 said "turning a received `ask_*` into a goal is the receiving side's S2", **the receiving side had no path to that card.** The first real round trip stood there for forty minutes, and the microscope execution seat kept on with its own question not out of laziness but **because it had no way to know that round existed.** The bridge writing the turn into `status.json` means nothing if the reading side is not in the documents — it was not dead lettering (check 48) but **absent lettering.** The reason to place it in the receiving tree is in §7.1 rule 8. **That reads are blocked too actually fell over on 2026-09-19** — the bridge seat read `librarian_agent/src/` while diagnosing the `caller_id` problem, and reported itself. It did not write and there was no harm, but **what characterises that violation is that the same conclusion was reachable inside the boundary**: the pattern is in `contracts/schemas/` and the grammar in §4.3.1, so it was reachable without opening the server file, and another bridge window did reach the same answer without reading. **It was crossed for convenience, not out of necessity.** — **That reason turned out to be wrong on 2026-09-19.** That the server held its own copy of the pattern — that the server refuses an id the schema accepts — is **a fact `contracts/` could not have told anyone**, which is why that day's fix was incomplete. That conclusion was **not** reachable inside the boundary. **The ruling stands** — up and back sideways is still the right route. But the reason changes: when something unknowable inside the boundary appears, that is **a defect report about the contract**, not a licence to read, and reporting it makes the contract carry the fact. That is what actually happened here. So the test for whether this rule was crossed is not "was there harm" but **"was that conclusion reachable inside the boundary"** — usually it is, and when it is, crossing is pure loss. Since a contract is a contract because the consumer does not have to read the producer's source (§4.3.1), a state knowable only by reading is **a defect report about the contract**, not a licence to read.
4. **Approvals are written by a person in another window.** Even with designer and operator inside one session, only a person can create an approval card (§5.1), so there is no path for a session to approve its own plan.

**The price paid**: round trips slow down going through files, and a person moves between four windows. So the bridge's `status.json` keeps **whose turn it is right now** on one line — without it, four windows soon go unmanaged.

**What is gained**: context stays small per agent, one session being contaminated leaves the other three intact, and "who could have done what" is answered by looking at the session settings alone.

#### 6.2.1 One working copy per session (D12)

**There is one working copy.** On 2026-09-18 it was decided to give each sub-session a `git worktree`, and **reverted the same day** — the person removed the worktrees. The argument for introducing it, and what is undefended now that it was reverted, are recorded below. The reason not to delete this is that the problem has not gone away.

**Before that there was one, and that produced today's three losses.** Four sessions running in the same directory share the git index too — a file one session's `git add` put up is taken by another session's `git commit`. Without `-A`, with a plain `git commit`.

It happened three times on 2026-09-17.

1. One commit held three sessions' work and its message described one.
2. Hours later the index simultaneously held the design seat's `contracts/validate.py` and four of the microscope session's `src/` files, and whichever of the two committed would have crossed a boundary — the pre-commit hook stopped it that time (§8).
3. One session's in-progress KB edits left check 25 red for hours and **refused every other session's commits.** The way out was `--no-verify`, twice. The gate was fixed to look at the tree the commit would create (§8), but that fixed the symptom; the cause is the shared working copy.

**Add sessions and this collision grows not with the session count but with its square.** So raising speed by adding a tier requires splitting the working copy first. Add sessions without splitting and it does not get faster — they wait for each other and overwrite each other.

**What the worktrees were going to give, and what is absent now.** Other people's unfinished work would have become invisible, making a `git add -A` accident structurally impossible, and two people editing the same file would **have surfaced as a conflict at merge.** Reverted, **neither of those exists.** And in the meantime two places recorded "what guards the shared surface is not a check but the worktree merge" (§6.2.1, `seats.json`'s `what_protects_the_core`) — **the defence those sentences point at does not currently exist.** The `contracts/` core the four managers share, and an execution pair looking at one agent, have **no refusal-level defence and only attribution.** The merge-awareness in checks 35 and 41 (`249045f`, `8f6b906`) remains correct and has no merge to guard.

**What is left instead is two of three**: the ban on `git add -A` and `git commit -- <paths>` (convention), plus the commit gate (enforcement). It is back to convention carrying half of enforcement, and that is the configuration that broke three times on 2026-09-17.

The path rules hold inside a worktree too. The three below are the rules while a shared copy remains, and habits to keep after worktrees.

1. **Do not use `git add -A`.** Name the paths.
2. **To commit without touching another's staging**, use `git commit -- <my paths>`. It uses a temporary index, so what others put up stays.
3. **The hook prints the set going into the commit.** It cannot adjudicate ownership — git does not know which session touched a file — but it can make it visible **before** the commit, and that is the difference from discovering it afterwards.

**To check merges, checks 35 and 41 have to know about merges. They did not.** Confirmed in a scratch repository on 2026-09-17 — if sub-sessions commit only their own on their own branches, both pass, but when a manager merges them:

- **Check 35 does not refuse, it crashes** (`RecursionError`). With a merge in the range, `rev-list --reverse M~1..M` returns the merge and the commits it brought, making more than one, and the check then re-invokes itself on the same range to decompose per commit. It does not decompose, so it never ends.
- **Check 41 silently skips the merge.** `diff-tree -r <merge>` prints nothing by default, so the changed-path list is empty and the check skips that commit. Meaning **no** attribution check applies to a merge at all.

**The rule is this.** A merge commit holding several boundaries is not a violation but the definition of a merge — the commits it holds were each checked on their own branch. What is checked at a merge is **what the merge itself contributed**, that is, changes in no parent (`git diff-tree --cc`). That is either a conflict resolution or an edit slipped in, and either way **the merging seat's own work**, so it has to stay inside that seat's boundary. So check 35 excludes merges from the per-commit decomposition, and check 41, instead of skipping a merge, looks at it with `--cc`.

**This change has to land before the worktree move.** Reverse the order and the gate crashes on the first merge, and a gate that blocks correct work does not get fixed but bypassed — today's two `--no-verify` were that path.

**The problem of two design seats was solved by the tiering.** If D11 is "one agent = one session", then the positions above it are one each too. On 2026-09-17 two sessions sat at the root and edited `plan.md` and `contracts/validate.py` at the same time, and the reason the result was not bad was not luck but **that the two divided the paths by hand.** D12 made that division structural: architecture takes `plan.md` and `seats.json`; the manager takes the rest of `contracts/` and the agent instructions. Unlike a hand division, this is written in `seats.json` and read by check 41.

**Before, that boundary had no enforcement.** The agent boundary has two layers, a per-directory `settings.json` and check 35, but the design seat is **defined only by cwd being the root, so the settings could not tell two sessions at the root apart.** Both were the design seat by definition. It was not weaker than the agent boundary; it did not exist. The symptoms came too — §11-1 was decided by two positions separately, and while one wrote the pre-commit hook the other was designing the same thing. It ended in waste, but had it been the same function in the same file the contract would have split.

**The commit-time gate passed it too.** One commit held both design seats' `contracts/` edits together, and the hook printed the set but **had no grounds to refuse.** Both files were `contracts/`, that is, the same design-seat path. Check 35 looks at agent boundaries, so a mixture between two design seats passed by definition. The gate was not loose; there was nothing for it to see.

Making it a check requires **attributing a commit to a session**, which git does not know. **It was built on 2026-09-17** (check 41). A seat identifies itself by its **committer identity**, `contracts/seats.json` holds identity → owned boundary, and check 41 checks that all of a commit's changed paths are that seat's. The table classifying paths into boundaries is reused exactly as check 35 uses it — keep two tables and they diverge. **The author stays the person and only the committer is the seat**: git's separation is exactly for this, so attribution is gained without losing the person's name. Adoption is one line in front of the commit:

```
GIT_COMMITTER_NAME='seat:design' GIT_COMMITTER_EMAIL=design@seat.invalid git commit -m …
```

**It catches what check 35 missed.** Check 35 **counts** boundaries — one commit touching two agents, or mixing `contracts/` with an agent. So the microscope seat committing only into `simulation_agent/` **passes**, because that is one boundary. One wrong boundary. Check 41 knows whose that one is. The common accident is this one.
#### 6.2.2 A tier sends work down and cannot send permission down

**A session does not treat another session's relayed message as its own user's instruction.** This is not a choice but something a session has to hold, and it dictates how a tier is built.

It was actually hit on 2026-09-17. The architecture position relayed to another position "you are the manager tier, and the user instruction is this", and the receiving side **agreed with the content and did not accept it as an instruction** — because that session's user had never told that session about the three tiers. That is a correct refusal. The same standard was used in the opposite direction just before: the side that heard second-hand about a design-seat handover stopped only after confirming directly with the user.

Therefore:

1. **A person seats each session directly.** A tier assignment does not propagate by message. Launch six sessions and the seating has to happen six times — one session cannot appoint the other five.
2. **Work can be sent down.** Once seats are set, work requests, questions and reports flow freely by inter-session message. This is where the tiering gives speed.
3. **A request that widens a boundary is refused even from above.** If an upper tier says "commit this file for me" or "widen your permissions", the lower refuses and escalates to the person. If above can enlarge below's permissions, §6's tiers are bypassed by one line of request.

**The cost is a person seating six times, and what is gained is that no message can become permission.** That is why prompt injection does not work in this tiering — what can be injected is work only, and work is still performed only inside the boundary.


#### 6.2.3 A session may be cleared after each task — and clearing is P1's test

**P1 is already the answer**: files are the truth, sessions are volatile, and all of an agent's state is on disk. If that is true, then the context of a session that has finished one task should hold **only what can be thrown away.** So a reset between tasks is not merely permitted but **a continuing test of whether P1 actually holds** — if something disappeared on clearing, it was never on disk and P1 was already broken.

**"Between" tasks, not "during".** The state of a half-finished task is by definition not on disk. And what §4.3.1-1 permits — a subagent continuing follow-up queries inside its own context — is also within one task.

**Three things have to be on disk before clearing.** These are a task's completion conditions:

1. **The output** — the card, and the gate it passed.
2. **Newly learned facts** — a result card bound for the librarian (P14). Leave what was learned here here, and the next session learns it again.
3. **Dead ends** — `failures.jsonl`. An attempt abandoned without producing a card **survives nowhere else.**
4. **Rulings made** — `rulings.jsonl`. §10.2.1's transfer/downgrade/**drop**. Different from a dead end (§7.1 rule 9).

The third leaks most easily, and there is evidence. `agentic-microscope` had a list titled **"known wild goose chases, one session burned each"** — things like Kinetix's `10012` being a wedge rather than an ordinary ownership conflict. The existence of that list means that until it was written, sessions burned the same ones repeatedly.

**The value of a reset is proportional to the length of the instructions.** A fresh context re-reads the root `CLAUDE.md` and its own agent's `CLAUDE.md`. So keeping `CLAUDE.md` short (§7) and clearing per task are **two ends of the same handle** — long instructions make clearing expensive, expensive means nobody clears, and then state creeps back into context.

**Judge for yourself, get confirmation from above, then clear** (2026-09-18). An execution seat asks its manager and a manager asks architecture. Architecture's is settled by the person — there is nothing above, so that one cell cannot be left empty, and leaving it empty means the longest-lived context is under no discipline at all (the person's answer on 2026-09-18: it does not clear).

**The reason not to decide alone is that neither side has all the grounds.** Below knows what it is holding, what was hard to recall, and whether the task is really finished — above cannot see that. Above knows whether a report is repeating facts already on disk, and whether below is asking things `plan.md` answers — **below cannot see that.** To a session with a long context, knowledge known only from context feels like something read off disk, and that is the whole of this problem. So each supplies half.

**The form of the request is one sentence** — whichever side is arguing, it answers **"what is not yet on disk?"** If nothing, the answer is "nothing" and it clears. If something, that is both a P1 violation report and the next task. That one sentence is all the material above needs to judge, and it removes any need to look inside below's context.

**If the answer is late, the default wins.** If no confirmation arrives by the next task boundary, it clears and reports that it cleared without confirmation. Stopping to wait for confirmation blocks everything below while above is away, and then this procedure is abandoned in the first week.

**The default is to clear, and continuing requires a reason.** As the paragraph above says, clearing is P1's test, so the side skipping the test carries the justification. And that justification has to be the single sentence **"what is not yet on disk?"** — that sentence is simultaneously a P1 violation report and tells you what to move onto disk next. Unable to answer, it clears.

**Four signals visible from above** — all readable from the report and the disk, with no need to look inside below's context:

1. The three completion conditions (output, facts bound for the librarian, dead ends) are actually on disk → it is time to clear.
2. **A report restates facts already on disk** → context is carrying a load the files should bear.
3. A report exceeds its line count or pastes in code bodies → the same symptom.
4. Below asks something `plan.md` already answers → the instructions need re-reading, and that is what a reset does.

**Instructions go inside five fields.** A reset is not a new field but `TASK`'s last step ("clear after reporting"). Add a field and the instructions grow; grow the instructions and the value of a reset gets expensive.

**And it does not take effect mid-task.** Told from above to clear, it executes at the next task boundary. Clearing a half-done task breaks this subsection's premise, and in that case below does not refuse but **defers** — and reports that it deferred.

**A seat identity lives in the worktree's git config, not as a command prefix.** A prefix is knowledge living only in context, so it disappears with a reset and the next commit goes out under the person's identity and drops out at check 41 as unregistered. Since D12 gives each sub-session a worktree, a per-worktree `--local` setting is exactly the right place:

```
GIT_COMMITTER_NAME='seat:manager-microscope' \
GIT_COMMITTER_EMAIL=manager-microscope@seat.invalid git commit -m …
```

**With the working copy back to one, the identity is a command prefix again.** Git does read `committer.name`/`committer.email` (v2.22+), but **one copy has one setting and cannot hold six seats.** While it sat per worktree under `--worktree`, the identity **survived a reset by itself**, and reverting lost that property — a prefix is knowledge living only in context, so a cleared session's next commit goes out under the person's identity. **So §6.2.3's claim that "a session that lost its seat can read from disk who it is" does not currently hold.**

**It is `--worktree`, not `--local`.** Until 2026-09-18 this subsection prescribed `--local` and **was wrong** — in a linked worktree, `--local` writes not to that worktree but **to the shared `.git/config`.** Followed literally, one seat's identity would have been read as their own by every session, and that is §11-10's pre-worktree hazard surviving **past** worktrees. The microscope manager caught it and confirmed both directions in a throwaway repository — a value written with `--local` is read from the main copy, and one written with `--worktree` is not.

**Git reads `committer.name`/`committer.email`** — since v2.22, confirmed on 2.50.1 on 2026-09-18: committing with no env prefix still makes the committer the seat and leaves the author as the person. So the worktree setting is **enforcement** rather than a record, and the environment variables are needed only on a shared copy with no worktree setting. This subsection said the exact opposite until that day — "git does not read those keys, so the first commit after a reset is downgraded to the person's identity". **The wrong side was the more cautious side, so nobody collided with it, and it nearly went unfixed forever** — a seat reading that comment merely kept attaching an unnecessary prefix and never sees a failure. An error whose conclusion is safer than reality lives longest. microscope-2 found it in its own worktree. The point is **that a session which lost its seat can read from disk who it is**, and without that a person has to re-seat it after every reset (§6.2.2 said seat **assignment** is a person's job; it did not say **remembering** the seat is).
## 7. Repository layout

```
rebuild/
  plan.md                  the English rendering, generated from plan_ko.md
  plan_ko.md               this document. The record (0, language convention)
  README.md                for **someone who has read neither**. What it is, what it becomes today, where to look
  CLAUDE.md                the monorepo's common rules (P0-P16, a summary of the card contracts).
                             **All six sessions read it, so its length is multiplied by six**
  ARCHITECT.md             standing orders for the architecture position. It binds one position only, so it is not in CLAUDE.md
  pyproject.toml           the dependency manifest. **Only the three counted from the source and filtered through
                             `sys.stdlib_module_names`** -- `jsonschema`, `referencing`, `numpy`. `referencing` is
                             separate because check 1 builds a `$ref` registry itself. **HOOMD cannot go here** --
                             it is not on PyPI and is conda-forge only, so `uv sync` gives the pipeline and not the
                             engine. That separation matches §9.2 rule 4 and §4.6: the mock is a first-class backend,
                             so **a machine running only the validator and the mock does all of M2's validation**
  uv.lock                  the exact versions that manifest resolves to. **Without it another machine resolves
                             different ones** -- the person's requirement of "easy on another computer too" hangs on this file
  docs/                    **the public introduction page** (GitHub Pages, `/docs` on `main`). Its reader is one step
                             further out than README's -- **someone with no intention of opening the repository**,
                             someone who was sent a link. Written in English (the only exception to the language rule
                             is plan_ko.md).
                             **It points rather than restates** -- 7's README rule applied once more at the document
                             layer, and **numbers especially are kept out** (they go stale on being written; wrong
                             three times in one day in `CLAUDE.md`).
                             **Architecture's** -- it is `README.md`'s neighbour and belongs to no agent.
                             It carries the same coupling as a root file (the addendum to §7.1 rule 9):
                             `ALLOWED_PATHS` first, `SHARED_PATHS` to make the boundary `design`, and then 7 closes it
    index.html             a one-screen landing page. The loop, the four-agent diagram, a slot for the film, three principles.
                             **No build step and no dependency** -- the CSS, SVG and script are inside the file.
                             The cost of opening it on another machine has to be zero, the same requirement as `uv.lock`
    assets/                film and images. **Empty is the normal state** -- with no film the page shows a
                             placeholder rather than a broken player (it says what is absent is absent, P1)
  contracts/               ★ the only shared code. All four agents depend on it.
    schemas/               goal/plan/plan_approval/scope_approval/result/refusal/ask
                           + axis/synthesis/common/kb_entry
    units.json             the unit registry (the record)
    units.md               a description of that registry + the mandatory form of a dimensionless-group entry (§5.7)
    observables.json       the shared observable vocabulary (the record). It grows one entry per question (11-1)
    quantities.json        the **quantity registry** that `numbers[].name` uses (the record). It is kept
                           **beside `observables.json` rather than merged with it**: that one registers *what can be
                           produced and compared*, giving each entry an `estimator`, `window_required` and
                           `producible_by`, while coverslip thickness and pixel size are **produced by nobody and
                           compared with nothing.** Inventing an estimator to make them fit is inversion. **Every
                           observable is a quantity and not the reverse** -- **a requirement, not a description of
                           the present state**: on 2026-09-19 two observables were not yet here, and check 60
                           enforces that inclusion. Rule 1 was written by the data -- **a name states the quantity,
                           not its own subject or locus** (§5.3.3\'s `at`, check 44's `subject`). Growth is as with
                           `observables.json`: one at a time when a question needs it, never speculatively
    seats.json             committer identity -> owned boundary. Read by check 41 (§6.2.1)
    validation_limits.json the validator's thresholds. `null` means "nobody has chosen one yet"
    validate.py            the deterministic validator
    capabilities/          the "producible observables" table per configuration (modality) -- S3.0's input
    hooks/                 the commit-time gate. Installed with `core.hooksPath` (8)
    examples/              one hand-written set of cards + cards that must fail
      rejected/            one file = one fixture
        check<NN>_<what>/  a defect that takes two files to express (11-7)
  microscope_agent/                 three top-level folders + CLAUDE.md
    README.md              what this agent is and what it becomes today. **The manager's**
    tasks/                 **the manager writes and the execution seat reads.** The home of downward instructions (§6.2-2).
                           An execution seat must not be able to edit its own queue, so this path is the manager's
    CLAUDE.md                       role / what it does not do / permissions
    envelope/                       safety.json        the safety policy -- the person's, Tier 3 (§2.1).
                                                       the only file envelope owns itself
                                    snapshot.json      a read-only copy of the librarian's KB -- the device registry,
                                                       valid optical paths, calibration (M3, §4.3.2)
    failures.jsonl                  **dead ends, per seat.** Seats with no `questions/` (librarian, bridge) write only here.
    rulings.jsonl                   **§10.2.1 rulings.** One line per item crossing from a prior repository:
                                      `{ruling: transfer|downgrade|drop, item, slot, rule, by, at}`.
                                      **`by` names the judgement, not the hand** -- an execution seat may write down
                                      a ruling a manager made, and without `by` the ledger silently attributes every
                                      ruling to the execution seat (§6.2.1\'s defect in a new file).
                                      The execution seat writes it. Append-only, never deleted (§7.1 rule 9).
                                      §6.2.3 hung a completion condition on it and gave it no path until 2026-09-18 --
                                      it was structurally unsatisfiable
    approvals/                      the only folder a person writes -- plan_approval, scope_approval
    inbox/<thread>/                 **the bridge writes and this agent reads.** Only delivered `r<N>_ask_*.{json,md}`.
                                    **No copy of `status.json` is kept** -- the turn is the fact of being in the
                                    inbox (§7.1 rule 8). **The boundary is `bridge`** -- only the place is inside this
                                    tree and the writer is the bridge (§6.2-3)
    questions/<qid>/                everything about one question, flat in this one folder
                                      failures.jsonl                  (validator failures, refusals, deviations, §8.1)
                                      question_microscope_<qid>.md    (S2, for people)
                                      goal.json                       (S2, the record)
                                      axis_<config>_a1.json …          (S3, per configuration × axis constraints)
                                      synthesis.json                  (S4)
                                      plan_microscope_<qid>.json      (S5, the record)
                                      plan_microscope_<qid>.md        (S5, generated)
                                      refusal.json                    (only when there is one)
    runs/<run_id>/                  raw/, log.json, deviations.json
    src/                            deterministic code (§7.2)
                                      axis_a1_snr.py … axis_a7_driving.py    (S3, seven)
                                      synthesis.py                           (S4)
                                      operator.py                            (S6)
                                      orchestrator.py   single entry point, parallel (§4.6.8)
                                      devices/          one per control channel + manual.py, mock.py
    .claude/skills/                 S2 refinement / system_designer / system_operator / deviation recording
  simulation_agent/                 the same structure, only the axis list differs (§4.5.3)
    CLAUDE.md
    envelope/                       budget.json (resource ceilings -- wall clock, storage, smoke), snapshot.json.
                                    **`safety.json` is not here** -- there is no irreversible physical action in this tree (§2.1)
    approvals/                      the only folder a person writes
    inbox/<thread>/                 **the bridge writes and this agent reads.** Only delivered `r<N>_ask_*.{json,md}`.
                                    **No copy of `status.json` is kept** -- the turn is the fact of being in the
                                    inbox (§7.1 rule 8). **The boundary is `bridge`** -- only the place is inside
                                    this tree and the writer is the bridge (§6.2-3)
    questions/<qid>/                question_…md, goal.json, axis_<config>_a1–a7.json,
                                    synthesis.json, plan_simulation_<qid>.{json,md}
    runs/<run_id>/                  config, trajectory_meta, observables, log.json
    src/                            axis_a1_stability.py … axis_a5_budget.py + axis_a7_driving.py
                                    (no A6, §4.5.3), synthesis.py, operator.py,
                                    hoomd_backend.py, mock_backend.py
                                    (no orchestrator and no devices -- there is one thing to coordinate, §4.6.8)
    .claude/skills/                 S2 refinement / system_designer / system_operator / convergence judgement
  librarian_agent/                  the system's only knowledge store (P14)
    CLAUDE.md
    kb/entries/  kb/sources/  kb/distilled/  kb/lessons/
    kb/staging/                     tables extracted from a prior repository. **Not the final form** -- decomposed
                                      into atomic entries at M3, when the query method is settled (§11.1)
    kb/index.json                   generated. `kb_version` = a content hash over all entries
    kb/exports/snapshot_<agent>.json  the publication point. Each agent session copies it into its own envelope (§4.3.2)
    queries/log.jsonl               who asked what and why. **Outside `kb/`** -- it is a record, not knowledge (§4.3.2)
    src/kb_index.py                 index regeneration (store maintenance, from M0)
    src/mcp_server.py               the read-only, caller-isolated MCP server (§4.3.1, M3)
    src/export_snapshot.py          publishes kb/exports/. It does not write into another's directory (M3)
    src/query_log.py                writing queries/log.jsonl and offline auditing. No read function (§4.3.2)
    .claude/skills/                 answering queries, distillation, conflict handling, external search (writes only here)
  bridge/
    CLAUDE.md
    README.md                       what this agent is and what it becomes today. **The manager's**
    tasks/                          the manager writes and this seat reads. The home of downward instructions (§6.2-2)
    threads/<thread>/               rounds are separated by filename prefix, not by folder
                                      r1_ask_simulation.json, r1_ask_simulation.md,
                                      r1_hashes.json, r2_…, status.json
  .mcp.json                registration of the librarian MCP server. **The resolution point is the root of its own
                             worktree** -- `sh -c 'exec python3 "$(git rev-parse --show-toplevel)/…"'`.
                             It is a constraint arrived at after being wrong three times: the resolution point
                             **must not be the session's cwd** (it differs per seat) and **must not be one
                             checkout's absolute path** (it becomes identical across worktrees). `.mcp.json` is
                             tracked, so each worktree has its own copy at its own root, and **that is the only
                             value that differs per worktree and is independent of the seat.**
                             A relative path (`librarian_agent/src/…`) broke because the launcher's cwd is a
                             **seat subdirectory** -- the launcher log said so itself -- and
                             `${CLAUDE_PROJECT_DIR:-.}` fell in the same place because the variable is unset.
                             An absolute path does come up but **breaks worktree isolation**: on 2026-09-18
                             `microscope-1`'s checkout was `kbv-fdef964aca56` while the shared copy answered
                             `kbv-67f9ad766d92`. Then what check 26 compares against (its own worktree's snapshot)
                             differs from what the server said, and **a card cites a `kb_version` whose bytes are
                             nowhere in its own commit history** -- P14's "which KB version entered this envelope
                             is a fact of this agent's commit history" does not hold. Two microscope seats measured
                             it and raised it.
                             Outside the repository it **fails rather than falling back** (§8.2: a silent fallback
                             passes the test and fails in the field).
                             **Architecture's** -- it is `.claude/`'s sibling and a shared entry point for four, so
                             it belongs to no agent.
                             **Unlike `.claude/settings.json` it is inherited downward** -- a session launched in a
                             subdirectory reads this registration too (demonstrated 2026-09-18: visible from
                             `librarian_agent/`, invisible outside the repository). So one registration at the root
                             suffices and there is no need to split it five ways.
                             **The path is written as `${CLAUDE_PROJECT_DIR:-.}`.** On 2026-09-18 it was written as
                             a relative path and **all four seats needing the librarian failed to connect** -- an
                             agent session's cwd is its own directory, so `librarian_agent/src/…` resolved to
                             `bridge/librarian_agent/…` or `librarian_agent/librarian_agent/…`. The only ones that
                             could reach it were the two seats at the root, and **those two are Tier 0 and write no
                             cards** -- every position that needed the registration could not use it and every
                             position that could had no use for it. The bridge seat caught it.
                             The `:-.` default is required by project-scoped entries.
                             **Registration alone is not enough -- a person has to approve.** It is `Pending
                             approval` right now, and approval is stored in `~/.claude.json` **per project path**,
                             so each worktree has to be approved separately. Before approval an execution seat
                             cannot see the tools, and that failure is silent -- a session with no tools simply
                             takes the degraded path (§0.3-4)
  .claude/
    settings.json          hooks (validation and permission gates)
    agents/                shared subagent definitions
```

**README must not become a third copy.** Four documents have four different readers:

| | Reader | Character |
|---|---|---|
| `plan_ko.md` | someone changing the structure | **the record.** Korean, and allowed to be long |
| `plan.md` | someone who does not read Korean | **generated.** The English rendering of the record; where they disagree, the Korean wins |
| `CLAUDE.md` | every session | **binding rules.** Read six times, so it has to be short |
| `README.md` | **someone who has read neither** | what it is, what it becomes today, where to look |
| `docs/index.html` | **someone who will not even open README** | an outsider sent a link. Within 30 seconds, only *what is this system trying to do* |

**And now that there is a fourth, the risk is not README but `docs/`.** The sentence guarding against a third copy repeats verbatim at the fourth position — `docs/` does not re-enumerate the principles, does not carry over the check list, and does not write a progress percentage. **There is exactly one thing that page can do and the other three cannot: pictures and film.** Everything sayable in sentences is already somewhere else, so it points there. That is precisely what the person asked for on 2026-09-20 — that a faculty member opening the link sees within 30 seconds that the loop is closed.

**README does not restate. It points.** Rewrite the principles, the decisions, the check list or the procedures and the failure seen four times today repeats at a third position — it is **the same rule applied at the document layer** as the envelope not echoing numbers (§4.4-5), a card not echoing a definition (§5.1), and Markdown not echoing JSON (check 9). Name the section number and stop.

**Numbers especially.** How many checks, how many cards, what percentage complete **go stale the moment they are written** — wrong three times in one day in `CLAUDE.md`. If the status has to be stated, write **what to run** instead.

**`agentic-microscope`'s README is 2215 lines.** It is open, so the structure may be looked at (§10.2), but **the length is a warning rather than a model.** Looking at that repository for the sake of the README is not a transfer of a value or an expression, so it is not subject to a §10.2.1 ruling — but **carrying a sentence across is.**

### 7.1 Output-tree rules (P12)

1. **One question = one folder.** The question, goal, per-axis constraints, synthesis and plan sit flat in `questions/<qid>/`. Open one folder and the whole story of that question is visible.
2. **Do not create per-stage folders** (`stage3/`, `system_designer/` and the like). Which stage an output belongs to is said by **the filename.**
3. **A round is `r<N>_` and a revision is `v<N>_`.** Digging folders only adds depth and stops the listing being readable at a glance. **They are different things so their prefixes differ** — until 2026-09-18 this rule said "rounds and revisions go in the filename prefix", **binding the two into one sentence**, and check 13's implementation picked the first and compared `r<N>_` against the card's `round` field. So putting revision 2 beside it as `r2_` per §4.5.5 produced `the filename says round 2 and the card says 0`, and **§4.5.5 became unfollowable.** It is not that the implementation was wrong but that **when one sentence means two things, the reader picks one** — the fifth today after `accept`/`refuse`, `unconstrained`, `derived` and `degraded`. Rounds live in the bridge's `threads/<thread>/` and revisions in `<agent>/questions/<qid>/`. They never appear in one folder, so position could have done it, but **an implicit rule bit four times today, so a visible mark is used.**
4. **Identifiers go only in the filenames of outputs that leave** (`question_…`, `plan_…`). Internal intermediates stay short, like `goal.json` and `axis_A1.json` — the path already says whose and which question.
5. **Approval cards go separately in `approvals/`.** A `scope_approval` spans several questions, so `questions/<qid>/` cannot hold it. The side effect is the essence — **agents write into `questions/` and the person writes into `approvals/`.** The writing party is separated by folder (§8 check 35).
6. **A depth ceiling of three** (relative to the agent directory). The only exception is `runs/<run_id>/raw/` — raw data follows whatever structure the instrument emits.
7. **A new folder comes into being by editing this document.** Write to a path §7 does not declare and the validator fails it (§8 check 13). **There is no ceiling on the count** — a number is bypassed by digging folders inside folders, while the obligation to declare cannot be bypassed.
8. **Delivery is placed in the receiving tree. The receiver does not go and open the bridge.** `<agent>/inbox/` is the only folder **the bridge writes and that agent reads** — the same shape as `approvals/` being the person's and `tasks/` being the manager's (rule 5), with the writing party separated by folder. **For classification the boundary is `bridge` and not that agent**: only the place is in that tree, and an agent writing its own inbox forges a delivery. The alternative — having the execution seat read `bridge/threads/` directly — is **refused. It breaks §7's separation path**: taking the microscope PC means taking `microscope_agent/` plus `contracts/` only, so `bridge/` does not follow, and putting the inbox there makes the round invisible the moment it separates. Today's smallest-looking move is D1's most expensive one. **The inbox holds envelopes and not the turn**: `status.json` is the only file in a thread that **changes**, so a copy goes stale the instant the turn moves, and that drift is exactly what left the example round reading "the human's turn" for a day — it happened to be the file a seat used as a model when writing its first round, and it was in fact copied. **An envelope being in the inbox already means it is your turn**, so there is nothing more to write, and what can go stale is not kept in two places (§11-11). The receiver's mark of having taken a round is the goal's `from_round` (`thr-…:r<N>`), and the bridge, already reading both sides' `questions/`, knows it **while writing nothing in the reverse direction.** Nothing is deleted from an inbox — the delivery happened and that file is the record of it (P1). The bridge manager settled it on 2026-09-19.
9. **What was abandoned and what was ruled live in different ledgers.** `failures.jsonl` is **dead ends** — things tried and abandoned. `rulings.jsonl` is **rulings made** — §10.2.1's transfer/downgrade/drop, and **a `drop` is not a failure but a successfully made ruling** (that item was judged to have no slot anywhere in A1–A7). Put them in one ledger and that distinction disappears. Nor `questions/<qid>/` — a ruling is made per **task**, not per question (§9.3).

    **And a file at the repository root has to go into **two** lists — `ALLOWED_PATHS` and `SHARED_PATHS` inside the validator.** The two holding the same six is not a coincidence but **different roles over the same subject**: the first asks *may this file exist*, the second asks *whose boundary is it in*. **Put it in `ALLOWED_PATHS` alone and check 13 passes while the path stays `unattributable`** — it may exist and nobody knows who may commit it, and check 41 finds nothing to attribute. On 2026-09-19 `pyproject.toml` and `uv.lock` were in that position. **They are not the two places §11-11 counts** (not the same fact but different questions about the same subject) **but the coupling is real and was written nowhere.** Entered into `SHARED_PATHS`, the boundary becomes `design`, and that is the right answer for a whole-repository manifest — the four managers will each add dependencies, so if it belonged to one seat the other three would round-trip every time. The same shape as `contracts/`: check 41 gives attribution and not refusal. The simulation manager raised it.

    **So when two seats have to declare together, the one whose absence a check tolerates goes first.** Here that is `ALLOWED_PATHS` — check 55 looks only one way, at **whether the regex permits a path §7 names**, so with the regex in first there is nothing for 55 to see and it stays silent, and §7 follows and passes. The other way round, 55 refuses the moment §7 lands. **Simultaneously is impossible**: `plan.md` is architecture's and `validate.py` is the manager's, so they cannot be one commit and check 41 blocks it.

    **And 55 looking one way is design and not a defect — written here so the next person does not "complete" it.** Bidirectional means **either half is blocked whichever is placed first, and the two seats can never get in.** One-way means **exactly one passing order exists.** The same shape is in §8 — implementation first and the declaration closes it, and the other way round the gate runs the whole validator and every session stops. **A check involving two seats has to leave one order that can pass.**

    **Where there is no place, that class is not counted, and that has already happened.** §9.3's criterion ② asks exactly *"how many were discarded for being unattributable"*, and **discarding by definition leaves no output.** On 2026-09-19 the repository-wide `ruling` values were transfer 5 · downgrade 1 · **drop 0**. The 0 is not a fact about the work but **the fact that there is nowhere to write one**, and while that distinction cannot be made, criterion ② can never be counted. **It has to exist before the A/B resumes** — whatever is discarded in between is never counted. The microscope manager raised it.
**The delivery path and the reader are two facts, and on 2026-09-19 only the first was written.** On the day rule 8 came into being, round 1 was actually delivered into `microscope_agent/inbox/` and every mechanism worked — checks 8, 13 and 41 passed, the payload hash recomputed identically, and the receiving side compared the envelope against the schema and confirmed it intact. **But the word `inbox` was not in the receiving side's instructions.** That seat's `CLAUDE.md` was last touched at 00:41 and this rule arrived at 10:25, so **there was no reason to open that directory.** The receiving side's own wording is kept: **it was a dead letter by design, and a message saved it.** Not "nobody read it" but **"the receiving side never had a reason to read it."** And that structure is exactly §6.2 rule 2's shape — the notification worked and **left no trace.** If that session resets, the only thing saying a round is waiting is an untracked file nobody was instructed to open.

**Therefore delivery goes only to a named recipient.** The receiving agent's instructions have to name `inbox/` for a delivery to happen, and where they do not, **the round is not delivered and stops visibly** (P0's shape: ambiguity does not proceed, it stops). That is better than sitting quietly in an inbox — a sitting round **looks delivered and is not read.**

**Naming the recipient is that agent's manager's job.** A thread names an **agent**, not a seat — one agent may have more than one execution seat (D12), and on 2026-09-19 the same notification reached two execution seats and **both correctly did nothing.** Each was correct because neither had been instructed, and the result is **a state that looks staffed and is not.** That assignment is work and not a tier, so the manager makes it (§6.2.2: work goes down and permission does not). **If the manager's position is empty, that agent does not receive rounds.** That is exposed rather than absorbed — when an empty position is the cause and something else fills in, the empty position is invisible.

### 7.2 Code rules (P13)

**Dependencies flow one way.** These five lines are the whole of the code structure, and they do not change however many files there are:

```
contracts/                   imports nothing (leaf)
      ▲
src/axis_*.py, synthesis.py  imports contracts only. Knows no device.
      ▲
src/operator.py              contracts + the orchestrator (or the simulation backend) only
      ▲
src/orchestrator.py          the only place that may import devices/ (microscope)
      ▲
src/devices/dev_*.py         imports neither a sibling nor anything above
```

1. **`contracts/` imports nothing.** A contract depending on an implementation is not a contract.
2. **Planning-stage code (`axis_*`, `synthesis`) knows no device.** Tied to a device API, a plan cannot be made without hardware and mock validation (§4.6.5) becomes meaningless.
3. **`operator.py` does not import a device directly.** On the microscope it sees only the orchestrator; in simulation only the backend module.
4. **Only `orchestrator.py` imports `devices/`.** It is the code-level expression of the single entry point (§4.6.8).
5. **`devices/dev_*.py` imports neither each other nor anything above.** A reverse dependency is a failure (§8 check 16).

**Folders are given only to what grows.** `devices/` is the only subfolder because devices are the one axis that keeps growing as they are swapped and added. `axis_*.py` is a fixed list (seven for the microscope, six for simulation — §4.5.3), so giving it a folder creates an empty layer. A flat `src/` with twenty files reads well enough by prefix (`dev_`, `axis_`).

**Where the LLM and Python sit**: judging stages go in `.claude/skills/`, and checking, computing and command derivation go in `src/`. It is not splitting one stage across two places but **judgement in skills, determinism in src** — P4 laid out as files.

**The separation path (following D1)**: so that physically separating onto the microscope PC later means detaching `microscope_agent/` plus `contracts/` and nothing else, the microscope agent does not read another agent's directory directly. What it reads is `contracts/`, its own directory, and the cards the bridge placed on its side.

---
## 8. The validation layer

**Check numbers in progress are assigned here.** The table below is **not a declaration** — check 42 reads only the `NN. ` form as a declaration, so it does not count this table. It exists because two seats proposed 45 on the same day, and when numbers collide two implementations fight over one function name.

| Number | What | Seat holding it |
|---|---|---|
| 65 | whether the four checks that read history (26, 35, 41, 46) have a test that builds a repository | manager-bridge |
| 63 | whether a tie verdict comes out carrying the worse grade of the two values compared (§5.8.1) | manager-bridge |
| 59 | whether the hook names and warns about the paths of an unattributed commit | manager-bridge |
| 66 | whether an irreversible action's run reads back compliance (`verification`) | manager-microscope |
| 53 | whether an agent setting's `deny` contains a pattern that blocks reading | manager-microscope |

**When the implementation is done, the declaration goes into the list below and it leaves this table.** The order is §8's own — agree → implement → declare.

**A check also says what it deliberately does not refuse.** On 2026-09-19 that stopped a correct guard from being deleted. Check 53's first draft refused the bridge setting's `Bash(python3*hardware*)`, and that is **the only denial actually enforced in that file, and adjacent to P0.** The seat's first impulse was to delete the entry to make the tree green. **What stopped it was that the docstring recorded that the pattern is legitimate and that an earlier draft had wrongly refused it** — so it read the implementation, saw the implementation at odds with its own description, and it was fixed on the second run.

**Deleting the right thing to satisfy a gate is the most expensive failure** — the same pressure as a gate that refuses correct work being answered with `--no-verify`, and this side is worse: a bypass leaves a trace while **a deletion leaves a green tree.** So a check's documentation records not only what it refuses but **what it deliberately does not refuse.** Without that sentence, when a check is wrong the reader suspects their own file.

**A card can be perfectly written, pass every check, and be false — because the world moved beneath it.** On 2026-09-19 §11-13 was rewritten **three times in one day**: a product was identified, retracted, and the retraction retracted. The record was right at each moment and false hours later each time. **This is different from stale prose** — stale prose is a reference that lost its referent, and checks 47, 48, 50 and 51 catch that class. Here **every reference resolves and every sentence is coherent and the world says something different.** No writing convention catches it, and **no check catches it either** — the validator reads the disk, not the bench. Only one thing catches it: **re-reading before acting.** So it is written down lest the conventions read as covering this too. The simulation manager raised it, distinguishing this class from its two stale holds — the former is **an instruction outliving its grounds** and is stopped by a writing convention; the latter is not.

**Check 33's group key serves two checks whose scopes differ — so the state it was preventing passes (2026-09-19).** The key is `(directory, qid, revision)` and it adjudicates two things: `caller_id` uniqueness and `kb_version` agreement. **The first needs revision in the key** (two revisions of the same axis share one caller_id under the legacy form, so without it a false failure hit correct cards — so it was added, and that reason is right), and **the second must not have it.**

Because one question's fan-out **has to read one store at whatever revision.** With revision in the key, when siblings split by revision, **the two groups are each internally consistent so it passes, and the fan-out is in fact reading two stores.** `mic-20260918-001` was in that state today — `a2·a3·a4·a5` at rev1, `a6` at rev2, `a1·a7` at rev3. And it is not hypothetical: the librarian seat measured from the log that `a1` read `kbv-67f9ad766d92` while its siblings read `kbv-49feb73662b7`, and **the two axes were incomparable.** **It was invisible inside the cards and visible only in the log.**

**So the group is split: `caller_id` uniqueness keys on `(directory, qid, revision)`, and `kb_version` agreement keys on `(directory, qid)` and does not look at revision.** And the constraint that follows is stated — **re-pinning a fan-out moves every sibling in one commit.** A half-moved fan-out is not a false failure but **genuinely an incomparable state.** The microscope execution seat found it reading card 008, and that card had already written *"siblings of one qid have to agree on kb_version, so this is not an A6-only re-pin"* and then **narrowed its own scope to five**, leaving `a4` and `a5` by the same logic. **The card's argument refuted the card's scope.**

**`inputs` accepts `kb:<entry_id>` too (2026-09-20) — the second case of the same class as `basis`.** A derived quantity's `inputs` currently accepts only names in the card itself, so **an input that is a derived value from the store is inexpressible.** On 2026-09-20 that blocked something real — an execution seat computed `tracer_diffusivity_expected` (τ_d ≈ 300 s, crossing within one order of magnitude with the simulation side's independent 312 s) and **reverted it for want of anywhere to write it.**

    **It is permitted for the same reason as `basis`, and for a different reason from the PFS case below.** What was refused down there was that **what was missing was data** — the PFS fact did not exist as an entry. Here **the entry exists and the field cannot name it.** When what is missing is an **expression**, widen the expression; when what is missing is **data**, make the data. Separating those two is the whole of this judgement.

    **And the resolution machinery already exists** — check 54 resolves `basis`'s `kb:` references against that card's `kb_refs`. It is a symmetric repair with no new vocabulary. **Check 62 in fact gets easier**: today it has to find the name in the store and ask about carrier unanimity, whereas `kb:<entry_id>` **points at exactly one, so the unanimity question does not arise.**

    **The direction of the asymmetry is what names this defect.** The same three inputs are **legal in an entry and illegal in a card** -- the entry schema accepts names that resolve against the store, while check 17 accepts a card's `inputs` only from that card's own `numbers[]` and `CONSTANTS`. And **the side that must show the gate its grounds is the card, and the side that cannot state them is also the card.** The microscope manager wrote it that way, and the sentence says why this is a defect more briefly than anything else here.

    **The loop was closed, which is the evidence that the expression gap is not cosmetic.** The fan-out could not move to the current store because **moving it made A2 inexpressible**: `missing` empties, the axis falls to `failed`, and that is false about an axis that ran fine and is a state that stops a plan. So **this one field was holding all seven cards of the re-pin.** Meanwhile the executing seat had computed `tracer_diffusivity_expected` -- 0.09 um^2/s, tau_d about 300 s, crossing the simulation's independent 312 s within an order of magnitude -- and **reverted it for want of anywhere to write the input down.** The first time two agents reached the same quantity independently, and it lived in a message rather than in a card (6.2 rule 2).

    Implementation is manager-microscope's — the same place that widened `basis`.

**No third form is created for `precondition.basis`.** A5's PFS interlock came up as having nothing to cite, and what is missing is not a form but **data**: *"PFS cannot verify the mounted state"* is **a fact about this instrument** and therefore knowledge, and knowledge lives in one place (P14). The librarian has to have an entry, and the service answering `absent` for `pfs` today **is reporting that absence exactly.** §2.1's interlock rule is the **reason** that bound stands, not the **grounds** it rests on, so it goes into the precondition's statement and not into `basis`. **Building a mechanism when what is missing is data is the inversion refused for the fourth time today.**

**Grounds that cannot produce their own number are worse than a bare number.** On 2026-09-19 §11-13, writing down why polydispersity could be ignored, said *"since D ∝ 1/d, twice the diameter spread"*, and **that number does not follow from those grounds** — an exponent of −1 gives 1:1, and twice would need −2. **That paragraph's output was not a number but the grounds**: the reason the paragraph existed was that nowhere said why polydispersity need not be considered when nobody was considering it, so **grounds that cannot produce their own number are the one thing that must not be there.**

And **the reason it is worse than a bare number is that grounds suppress checking.** With a number alone the reader doubts it; with a derivation attached they pass over it — and in fact the simulation manager copied it straight into its own card and found out a day later, having gone to confirm the value for another reason. **Wrong grounds make a wrong number trustworthy.**

**When a check's question scope is set by what the check happens to see, it asks what it saw instead of what it should ask.** Check 64's first version failed all forty-eight — it read `b.cards`, and **an ordinary run excludes the rejected tree entirely.** Where it should have asked *"what is this directory like"* it asked *"what did this run collect"*. **Two cases is not an anecdote**: check 61 drew the same line the same day with *"a property waiting on a real rack passes vacuously on a rackless day"*, and check 26's branch fixture, testing *"there is no snapshot"*, **burns the wrong branch and is green anyway.** The three are one class.

**So when writing a check, ask first: what is the target set of the question this check must answer, and what is the set actually in hand.** When they differ, **what is in hand decides the answer** — and that failure is usually green and therefore silent. 64 turned forty-eight red on its first version and **failed loudly, which is why it was caught.** 61 and 26 did not.

**Sometimes what counting fixes is not the answer but the question.** Four censuses ran on 2026-09-19 — 28 intervals, 55 `numbers[].name`, five target references against nine, E5 per plan — and **all four times the pre-count framing was plausible and wrong afterwards.** The last is clearest: the question started as *"why does my agent guess so much"* and the answer was not that it guesses much but **that the derivations are long.** **What the act of counting fixed was the question, not the answer.** §11-12 had the same shape (counting how many the `kind` argument would have fixed gave 0), so there is one rule: **when you think you have found a class, count. Do not put that class's name in a document before counting.**

**An advisory is not a new state but a number carried in a passing message.** When something arises that **must not go red on correct inaction** — like envelope currency — an `ADVISORY` is not added to the validator: add a state and everyone has to relearn the meanings of five, and how `--strict` counts it becomes a new question. **Use the idiom already here: a passing check's message carries the number.** That is what check 52 does with `4 still by reference`, and what check 3's `UNDECIDED` line does with a per-plan count. **A gate that refuses correct work is bypassed** (§6.2.1), and making an advisory a failure is exactly how to build one — if the tree goes red merely because a seat was briefly not running, people learn to skip it.

**And the same rule was being enforced differently on two surfaces.** §5.3 defines `computed:` as max(E4, worst input), and **check 21 derives that from a card** (`computed from {grades} gives max(E4, worst)`) while **check 43 only looks at the range on a KB entry** — `declared in ("E4","E5")`, reading no inputs. So a value whose worst input is E3 passes when written as E5. **One rule with two enforcers and only one of them knows the rule** — the shape §11-11 counts, with the place being inside the validator. Check 62 aligns 43 with 21. The librarian seat had honestly written into its own entry *"the validator enforces the range only"*, and that sentence goes stale when 62 lands.

**A check that sees whether a name resolves cannot see whether that name is right — this class is written once here and each declaration points at it.** Checks 47 (seat names), 48 (registry paths), 50 (recipient instructions) and 51 (`open_question`'s home) all have the same shape: **they read a declaration, not an understanding.** An instruction naming the inbox may describe it wrongly, and a field naming `§11-13` passes while pointing at the wrong item. The reason they are worth it anyway is that what actually bit in this repository was **an absent name, not a wrong one** — on 2026-09-19 four pieces of prose went stale in one day, a delivery path stood with no reader, and eight registry entries were dead letters. **A declaration one end of which nobody reads** is this repository's mode of failure, and this class catches that. The limit is written here so **that someone who trusts the checks does not entrust more to them** (a cousin of §8.2: a silent fallback passes the test and fails in the field).

One `contracts/validate.py` checks every card. The model does not participate in this checking (P4).

The check list:
1. Schema conformance (mandatory fields, types, enums)
2. Unit existence and dimensional consistency
3. Sources and grades — zero numbers without a `source`, zero without a `grade`, E5 count ≤ the ceiling, zero E6
4. Whether an `assumed` is actually explained in the `assumptions` list
5. Envelope/budget comparison — whether every condition is inside its limit
6. `stop_criteria`/`success_criteria` present and machine-readable
7. State-transition legality (§5.5) and approval–revision match
8. The bridge wire (§4.4): whether the payload hash matches both the envelope and **the original card**, whether the direction agrees with the envelope kind and the payload's author, whether the envelope is free of numbers, assumptions and `kb_refs`, whether the producibility verdict **equals the value derived** from the vocabulary and the capability table, whether the unit comparison was skipped, whether a round was opened twice on the same (direction, observable), whether a repeated `(reason_code, parameter)` is recorded in the ledger and escalated, and whether `status.json`'s turn agrees with its state
9. Markdown ↔ JSON mismatch — numbers and units, and **whether the `thr-…` and qid identifiers the Markdown carries equal the paired card's** (a mismatch fails; the JSON is the record, P3). **This is not checking prose**: those two are the identifiers a reader sees and acts on — which thread, which question — and the rest of the prose is explanation with nothing to compare against. On 2026-09-19 an example round's Markdown was calling **a thread name that exists nowhere in the repository.** The name changed in the card and the prose stayed, and a check that looked only at numbers and units caught nothing. That file happened to be what a bridge seat uses as a model when writing its first round, and **one seat actually copied it.** The better answer is for the Markdown **not to restate what the JSON holds at all** (`bridge/CLAUDE.md`), and this check is the net for when somebody restates it anyway
10. `degraded` propagation — whether a plan's `degraded` is also on the result that came from it (§3.1 rule 2)
11. S3 independence — whether `axis_*.json` files reference each other (§4.5.2)
12. S4 closure — whether every number in a synthesis originates in an S3 output or the goal card. A new number with no source fails (§4.5.4)
13. Path legality — whether something was written to a folder §7 does not declare or to a path four levels deep or more, and **whether the filename's round prefix equals the card's `round`** (§7.1 rule 3). The prefix check applied to envelopes only until it was widened to every card and ledger on 2026-09-17 — rounds are separated by filename rather than folder, so when name and content disagree, a thread's ordering is false in the file listing
14. Command traceability — whether every command parameter in `log.json` has a source field `from` (the field path in plan.json) (§4.6.1)
15. Approval precedence — fails if `runs/<run_id>` exists with neither a `plan_approval` nor a valid `scope_approval` (§6.1)
16. Dependency direction — whether §7.2's five lines hold: zero imports in `contracts/`, whether `axis_*` knows no device, whether there are sibling or reverse imports inside `devices/`, and whether any instrument call bypasses the orchestrator
17. Units and derived values — whether every quantity uses a unit `units.md` permits, whether a `derived:` value's defining expression is in the KB or written in the card, and whether it matches the result of recomputing from the physical values (§5.7)
18. Scope range — whether a `scope_approval`'s condition range is a subset of the envelope, and whether it has an expiry and a count ceiling (§6.1)
19. Scope validity — whether execution happened under a `scope_approval` whose destruction condition had occurred (§6.1)
20. Grounds for the configuration choice — if more than one configuration passed S3.0, whether `alternatives_rejected` is non-empty and each elimination carries its numbers (§5.4, S6)
21. Grade derivation — whether every number's `grade` is derived from its `source` per §5.3's table. **A self-reported grade fails**
22. Grounds for an irreversible action — whether a `plan_approval` exists when the parameters of a `reversible: no` action depend on E4/E5 (§2.1 rule 3)
23. Manual lockout — whether automatic commands went to the same device group while a `manual` instruction sheet was open (§2.1 rule 5)
24. E2 validity — whether a calibration-derived value's expiry and condition range are valid at execution time (§5.3)
25. Recording the librarian's response — whether `axis_*.json` has `kb_refs`, and whether the grade the librarian gave propagated unchanged, neither lowered nor raised (§4.3.1)
26. Snapshot integrity — whether each item in `envelope/snapshot.*` matches the KB record by hash, with no sign of hand editing (§4.3.2)
27. Knowledge ownership — whether a KB-like file (a collection of claims or literature values) has appeared in an executing agent's directory (P14)
28. Precision — whether an E4/E5 value in a plan with `intent: explore` carries significant figures beyond an order-of-magnitude notation, and whether a computation with an estimate mixed in was written as a numeric interval (§5.8)
29. Failure recording — whether validator failures, refusals, deviations, scope destruction and **abandoned attempts** are in `failures.jsonl`, and whether each record has **exactly one** of `qid` and `task` (§8.1). In a seat with no `questions/` — the librarian and the bridge — a dead end belongs to a **task** rather than a question. With neither, the record does not say what it is about; with both, M5 counts the sample twice
30. Lesson form — whether every lesson has an evidence id, `n`, a condition range, a **`falsifier`** and a `valid_until` (§8.2)
31. Candidate preservation — whether a lesson removed a configuration candidate from S3.0 (P16)
32. Purpose — whether the goal card has a `purpose`, and whether a reason is written when `intent` differs from that purpose's default (§4.5.1)
33. Caller isolation — whether the `axis_*.json` files of one `qid` use different `caller_id`s and all cite the same `kb_version` (§4.3.1)
34. Sameness of a comparison — whether, in a plan with `purpose: compare`, the arms' conditions are identical apart from the compared variable (§4.5.1)
35. Session write boundary — whether each commit's changed paths are inside that agent's directory, and whether `contracts/` was modified from an agent session (§6.2). **It fails only after `contracts/seats.json`'s `enforced_from` (`f971c40`, the commit that turned the boundary from a convention into a gate) and merely reports before it.** The same reason check 41 moved to the parent's registry — if a retrospective sweep turns history from before the boundary red, nobody runs the sweep. Two grounds were confirmed on 2026-09-17: before `f971c40`, §6.2 existed only as prose and refused nothing, and **every commit in that span is the person's**, and the person owns every boundary (the `human` seat). Exactly three commits are affected — `0ea116e`, `e6a87f1`, `72d17fc`, from when one design seat held `contracts/` and `librarian_agent/` together and `kb/` was hand-curated
36. Symbol collision — whether a card's ad-hoc dimensionless-group definition conflicts with a definition of the same symbol in the KB (§5.7)
37. Time base — whether every event in `log.json` has an offset against the common `t0`, and **whether the times used in physics came from a trigger counter or a hardware timestamp** (§4.6.9)
38. One table — whether `contracts/capabilities/`'s configuration id set equals the optical-path table's, whether each configuration points at an entry in that table, **whether each configuration's `devices[]` are channels actually in the channel table** (pointing at a retired row fails with the retirement reason), whether declared observables' units are in `units.json`, and **whether a `produces` item requiring composition is actually composable** — whether the named configuration is a `perturbation` and its `composes_with` points back (§4.6.7)
39. Justification of estimates — whether every `assumed:` (E5) number on a card that reached the librarian (a card with no librarian in `degraded`) points at an item in `kb_gaps` (§4.3.1). It does not apply to a card that did not reach it — `degraded` states that fact
40. Window conditions — whether a plan using an observable the vocabulary marks `window_required` carries that `window_parameter` as a condition, and whether the number that condition points at is actually in `numbers[]` (§5.7)

    **A name absent from the vocabulary is a `FAIL`** (`728f6b9`). It used to be held as "the window requirement is unknown", so a plan containing a typo passed **unrefused with only the window requirement quietly unenforced** — and on the bridge side that card derives as `undeclared`, so **one typo becomes a thread waiting on a person.** It is different from §4.4's `undeclared`: that is a hold meaning "we do not yet know whether the other side can produce it", and this is **a reference pointing at something that does not exist.**

    **A name absent from the vocabulary is a `FAIL`, not `PENDING`** (2026-09-18). It used to be held as "the window requirement is unknown", so a plan containing a typo or an invented name passed **unrefused with only the window requirement quietly unenforced.** On the bridge side that card derives as `undeclared` and the round stands held, so **one typo becomes a thread waiting on a person.** Do not confuse it with §4.4's `undeclared` — that is a hold meaning "we do not yet know whether the other side can produce it", and this is **a reference pointing at something that does not exist.** As a side effect §11-1's ordering is enforced: a new observable can be used by name in a plan **only after it is entered in the vocabulary.** Every card today uses a known name, so this change breaks nothing.
41. Seat attribution — whether a commit's (or the staged set's) **committer identity** is a seat in `contracts/seats.json` and all its changed paths are that seat's (§6.2.1). It is three layers: `owns` gives the boundary, `paths` if present narrows again **inside** that boundary, and `excludes` **subtracts** from it. `excludes` is adjudicated before the narrowing so the refusal message states the real reason. The subtraction is needed because D12 gives `contracts/` to the managers while leaving only `contracts/seats.json` with architecture, and the reason that stays is that **when the constrained party owns the file saying what it may touch, that is not a boundary but a preference.** An unregistered identity fails only when `unknown_committer` is `refuse` — **except a merge, which fails then too.** On a plain commit, `report` is partial coverage (check 35 still counts boundaries and the paths are visible). On a merge, `report` is **zero coverage** — check 35 does not decompose merges by design, so with no attribution not one check looks at what that merge contributed, and the shared core's only defence goes off entirely. The same policy means two different things in the two situations, so the default splits. A person merging by hand uses `human@seat.invalid` — a seat that already owns every boundary, and merges are far rarer than plain commits.

**The judging standard is the registry as it stood at that commit's parent.** Not the `seats.json` in the current working tree. `d6f5323` showed that on 2026-09-17 — when it was made, `contracts/capabilities/microscope.json` was that seat's path, and minutes later when the boundary was divided **the same commit turned into a FAIL.** If the retrospective sweep §8 prescribes (`--commit-range`) turns old history red every time a boundary moves, nobody runs the sweep. What check 41 asks is "**was that seat inside its boundary then**", and that is a question about the commit's moment.

**The reason it is the parent and not its own tree** is that otherwise a commit that widens its own boundary is judged by the widening it just made. Read from the parent, a commit widening the registry is judged **by the rules before the widening**, so it has to be a legitimate `seats.json` commit by architecture, and the new boundary applies from the next commit on. A merge uses its first parent, and a root commit with no parent falls back to its own tree. `--staged` uses **HEAD's** registry on the same principle — so a staged widening cannot approve itself.
42. Check-registration agreement — whether §8's declarations, the `def check_NN_` implementations and the `CHECKS` list are the same set in all three places. It diverged twice on 2026-09-17 (38 declared only, 40 implemented only) — a state where a number in the document points at nothing
43. Entry grade derivation — whether each entry's `grade` in `kb/entries/` is derived from its `source` kind per §5.3's table, and whether any E6 is in the store. Check 21 looks only at cards, so nobody was checking the store's grades — the self-reporting forbidden in a card was open on the store side. Entries with no `source` are counted and reported (not passed); once the store fills them all, that field becomes mandatory (§4.3, §5.3)
44. Subject resolution — whether the id an entry's `subject` names is actually in that kind's registry. `device` means a channel, element or **retired row** id in the device table, `configuration` the optical-path table, `observable` `contracts/observables.json`, and `quantity` a name actually used in `numbers[]` (the weakest of the four; a de facto rather than declared registry, so it catches about as much as a typo). Retired rows are included because **a fact about hardware that was put away gets looked up later** — `sample_temperature_not_actuated` is that case. **A subject is only meaningful if it can be wrong, so adding an id to a registry in order to pass is emptying the check** (§4.3.1)
45. If `degraded` does not name the librarian, the query log carries that call — a card without `librarian_agent` in `degraded` is not an absence but **a claim**: this question went to the service and the service answered. Comparing that claim against the only record that could show it did not exist until now. The claim is easy to make by accident — an agent that read `kb/` by hand gets the same numbers and writes the same card, and the reason §0.3 draws a line between reading a file and the service answering is that the two **look identical inside a card.** **What it cannot establish is written with it (§9.1): the log holds the claim, it does not confirm it.** `caller_id` is an argument the caller supplies and the server does not see the identity behind it, so a line means a call happened under that id and **not that that seat made it.** What it blocks is there being no line at all. The `caller_id` revision migration window is acknowledged (§4.3.1) — a card that has to drop `:v<N>:` to match the log is reported, not failed. The call happened and the id changed later, and it turns into a failure when the pattern tightens
46. Vocabulary pin resolution — whether a `result`'s `estimation.vocabulary_version` is **a derivation of the current vocabulary, or a commit in history where its content stood.** It was a place where any value passed as long as the form matched (`obs-` + 12 hex). A version never committed fails because **there is nowhere to read it back from** — the same case as the librarian MCP writing "a hash of a working tree cannot be served", and the same shape as what check 25 does against the store index
47. Whether the seat names `seats.json`'s prose cites actually exist in that file — this registry's prose really does work: `growth` dictates the identity a second session takes, and each seat's `note` says which identity that session holds. On 2026-09-18 one of them cited `seat/simulation-1`, and **a name never registered, whose branch was gone, was deciding who may commit.** It survived because prose is not data and only people read it. It is §11-11 one level over — there the same fact lived in two places and diverged; here a name lives in the prose and its referent lives in the list, and **only the list is maintained.** **Citing a dead name is not a defect, and the `simulation-1` fix is the evidence**: fixing the note was itself an act of writing a dead name. This check is in the 47/48/50/51 class (it reads a declaration, not an understanding), so it does not try to tell the two apart. In the top-level `retired_names` it is a citation; absent from it, a dangling reference. **That key belongs to the registry's owner, so the check reports while the key is absent and refuses once it exists** — the first entry arms the check, so two seats do not have to coordinate an order (expand → migrate → contract)
48. Registry grantability — whether every path some seat lists in `paths` in `seats.json` is classified by `seat_boundary_of` into a category that seat `owns` (§6.2.1). **`paths` only narrows and cannot grant** — check 41 first classifies the path into a category and compares against `owns`, and uses `paths` only afterwards. So a misclassified entry is **a dead letter that reads as a grant and is refused at the gate**, and it fails nothing, so it stays quiet until someone actually tries to use that path and hits a wall. On 2026-09-19 that was half a day, and turning this check on then caught eight — four of them belonging to seats nobody was sitting in, so there was nobody to hit the wall. **It retires once the classifier is derived from `seats.json`** (§11-11): derivation makes divergence impossible, while a comparator only tells you after the fact
49. False gaps — whether an `absent` gap was asserted **after computing `nearest`** (§4.3.1, §8.1). Without computing it, all that gap can say is not "there is none" but **"I could not find it under this name"**, and the two lead to different next actions. **A false gap fails nothing** — what a check sees is the gap's form, not whether the gap is true, so a wrongly recorded absence stays and the next person reads it as evidence that "this value is not in the store". On 2026-09-19, of nine empty-handed results **eight were the store failing to recognise its own knowledge in the caller's words.** Now that the server emits `near_names`, `numerical_aperture` → `['na']` rides in the answer — the very case that produced this check. **"Near" is adjudicated by an exact predicate, not a score**: a score has a threshold, a threshold is a dial, and a dial widens until the report cries at everything. An empty `near_names` is not a failure but **an honest empty hand**
50. A delivered envelope has a reader — an `r<N>_ask_*.json` in `<agent>/inbox/` requires that agent's `CLAUDE.md` to name the inbox (§7.1 rule 8). **The delivery path and a seat with a reason to open it are two facts, and on 2026-09-19 only the first was written.** That day the round was correctly delivered and checks 8, 13 and 41 all passed, and it still was not read — one session reached another out of band, and **a notification that works and leaves no record** is that (§6.2 rule 2). **The check attaches to the delivery, not to the tree**: it refuses a bridge that delivered into a tree that cannot receive, and does not refuse an agent over an instruction file it does not even own. Aim at the wrong target and a correct seat is blocked by something it cannot fix, and that is the situation answered with `--no-verify` (§6.2.1). **The limit is written with it: like check 48, this check reads a declaration and not an understanding.** An instruction naming the inbox may describe it wrongly. The fixture catches that place exactly — `check50_delivery_without_a_reader/` holds **one delivery and one `CLAUDE.md`**, and that instruction explains questions, axes and approvals while **saying only nothing about where a round arrives.** A fixture made by removing a file would have tested the wrong branch: the failure is not **an absent seat** but **a seat told everything except this** (§11-7)
51. A `held` thread's `open_question` resolves to a recorded place — two halves. **The field has to exist, and its reference has to name an actual §11 item.** The first half was already written as prose in `thread_status.schema.json` — "required when state is held" — and **there was no conditional below it to hold it.** A rule written beside a mechanism was not a mechanism, the shape counted a sixth time in this repository. What the second half blocks is an `open_question` ending in "not yet recorded in §11" — which it actually was on 2026-09-19, and being **a declaration one end of which nobody reads**, what was being asked of the person arrived in no ledger. Two fixtures dig the two branches separately: a hold naming `11-99`, and **a hold that never says what it is asking.** The latter is the quiet one — a ledger can be perfectly well formed and ask nobody anything. The class's limit is the one §8 wrote once
52. A target is a decision, not a graded number — an inline `targets[]` item must not also appear in `numbers[]`, and its **unit must be registered in `units.json`** (§5.3). The slot itself makes a grade **inexpressible** (`c8ee7b3`, `additionalProperties: false`), but that is true only of the new shape — this check stops the old shape returning by habit, and inherits in the new container the unit check `numbers[]` was doing for free. **Moving a value from a checked container to an unchecked one is how coverage silently shrinks**, so the commit that opened the hole closed it.
53. An agent setting's `deny` does not block reading — it refuses entries beginning with `Bash(` or `Read(` (§6.2). `contracts/` is the place everyone reads and nobody writes, so **a rule blocking reads is not broader than the intent but contrary to it**, and a blocked seat **guesses** instead of reading. **What it cannot see is written with it: this check looks only at settings inside the repository.** The read actually denied on 2026-09-19 came from a user-level setting or the harness, and neither this check nor this document reaches there — unwritten, a pass reads as a guarantee.
54. Whether a `basis`'s `kb:` reference resolves against that card's own `kb_refs` (§5.3.2). **This is not the 47/48/50/51 class** — it looks not at whether a name exists but at **whether the reference actually resolves**, and what it resolves against is inside that card. It became necessary when A4 stood on five served `kb_refs` with an empty `numbers[]` (§5.3.2), and it closes the place where the schema promised *"this reference resolves"* with nothing to enforce it — **a promise written with no implementation is the shape this repository counted seven times in one day.**
55. Whether `ALLOWED_PATHS` permits the filenames the §7 tree names (§7.1). **§7 is the human-facing record and what refuses is the regex**, so a seat that fixed only one side could not tell why it kept being blocked — on 2026-09-19 `bridge/README.md` and `contracts/quantities.json` were in that position and **both times a line went into §7.** Being one-directional is **design**: bidirectional means either half placed first is blocked and the two seats can never get in, and one-way means **exactly one passing order exists** (§7.1). **It reads only each line's first token, so it does not see files listed on a directory line** — there are nine such lines in §7, of which two `envelope/` ones are real declarations, and this is not on the docstring's list of deliberate non-catches
60. Whether every observable id is registered in `quantities.json` (§7, §11-8). **Inclusion, not synchronisation** — `observables.json` registers *what can be produced and compared*, so it is a **subset** of `quantities.json` and not the reverse. **No escape hatch such as `not_yet_registered`**: registering an observable carries **the more expensive promise** of `estimator`, `window_required` and `producible_by`, so **a name blessed on the expensive side cannot be held pending on the cheap one.** The check and the registrations that make it hold went in **one commit** — landing the check alone would stop **every seat's next commit** on a condition `plan.md` already records as unsatisfied
61. How far behind an envelope is against the published export — **advisory, not a failure** (§4.3.2). A lagging envelope is not a defect (a consumer may pin deliberately) and **a gate that goes red on correct inaction teaches people to skip it** (§6.2.1). No new status is created; **a passing message carries the number** (§8). **It compares against the published export, not the store**: an envelope behind a stale export cannot close the gap by copying, so folding it into one number mixes **two racks with different owners.** It sits differently from check 26, which compares an envelope against **the commit it named** — that is integrity and this is currency, and the route by which the microscope envelope being 34 behind while sitting inside `0 failed` was noticed was a person opening two files by hand

    **A second leg, added 2026-09-20, with its own owner.** The first compares an envelope against the
    export that fed it. The second compares that export against the store -- a bridge that existed only
    in `export_snapshot.py --check`, which is a librarian tool and therefore runs in **no gate**. While
    the store moved twice one morning the published export sat on the previous night's version, every
    seat's gate read `0 failed`, and this check called the microscope envelope **`current`** -- true of
    the export it copied and two versions stale of the store. **A misleading word is worse than silence,
    because silence does not reassure**, and the person was choosing safety ceilings against that
    envelope at the time. Two legs and two owners, kept as separate counts: the original argument forbade
    **merging two lags into one distance**, and two distances reported side by side do not.

62. Whether check 43 **derives** a `computed:` grade **from its inputs** (§5.3). 43 derives grades from source kinds, and its `computed:` branch alone only asks whether the declared value is in `("E4","E5")` and **reads no inputs at all** — E5 passes where §5.3 says E4. **A grade that looks derived and is not is the quietest kind of wrong**: what would catch it is precisely what is absent. The rule is `max(E4, worst input)`, where **the E4 floor is the limit of how good arithmetic can make it** and **the worst input is the limit of how good the chain can be.** It does on entries what check 21 already did on cards — **a place where one rule had two enforcers and only one knew the rule** (§11-11's shape, with both copies inside the validator).

    **Corrected 2026-09-20: `inputs` names three different things and a grade composes from only one.** A
    **relation's formal parameters** (`derived_quantity`, `dimensionless_group`) are bound variables --
    `bead_diameter` in `bead_diameter**2/diffusivity` is one -- and 5.3's max(E4, worst input) is a rule
    about a **computed value**, so a relation composes no numbers and takes no grade. `tau_d` is E4 in a
    store holding no diameter at all. A **quantity an inference rests on** is the one shape that composes.
    A **claim it rests on** has no numbers to compose, and now has its own field (`supports`, 5.3).

    **The evidence that the distinction was real cut the seat's own count down.** `tau_d` and
    `tracer_diffusivity_expected` share a kind and a formula key and the check treated them differently,
    for one reason: the second's parameter names **coincidentally** match names the store holds values
    for. Carriers 0, 0 against 1, 1, 1. **Editing one string inside a formula would have produced a
    grade** -- task 020's option 2, refused at the front door, arriving at the side. The honest count of
    derivations is **1, not 2**, and the librarian seat argued the point that lowered it.

    **Fourth instance of section 8's scoping class, and the first that was green.** The three before it
    went loudly red or produced a visibly wrong number. Here what the check happened to see was the
    carrier map, and seeing the wrong set produced a passing line with a number in it.

64. Whether `--expect-fail` reaches **input** fixtures that are not cards (§11-7). `--expect-fail` asserts that fixture **cards** fail, and that is how a silently broken check is caught, but that folder holds files that are neither cards nor artifacts — two `.md` exist to fail their paired `.json` at check 9, and a group's `receiving_agent/CLAUDE.md` exists to fail the group at check 50. **They are inputs, and nothing was sweeping them.**

    **Deleting an input is already caught** — the subject stops failing and `--expect-fail` says so. **What is not caught is an input that remains and stops doing its job while another defect keeps the subject failing**, and then the fixture **passes for the wrong reason.** So it does not try to separate live inputs from dead ones — that is **running** the fixture and is `--expect-fail`'s job. All that can be said is **that every file is reached**: it is accepted if it shares a stem with a swept file, or sits in a group folder with a swept member. Neither, and it is **dead weight**, and **in a directory whose purpose is failing, dead weight is indistinguishable from a test**

    **An input resolves when the store carries that name and every carrier is unanimous on the grade.** Unanimity rather than uniqueness is arithmetic — six names ride on two or more entries and all six are unanimous, so demanding uniqueness would refuse without cause. And **unanimity cannot be quiet**: where they split, it names them rather than taking a side. **It asserts nothing about which value** — `pixel_size` is twelve different values under one grade. **It resolves a name's grade and not its value**, and that is the limit §8 records for this class.
    **Underivable is neither a failure nor PENDING.** It is not a failure because the entry is not wrong but because **there is nothing that can be said**, and not PENDING because that would mean *a later milestone produces it* and **no milestone resolves a symbol.** So it comes out as a number inside a passing message, split into three shapes — a symbol the store does not carry, **no `inputs` key at all**, and carrier disagreement. **The next action differs for all three.** The second is a different kind from the other two: the symbol is not failing to resolve, **what would resolve it is not written down.**
56. Whether check 3's undecided threshold reports in the unit §11-2 settled — while the threshold is open, that one `UNDECIDED` line is **the only place in the repository that states the unit**, and it is read far more often than §11-2's body. While it said `counted E5 = [7, 5, 17]`, that line **was teaching a unit that had just been rejected** — and **a message pointing at the wrong thing is believed**: the same day check 13's message named §7 and two seats fixed only §7 and stayed blocked, and check 41's message named `owns` and half a day went. **It compares numbers, not wording** — it recomputes the counts and compares per plan, so reverting the unit fails even if the sentence still says `rationale`. The key in `validation_limits.json` moved with it to `max_rationales_per_plan`: **a message teaching rationale while the refusal is made on raw E5 is worse than either alone.** **The limit is written with it — a rationale count counts the *number* of guesses, not their *weight*.** One rationale holding up a whole plan is still 1, and that is the price of not counting chain length. Unwritten, a pass reads as "this plan has few assumptions"
57. **An irreversible action rests on a confirmed limit** — the parameters of a `reversible: false` action in `actions[]` have to be bound by a limit in `envelope/safety.json`, and that limit's `confirmation` has to be **`physical`**. **`carried_over` is legal inside the envelope and not here**: forbid transcription and the file cannot exist until every ceiling is confirmed, and then nobody starts the file (§10.3 rule 4) — **and that licence ends in front of an irreversible action** (§4.6.6.1 rule 3). Whether it is irreversible, and the parameter list, **use exactly the `actions[]` check 22 reads**; a second definition would diverge (§11-11). Parameters and limits are joined by the naming rule the schema uses, `<quantity>_max` / `<quantity>_min`.
58. **One fan-out reads one store** — every axis card under one `qid` and one configuration has to pin the same `kb_version`, and **a differing revision is not an exemption.** Check 33 asks the same thing and cannot see this: 33 groups by `(scope, qid, revision)` and **has to.** A revision is a re-run (§4.5.5) and `caller_id` has no revision component, so grouping without it makes **"caller_id reuse" fire on a card and the card that replaced it.** For that question it is right. **The price is that the same grouping is also used for `kb_version` agreement**, and then agreement holds trivially within each partition and **nothing looks across the partitions.**

    **A revision counts a re-run of one axis. It does not count a re-run of the fan-out.** Six axes at revision 2 and one at 1 is **one fan-out**, and S4 intersects all seven. Taking intervals from two stores and intersecting them **compares two knowledge states**, and **the abstaining side is worse** — an axis on an old pin reports `absent` for what the new store holds, and downstream that is **indistinguishable from a real absence.**

    **It was written on top of a real case.** `mic-20260918-001` had six axes at `kbv-7c77fa74ee5a` and `a5` alone at `kbv-49feb73662b7` — six commits and 58 items apart — and **check 33 was passing.** Re-deriving `a5` found all seven inputs **still absent**, so that split had not yet produced a wrong answer. **That is a reason to close it then, not a reason to leave it — the hazard is the shape, not today's values.**

    **It landed after the defect was gone, and that order is the rule.** The implementation was finished while the split was live and the gate refused the failing tree. **It was not weakened to get in** — deleting the right thing to satisfy a gate leaves a green tree and is worse than a bypass (§8). Meanwhile the implementation was kept outside the repository: left in the working copy, another seat's `git commit -- <paths>` carries it off (§6.2.1).

    `scope` was lifted from 33's local function to a module-level `card_scope()` — **the two are halves of one question and have to partition the same way, and two copies drift** (§11-11).

    **Two things it does not handle.** **It compares versions and not contents** — two cards pinning the same version may still disagree about what they read, and checks 25 and 49 carry that. And **it does not say that version is current** — a fan-out standing **in agreement** on an old store is legitimate, and the test for when to move is card 008's: **move because the question's answer changed, not because the store's version moved**

    **What it does not handle is written with it: a limit being confirmed is separate from whether that limit was respected.** `optical_power_max` is `physical` as of 2026-09-20, and the channel it binds is `read_back: false`, so nothing reads compliance back — **that is the rule check 66 carries and not this one.** **Becoming able to command is not becoming able to confirm it is off.**

    **It is PENDING today and not PASS.** The repository's only irreversible action `act_bleach_ref` rests on `illumination_power`, and the microscope envelope holds only the two P0 ranks highest, which does not yet include it. **Failing now would refuse something that could not have been done**, and it flips itself the moment any irreversible parameter gets a limit

    **Upkeep moves to manager-microscope (2026-09-20), on the implementing seat's own reading.**
    manager-simulation built the schema and the check, then pointed out that its own tree holds
    **no irreversible action at all** — 57's only subject is the microscope's `act_bleach_ref`, and
    manager-microscope owns both the `safety.json` and the `actions[]` it reads. The implementation
    stays; who keeps it and builds its fixtures changes.

    **The shared surface produced that, which is worth naming.** `envelope_safety.schema.json` is in
    `contracts/`, which no manager owns alone, so the seat that reached for it designed **both
    halves — including the half it cannot exercise.** The floor-versus-ceiling distinction came
    entirely from `objective_clearance_min`, and **every limit in the simulation tree is a ceiling.**
    A shared file does not make a seat the owner of what lives in it, and the seat drew that line
    itself after crossing it.

    **And this check's draft earned §8's principle.** The draft refused `Bash(python3*hardware*)`, which is **the only denial actually enforced in the bridge setting and adjacent to P0.** The seat's first impulse was to delete it to make the tree green, and what stopped it was **the docstring having written in advance that the pattern is legitimate.** If a check does not say what it deliberately does not refuse, then when the check is wrong the reader suspects their own file

    **It was written by shape, not by name.** A naming rule would have refused `target_relative_error`, which is a statistics requirement an axis **derived** — a claim with a grade and a source. The line is not between names beginning with `target` but between **a person's decision and everything computed from it** (§5.3).

    **A third branch not in the plan was found: a dangling reference.** The old shape could point at a `numbers[]` item not in the card and **nothing looked** — a target pointing at nothing **reads exactly like a target that was set.** It was already sitting inside the shape the 47/48/50/51 class assigns.

    **The migration list is five, not two.** When the check came on it said `0 targets are stated as decisions, and 5 still by reference`, and `targets[]` appears beyond the two goal cards. The schema's removal condition names the two, so **that condition is undercounting** — **an undercounting removal condition is worse than none**: it says deletion is allowed while hiding what remains. The condition is not fixed before the full list is counted

**Check 42 binds two seats after D12 — declaration first, implementation second.** §8's declaration is in `plan.md` and therefore architecture's, and the implementation and `CHECKS` registration are in `contracts/validate.py` and therefore the manager's. With one seat, adding a check was one commit; now it is necessarily two. That leaves a span where the tree is red, and **which side goes first changes the character of that span.**

**Implementation first, and the declaration closes it.** This subsection first wrote the opposite and reversed it the same day. The wrong argument was "choose the side whose object of waiting is in its own place", and **it left out the length of the red span.** With the declaration first, the red span runs until the whole implementation and its self-test are done; with the implementation first, it lasts as long as writing one line.

**A contract change that has to move another seat's files together is loosen → each migrates → tighten** (2026-09-18). **Enforcing a new form immediately** refuses every other seat's cards the moment it lands, and the way those seats coordinate commits by hand broke twice the same day. Instead the schema is opened to accept **both the old and the new form**, each seat moves its own files, and **it tightens last.** It costs one more commit and **has no red window.** When the tightening commit becomes possible can be known by counting — when the files using the old form reach zero.

The length matters because a red check 42 blocks **not only those two seats but everyone.** The gate looks at the tree a commit would create (§8), so if HEAD is red then any commit after it creates a red tree. And there is a lesson from today — **a gate that blocks correct work does not get fixed, it gets bypassed.** Two seats adding a check is correct work, so a design that blocks everyone meanwhile invites `--no-verify`.

So the procedure is: **agree the wording first** (so the contract does not follow the implementation — the direction §6.2 warns about), the manager commits the implementation, registration and self-test (check 42 goes red), and architecture closes it with one line of §8 declaration. The agreement precedes the commit order, so the design still leads. On the afternoon the librarian seat added check 43 there was one seat and this problem did not exist.

**If that is not enough, the next move is not to soften check 42.** Simply turning a one-sided state into `PENDING` lets quiet disagreements pass too. When it becomes necessary, §8 **records the checks in progress separately** (with the seat holding each), and check 42 permits one-sidedness only for numbers on that list — a recorded in-progress and a disagreement nobody knows about are different things.

**Hooks**: the gate runs at commit time. `contracts/hooks/pre-commit` **shows** the set going into the commit, separately shows the files that **differ** from what will be committed (meaning they were not checked), runs `validate.py --staged` (including checks 35 and 41), and uses `--expect-fail` to see that the cards which must be refused still are. The validator's exit code is the only truth.

**What the gate looks at is not the working copy but the tree the commit would create.** Five sessions share one working copy (§6.2.1), so the working copy is nobody's commit — it holds everyone's unfinished edits at once. The first version validated it, and on 2026-09-17 one session's in-progress KB entries left check 25 red for hours and **refused every other session's commits.** Including commits that would have produced a green HEAD. The way out was `--no-verify`, twice. A gate that refuses correct work does not get fixed but bypassed, and a bypassed gate is not a gate.

So the hook unpacks the index into a scratch directory and runs the validator there. `git commit -- <paths>` and `git commit -a` each build a temporary index and hand it to the hook through `GIT_INDEX_FILE`, so what is unpacked is exactly the tree that commit would create — neither the working copy nor the ordinary index. **Validating a filtered subset by path was not chosen**: checks that compare **between** files, such as 12, 25 and 38, report drift that is not there or miss drift that is when they see only a subset.

The content checks read the export. Checks 35 and 41 cannot — what is staged and who is committing has to be asked of the real repository, and the export has no `.git`. The `SMA_GIT_REPO` environment variable separates the two: the hook names the repository and only the checks that call git use it. Without this variable check 35 **fails** rather than passing — so that wherever the export is placed inside some repository, it never quietly answers about that one.

Installation is once per working copy: `git config core.hooksPath contracts/hooks`.

**A hook is a gate, not a lock.** `git commit --no-verify` bypasses it as ever and leaves no trace of having done so. So separate after-the-fact enforcement is needed — re-running check 35 with `--commit-range` over a pushed range. What a hook does is make the right thing easy, not make the wrong thing impossible.

**Why it was built**: the boundary was a convention and not a gate. Each agent's `.claude/settings.json` denies `Write`/`Edit` on another's files and **does not deny `python3 - <<PY` or `sed`**, and in fact every session — including the design seat — wrote by that route. A rule enforced only where convenient stands P4 on its head: the model ends up judging whether the check applies.

### 8.1 Recording failures and successes
**The place a failure points at may not be the place the defect is.** On 2026-09-18 one enum failed two levels below `kb_gaps` and `unevaluatedProperties` failed alongside it, naming **twelve perfectly fine fields** such as `author`, `qid` and `id` — JSON Schema counts **only what a successful subschema evaluated**, so when something inner fails, every field that subschema covered becomes "unevaluated". The real defect was not in that list of twelve. **Read the deepest and most specific findings first, and findings that name fields in bulk last** — bulk is usually a symptom, not a cause.

**Why the validator failed is the cheapest data there is.** A failure comes before execution, for free, already structured.

What is recorded — all append-only in `questions/<qid>/failures.jsonl`:

| What | When | What is left |
|---|---|---|
| Validator failure | every time a card is written | check number, field path, failing value, card revision |
| Refusal | S3, S4, the bridge | which axis or configuration and why, with counter-example numbers |
| Deviation | during and after execution | planned vs actual, whether a stop criterion was violated |
| Scope destruction | when an approval is invalidated | which destruction condition fired |
| **Abandoned attempt** | when folding without producing a card | what was attempted and why it was abandoned. **An attempt that produced no card survives nowhere else** |
| Success | when a result is DONE | which configuration and conditions met the goal |

**Success is recorded with the same weight.** Collect only failures and it becomes a system that knows only what does not work; collect only successes and it is survivorship bias (§8.2-1).

### 8.2 Learning and bias — what can and cannot be done

**Discoveries come from the place where you wrote down what you did not confirm.** On 2026-09-18 a seat counted its day and said — **all four of the wrong ones were places it believed it had confirmed, and the one right one came from a place where it had written down what it had not confirmed.** That day it wrote **a limit** into its own fix — "the check was made to survive the conflict, not to remove it" — and that sentence exposed §4.3.1's defect (the server's isolation unit has no revision). What was written as a limit became a discovery. So a report carries not only **what was confirmed** but **what was not** — the latter is where the next defect lives.

**Test with the variable set and you measure the expansion, not the environment.** On 2026-09-18 `.mcp.json` was fixed to `${CLAUDE_PROJECT_DIR:-.}` and confirmed to "reach" from five working directories, and **that confirmation was done with the variable set by hand.** In a real session that variable is unset and the fallback `.` resolves to the session cwd, so it **failed exactly as before the fix.** The test was true and the conclusion false — what was measured was "is the path right" and what should have been asked is "does that value exist in that environment". **A silent fallback passes the test and fails in the field**; better to fail than to fall back when the value is absent.

**An error whose conclusion is safer than reality lives longest.** The same day `seats.json` said "git does not read `committer.*`", and git does. That error only made seats **keep attaching an unnecessary environment prefix** and produced no failure at all, so nobody collided with it and it nearly went unfixed forever. A sentence that is wrong while its consequence is more cautious **has no symptoms and is caught only by reading.**

**A false gap is quiet, and later becomes grounds.** An entry recording an absence that does not exist **fails nothing** — what a check sees is the gap's form, not whether the gap is true. And that entry stays, and the next person reads it as grounds for "this value is not in the store". **The librarian's central function fails in exactly this direction**: recording what could not be answered is the value, and a wrongly recorded absence returns that value with the sign flipped.

On 2026-09-19 there were eight real cases — of nine empty-handed results, eight were **the store failing to recognise its own knowledge in the caller's words** (§4.3.1). Five were closed by `in_published_table` and **three are closed by nothing.** The same day pixel size nearly became a ninth: architecture ruled "pixel size at the sample plane is a gap", and the librarian asked the person instead of executing, and it emerged that it is **this repository's first E2.** Without that asking back, "none" would have been recorded in the place of the repository's first calibration value.

**The contract already has the means to distinguish and no enforcement.** §4.3.1 says a gap with an empty `searched` is not a gap, and `nearest` separates "there is nothing similar" from "there is one at different conditions". Then **`absent` can be asserted only after `nearest` has been computed** — without computing it, all that gap can say is not "there is none" but "I could not find it under this name". The two lead to different next actions. This is derivable, so it becomes a check. **Assigned as check 49 — manager-librarian.** The librarian manager decides the form: where "computed" ends is a fact on the server side, and inside the boundary only that side knows it.

**The document already had the answer and two seats inferred instead of reading — twice on 2026-09-19.** On the delivery path, §7's separation path had said from the start *"the cards the bridge placed on its side"*, and the bridge manager and architecture debated three options. On pixel size, §12's table had a row saying *"a measured value per objective × zoom × binning combination, `calibration:` source, an expiry, E2"*, and architecture split it into "sensor pitch E3 plus the sample plane is a gap" and sent that down to the librarian, who executed it as given. **Both times the grounds were inside the instructing seat's own file.**

**The diagnosis of the second is sharper than "did not read": it applied a source rule without confirming the source.** §10.3's "E3 ceiling" is a rule that binds **numbers crossing from a prior repository** — a measurement taken elsewhere is not a measurement taken here. The Kinetix pixel size was not crossing from a prior repository but **calibrated by a person on this instrument**, and with that provenance §12's row was the right place from the beginning. It did not pick the wrong rule; it **picked without confirming the fact that decides which rule binds.** So the lesson is not "read §12" but **"settle where a number came from before grading it."** A grade is derived from the source (P2), not from the kind of value.

**The price was small for structural reasons, not luck.** The librarian asked the person back, and the answer overturned the classification. Had the instructed side executed without confirming, the repository's first E2 would have been recorded as a gap — and **gaps are quiet.** An entry recording an absence that does not exist fails nothing, and later someone reads it as grounds for "this value does not exist". This is the practical counterpart of §6.2.2's permission not flowing down: **a classification that came down is still only a classification and not a fact.**


**Finding a class and not sweeping that class is the most common mistake in this repository.** On 2026-09-18 a seat counted seven of its own mistakes and all seven had the same shape — it fixed check 36 and did not look at `kb_group`, it asserted there were three rename sites and there were four, it fixed `relative_to` in one place and left two. **The moment one defect is fixed, knowing it is a class, the rest are not counted.**

And what caught it was never a resolution: a self-test found the place it would stop, a census killed two proposed repairs, and the gate caught a truncated `grep`. **Actually walking the path beats the habit of doubting the list.** So a report that a class was fixed has to arrive carrying **a test that passes through that class**, not "I will be careful" — a class that was not counted is a class that was not fixed.

The librarian distils this record into lessons in `kb/lessons/` (P14: lessons are knowledge too, so the librarian owns them). **A lesson is knowledge, so it carries a grade and a falsification condition.**

A lesson entry's mandatory fields:
`{trigger, claim, evidence: [run_id | failure_id …], n, condition_range, falsifier, valid_until, grade, hit_rate}`

Bias cannot be removed. The goal is to make it **measurable and reversible.** Six known branches and their responses:

| Bias | How it arises | Response |
|---|---|---|
| **Survivorship** | only successful plans remain and failures disappear | force failures, refusals and deviations to be recorded **in the same schema** as successes (§8.1, P9) |
| **Exploration collapse** | keep choosing the configuration that worked, so others accumulate no data and are disadvantaged forever | **P16**: a lesson only reorders and cannot delete a candidate. S3.0 screening looks only at `capabilities/` and not at lessons. On a tie, choose **whichever has been tried less.** A fixed fraction of runs go with lessons off (an exploration budget) |
| **Confirmation** | a lesson that "this condition is bad" makes only that condition's bad outcomes memorable | **`falsifier` mandatory** — "if this is observed, this lesson is retired". A lesson whose falsification condition cannot be written is **refused entry** |
| **Overgeneralisation** | a rule is made from an n=1 failure | `n` and `condition_range` mandatory. Below the n ceiling it stays `provisional`, **affects no ranking**, and is shown only to a person |
| **Self-reinforcement** | an LLM reads a lesson an LLM made and makes another lesson | every lesson **must cite an actual record** (a run_id or a failure_id). An LLM's interpretation is the lesson's *explanation*, not its grounds. A lesson with no grounds is E6 and cannot enter the KB |
| **Drift** | the instrument changed and an old lesson remains | a lesson carries `valid_until` and a condition range like an E2, and enters a review queue when a calibration is renewed |

**Bias indicators** — computed periodically and shown to a person:

1. **Configuration-choice distribution**: over time, how often each configuration was a candidate and how often it was chosen. A skew is a warning.
2. **Refusal-reason distribution**: if the same axis keeps being the refusal reason, that axis's model may be wrong.
3. **Lesson hit rate (`hit_rate`)**: how often the actual result supported a lesson, against how often that lesson changed a ranking. Low means automatic demotion.
4. **Falsification-check history**: a lesson applied K times whose `falsifier` has never once been checked gets a review flag.

**What cannot be done is written down**: **the system cannot correct the bias in the questions a person asks.** The system knows only what it was asked. So the question distribution is kept as an indicator and shown to a person, without trying to correct it.

---
## 9. Milestones and concurrent construction

**The four agents are built at the same time.** It was changed that way on 2026-09-17 — before that the microscope came first, and for the following half-day the librarian came first.

**Milestone names are not an order.** M0–M5 are names attached to bodies of work, and there is now no order at all. The reason the names are kept fixed is unchanged — so that references such as "what M3 produces", scattered across this document, the validator's messages and four `CLAUDE.md` files, do not quietly point at something else every time the order changes.

**In place of the order column, the dependencies are written.** Building concurrently does not make dependencies disappear. What disappears is **the fiction of an order**, and what remains is what actually blocks what.

| | Content | What blocks it | Completion condition |
|---|---|---|---|
| **M0** ✔ | **Contracts first.** Card schemas + `units.json`/`units.md` + `validate.py` (all of §8's checks) + a `capabilities/` skeleton | — | **Done.** A hand-written goal → axis → synthesis → plan → approval → result round trip passes the validator (`0 failed`), and not one card in `rejected/` fails to be refused (`--expect-fail`). Why no counts are written: on 2026-09-17 hand-counted numbers disagreed in three places. What can be counted is read off the validator. |
| **M3** | **The librarian agent.** Making entry `validity` machine-readable → decomposing `kb/staging/` → the read-only MCP server (four tools, `caller_id` isolation) → producing `gaps` → conflict detection → external search and distillation → publishing `kb/exports/` | **Nothing.** It is the only agent with zero collaboration dependency (§4.3.2) | One real query returns entries plus gaps, and calling the same `(query, kb_version)` twice returns a **byte-identical** answer. No E6 in the KB. §12 is empty. |
| **M1** | **The microscope agent.** S2 → S3.0 → per-axis analysis → S4 → S5 → approval → execution. `envelope/safety.json` (**a person writes it**, §10.3 rule 4), the link between the optical-path table and `capabilities/` (check 38), the approval-gate hook | S3.0 screening is blocked on **§11-1** (the observable vocabulary). Execution is blocked on `envelope/safety.json`, which a person writes. **It is not blocked on the librarian** | A Tier 2 call with no approval is **actually blocked.** One pipeline pass on the mock backend, then one real measurement with its deviation record. **And one pass with the librarian on** — see below |
| **M2** | **The simulation agent.** The same five-stage pipeline, axes A1–A5 + A7 (applying only in a driven configuration and abstaining at equilibrium; no A6 — §4.5.3), the HOOMD backend | The same: the `produces` declaration is blocked on §11-1 | One goal → a plan that passes validation → a smoke run → convergence evidence. **One pass with the librarian on** as well |
| **M4** | **One bridge round trip.** Hashes, unit and dimensionless consistency, producibility | Producibility derives only once both sides' `capabilities/` are filled (§11-1) **and** each side has at least one card | One side's result → the other side's plan → the results compared as the same observable (S4) |
| **M5** | **The retrospective loop.** `failures.jsonl` → librarian distillation → `kb/lessons/`, the four bias indicators (§8.2) | There has to be a `failures.jsonl` from real runs | A second round trip on the same question is faster and free of contradiction (S5). That a lesson does not delete a candidate is confirmed by a check (check 31) |

**The real critical path is not a milestone but one decision.** Reading the "what blocks it" column above, §11-1 (the observable vocabulary) blocks three of the four. It is not something to build but something to settle, and only a person can answer it. This is concurrent construction's first dividend — with an order in place, that fact would have been hidden behind "it is not that turn yet".

### 9.1 What concurrent construction inverts: which path goes unwalked

**It was first satisfied on 2026-09-19.** Three cards in `microscope_agent/questions/mic-20260918-001/` — `axis_widefield_inline_a2`, `_a3` and `_a6` — each have `degraded: []` with `kb_refs` and `kb_gaps` filled, and their `caller_id`s are in `queries/log.jsonl` (9, 6 and 21 lines respectively). What counts them is check 45.

**This subsection cited a fourth card, `_a4`, all that day, and that path is in no commit in this repository.** It was not deleted but **never committed** — that axis's `caller_id` appears most often in the log at 23 lines, so the axis ran and queried and no card survived. There is precedent for uncommitted files being swept away in a shared working copy (`146276f`). **It is not that the milestone was wrong but that the evidence was unreadable**, and that state was in a file every session loads — the same class check 47 blocks for `seats.json`, one level up. The simulation manager found it. **Do not offer what you saw in the working copy as evidence: only what is committed can be read by the next person.** **That all five gaps are `absent` says what this pass is** — the service answering does not mean "everything was found" but **that the service said what is missing**, and that is why §4.3.1 has `kb_gaps`. Had the files been read directly, those five would have been recorded nowhere.

While there was an order, this document **required the degraded path as a completion condition.** The reason was sound — stand the librarian up first and the other agents are born into a world where the librarian is alive, so nobody ever walks the `degraded` branch.

**Under concurrent construction that logic stands on its head.** When four grow together, each one's counterpart is unfinished for a while. The microscope's first card is written while the librarian has not yet raised its service, and the bridge's first envelope is made when the other side has exactly one card. **The degraded path gets walked by itself without being required.** What becomes risky instead is **the normal path** — everyone gets used to reduced mode and carrying `degraded` stays normal even after the service is attached.

So the completion condition is inverted: **M1 and M2 each require one pass with the librarian on.** A card with `kb_refs` filled, `kb_gaps` filled and `degraded` **empty** has to pass the validator. A degraded pass is not required — it happens first anyway, and a condition requiring what has already happened validates nothing.

**The log holds that claim and does not confirm it — corroboration, not verification.** `caller_id` is **an argument.** The server does not see the identity behind it and has no way to confirm that the calling process is the seat that id names. So "backed by the log" is **a demand on the writing side** and not a gate, and if a round points at a line it did not create, nobody downstream knows. The bridge seat showed it from the log itself on 2026-09-19 — three different seats' ids standing **one second apart on the same observable with the same result**, and three seats do not do that. One process swept the id form, and **the log cannot say so.**

This is the same place as check 8 **deriving** producibility and check 21 deriving grades: **a verdict the writing side can choose is not a gate.** Here, though, there is nothing to derive from, so it remains a demand — until the server is made to see identity. So a green completion condition is not read as "verified". Satisfaction holds **on the assumption that the seat which wrote that card was honest.** The bridge manager raised it.

**And a measurement that had been lost comes back.** Standing the librarian up first was recorded as losing the ability to look back at "which of the E5s accumulated in M1–M2 were actually in the literature", because no pile would accumulate. Under concurrent construction, plans made before the service attaches really do pile up, so the moment `gaps` comes on that measurement can be made against that pile. **It is the only experiment that measures the service's value, and it cannot be done twice** — it cannot be measured with plans made after it is on.

### 9.2 What concurrent construction requires

With no order, §6.2.1's rules turn from advice into **requirements.** Four sessions sharing one working copy and one git index and writing at the same time is now the default state rather than the exception.

1. **The integration point is the contract, not the code.** If one agent ever waits for another agent's code, that means an order is needed, which means the contract is insufficient. What is waited on is the schemas in `contracts/` and the declarations in `capabilities/`, and both are in M0.
2. **No `git add -A`, use `git commit -- <paths>`, and the pre-commit gate** (§6.2.1, §8). On 2026-09-17 one commit held three sessions' work, and hours later the index held two sessions' files mixed. What happened even with an order happens daily under concurrent construction.
3. **There is one design seat at a time, and if two are needed, divide the owned paths first** (§6.2.1). The contract is the integration point for all four, so editing the contract in two places at once shakes all four at once.
4. **Hardware connection is the last item of every stage.** Validation is done on the mock, and the real instrument and HOOMD are attached after the pipeline passes on the mock (§4.6.5).

**The store and the service are still separate** (§4.3.0). `kb/` has existed since M0 as a store a person curates, and M3 is the work of putting a service on top of it. Entering stays the work of the person and the librarian session (`curated_by`), and what the service does automatically is **queries, `gaps` and conflict detection.**

**The E5 ceiling (§11-2) is still open.** There are two conditions and concurrent construction fills neither automatically: gap detection has to be on, and plans made in that state have to accumulate to a sample. Until then check 3 stays `UNDECIDED` — a threshold nobody has chosen is not a threshold that is satisfied.

---

### 9.3 Running two variants side by side (2026-09-18)

**On hold (evening of 2026-09-18).** The person decided **not to do microscope variant 2 yet** and removed that session and worktree. This subsection is not deleted but left on hold — branch `seat/microscope-2` still holds what it built, and deleting the record is precisely what P16 prevents.

**One consequence follows and it is the point of this hold: the constraints in this subsection exist to protect the comparison, so while there is no comparison they do not bind.** The starting gate, the shared `qid`, and the ban on ruling before the start were all **devices for making two variants fair.** Tying the remaining side to them while the other is stopped protects nothing and leaves only cost. So `microscope-1` is **simply the microscope execution seat**, does not wait for the librarian gate, and works under its own `qid`.

**What is needed to reopen**: the two variants diverging from **the same named SHA** (the body of §9.3), and settling **first** how what one side accumulated up to that point is treated in the comparison. What `microscope-1` did in the meantime becomes **a common ancestor** rather than the comparison's starting line — treat it otherwise and a tilt is already in place the moment it resumes.

The person decided to build the microscope execution **split in two.** One consults `agentic-microscope`'s `version2` and the other its `main`, and **whichever works better is chosen as final later.**

**The separation is worktrees and branches.** Two sessions using one working copy's `microscope_agent/src/` overwrite each other — this morning's accident, except this time **certain by design.** Two people editing the same file differently is the point. So `microscope-from-version2` and `microscope-from-main` run as two branches in their own worktrees. This is the **first step** of the order §11-10 set, so it is walking that order rather than jumping ahead.

**A seat is a worktree, not a session.** `microscope-1@seat.invalid` and `microscope-2@seat.invalid`, with one session using one worktree at a time. When a session is replaced, the session inheriting the branch inherits the identity — because **for the comparison to be readable off the history, a commit has to say which variant it belongs to.**
**Write down what "works better" means before starting.** This is the core of this subsection. Decide afterwards and it is not choosing but **justifying what was chosen** (§8.2's bias). And if the two variants **answer different questions the comparison does not hold** — they have to run under the same `qid`, the same goal card and the same observable.

The criteria are set by a person, but every candidate has to be **something countable from the history.** A report's persuasiveness is not a criterion:

| Candidate criterion | Status (actually counted by the microscope manager on 2026-09-18) |
|---|---|
| Passing the gate | **not a criterion but a premise.** The commit gate refuses a failing commit, so both variants necessarily read `0 failed` |
| Grade distribution of numbers | **countable** — check 21 already counts 151 and check 28 counts 124 |
| Axes that produced intervals / axes that abstained | **used as-is it creates bias.** See below |
| Whether `degraded` is honest | **not countable today** — there is no `queries/log.jsonl`, so there is nothing to compare against |
| §10.2.1 discard count | **there is nowhere to write it** — see below |

**Do not score by interval count.** §4.5.2.1 refuses silence while treating **a reasoned abstention as a correct result**, and P5 also says not to guess without grounds. But counting "more axes producing intervals is better" means **the variant that invented numbers for absent inputs wins** — a subsection built to prevent §8.2's bias turned into a scoring rule for that bias. To use it, it has to be **paired with "was the abstention justified"**, and a better form reverses the direction and **counts unjustified outputs**: numbers produced with no input, estimates naming no gap (check 39), extrapolations the source does not cover.

**The `degraded` comparison is a question of timing, not of principle** — once the librarian starts serving it becomes countable. But **cards accumulated before that cannot be verified retrospectively**: a `degraded` recorded with no log cannot later be asked whether it was true. So using this criterion requires the A/B to start after serving begins, and if that is not chosen, **this criterion is dropped from this comparison.**

**Discards have nowhere to be written — that has to be fixed first.** A discarded item by definition leaves no output, so the denominator is invisible. The numerator is weak too: as of 2026-09-18 `ruling` stands at transfer 5 · downgrade 1 · discard 0, and of those six **only two actually named an A1–A7 slot**, while §10.2.1 requires it of **every** transferred item. The place is **beside** the task file — `<agent>/tasks/NNN-rulings.md`. Not the task card itself because ownership splits: a ruling is made by the **execution seat** while the task card is the **manager's**, and the execution seat does not edit it (§6.2-2). Writing into the card makes two seats write one file. One line per item, fixed columns, transfer, downgrade and drop alike — **a transfer that named no slot closes on the same line.** The microscope manager stood it up in `93f297d`. If the two variants start before this place exists, the discards of that period are never counted.

**The two variants have to diverge from the same commit, and that commit has to have a name.** "From current main" is not a condition — main moves, so it never becomes true, and it moved ten times while this sentence was being written on 2026-09-18. **A starting condition pointing at a moving reference is not a condition.** The microscope manager nailed it to `93f297d`, and the grounds for that SHA are that all four things that have to stand before starting are under it (`ab2eb6f`, `156ba12`, `44f368b`, `93f297d`). Otherwise both sides make the same repairs separately and **the comparison measures the difference between those repairs.**

**The losing side is not deleted** (P16). The same argument as an untried configuration being disadvantaged forever, and here it is more direct — the losing variant's record is the only material holding **why it lost**, and deleting it means making the same choice again next time. The losing branch is left unmerged.

**It is a comparison of two designs** (the person's decision, 2026-09-18). Not a port versus a redesign. **Both** variants pass through §10.2.1 identically, and `main` and `version2` alike are **references** rather than things to be copied over. So the question this comparison answers is **"which reference produces a better design under our rules"**, and the question it does **not** answer is "is the existing system better than a redesign". Mix the two and it becomes unclear what the result is about, so a loss must not be read as "therefore the old system was better".

**The start is after the librarian has actually begun serving** (the same decision). That is what keeps §9.3's `degraded` criterion alive, and cards accumulated before it cannot be verified retrospectively.

**That moment has to have a name too.** "After the librarian serves" is the same trap as "from current main" — unobservable means not a condition. Written as an observable state: **`.mcp.json` registers the server** (it stood up at `2bfc229`) **and `librarian_agent/queries/log.jsonl` holds at least one record carrying a real question's `caller_id`.** The commit where that record appears is the starting SHA, and the two variants diverge there.

**No pre-start rulings while waiting — on either side.** It was first written that "reading the references and recording §10.2.1 rulings may be done now", and **the same day that permission created a directional bias.** There was only one microscope execution session, so only one side could record rulings, and that side was the `main` reference variant. Then at the starting line one variant has a rulings file and the other is empty, and **§9.3's criteria count exactly that file** — what the comparison measures becomes not the design but "was there a session during the wait". It is not even random noise; the tilt has a direction.

**The ban binds §10.2.1 rulings, not contract-compliance fixes.** Things like adjusting cards because a schema changed are neither variant's design and are neutral. **But doing it on only one branch is a tilt too** — even neutral work done on one side means the comparison measures that difference. So **shared fixes are made on `main` before the divergence point**, and the two variants diverge from the SHA after they land. The microscope manager asked and that distinction is right.

**The reason the ban is the default is that it waits for nobody and creates symmetry.** Only a person can open a session, so "open a session on the other side to match" waits on a person, while a ban stands immediately. **The ban lifts once sessions stand on both sides** — then the preparation is symmetric. Until then, "permitted but only possible on one side" is the worst state.
## 10. Out of scope

### 10.1 Non-goals

- Autonomous discovery of physical theory or mechanism. This system goes as far as **condition design and execution.**
- Automatic writing of papers or drafts.
- Real-time closed-loop control (changing conditions on the fly while measuring). Out of the initial scope — it conflicts with the gate model.
- Writing new hardware drivers. It only calls existing control paths.
- Multi-user simultaneous instrument control.
- Becoming a general-purpose workflow/orchestration engine (P10).
- Driving the instrument without human approval (D4).

### 10.2 When the four prior repositories may be consulted

The prior repositories clearly hold useful things — hardware control paths, device specifications, concrete values such as NA, axis calculation logic, and a record of what went wrong. **The problem is when to look.** Look before the design has set and its structure is inherited wholesale, and then there is no reason to have done a redesign.

**The gate is a condition, not a milestone.** With the order gone (§9), "look at M1" no longer denotes a moment. The original logic is carried over as a condition — **look after our counterpart has set.** Then the rule says the same thing whatever the order.

| What has to set first | What | Rule |
|---|---|---|
| our card schemas ✔ | comparison against `sim-exp-bridge`'s card schemas and validator | settle our schemas first, then compare **only the differences.** Do not read first and copy. |
| the device interface's four functions ✔ | **hardware control paths** — driver call style, channels, read-back | rewrap to `src/devices/`'s four functions. Wrapping a control path needs no safety limit — which is why this row does not wait on `envelope/` |
| `envelope/safety.json` (**a person writes it**) | **concrete device specification values** — NA, magnification, pixel size, power limits | **every figure must pass §10.3.** This row waits on `envelope/` because a specification figure not placed beside a limit gets used as a limit |
| the shape of the `kb/staging/` tables ✔ | **the initial contents of the device registry and the valid optical-path table** (placed in `kb/staging/` per §4.3.2) — per-device control channels, automatability, read-back availability, and the selector combinations where light actually reaches the detector | **extract** from the prior repository. Do not fill by guess. An extracted value is also capped at grade E3 per §10.3 rule 1, and is promoted to E1 once confirmed on the real instrument. **Safety limits are not transferable per §10.3 rule 4** — a person writes them directly. |
| the axis decomposition A1–A7 ✔ (§4.5.3) | **microscope axis calculation logic** — SNR, photodamage, resolution, the escape condition | rearrange onto our axis decomposition (§4.5.3). Where an already-validated expression exists, such as A7's escape condition, use it |
| the axis decomposition A1–A5, A7 ✔ (§4.5.3) | **simulation axis calculation logic** — stability, sampling, convergence judgement | consult the expressions and criteria but rearrange onto our axis decomposition. |
| the entry schema and `kb_query`'s argument shape | comparison of the two KB structures | structure only. Entries transfer individually after source verification (§10.3). |
| our structure ✔ (§3, §4, §6) | **the architecture itself** — module decomposition, agent boundaries, pipeline stages | **read the branch difference first**: what `agentic-microscope`'s `main` → `version2` changed. That is "what did not work on the first attempt", and it is the reading that gains the most without inheriting the structure. Only then look at the structure itself, and only what passes §10.2.1's classification crosses |
| open now | **sample and consumable lots / vendor part numbers** — beads, coverslips, media | **take the numbers only. Do not take the values.** Figures such as diameter and density are `prior_run:` E3 per §10.3 rule 1, but that is **an E3 about their beads**, and applying it here puts an E5 assumption of "the same stock" on top and it returns to E5. A lot number is different — **a person can look at the bottle and confirm it is the same**, and once confirmed it is `spec:<lot>` E3. So what is taken is only **an identifier a person can verify** |
| failure cases from operating round trips | what did not work | consult as a failure list only. Entering it in `kb/lessons/` requires §8.2's mandatory fields (evidence id, `n`, `falsifier`) |

✔ marks what has already set, and that row is open. On 2026-09-17 the device registry, the optical-path table and the objective table were opened on those grounds (§11.1), and the same day the person opened `agentic-microscope` with the condition **"nothing is transplanted as-is, and anything over-claimed is downgraded or deleted."** §10.2.1 is that condition moved into a mechanically checkable form.

**§10.3 is a transfer procedure, not a prohibition.** A row being open does not mean "you may look" but "bring it across by passing it through §10.3" — an E3 grade ceiling, vendor values cited to their original source, no transfer of figures embedded in prose, and safety limits not transferable.

#### 10.2.1 Everything that crosses is ruled one of three

A row being open means "you may look", not "you may take". **Every item crossing from a prior repository is ruled one of three before it is used.**

- **Transfer** — an expression or criterion with a place in our A1–A7 (§4.5.3). It has to be **rearranged** into that place, and any figures attached pass §10.3.
- **Downgrade** — useful, but over-confident on their side. An assertion with no grounds becomes **E5** with a falsification condition attached, a calibration constant with no `run_id` becomes **E3 at most**, and a model-generated value is **E6 and therefore enters nothing** (P2).
- **Discard** — no place in A1–A7, existing only in prose, or **being a safety limit** (§10.3 rule 4: not transferable).

**One discriminator makes it checkable: a transferred item names the A1–A7 place it went into and the §10.3 rule number it passed.** Unable to name a place, it is discarded — that is the mechanical form of "delete what does not help".

   **"A place" is not only an axis** (corrected 2026-09-18). The first use of this discriminator wrote only A1–A7, and that **discards legitimate transfers for being unable to name a place** — a hardware control path goes not into an axis but into `src/devices/`'s four functions, a preflight check into O1, a value into a KB entry, a shape into a contract field. The discriminator's intent is not "does it go into an axis" but **"is there a place for it in something we have already designed."** So the places that can be named are the A1–A7 axes, the orchestrator's four functions, O1 preflight, a contract field, and a KB entry, and naming a place not on this list requires **designing that place first** — which means it is design and not transfer, and then it goes to §11. The librarian manager raised it.

And this rule **structurally guarantees "nothing is transplanted as-is"**: what is not re-placed into our decomposition cannot cross. Transplanting is moving without asking about a place, and demanding a place makes that impossible.

**A case already caught is the grounds.** The prior project's `20.078x` — a nominal magnification wearing a value back-calculated from a calibration, and precisely "over-claimed". §5.3's nominal-notation rule stopped it (a nominal designation is a string, not a number), and the device registry recorded the reason. Without the classification, that value would have come in looking like an E2.

**The classification stands first and then it opens.** Reverse the order and there is a span opened with no rule, and what came in during that span is never revisited by anybody.

### 10.3 Rules for transferring figures

Numbers from a prior repository **do not enter code or `envelope/` directly.** They all pass through the librarian and become KB entries (P14). Five rules:

1. **A transferred value's grade ceiling is E3.** E1 means "a value this system measured at these conditions" and requires a `run_id` (§5.3). A prior repository's measurement has no `run_id` in this system, and its calibration state then cannot be reproduced here. So **a prior measurement also comes in as E3.** Measured again it is promoted to E1 and the old entry is linked with `supersedes`.
2. **A vendor specification goes to its original source.** Values such as NA, pixel size and power limits are recorded **with the instrument documentation as the source**, not the prior repository. The prior repository is an index telling you where to look, not a source.
3. **Figures in prose are not transferred.** Only values in a machine-readable position with a source attached cross over (P2, P3).
4. **Safety limits are not transferable.** `envelope/safety.*` is policy and not knowledge (§4.3.2), and per P0 rule 7 a person writes it directly **after confirming physically outside the system.** Limit values written in a prior repository are reference material and not grounds.

    **But "after confirming physically" was uncheckable until 2026-09-19 — the file does not distinguish a confirmed limit from a transcribed one.** Confirm three of twelve on the instrument and transcribe nine from another document and the file looks the same. **When a rule kept and a rule broken have the same shape, that rule is a hope and not a requirement.** And P0 entrusts safety to deterministic code, and the very file that code reads does not carry this. The librarian manager raised it while opening and classifying `agentic-microscope/SAFETY.md` on the person's instruction — **what it asked for was a tightening, not a relaxation.**

    **So a confirmation record is required per limit.** For a physical confirmation, **who, when and how**; otherwise, **the fact that it was transcribed without confirmation, and from where.** **Transcription is not forbidden** — forbid it and all twelve have to be confirmed at once and nobody can start the file. **It only has to be distinguishable.** Distinguished, a later check can say *"an unconfirmed limit is parameterising an irreversible action"* (§2.1 rule 3's shape), and today it cannot.

    **A file-level `written_by` is exactly that batch stamp.** One signature covers twelve limits and says which are confirmed of none of them. Librarian rule 10 already says the same — *"a confirmation mark stamped in batch is not a confirmation. Stamp the row you re-read, not the batch."* If that sentence is true of a KB entry, it is more true of **the file bearing the most load.**

    **This is not a grade.** It does not conflict with what was settled about target accuracy the same day (§5.3): a ceiling remains a decision about **what is permitted**, with no source and no grade. What is newly required is not that decision but **the event of confirming** — who did what and when is not a claim but something that happened, and what happened is recorded. `limit`'s `{value, unit}` is policy, and the confirmation record is an event record beside it.

    **Resource ceilings leave `safety.json` — P0 binds instruments, not budgets (2026-09-20, settled by the person).** The simulation tree's ceilings are `wall_clock_max`, `storage_max` and `smoke_budget`, and **all three are resources.** P0's order is people → instruments → samples → data, and a wall-clock ceiling protects none of them — **it protects a schedule.** Yet living in that file, Tier 3, physical confirmation and the model ban **all attach to a disk quota.**

    **The point is that the grade of harm differs**: get the laser ceiling wrong and you lose an eye; get the wall clock wrong and you lose a night. **Putting the same lock on the same door was never decided**, and the reason `safety.json` exists in the simulation tree is that it was the only place a ceiling could live.

    **So it splits into `simulation_agent/envelope/budget.json`.** There is no `safety.json` in that tree. Splitting does not remove the gate — A5 and the operator still read from one place, and **a run that cannot determine whether it is inside budget still stops** (P0's stop-on-ambiguity binds resources too). What goes away is **the physical-confirmation requirement and Tier 3**, both of which were meaningless about a disk quota.

    **And that amends P0 rule 7's wording.** *"After a person confirms physically outside the system"* **was written with instruments in mind** — putting a power meter in a beam and knowing a cluster's job limit are different acts, and demanding "physical confirmation" of the latter makes a requirement with no way to satisfy it. **Rule 7 now binds `safety.*` only, and what `budget.*` needs is only that somebody who knows that machine chose it.** The person was asked and settled it — the question was raised by architecture and **the simulation manager's per-agent split is what made the question visible.**

    **And this line is currently invisible to check 55 — it gets looked at when this is fixed.** 55 reads only the **first token** of each line in the §7 tree (`tok = line.strip().split()[0]`), so `budget.json` and `snapshot.json` listed after `envelope/` are not caught by name. **`safety.json` was not being caught either.** There are nine such lines in §7, four of them placeholders such as `questions/<qid>/` that 55 skips **deliberately**, but **the two `envelope/` lines are real declarations and are not on 55's list of deliberate non-catches — an undocumented blind spot.** The side to fix is §7: real declarations are written **one file per line** so 55 can see them. The reason not to change it now is ordering — the moment they become visible the gate refuses them for not being in `ALLOWED_PATHS`. Once `ALLOWED_PATHS` lands, the format changes then.

    **Implementation is manager-simulation's**: split `simulation_limits` out of the schema into `envelope_budget.schema.json`, plus `ALLOWED_PATHS` and the paths in `axis_a5_budget.py`, `operator.py` and `plan_card.py`. **§7 was fixed above, so `ALLOWED_PATHS` goes first** (§7.1 — the side whose absence a check tolerates goes first).

    **`carried_over` is a route for the laser ceiling too — except the constraint attaches to use rather than to writing (2026-09-19).** The microscope manager, seeing that *"a field present and marked unconfirmed is better than no field and nothing writable"*, raised it as not being its call. That is right — and those two are not the only options.

    **Transcription is legal for every limit.** Forbid it and all twelve have to be confirmed at once and nobody can start the file. But a compute budget and a laser power **differ in what being wrong costs** — the first loses time and the second loses an eye or an objective. **Handle that difference as what may be written and the file never gets made; handle it as what may be run and you get both.**

    **So the rule is this: an unconfirmed limit cannot parameterise an irreversible action.** It does for **the confirmation event** exactly what §2.1 rule 3 does for grades — the same place as E4/E5 being unable to enter an irreversible action, and for the same reason. So a file writing the laser ceiling as `carried_over` **may exist**, and under that ceiling **no irreversible action runs.** The moment a person confirms, both open. It is the only arrangement that keeps what P0 demands without blocking the file from being started.

    **Assigned as check 57 — manager-simulation.** The schema's `confirmation` description already foretells this check: *"a later check can say an unconfirmed limit is parameterising an irreversible action, which today it cannot."* **A foretelling written with no implementation is the shape counted seven times today** — written down and doing nothing. The seat assigned is simulation not because that tree is the one with no irreversible actions but **because that seat just stood the schema up and the microscope seat is empty.** The check looks at both trees.

    **The shape went in as mandatory fields on `$defs/limit` in `contracts/schemas/envelope_safety.schema.json` — `cd7475c`, manager-librarian.** This paragraph said "goes in" until 2026-09-20, and **when something already done is written as open, the next person picks it up again** — a seat in fact started to and checked and raised it. Making it mandatory is possible **because there is not one `envelope/safety.json` yet.** The migration is zero, and the first safety file this repository receives has that shape from the start. The same window was used once that day on `calibration:`'s `valid_until` — **it is cheap before there are consumers, and that window is usually visible only after it has closed.**

Rule 1 looks inconvenient and it is the only way the grade system means anything. **Put "measured somewhere" and "measured here" at the same grade and E1 means nothing.**

---
## 11. Open questions (to be settled in a later session)

1. ~~**The observable vocabulary**~~ → **Settled 2026-09-19: no list is made.** The person decided — the vocabulary **stays addable and changeable at any time.** That is what lets an unanticipated experiment be taken. `observables.json` was already that shape with `status: rules_fixed_content_open`, and this decision turns it **from open into a conclusion.** The number is left empty — several places point at §11-1.

   **So this item no longer blocks anything.** S3.0 screens **over what is registered**, and an unregistered name is not a refusal but **"register it first"** (check 40). It is not a block but **an ordering**: a new observable stands in the vocabulary first, and then a plan uses that name.

   **Adding has to be cheap, and changing must not be.** Adding is a new id and makes nothing mean something else. Changing is different — since a card **carries only the name and reads the definition from the registry** (§5.1), editing an entry **retroactively changes the meaning of every card that already used that name.** Without a trace. This has the same shape as the problem `kb_version` already solved one layer down.

   **So the fields split in two:**

   | Fields that change meaning | `definition` · `estimator` · `window_parameter` |
   |---|---|
   | **No in-place edits.** If one must be fixed, stand up **a new id with `supersedes`** and leave the old entry readable | |

   | Fields that do not change meaning | `units` (adding a permitted unit) · `producible_by` · `comparable` · `note` |
   |---|---|
   | In-place edits are fine. What past cards meant does not change | |

   `estimator` is on the meaning-changing side for the reason this subsection originally wrote — **two sides agreeing on a word and not on how the number is extracted is worse than disagreeing openly.** Change an estimator quietly and old and new values land in the same column.

2. **The E5 ceiling**: how many estimates are allowed in one plan? Zero and nothing can be done; unlimited and the grade system is meaningless. **It is settled only after both conditions hold**: ① gap detection is on (the librarian service), and ② plans made in that state have accumulated into a sample. Concurrent construction advances neither — when the librarian comes on is not fixed by an order, so ①'s moment is itself open (§9). Until then check 3 is `UNDECIDED`.

    **The unit was settled on 2026-09-19: the number of distinct `rationale_id`s. Not the raw E5 count.** The threshold is still undecided and waits on condition ②, but **what to count does not have to wait for a sample** — that is settled by argument and not by data. And without settling the unit first, once the sample accumulates you get **a sample of the wrong thing counted.**

    **A raw count counts the length of the derivation chain, not the guessing.** The simulation manager counted three plans and raised it, and architecture confirmed:

    | Plan | E5 | `assumed:` | `computed:` | distinct rationales |
    |---|---|---|---|---|
    | `mic-20260917-001` | 7 | 5 | 2 | **5** |
    | `mic-20260917-002` | 5 | 4 | 1 | **4** |
    | `sim-20260917-001` | 17 | 8 | 9 | **7** |

    **Every `computed:` E5 is inherited — not one is E5 under its own power.** `diffusivity` is E5 because `bead_diameter` is, `tau_d` because those two are, `integration_timestep_max` because `tau_d` is. That is §5.8 working exactly as written, and not a failure. So 17 against 7 looks like 2.4×, and **by rationale it is 7 against 5, or 1.4×.** The simulation side is higher not because it guesses more but **because its pipeline derives more.**

    **The decisive point is the incentive.** Put the ceiling on the raw count and **a plan with a long chain is punished**, and the way to shorten the chain is to omit `formula` and `inputs` — the very fields check 17 reads. **A ceiling that rewards hiding a derivation is inverted.** It is the same class as a gate that refuses correct work getting bypassed, and this side is worse: a bypass leaves a trace and **a hidden derivation leaves a green card.**

    **Why the count of `assumed:` numbers was not chosen** (counting separately when one rationale covers several numbers) **is that those numbers are wrong together.** If one rationale is wrong, the three numbers it covers are wrong simultaneously, so it is one risk and not three independent ones. Counting them separately inflates correlated risk as if it were independent. **But one rationale covering many numbers is itself a concentration**, and that is a separate concern rather than a ceiling — if it becomes necessary, it becomes a check then.

    **And a condition being satisfied and a threshold being chosen are different things.** Even once ② holds, the number **does not follow automatically** — a sample gives grounds for choosing and does not do the choosing, and the chooser is a person. §11-17 showed the same distinction the same day: two conditions for reverting were met, it was asked, and **the answer was the same.** The simulation manager pointed it out.

    **And condition ② does not move along this axis.** Not one plan has yet been made with the librarian on, and simulation's revision 2 becomes the first. E5 **will not fall** then — the diameter moves from `assumed:` to `operator_recall:` and both are E5. The sample accumulates and the grades stay, and what moves is **the rationale count.** The unit has to change for that sample to say anything.

3. **Fixing the S3 axis list**: §4.5.3's seven axes are a proposal. Adding a new axis requires passing the criterion "can it produce an interval without knowing another's variables" (§4.5.3).
4. **Module decomposition and the backend interface**: can the four functions `preflight/apply/read/abort` cover both HOOMD-blue calls and control of nine kinds of device? If not, what is missing. Actually wrapping them at M1 gives the answer.
5. ~~**Fixing the librarian's MCP tool list**~~ → **Settled 2026-09-17, moved into §4.3.1.** Three were not enough: a dimensionless group is looked up by symbol, so `kb_group` is added as a fourth. A condition range is **a map of intervals**, and for it to be comparable the entry side needs a machine-readable `validity` of the same shape — which is why M3's first task became the schema rather than the server. The number is left empty. Other subsections point at §11-5, and pulling the numbers up would make those references quietly point at something else. **In this repository a section number is an identifier and not decoration** — `capabilities/*.json` cites §11-1, a check message cites §6.2.1, and `seats.json` cites §10.3 rule 4. So there is one rule: **the number published first keeps its meaning.** On 2026-09-18, inserting the A/B subsection, I made two §9.2s and the simulation manager caught it — nobody had miscited yet, but from that moment everybody writing "§9.2" meant one of two and the reader could not tell which. The new subsection was pushed to §9.3. **Duplicate numbers are checkable** — count the headings in one file — and nothing checks it yet.
6. **The propagation range of reduced mode**: is the `degraded` marking used only inside the system, or carried into external reporting (figures, papers)?
7. **Fixtures that test the gate itself — a check that is not about cards has no evidence.** What `--expect-fail contracts/examples/rejected` holds is **cards**, so a check that looks at something other than a card has no fixture: entry grades (check 43), KB index freshness (check 25), table agreement (check 38), seat attribution (check 41), and merge handling (§6.2.1). On 2026-09-17 check 43 was tested with eight cases and a defect was caught in the process, and **that proof survives only in a commit message.** **It bit for the first time on something real on 2026-09-18**: migrating the `caller_id` form, only `bad_sibling_b`'s field was fixed and **the sibling reference embedded in its body** was left, so that card stopped failing, and `24/24` became `23/24` and it was caught. Uncaught, that fixture would have **looked fine while no longer testing sibling detection.** Card fixtures are re-confirmed at every commit, and the next time someone disables check 43 nothing will ring — a check nobody has seen fail is a check nobody has tested. The direction is settled: non-card fixtures go beside the card fixtures and `--expect-fail` sweeps both. What has to be decided is **the shape** — whether to export a small repository per check, or whether one input file per check will do. Three of the five above (25, 41, merges) **need git history** and are not covered by a single file. And if a fixture is a repository, the cost of making one becomes the cost of adding a check, so it has to be cheap for checks to grow.

    **Settled 2026-09-20: there are two shapes, and what a check reads chooses between them. And it is cheap because only four are on the expensive side.** Counting showed **the checks that read git history are 26, 35, 41 and 46 — four — and the other 55 read files only.** (The list this item gave on 2026-09-17 is stale — 25 does not read history now, and 26 and 46 do.)

    - **Checks that read files only → `rejected/` as it stands.** It is only widening an already-running mechanism to non-card inputs, and group folders already hold defects that take two files to express. **The marginal cost is effectively zero, so checks grow.**
    - **The four that read history → a script that builds a repository rather than storing one.** Keeping four repositories as fixtures is expensive, and stamping a few commits after `git init` takes seconds — that is how architecture reproduced the pathspec commit and the same-file misattribution on 2026-09-19. **What is expensive is not making a repository but keeping one.**

    **The trigger arrived for real.** 018 demanded a mutation test for check 61, and the librarian manager ran six shapes in a scratch tree and **left the results only in a docstring** — there was nowhere to put them. And today's tree actually burns **only two** of those six. The moment the simulation envelope catches up, the rest **test nothing.** In 018's own words: **a property waiting on a real rack passes vacuously on a rackless day.** The checks the group fixtures currently aim at are **four** (08, 50, 51, 52) and the checks that run are forty-nine.
    **The place is `contracts/` and a shared surface of four managers, so one seat does not settle it alone** — which is why the librarian manager raised facts without a judgement, and that was the right route. With the shape settled, **the implementation is assigned**: the file-side extension to manager-librarian (61 is its first consumer), and the history-side script to manager-bridge (35 and 41 are the checks that seat has touched most).

**Partially settled 2026-09-17 — the unit of a card fixture widens from a file to a group.** Today `--expect-fail` demands a failure **per file** in the folder, so **a defect that takes two files to express** cannot be added: a ledger disagreeing with an envelope fails only the ledger and the envelope is caught as `NOT REJECTED`, and a case where two refusal cards in one thread repeat the same `(reason_code, parameter)` with the ledger not recording it cannot even be added, because the cards themselves are fine. So several of check 8's ledger rules stand untested. **When testability is dictating the shape of the contract, it is inverted.** One level of `rejected/<group>/` is permitted, and for a folder, one FAIL anywhere inside the group counts as refused. Flat files stay per-file, and check 13's depth ceiling and §7's declaration obligation hold.

**One condition attaches: a group states which check it is a fixture for.** Leave "one FAIL anywhere passes" as it is and a group **counts on a failure from an unrelated check** and stays green even after the intended defect is gone — a fixture no longer testing what it says it tests, which is exactly what this folder's rule ("a card that stopped failing means a check stopped") exists to prevent. At file granularity each fixture was nailed to its place and this problem did not arise, and widening the unit pulls the nail. So a group carries its expected check number, and counting requires **a FAIL from that check.** Flat files would be better with the same, and that is separate work.

17. ~~**Should manager seats get worktrees**~~ → **Settled 2026-09-19: no. One shared working copy.** The person decided, after seeing both sides.

    **So this defect remains, and it was chosen rather than overlooked.** `git commit -- <paths>` keeps carrying other people's hunks, no check catches it, and check 41's attribution stays wrong by that much. The only thing that closes it is §6.2.1's one habit — **before committing, run `git diff -- <that file>` and see that every hunk is yours.** That the habit did not survive an hour today is written there too. So this repository's commit attribution is **unreliable for shared files under `contracts/`**, and where who wrote what matters, one reads the records in §8.1 and §6.2.1 rather than the commits.

    **The conditions for reversing are written too**: if misattribution accumulates again in the same file, or if manager seats exceed four, the cost calculation changes. It is raised again then.

    **2026-09-20: both conditions are met.** There are **five** manager seats (manager-microscope, manager-simulation, manager-librarian, manager-librarian-2, manager-bridge), and misattribution happened **again in the same file** — `contracts/validate.py`, `779269b`. And that day **the mirror surfaced too** (§6.2.1): uncommitted edits being silently erased, and the two habits pushing against each other. **A worktree is the only thing that closes both at once** — if another's unfinished work is invisible, it can be neither carried nor erased. **The cost is still paid by the person, so the judgement is the person's, and architecture only raises that the conditions are met.**

    **It was raised, and the person answered that it stays as it is (2026-09-20).** One working copy, one branch `main`, and no trace of a worktree were confirmed. **So a condition being met and a decision changing are different things, and this item keeps that distinction on the record** — the condition was "ask again", not "reverse it", it was asked, and the answer was the same.

    **So the two defects remain, and remaining was chosen.** My commit carrying another's hunks, my edit being silently erased, and **the two habits that close them pushing against each other** (§6.2.1). Only two habits close them and neither closes the window between checking and committing — today that window was three minutes. **What reopens this item next time is a person, not a condition.** The conditions are already met, so they are not counted further. The original item is kept below.

    **And there is a third habit that does not work on this file alone — manager-librarian-2 pointed it out on 2026-09-20.** What `librarian-3`'s `unguarded` records, **claiming paths by message before writing**, actually worked at the execution seats. It worked because that surface **decomposes into work units** — one card, one axis, one check. `contracts/validate.py` does not decompose: five seats **append checks to the same file.** "I have this file" is a sentence that blocks four, so nobody says it, and so a practice that works elsewhere **structurally does not work here.** `seats.json`'s `shared_in_contracts` already wrote *"a `paths` entry starting at `contracts/` looks like a division and is not one"*, and on 2026-09-20 that sentence got a measurement — since 2026-09-19 00:00, that one file has **49 commits / 5 seats / about 30 hours.** **Three habits still do not close it, because the third is a sentence this surface cannot use.**

17-a. **(the original item, for the record)** Since introducing and reverting it on 2026-09-18 was **the person's decision** (§6.2.1), reverting the revert is the person's too. The `.mcp.json` absolute-path problem that was breaking isolation then has since been solved, so **the technical obstacle of that time is gone.**

    **What is at stake.** Four managers share one working copy, `contracts/validate.py` is **the repository's highest-traffic file** written by all four, and there is no isolation. `git commit -- <paths>` carries another's hunks under your identity, and **no check catches it** (§6.2.1). Closing it by habit was attempted and **failed in both directions within an hour.**

    **The cost is paid by the person**: manager sessions have to be relaunched in their own worktrees, and integration passes through §6.2.1's merge. So this is not a design judgement but **a judgement about operating cost**, and not architecture's to make.
16. **There are two places an interval lives in an axis card — what compares them.** `inequalities[].interval` and `constraints[]` (the latter simply an array of `$ref: interval`), the same shape in two places. It may be a new row for §11-11 with an empty third column, and it may not — because the two may mean **different things** (one a per-inequality verdict, one the axis's output). The microscope manager raised it on 2026-09-19.

    **Count before deciding.** §11-12 is today's lesson — before counting how many the `kind` argument would have fixed, that item's framing was plausible, and counting gave zero. So the question is not "should they merge" but **"have the two ever appeared simultaneously on the same parameter in the same card, and were the values equal when they did"**. If the answer is "never", the two places are different things and not a row for the table. The A4 and A6 revision passes through this place, so it gets counted then.
15. **An envelope snapshot has nowhere to test failure.** What `contracts/examples/rejected/` does for cards, nothing does for snapshots. It surfaced when check 26 was implemented on 2026-09-19 — the missing-commit and missing-table branches actually fired during development, while **the branch where the entry text disagrees with the committed bytes has never fired.** Forcing it requires touching a real envelope, which is execution-seat property and blocked from a manager seat — **correctly blocked.** So this is not a permission problem but **a problem of having nowhere.**

    The value of this class is already written in §8: if a fixture stops failing, the check has stopped. Check 26 currently has **only half that guarantee.** What has to be decided is where the place goes — whether to add a snapshot class to `contracts/examples/rejected/`, or whether envelope fixtures get their own place. The latter adds a folder to §7 and check 13 has to know about it. The microscope manager named it rather than filling it.

    **Closed on 2026-09-19: what was needed was not permission to touch a real envelope but the fixture's shape.** The bridge manager produced it — **a snapshot that is a real export and not the one of the tree you sit in**, placed in `contracts/examples/rejected/check26_…/`. Take a byte-exact real export and have its `built_from_commit` name a **different** commit this repository actually has. `*_agent/envelope/` is untouched and no seat boundary is crossed — the fixture lives in `contracts/`, which is the manager's. **And the reason this works is the reason check 26's design is right**: it compares against git rather than the working tree, so a fixture can be **an honest export from another moment.**

    **The dividing line is the one check 50's fixture drew.** An absent snapshot tests the wrong branch — "there is no snapshot" is not the divergence §4.3.2 describes. The divergence is **a real export that belongs to another commit.** Implementation is manager-librarian's (check 26 is theirs) and the folder is manager-bridge's. The two of you decide.

14. ~~**Target accuracy**~~ → **Settled 2026-09-19: one decade.** The person decided — placing the value within a factor of ten is enough. **Both goal cards already carried `target_decade_resolution = 1 count`, so the number does not move**: what the settlement changed is not the value but **the source**, and `assumed:a_target` E5 ceases to be how a person's target is recorded (§5.3, §5.3.1). Four bounds are unblocked. The original item is kept below.

14-a. **(the original item, for the record)** The microscope manager raised it on 2026-09-19: four bounds hang on this one thing, and **it does not arrive when the sample arrives next week** — because it is a person's target and not a fact about the sample. So it is cheaper to have **before** the sample in the ordering. Have it, and the axes unblock all at once when the lot number arrives; lack it, and the sample arrives and things stand in the same place.

    **Since explore is the default (P15), this may be a decade rather than a decimal** — not whether it is 10% or 30% but "is it the 10% decade or the 100% decade" is usually enough. Ask for a precise number and the person invents a precision that does not exist, and that makes one more E5 (§5.8).

13. **The bead lot number — `thr-tracer-diffusivity-001` is stopped here. Only a person can answer, and it is a number, not a ruling.** The two sides of the first real round **are planning different samples**: the microscope side has `tracer_diameter` 5 µm (`operator_recall:kyuhwan_20260918`) and the plan being carried has `bead_diameter` 2 µm (`assumed:a_sample`). **Both are E5 and neither beats the other** — there is no ranking between a value stated from memory and one assumed.

    **Where the difference leaves the tie is this item's grounds.** The diffusion coefficients are 2.5× apart, inside explore's tie band (§5.8, under 10× is a tie), while `tau_d` is **15.6×** apart — because it goes as d³. And `tau_d` sets the record length. So the two sides would **run experiments sixteen times apart and call it one comparison.** What was not a tie was hiding behind what was, and the bridge manager measured it from the disk and raised it.

    **What ends it is the bead lot.** With a lot number both sides become `spec:<lot>` E3 and the estimates disappear. So what the person is asked is **not** "5 µm or 2 µm" — that is a ruling, and a ruling between two E5s only makes one more E5. What is asked is **the lot number.** `microscope execution` recorded that it has been due to receive that lot from the operator for several days, and that is now **the precondition for this repository's first real round.**

    **The reason this item is here at all is a contract requirement.** A thread's `open_question` has to name where the person's answer is recorded, and §11 is that place. While the item did not exist, that field ended in "not yet recorded in §11" — **a declaration one end of which nobody reads**, the shape that bit three times today. `bridge-85` was blocked on this.
    **Updated the evening of 2026-09-19: the product was identified, and the two sides align now. Only the lot remains.** The person found the vendor page and named it **Abvigen `AFR-0500-COOH` — Red PS Fluorescent Particles, 5 µm-COOH**, and the microscope manager confirmed the same product key (`abvigen-red-5um-cooh`) **on disk** in `agentic-microscope`'s `data/particles.yaml`. **The reason that is a second trace rather than a re-confirmation of memory is that the file was written then** — not from today's memory.

    **So the symmetry of the two values broke.** 5 µm now has one claim (`operator_recall:`) with **one contemporaneous document and one vendor catalogue** attached, and 2 µm is still `assumed:a_sample` — **a placeholder.** Exactly as §5.3 wrote today: **a blank is not objecting.** So **the simulation side aligns to 5 µm without waiting for the lot.** The grade stays E5 and the gap stays open — the uncertainty is not removed but **shared.** What alignment removes is not uncertainty but **the harm §11-13 records**, namely calling experiments sixteen times apart one comparison.

    **The alignment is decided and not yet executed — and cannot be executed now.** The paragraph above is the record of a decision, and the cards are still 2 µm: `goal.json`, `plan_simulation_…`, `synthesis.json` and axes a1, a3, a4 all carry `bead_diameter 2 um assumed:a_sample E5`. **What blocks it is the same pin** — `r1_hashes.json` froze that plan as revision 1, and fixing the diameter moves `card_sha` and check 8 fails **exactly** as it does when moving the target. So **the diameter alignment and the target migration are not two tasks waiting together but one commit of revision 2.** Blocked by one pin and unblocked by one revision.

    **And this is not a field edit.** `tau_d = 20 s` is `computed:diffusive_time` from 2 µm and τ goes as d³, so matching the diameter makes **20 s become about 313 s** and every interval resting on record length moves with it. The 15.6× §11-13 records arrives **as arithmetic and not as a disagreement.** The bridge manager read the cards and raised it — architecture's handover list had written this so that it read as "alignment complete".

    **Retracted the night of 2026-09-19: what is on the bench is not that product (`8646426`).** The two paragraphs above are the record from while the identification stood, and the person withdrew it. Two entries force it — `bottle_label_states_no_product` (an operator looked at the bottle and the label does not state the product identity) and `particles_show_on_the_green_605_path` (`calibration:` E2). The second is decisive: **particles emitting at 680 nm are not visible on the 605 band.** So it is not that the catalogue's 620/680 is wrong about these particles but **that these particles are not that catalogue item.**

    **The alignment survives, for a different reason than the one written above.** 5 µm **was never derived from the product** — it is `operator_recall:kyuhwan_20260918` and was so before the catalogue was found. The catalogue was the **second** trace, and with it gone the first remains. The asymmetry argument holds too: **a weak claim beats a placeholder that claims nothing** never rested on the catalogue. **What thinned is not the value but its support.**

    **And one thing inverts: the exit closed.** The paragraph above wrote *"reading the label next week makes that layer E3"*, and **the label has already been read** — on 2026-09-19, and it did not state a product. So **the doubt becomes permanent rather than pending**: the one cheap means that could have resolved it has already happened and did not. **Architecture wrote that exit into both §11-13 and the handover message, and both were already false at that moment.** The simulation manager caught it.

    **The same night, the retraction was retracted.** The person ruled again: **the bottle is that product and the vendor page is wrong.** The librarian manager raised it first and **the person confirmed directly at the architecture seat** — *"confirmed the vendor page is wrong."* 016 holds that ruling. The occasion was a prior repository's four-band measurement, but **what was decisive was not the measurement but the asymmetry** — the Abvigen page already has **two unrelated errors** recorded against it, so *"the datasheet is wrong"* is **a much cheaper explanation** than *"the bottle is not that product"*, and **the silent label that was 015's evidence cannot distinguish the two.** Silence explains both hypotheses equally well.

    **The restoration is partial. And that split fills exactly the individual / type / joining-claim trio settled yesterday.**

    | | |
    |---|---|
    | Identity | **restored, E5.** The label is still silent, and what the two measurements say is *"it behaves like a Cy3-family dye"*, not *"it is this catalogue number"* |
    | Material and diameter | **restored, E5.** The type specification is E3, and **that it applies to this bottle** is E5 |
    | Emission and excitation | **not restored.** Falsified, with two independent observations giving the same answer |

    **So the paragraph above saying "the source closed" is wrong.** It did not close — but **the vendor page is still not a source, and the reason changed**: not because there is no identification but **because that page itself was ruled untrustworthy.**

    **And the two grounds for the diameter now support each other.** The person's measured 5 µm (E2) and the catalogue's 5 µm (type, E3) **state the same value independently.** Unlike a few hours earlier, when the measurement was a substitute for a closed source, the two are now each other's corroboration — and **the measurement side is still higher, so the diameter ruling does not change.**

    **The night of 2026-09-19 a measurement arrived and this item's diameter side closes.** The person **measured it directly**: diameter 5 µm, **CV within 2%.** That is `calibration:` **E2**, and **higher than the `spec:<lot>` E3 a lot would have given.** So **the lot is no longer needed for the diameter** — what this item was asking a person was answered by measurement, and answered with something better than what was asked.

    **And the whole two-E5 symmetry problem disappears.** §11-13 was opened because *"both are E5 and neither beats the other"*, and now one side is **a measurement** and the other is still an `assumed:a_sample` placeholder. The alignment argument rises from "a weak claim beats a blank" to **"a measurement beats a blank"** — the same conclusion with a far shorter argument.

    **That a point value became a distribution is also value.** CV ≤ 2% is a dimensionless bound with only an upper limit, and monodispersity settles one side below. **Since `D = k_BT/3πηd`, `D ∝ 1/d`, and with an exponent of −1 the relative spread carries over 1:1** — from `ln D = const − ln d`, `δD/D = −δd/d`. So **the CV of the diffusion coefficient across individuals equals the CV of the diameter**, whatever it is. Either way it is far inside explore's tie band, so the conclusion is the same.

    **On 2026-09-19 this paragraph said "about twice the diameter spread (D ∝ 1/d), so 4%", and it was wrong.** Twice would require `1/d²`. The 4% is the number you get reading "within 2%" as the **full width** of ±2%, and that is neither what CV means nor what `1/d` does. The simulation manager confirmed it both analytically and numerically and raised it — drawing 400,000 at CV 2% gave 2.00% in and 2.00% out.

    **There is a reason the number is not restated.** Per issue 019, `tracer_diameter_cv_upper_bound` is `value: 2, unit: "1"` — dimensionless 2, that is 200% — with the percentage in a note. **It is a value/unit pair that reads wrongly without the note**, so copying any number by hand now cements the very thing 019 is removing. **The statement that the ratio carries over 1:1 does not depend on the value and is therefore stronger than the number.** **Nobody is currently considering polydispersity and the reason it need not be considered was written nowhere.** Now it is.

    **The lot does not disappear; it narrows.** `agentic-microscope` wrote *"size CV and dye loading vary lot to lot"*, and **size CV was measured directly and so is released from the lot**, leaving **dye loading → `tracer_brightness`.** That has not been measured, is lot-dependent, and is read by A1. **What this item asks narrows from "which lot" to "how will brightness be obtained"** — and that answer may be a measurement too.

    **When the source closes, what remains is measuring.** If the lot number is on the label, `spec:<lot>` is still possible; if not, every route to provenance is blocked and **then the diameter is measured** — which is exactly what a microscope does, and the result is `measured:<run_id>` E1, **higher** than `spec:`'s E3. So what this item asks the person changes: **from "what is this" to "is there a lot on the label, and if not, shall measuring the diameter be the first real measurement".**

    **It is still the lot.** The product specification is `spec:AFR-0500-COOH` E3, and **that our tracer is that product** is still E5 — the person identified it from a vendor listing rather than reading the bottle's label. Reading the label next week makes that one layer E3, and the effective grade rises **automatically.** `agentic-microscope` has no lot either, and that is **a confirmed negative** — that file wrote *"size CV and dye loading vary lot to lot -- record it"* beside `lot:` and left the value empty.

    **The person announced on 2026-09-19 that they would read the bottle's label "next week". Until then this hold is a wait and not a hole in anyone's work.** This line is needed because an undated open item reads as **something to chase today** — `microscope execution` recording that it has been due to receive this lot "for several days" was that state, and a scheduled wait and a dropped ball are different while the record could not tell them apart. **The date lives only here.** The thread's `open_question` already points here, so writing it in `status.json` too would put the same fact in two places with nothing to compare — in the very item that taught that (§11-11).

    **What the sample opens together**: `tracer_number_density` (A2, A3), `tracer_brightness` (three of A1), `bleaching_rate` (A1, A3), and `tracer_diameter`. One lot number opens four.

    **The workaround of planning dimensionlessly was considered and not adopted — written down so it is not re-proposed later as a new idea.** It is that both sides plan in multiples of `tau_d` rather than seconds, so one substitution converts when `d` arrives, and there is precedent in the repository (`axis_a5_budget.py` prices cost against a reference step it chose itself and S4 rescales). **It is refused because the trigger is a week-long schedule rather than a defect.** The price is revising both sides' goal and plan cards plus what a dimensionless-unit question does to `units.json`, and that is **a structural change where a calendar lives.** And the work not depending on `d` is already reachable — the microscope's SNR and localisation reasoning, and A2's statistics, which are dimensionless to begin with. The bridge manager raised it and did not recommend it.

12. ~~**Is `observable` the right argument for `kb_query`**~~ → **Refuted 2026-09-19. Neither the argument is widened nor a tool added.** I set this item up as "the question side is wrong" and **the framing was wrong.** The librarian manager classified all sixteen log lines exhaustively and showed — nine of ten `kb_query` calls came back empty-handed, and those nine split like this:

    | What it was | n | What fixes it |
    |---|---|---|
    | present in a published table | 5 | `in_published_table` ✔ |
    | **the store has it under a different word** | 3 | **neither a kind nor a new tool fixes it** |
    | genuinely absent | 1 | `absent` is correct |

    **The decisive question: how many would have got an answer had there been a `kind` argument. Zero.** `kind=observable, name=numerical_aperture` gives zero and `kind=device, name=objective` gives zero — the store has them as **`na`** and **`objective_mrd70040…`**. **A kind tag does not create synonyms.** Adding a tool gives zero for the same reason, and that would break "four tools" for something not even free. And **not one call** was refused because of the argument's name — `subjects()` is the union of the four handles, so the server **never filtered by kind in the first place.** The name was decoration.
    **The real remaining half is the log's column.** One column mixes table names, column names, entry_ids and observables, and §0.3-4's comparison quietly drifts on top of it. That **closes by renaming alone** (`observable` → `subject`), taking no kind. Cheap and honest. The migration is `query_log.py` and `FIELDS`, and with no consumers yet, now is cheapest.

11. **One fact lives in several places and nothing compares them — add a comparator, or reduce the places.** This shape appeared three times on 2026-09-18 and only one of the three is being kept.

    | Fact | Where it lives | Comparison |
    |---|---|---|
    | one check | §8's declaration · `def check_NN_` · `CHECKS` | **check 42** |
    | one path | the §7 tree · `ALLOWED_PATHS` · `seats.json` | check 55 (2026-09-19) |
    | one boundary | `seats.json`'s `owns`/`paths` · `DESIGN_OWNED` · `AGENT_OF_PATH` | check 48 (2026-09-19) |
    | **the meaning of one field** | the schema description · the check code that reads it · **the actual data** | none |

    **The fourth was the most expensive on 2026-09-18.** `derived`'s documented meaning and its actual usage had diverged **to an intersection of zero** with nobody knowing, and a check approved on top of it had to be reversed. It surfaced only after running a census — unlike the first three, **it is invisible until the data is counted.**

    **The latter two have worse failure modes than the first.** A check declared with no implementation **does not run** — a silent hole. A path declared and not in the allow list **refuses correct work at the gate**, and that is exactly the situation answered with `--no-verify` (§6.2.1). Today two managers each hit the wall, each fixed it, and moved on.

    **What has to be decided is comparator versus fewer places.** Check 42 chose a comparator, but that is because §8's declaration is prose and cannot be derived from code — **a constraint, not a choice.** Paths and boundaries are different: `ALLOWED_PATHS` **can be derived** from §7's declarations, and `DESIGN_OWNED` and `AGENT_OF_PATH` from `seats.json`. And derivation beats a comparator — a comparator permits the two to stay diverged until somebody runs it, while derivation **makes diverging impossible** (the same argument as §0.4-6's "one declaration, one parser", one level up).

    So what this item asks is not "how many more checks to build" but **"where does the record go".** The candidates are `seats.json` (boundaries are already there) and the §7 tree (the human-facing record of paths), and per P3 the machine-readable side is the record and the §7 tree should be generated from it. The librarian manager raised it on 2026-09-18.

    **The second row bit twice the same day too, and bit in the same direction.** `bridge/README.md` in the morning, `contracts/quantities.json` in the evening. **Both times a line went into §7 and the gate kept refusing** — because what refuses is `ALLOWED_PATHS`. The opposite direction (the regex permits and §7 lacks it) never happened once. **Someone editing `ALLOWED_PATHS` knows they are editing a regex, and someone putting a line into §7 believes they have declared it.**

    **And check 13's message pointed at the wrong file both times**: *"path is not declared in plan.md §7"*. Putting it in §7 does not resolve it. In the evening case the librarian manager raised "§7 needs a line" to architecture, and architecture put in that line expecting it to work — **both believed the message.** The same as check 41 saying `owns` in the morning when what needed fixing was not `owns`. **The cheapest fix is not a new check but one line of message**, and that alone would have prevented both of today's cases.

    **The record is settled as `ALLOWED_PATHS` (2026-09-19, architecture).** Unlike the third row, **derivation is not the answer here**: the §7 tree is human prose and carries reasons, references and explanations beyond paths, and making it generated loses what it carries. And the opposite direction, parsing §7 to derive the regex, is **the tree parsing refused in the morning.** So here **a comparator is right, and it is the exception to §11-11's general preference for derivation** — because the two places do not hold the same thing.

    **Check 55 — whether `ALLOWED_PATHS` permits the filenames the §7 tree names. manager-librarian.** It does not parse structure: what is needed is **the set of names §7 states**, not the tree's shape. It is the 47/48/50/51 class (the limit §8 wrote once), and **the reason it is worth it anyway is that what bit today was an absent name, not a wrong one.** **Fixing check 13's message to say `both §7 and ALLOWED_PATHS` goes in the same commit** — what the check catches is a quiet divergence on a path nobody uses, and what the message fixes is **where to look when somebody actually hits it.** The two prevent different failures.

    **2026-09-19, the boundary row's price actually came in — half a day.** A manager wrote `bridge/README.md` and was refused by the gate. Architecture put README into the four managers' `paths` in `seats.json`, the manager put it into `ALLOWED_PATHS`, and **it was still refused.** Because check 41 passes three gates in order: first `seat_boundary_of(path)` classifies the path into a category, and if that category is not in `owns` it dies there. `paths` **only narrows, afterwards.** That is, **the registry cannot grant ownership.** What grants is the `DESIGN_OWNED` regex inside `validate.py`, and the registry can only shave it.

    So both sides correctly fixed their own half and the door did not open, and each seat suspected the other's half. The manager reported it three times as "§7 versus the validator" and proposed a §7 tree parser — **the wrong move.** The root is not §7 but this table's third row, **registry versus validator.** The reason a diagnosis that ended in reading three lines took half a day is that the symptom did not point at the cause: the refusal message says `owns`, and `owns` was not what needed fixing.

    **A `paths` entry that cannot grant is a dead letter.** It is quiet — it fails nothing and simply opens nothing. Check 48 catches it (eight cases in that morning's state). It reads the registry and the classifier only, with no tree parsing.

    **The record is settled as `seats.json` (2026-09-19, architecture).** P3 says so, the boundaries are already there, and today's price is the value of two places with no comparator. `DESIGN_OWNED` and `AGENT_OF_PATH` are **derived** from a machine-readable boundary table in `seats.json` — `boundaries` currently holds that fact only as prose, so that prose has to become a table, and that file is architecture's. Check 48 **retires when the derivation lands**: derivation makes divergence impossible and a comparator only tells you afterwards. Until then 48 is the net. The §7 tree's row (the second) is still open and the same argument applies without being the same decision — §7 is human prose and carries more than `ALLOWED_PATHS`.
10. **Worktrees, seat identity and `refuse` — an ordering constraint.** The three interlock and getting the order wrong makes one block another. §6.2.3 says to put the seat identity in the worktree's git config, and **with only one working copy, setting `--local` makes every session's commits go out under that identity.** So that prescription cannot apply before the worktree move, and until then the identity lives only as a command prefix and **disappears with a reset.** Flip `unknown_committer` to `refuse` in that state and **the first commit after a reset hard-fails** — today it is `report` and passes quietly unattributed. The order was **worktrees → identity in config → `refuse`**. The librarian manager raised it on 2026-09-18.

    **On 2026-09-19 the first step of that order disappeared permanently — the person decided not to give worktrees (§11-17).** So what this item asked (whether to take the three steps at once or separately) is no longer a question, and **the remaining question is whether `refuse` is reachable.**

    **It is unreachable. And the reason is structural rather than scheduling.** Without worktrees, **two sessions of one agent share everything on disk** — the same working copy, the same `.git/config`, the same directory, the same `CLAUDE.md`. So **nothing on disk can tell them apart.** Set `--local` and every session commits under one identity, and `extensions.worktreeConfig` has nowhere to attach with no worktrees. A seat identity is **a property of a session**, the only place a session's state lives is **context**, and context gets reset. Flip to `refuse` and **the first commit after a reset hard-fails**, and that is not a fixable failure but **a state where the seat can do nothing until it is told again who it is.**

    **So one line of §6.2.2 comes back.** On 2026-09-18 it was written that *"seat assignment was said to be a person's job; remembering the seat was not"*, and that presumed the worktree config would stand in for the memory. With that premise gone, **a reset seat has to ask the person again who it is.** That is the real cost of a reset, and the reason that cost has not been billed until now is that unattributed commits **pass quietly.**

    **And on 2026-09-20 that cost was counted: all 63 of the architecture seat's commits are unattributed.** While writing this item, closing §11-17, issuing seats in `seats.json` and pointing out others' unattributed commits, **that seat itself committed under the person's email all day.** Because it never once attached the prefix, and because not attaching it passes quietly — the single largest instance of the failure this paragraph describes is the seat that wrote it.

    **The distinguishing point is that the boundary was kept.** Those 63 touched only four things — `plan.md`, `CLAUDE.md`, `README.md` and `contracts/seats.json` — and check 35 passes on all 252 commits. **What is wrong is not where it wrote but who wrote**, and check 41 looks only at that. So this failure **damages the record without damaging the work** — the worst shape of a quiet failure.

    **It is not fixed retroactively — and the reason is stronger than "expensive": this repository uses commit SHAs as identifiers.** Counting on 2026-09-20 found **124** short-SHA citations across `plan.md`, `CLAUDE.md`, `contracts/` and the four `tasks/`, of which **26 point at real commits** — `seats.json`'s `enforced_from`, the range `librarian-3`'s `registered_late` names, dozens of grounds in §8 and §11. **A rewrite changing only the committer changes the SHA of every commit after it, so all 124 become dead references.** And **no check confirms a SHA citation, so they die quietly** — nothing does for SHAs what check 47 does for seat names. **An attribution gap is recorded and visible; a broken citation is not.** So a rewrite is worse than the gap, and what remains is to count it, write it down, and not do it again. Since registration takes effect from the next commit (`librarian-3`'s `registered_late`), there is no way other than rewriting history, and rewriting 252 commits **moves everyone else's work.** Instead it is counted and written here, and from now the prefix goes on every commit:

    ```
    GIT_COMMITTER_NAME=architecture GIT_COMMITTER_EMAIL=architecture@seat.invalid \
      git commit -- <paths>
    ```

    `--local` will not do — there is one working copy, so every session goes out under that identity. **That is what this paragraph says, and this commit is the first to go in with that prefix.**

**So it goes to a loud `report` rather than `refuse`.** `unknown_committer` stays `report`, and **the hook names the unattributed paths and warns at commit time.** A hard failure blocks a seat and a quiet pass hides the cost. **A warning makes it visible without blocking** — and that is exactly what this repository learned today: a deficiency nobody counts looks like a deficiency that is not there. The hook is the manager's file, so the wording is handed down with the assignment.

    **The conditions for reopening `refuse` are written too**: worktrees come back (§11-17's reversal conditions), or a place appears where a session can read its identity off disk — the latter is possible **only with one execution seat per agent**, and D12 multiplying execution seats closed it. **What was added for speed took what was needed for attribution**, and that trade is recorded as reversible.
9. ~~**S4's tiebreak order**~~ → **Settled 2026-09-19: no fixed order. The purpose decides.** The person settled it — the concession order is a property of the question rather than of this instrument, so the goal card carries it in. No default order either: if a card carries no order, S4 **does not guess and escalates to the person** (§4.5.1 (c)). The detail moved to §4.5.4. The number is left empty.
   **It is the same decision as §11-1.** Neither the vocabulary nor the order is fixed in advance; **the question brings it** — so that an unanticipated experiment can be taken. Having chosen the same side twice, it is written down as this repository's disposition: **instead of settling in advance what cannot be settled in advance, settle what to do when it is unsettled.** For the vocabulary that is "register it first", and for the order it is "escalate to the person".

8. **Registering derived quantities — half closed on 2026-09-19 and half open for want of anything to count.**

    **The closed half: derived quantities live in `quantities.json`. The same place as every other quantity.** Neither of the two options this item laid out — the same registry as observables, or a separate one. What appeared today is **a third shape**: `quantities.json` registers what can become a `numbers[].name`, and **`observables.json` is a subset of it** (§7). So the worry about `producible_by` and `window_required` sitting empty on derived quantities disappears — **those fields live on the narrow side, and living on the narrow side is why they exist.**

    **And comparing the two lists did turn out to be needed, but it is one comparison with a direction: inclusion.** Every observable id has to be a registered quantity. Not synchronisation but one-way inclusion, so it is cheap. **And it does not hold today** — neither `tracer_diffusivity` nor `trapped_position_distribution` is in `quantities.json`. The registry started at nine and held only what is actually used as `subject:quantity`, and the observables did not go in. **What I wrote in §7 — "every observable is a quantity and not the reverse" — is a true statement about kinds and false about the files, and the reader reads the files.** It is issued as check 60.

    **The open half: what catches the same quantity living under two names — there is nothing to count right now.** There are **two** derived quantities (`tau_d`, `tracer_number_density_from_diameter`), **their dimensions differ**, and the `tau_a`/`tau_d` case that produced this item is resolved with only one left. **Designing a duplicate detector from zero collisions is what §11-12 did**, and §8 wrote that as a rule today: **when you think you have found a class, count.**

    **So instead of a design there is a countable trigger: reopen this item when two registered quantities have the same dimension.** Then it is opened by a count rather than a judgement, and the shape is set from the real case at that moment. There is currently no pair with overlapping dimensions.

### 11.1 Not open questions but M1 extraction tasks

The following two are not "things to be decided" but **things pulled out of a prior repository**, and they were extracted on 2026-09-17 (§10.2's device registry row, §10.3):

- **Automatability per device** → `librarian_agent/kb/staging/devices.v0.json` (12 control channels)
- **The list of valid optical paths** → `librarian_agent/kb/staging/optical_paths.v0.json` (5 configurations + 1 exclusion rule)

**Why they are in `kb/staging/` and not `envelope/`**: device characteristics and optical paths are **knowledge**, and knowledge is owned by the librarian (P14, §4.3.2). `envelope/` holds only policy (safety limits) and **snapshots exported from the librarian's KB.** Snapshot export is M3's work, so until then the microscope agent reads these files by the direct read §4.3.0 permits.

**The storage form is not final.** The two files are flat tables and do not keep "one entry = one atomic claim" (§4.3). That was intended — the right decomposition depends on **how it will be queried**, and there was no querying side. Splitting into forty entries now would fix a shape on top of a guess.

**That condition was released on 2026-09-17.** With `kb_query`'s argument shape and an entry's `validity` settled (§4.3.1) there is something to decompose against, and the reordering made the librarian first (§9). **Decomposition is the second task after M3's first, and the criterion is one: can this claim become wrong on its own.** A channel that goes quietly wrong with one rewiring is an entry in itself, and things that go wrong together are one entry. Until decomposed, these files sit in `staging/` and cannot be cited as a `kb:` source — because a `kb:` citation has to resolve to an entry with a grade. By the time the microscope needs these tables (position 2 in the order) they have to be entries already, and that is what the reordering buys.

**On the numbering.** The list below **counts from 1 again.** Before this it continued §11's open-question numbers as 7–11, and as a result `§11-9` read as "open question 9" — a number that does not exist. That reference had in fact gone into `capabilities/microscope.json` as grounds, and this document repeated it once too. **The items in §11 are open questions and the items here are extraction rules.** The two lists do not continue each other.

**What was kept in the extraction:**
1. **Only fields a consumer reads.** Every field was asked "which of S3.0 / A4 / the orchestrator's locks / O1 preflight reads this", and fields with no reader were dropped — part numbers, serials, firmware, spectral band tables, per-fact verification dates, and narratives of each fact being corrected, retracted and re-confirmed. **A field with no reader goes stale with nobody knowing.**
2. **An E3 grade ceiling** (§10.3 rule 1).
3. **Safety limits were not extracted** (rule 4). A person confirms physically and writes them directly into `envelope/safety.json`.
4. **The port positions carrying the detection paths were deliberately not taken.** They are written in the prior repository, and that is one integer that goes quietly wrong with one rewiring. Left as a gap.
5. **What is unknown was written as unknown.** Three things the operator mentioned that are not in the register (the motorised XY stage, the spinning disk's speed and in/out, a separate laser shutter) were put in `gaps` rather than guessed.

---

## 12. Facts awaiting transfer

With no KB yet (pre-M0), facts the person supplied are collected here temporarily. **At the librarian milestone (M3, first in execution order) each item becomes a KB entry with a source and a grade and this section is emptied** — that is one of M3's completion conditions (§9). While they are here, these values cannot be the grounds of a plan (P2, P14).

| Fact | What is undecided | Why it matters |
|---|---|---|
| Laboratory temperature 20 °C | **is it a setpoint or a measurement**, plus the variation (±?) and the measurement location (room / near the sample) | Temperature enters by two routes: `k_BT` and `η(T)`. Around 20 °C water's viscosity changes by roughly **2% per °C**, so a ±1 °C variation makes a change of the same size in `τ_D`. In explore mode (§5.8) it does not change the order of magnitude and can be ignored; in confirm mode it cannot — so what is needed is not a setpoint but **the actual value near the sample and its variation** |

The form of this table is itself a rule: when a person gives a number, do not write the value alone but write **what is still undecided** with it. "20 °C" on its own cannot say whether it is a setpoint or a measurement, and the grade (E2 or E5) turns on exactly that.
