# 006 — the pared-down console: screens and decisions

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**This card assigns no work.** It is the specification that the console's app
cards, from 007 on, cite. Each of those cards is assigned to the console seat
on its own. **Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

The person asked for the console to be redesigned as the agents' user
interface (I-20261022-office-04, `d1068945`). The person said the biggest
purpose is paring it down, because it holds too much (`c84c0f32`). The person
also said the design canvas is redrawn first and the app is changed after it
(Q-20261022-office-12, `be28bbca`). This seat drew the canvas, with the
holders' agreement (Q-20261023-office-02, `ac839de8`).

The canvas is a claude.ai Design artifact, outside the tree, and it can change
after this card. So the canvas's decisions are written here, and **where the
two differ, this card holds** until a later card revises it.

- **Canvas**: https://claude.ai/artifact/Wfw2ybEMyLpfU6UYyQCeVo, **version 46**
  (version id `1792787755-e834`), page "Pared down - 2026-10-23". The 24
  earlier screens stay on its first page as the record of what was too much.
  Do not build from them.
- **Artboards**: `PLogin`, `PQuestions`, `PQuestionDetail`, `PSign`;
  `PInstStatus`, `POptics`, `PCameras`, `PTweezers`, `PConfocal`, `PPiezo`;
  `PExperiments`, `PSimulation`, `PLibrary`, `PResults`, `PAdmin`.
- **Read by each rule's holder before this card.**
  - architecture-20261003-1 (6, 6.1, 8.3): the sign dialog, login, admin and
    hand step. Cleared at version 43.
  - architecture-office-20261017-1 (15.1): the instruments tab. Its points 0
    to 5 matched at version 42, and the hand step was settled at version 43.
  - architecture-20261007-1 (4, 4.5): the question and library screens, at
    version 44.
  - manager-librarian-20261007-1: the library screen, verified at version 46.

## Build order

1. The canvas. Done.
2. The app's screens, on example data.
3. The mock backend.
4. The real instruments last, connected by the person at the bench
   (`d1068945`).

The app keeps the canvas's look: the dark ground, IBM Plex, and the amber
accent.

## What every screen leaves out

The measure of a screen is what it leaves out (`c84c0f32`).
- **No internal codes.** No seat names, and no stage, grade, tier or check
  codes. A hash appears only where the person signs.
- **Details open on a click**, on the thing they belong to, never beside it.
- **A number keeps its word beside it**: measured, computed, guessed, read
  back, or sent. A guess reads as a guess at a glance.
- **Example data is labelled as example** on every screen.

## The shell

- **Left sidebar**: Questions, Instruments, Experiments, Simulation, Library,
  Results. Admin sits below a rule.
- **Footer on every screen**: STOP, which stops every running run and works
  for every login. At the right, who is logged in, and Log out.
- **No password is ever shown or pre-filled.**
- This replaces the app's twelve areas. The seven that only say "not
  connected here" go: hardware, sample, map, objective, patterns, tweezers
  and sessions. So does the overview.

## Screens

**Log in (`PLogin`).**
- Login and password. Logins are plain ids, never an email.
- Create an account: a request that waits for the administrator to approve
  it and set what it may do.
- First start: creates the administrator account (`softmatter`), with the
  password typed there by the person. Advise a password never written
  anywhere else, a chat window included. No credential ships with the
  console.
- STOP works here without a login, at the microscope computer only (card
  004).

**Questions, the first screen (`PQuestions`).**
- One field. Autocomplete offers only strings already on disk: earlier
  questions and registered names, each labelled as which. It never offers a
  model's completion.
- An optional "Ask" choice: let the agents decide, the microscope, the
  simulation, or the librarian.
- Send writes a **question request** into the console's own folder. It holds
  the words verbatim, the login, the login's console role, the time, and the
  agent addressed if one was chosen. The screen says "Request written". How
  the request reaches an agent is not drawn (Q-20261022-office-04, open).
- Below the field are earlier question cards: the question, its state, and a
  five-step bar (asked, designed, signed by the person's own login only,
  run, result).
- **No console question is marked as the person's own in the first build**
  (plan.md 6, 15.1). Every run from one waits for the person's signature,
  and the card says so. A question from another login starts the design at
  once (`7d8b7c73`), and every run from it waits for the person, small ones
  included (`231f0c76`).

**One question (`PQuestionDetail`).**
- The question verbatim, who asked and when, and the progress.
- A plan waiting for a signature, with Review and sign. Another login sees
  "Waits for the person's signature" and no button.
- A summary assembled from card fields. Anything the assistant wrote is
  labelled as the assistant's.
- The cards made from the question, one row each, opening on a click: goal,
  design, each plan, and the bridge's rounds. Bridge, decisions and permits
  have no tabs of their own.

**Sign (`PSign`)** (Q-20261022-office-02 and -09, `d1068945`, `55a635b6`;
plan.md 6.1, 15.1; schema `e2f5b08b`).
- Shows the plan's full fingerprint, bound to that revision.
- The password is typed again at every signature. A click alone signs
  nothing.
- Signing writes a plan approval into `microscope_runtime/approvals/`,
  carrying `signed_through: {via: "console", login}`. That folder is the
  console's one write outside `console/`.
- Only the login the person names as their own signs. The runtime checks
  that login against `microscope_runtime/envelope/console_login.json`, which
  the person places by hand. The console's settings decide only what the
  screen offers.
- The administrator account signs only if it is that login, and then not
  until its password is changed at the console.
