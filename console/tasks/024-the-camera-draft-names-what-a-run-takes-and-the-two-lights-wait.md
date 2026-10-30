# 024 — the camera draft names what a run takes, and the two lights wait

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 023.
Build to `3f4bd6de` and this card's commit, and cite both in your report.
Build nothing to a draft seen uncommitted in the working copy. If you are not
that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

This is still the interface step (I-20261029-office-06, `d3b71d83`). Nothing
here waits on a runtime commit, and nothing here connects to a run.

## Why

The three part drafts do not name what a plan names, so the run would refuse
each of them for a reason the page does not give. Card 017's notice beside
them says the runtime "cannot yet match the element to what software may
command". That was true when it was written, and it is no longer the reason.

On 2026-10-29 `manager-microscope-20261003-1` read the runtime at `3f4bd6de`
(`operator.py`, `orchestrator.py`, `devices.v0.json`) and answered how a plan
names each part. Its summary, which it said may be quoted:

> In short: camera = {device: camera_red, action: set_exposure, parameters:
> [exposure_time]}, refused for lack of a binding. Aura = hold until card 102
> lands and the model string has a source. Lamp intensity = withdraw. Lamp
> on/off = hold until mm_states.

What `src/sma_console/agents/drafts.py` writes today is none of those.
- **The camera draft names the device `Kinetix_red`**, a Micro-Manager label.
  A plan never writes a label (`plan.md` 15.1 item 9). The run refuses it as
  neither a channel nor an element, before it reaches the binding at all.
- **The Aura draft names the device `Aura` and the action `set_<colour>`.**
  `Aura` is the read-back's label. A light engine's registry name is its
  model, exactly, and only once runtime card 102 (`cad83b19`) is built. The
  run ranks `set_<colour>` as neutral, not as raising power. The microscope
  manager reads that as letting the light come up before the path is set.
- **The lamp draft names a parameter `intensity` in percent, and the action
  `state_on_and_intensity` or `state_off_and_intensity`.** No quantity of
  that kind is registered, `contracts/units.json` has no percent, and the
  lamp's channel `dia_lamp` has no binding. That action ranks neutral too.

So this card corrects the camera draft, withdraws the Aura and lamp drafts
until a run can take them, and makes the notice give the true reason.

## What changes

- **The camera draft's plan action is exactly this:**
  `{"id": "set_camera_exposure", "device": "camera_red", "action": "set_exposure", "reversible": true, "parameters": ["exposure_time"], "tier": 1}`.
  - Its one number is named `exposure_time`, in `ms`, with the source,
    grade and precision drafts carry now (`assumed:the_persons_choice`, E5,
    `order_of_magnitude`). The form still asks for milliseconds.
  - `exposure_time` is the registered quantity (`contracts/quantities.json`,
    `a0aaea22`), in seconds. A value in milliseconds is converted through
    `contracts/units.json`, by the run and not by the console.
  - In the changes draft, `system_configuration.devices` lists
    `camera_red`.
  - `camera_exposure` stays the console's own name for the form and for the
    server's draft kind. It never appears in a plan.
- **The notice beside the camera draft gives the true reason.** The server's
  `refused_today` and `web/src/features/instruments/parts.ts` say these
  words, exactly:
  "The run will refuse this draft even when it is made and signed: nothing
  recorded yet tells it how to set the red camera's exposure on this
  microscope."
  - That is the missing binding, in words. The run also needs that binding,
    its label and its state read under the configuration it loaded, and
    none of them exists yet.
  - 017's sentence about matching the element appears nowhere in `src/` or
    `web/src/` after this card.
- **The limit refusal before signing stays, for the camera's exposure.** The
  person's answer of 29 October holds (D-20261029-office-04, `698ba049`):
  no limit is set for it, so the draft is refused before signing and the
  page says no limit has been named for that quantity yet. The console still
  names no limit, reads none from the safety file for it, and takes no other
  quantity's limit as covering it.
- **The Aura and the transmitted lamp get no draft.**
  - The server's draft kinds no longer hold `aura` or `dialamp`. A request
    naming either, to the single draft or to the changes draft, is refused
    as an unknown kind, and no card is built.
  - `drafts.py` names no device, action or number for them.
    `AURA_REFUSED_LONGER` goes with the Aura draft. The table of quantity
    words keeps one entry, the red camera's exposure.
  - No page offers their draft. That covers the Optics draft panel, the
    Experiments page's "Kind of draft" list and a click on the element.
