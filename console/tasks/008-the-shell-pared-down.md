# 008 — the shell, pared down

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, from 2026-10-24. If
you are not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

The person asked for the console to be finished (`7c33b8c3`). Card 006, as
revised by 007, is the specification. This card is the first of the app
cards in 007's order: the frame every screen sits in. The canvas screens it
follows are the sidebar and the footer on every artboard of the canvas's
"Pared down" page, version 58 (version id `1792807301-4968`):
https://claude.ai/artifact/Wfw2ybEMyLpfU6UYyQCeVo.

The app today has twelve areas in a header. Seven of them only say "not
connected here": hardware, sample, map, objective, patterns, tweezers and
sessions. The status bar still carries the lights, the assistant, and the
take and release control of dino's engine, which card 077 retired. The
person's purpose is to pare the console down (`c84c0f32`).

## What to do

1. **The areas** (`web/src/app/areas.ts`), in this order, with these ids and
   labels:
   - `questions`, Questions
   - `instruments`, Instruments
   - `experiments`, Experiments
   - `simulation`, Simulation
   - `library`, Library
   - `results`, Results
   - `admin`, Admin, administrator only

   `DEFAULT_AREA` is `questions`.
   - **Questions** loads today's console screen unchanged. Move
     `features/console/` to `features/questions/`. Its own redesign is a
     later card.
   - **Simulation** and **Results** load their screens unchanged.
   - **Admin** loads today's accounts screen. Move `features/accounts/` to
     `features/admin/`.
   - **Instruments**, **Experiments** and **Library** are new folders, each
     with one plain screen: its title, one sentence of what it will show
     (the canvas's subtitle for it), and "not built yet". They request
     nothing.
2. **Remove the seven retired areas**, their folders, `app/Retired.tsx`, and
   the tests that walk them. Today's `features/live/` is not one of them:
   keep its code where it is, out of the navigation. The cameras card will
   place it under Instruments.
3. **The layout**, as on the canvas:
   - A **left sidebar** with "Soft-matter agents" at the top, then the six
     areas, then Admin below a rule, shown to an administrator only. It
     stacks above the screen at phone width.
   - The **footer on every screen**: STOP at the left, from the existing
     `StopAllRuns`, so the same stop the lock screen has is on every screen;
     a chip saying "Example data" when the store is the mock; and at the
     right the logged-in user's name with Log out.
   - **No password is ever shown or pre-filled.**
   - The title "Takatori Lab Console" goes.
4. **Leave out of the shell**:
   - the lights reading;
   - the assistant's status;
   - the take and release control;
   - the focus readout in the status bar;
   - the assistant side panel.

   The modules may stay in the tree; nothing in the shell renders them. The
   last-shutdown notice reads `last_shutdown_lights` from the engine status.
   Under `--backend placeholder` that is the placeholder's. If it only ever
   reads the placeholder, leave it out too. If you find it reads anything
   real, keep it and report.
5. **Routes.** `#/questions` and the rest work. An old hash such as
   `#/console`, `#/hardware` or `#/map` lands on Questions, as an unknown
   area does today.
6. **Tests, each watched failing first:**
   - the navigation lists exactly the six areas, plus Admin for an
     administrator only;
   - every screen shows STOP and Log out in the footer;
   - none of the seven retired ids is an area, and no file imports
     `Retired`;
   - an old hash lands on Questions;
   - the new Instruments, Experiments and Library screens make no request.

## What not to do

- Do not change the server, the data layer or any route.
- Do not redesign the screens inside the areas; later cards do that.
- Install nothing. `web/node_modules` and the lock stay as they are.
- Write nothing outside `console/`.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`, with
  Node from `.venv/Scripts`.
- `uv run pytest` passes.
- The validator ends `0 failed`.
- One commit, under your seat, through `contracts/tools/seat_commit.py`.
  Report the hash to this seat.