- A practice login is shown as signed and writes nothing real.
- If the approvals folder is absent, nothing is signed and nothing is
  written elsewhere.

**Instruments**: show, draft and stop only. Hands-on control is decided after
the reduction (`cd9dcb57`): no click-to-hold and no dragging traps. What
software may command is the runtime's `SOFTWARE_MAY_COMMAND`
(`microscope_runtime/src/devices/micromanager.py`). A part outside it is
drawn "set by hand; software may not move it", with no draft.
- **Status (`PInstStatus`)**
  - Reads the runtime's idle status file as data (`idle_status.schema.json`,
    `d549cc42`): "As of <time>, from <run>", and each reading with how it was
    read and when.
  - Which program holds which instrument: "not checked yet".
  - Check now runs the person's once-approved read-only list, and is offered
    only under the person's own login (`471ef2df`). It has a state for no
    approved list, and one for a run holding the instruments: it never
    waits or queues.
  - The tweezers laser is set by hand, not known, and **assumed on**. Trap
    strength is "sent through the tweezers program".
  - The disk shutter reads Open, and which value means closed is not
    recorded.
  - Which camera the tweezers program holds is not settled.
- **Optics and control (`POptics`)**
  - The light path drawn smaller. Double-clicking a part opens its controls.
  - Drafts exist only for the Aura LED, the transmitted lamp and the red
    camera's exposure, each "refused until you write a limit".
  - Filters, objective, condenser and the Spectra III via DMD are set by
    hand.
  - The laser combiner shows "close was sent; assumed open until a shutter
    that reads back shows it blocked".
- **Cameras (`PCameras`)**
  - 2x2 panels. Frames appear only while a signed run acquires; live view is
    one such run.
  - Live view on is offered under the person's own login only.
  - The blue camera is not opened by software yet, so panels 2 and 3 say so.
  - The overlay draws no traps until a trap-to-camera mapping is measured.
- **Tweezers (`PTweezers`)**
  - Trap positions are "sent".
  - A pattern is a trap-steps draft. Traps are allowed only at 40x (±100 µm),
    60x (±67 µm) and 100x (±40 µm), at most 1 µm per step.
  - Trap count and flicker rate are refused until a limit exists.
- **Confocal (`PConfocal`)**: state only.
- **Piezo stage (`PPiezo`)**
  - x, y and z read back, with time, in micrometres and seconds. The range is
    0 to 600 µm on each axis.
  - The time window and refresh are screen-only. The read rate is a plan
    field.
  - The pattern generator is designed later.

**Experiments (`PExperiments`).**
- Drafts waiting for a signature.
- The run list, with each run's detail opening on a click.
- **A run waiting on a step done by hand is shown, not confirmed.** The
  screen says to confirm it at the microscope, where the run asks for it.
  Handing the bench back is the person's own act, and a console confirm
  would be the first run-interface request that releases motion.
- A stop involving traps says the trap laser is assumed on until the person
  confirms.

**Simulation (`PSimulation`), Results (`PResults`).**
- One screen each.
- Every simulated value is labelled "computed in the model".
- A result states its precision in words, and a difference under a factor of
  ten is no trend.

**Library (`PLibrary`)** (`89e7cf05`, `0a387d1b`).
- A notice that the library's contents are not shown yet. That waits on
  4.3.1's holder.
- Three requests, open to every allowed login, none waiting for the person.
  - **Add a document or a value**: the kind of source, who read it, and the
    fact wanted in words. A remembered value is labelled as entering at the
    lowest grade.
  - **Withdraw a value**: the entry's name, the reason, and optional
    evidence. Words alone cannot refute.
  - **Offer a result.**
- The librarian's answers:
  - entered, naming its entry;
  - waiting for a name to be registered;
  - refuted;
  - in conflict;
  - superseded;
  - kept, with the reason;
  - no entry of that name.
- The request and answer schemas are manager-librarian's, once the route is
  settled.

**Admin (`PAdmin`).**
- **Accounts**: approve, reset a password, switch off, never delete.
- **Permissions**: console-side roles only (`231f0c76`): may ask, may draft,
  which agents, and may ask for a model run. Signing is never on this list.
- **Agents**: the agents' own permissions, read-only.
- **Services** (`86db5134`, `ac839de8`)
  - Usage and cost per connected service, shown under the person's own
    login, not the administrator role as such.
  - Paying opens the service's own page, where the person pays. The console
    holds no card details and no keys, and never pays.
  - The list of services comes from architecture-20261007-1's registry file,
    once it lands.
- **Self-improvement**: shown and drafted only. A proposal shows its
  fingerprint and waits for the person's word said in the intake window. The
  console does not sign it (plan.md 8.3).

## Dropped

The overview; Decisions and Permits as tabs; the Bridge tab; the librarian's
service log; the sample map and the sample screens, which are not in the
person's list.

## Still open

- **Q-20261022-office-14**: whether the self-improvement tab stays. It is
  drawn, and marked as open.
- **Q-20261022-office-15**: whether the sample map and the sample screens
  come back.
- **Q-20261022-office-04**: how a question request reaches an agent.
- **Hands-on control**, after the reduction.
- **A "measured here, with its raw record" source kind** for the library.
  This is the person's call, and goes through "Offer a result" until then.
- **The connected-services registry**, architecture-20261007-1's.

## What is not the console's

Clearing or filling the store, which is only ever a request to the librarian.
Granting an agent a permission or a level. Setting a laser's power or
emission. Confirming a step done by hand. Signing a harness proposal.