- **Their elements stay on the path and in the list**, each with its state
  as read, as now. Where the element's control said "drafted", it now says
  that no draft is offered yet. A click opens the element with these words,
  exactly, and with no fields:
  - Aura: "No draft is offered for the Aura yet. A plan will name the light
    engine by its model, and the console has nowhere to read that model from
    yet, so it guesses none."
  - Lamp: "No draft is offered for the transmitted lamp yet. The run has no
    recorded quantity for its brightness, and no table of its on and off
    states."
  - The row's control value for this is yours to name. The words are the
    server's and the page's, pinned on both sides.
  - The row's `draft` field carries only a kind the server's draft list
    holds. The camera's form is still reached through the channel table
    (`camera_red`), as 023 part 3 built it.
- **This card replaces, in earlier cards:**
  - 017's notice wording, and its bullet that the Aura stays refused
    longer;
  - 023 part 3's "drafted elements (the Aura, the transmitted lamp, the red
    camera's exposure)" and "The Aura and the lamp keep the draft the
    server's row gives them".

  The tests that pinned those change in the same commit as the code.

## What the console does not check

- **The console does not run the runtime.** That the run refuses the
  corrected camera draft for want of a binding is the microscope manager's
  reading of the code at `3f4bd6de`, not a console test. A run shows it once
  the mock connection lands.
- **The draft meets the shape the run asks before any data:** an id, a
  device, an action, `reversible: true`, parameters and a tier, with every
  parameter in `numbers`. The rest the microscope manager listed is the
  run's, and the page claims none of it:
  - each binding, label and state read under the loaded configuration;
  - a decision for tier 2 or more;
  - a matching signed approval;
  - and, with no light limit, a comparison that is empty, which is not a
    pass.

## Not in this card

Each of these returns, if it does, by a card of its own. The person's
refusal before signing applies to it then as now, unless the person decides
otherwise.
- **The Aura's draft** waits for two things: runtime card 102 built, and a
  source the console may read for the engine's model. The microscope manager
  offered to pin such a field beside the read-back in the idle status
  schema. It has not been asked for yet.
  - When it returns, the plan is `set_power` on the engine's model, with
    `illumination_power` and a line exactly `UV`, `CYAN`, `GREEN`, `RED` or
    `NIR`.
  - The binding's unit is permille, so a power in mW or W needs a recorded
    calibration and a step.
  - One plan carries one `illumination_power`, so one line per plan. That
    is a known gap.
- **The lamp's on and off** waits for a recorded state table for
  `dia_lamp`. It will then be a required state on that element, not a
  parameter.
- **The lamp's brightness** has no registered quantity, and the console
  registers none.
- **Lowering a light by draft** would use `disable` or `ramp_down`, which the
  run ranks as lowering power. Until then, the [Lights off] button covers
  turning every light off.

## Tests, each watched failing first

- The camera draft's plan card holds exactly the action above, and one
  number, `exposure_time` in `ms`. It validates against
  `contracts/schemas/plan.schema.json` itself, alone and in a changes draft.
- **Every draft the server can build names a device id in
  `contracts/capabilities/microscope.json`.** Build one of each kind the
  server's draft list holds. The piezo stage, which that file does not hold,
  is named in the test with why, as 023 part 3's table test does.
  - Watch the test fail against today's `Kinetix_red` first.
- A request naming `aura` or `dialamp` is refused at both draft routes,
  with no card returned.
- The Aura and lamp elements show their words above and no fields. Neither
  the Optics page nor the Experiments page offers their draft.
- The camera draft shows the new notice. 017's old sentence appears in no
  file under `src/` or `web/src/`.
- The camera draft is refused before signing, saying no limit has been
  named for the red camera's exposure yet. A fixture safety file carrying
  every limit the safety schema names changes nothing.
- 017's and 023's other tests still pass.

## What not to do

- Hard-code no engine model string.
- Register no quantity, and add no unit or state word.
- Write no device name the capabilities file does not hold, other than the
  piezo stage named above.
- Read nothing of the store but its wiki pages.
- Write nothing outside `console/`, and install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
  The build also refreshes the page the running server shows.
- `uv run pytest -p no:cacheprovider` passes.
- `uv run --offline --no-project --python 3.12 --with jsonschema python contracts/validate.py`
  ends `0 failed` on the tree it names.
- Report the commit, and the commits it was built to.
