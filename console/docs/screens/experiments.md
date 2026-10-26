# Experiments screens (console card 014)

Area `experiments` (`web/src/features/experiments/`, hash `#/experiments/<page>`). Two pages, **Plan** and
**Sample map**; the sample's record view is a panel on Sample map. The screens **read files and show them**.
Nothing here starts a run, confirms a hand step, stops a run, switches a light on, or saves a draft. A piece the
runtime has not built yet says "not built yet", and the console builds no stand-in for it.

Server routes (`server/api/experiments.py`), all reads except Run, which answers and sends nothing:

| Route | What |
|---|---|
| `GET /api/experiments/plans` | every plan card on disk with where it stands, every run in `microscope_runtime/runs/` with how it ended, and why an approval file does not cover a plan |
| `POST /api/experiments/run` | what Run would send for an approved plan, and that Run is not built yet. **Sends nothing and writes nothing**; a login that is not the person's, a browser that is not at the microscope computer and a plan that is not approved are refused |
| `GET /api/experiments/sample` | the sample panel: no record yet, and the loading checks read from hand-step sheets |
| `GET /api/experiments/sample-map` | the four parts of the sample map, each "not built yet" with why |

## Plan

- **Plans on disk**: plan, revision, state in words (waiting for a signature, approved, changed after it was
  signed, and so on), who approved it and how, the runs made from it. An approval file that does not cover a
  plan (a different revision, a different plan hash, a file the console did not write) is listed under it with
  why.
- **Runs**: who signed and how, how it ended in words (finished, stopped from outside, stopped by the monitor,
  refused, running now), the event summary, and the plan it came from. A run whose plan is not on disk says so.
- **A hand step that is open** reads "Waiting for a step at the microscope. Confirm it there." and has **no
  button**. A confirmed one shows who confirmed it, when, and what they observed.
- **A stopped run that had traps** reads "tweezers laser: software cannot switch it; assumed on until you
  confirm".
- **Run** is offered only on an approved plan whose approval file is on disk, to the person's login at the
  microscope computer. The request it would send is `{"run": <sha256 of the approval file's bytes>}`. In the
  app it answers "not built yet" and shows what it would send; nothing leaves the console until the runtime
  has a part that receives it.
- **Drafts waiting for a signature** reuses the draft composer from Instruments: a trap pattern, the Aura
  LED, the transmitted lamp, the red camera's exposure and a piezo move. A trap or piezo draft is checked
  against `plan.schema.json`; the light and exposure drafts show the schema's refusal. **A draft is saved
  nowhere**, and the section says so.

## Sample map

Four parts, each with "not built yet" and why: frames with the stage's read-back position, the hole fitter,
the candidate finder, and flags and candidate confirmations. Nothing is drawn: no move, no flag, no candidate,
and a model's guess is never shown as one.

## Sample panel

"No sample record yet: where a sample's record lives is still being designed." The console invents no path.
A loading check made at the microscope reads "done at the microscope, from <run>'s hand-step sheet", with who
confirmed it and when.

## Where a draft goes

Where a console draft goes before the person signs it is **still to be designed**. Until then a draft exists
only on the screen it was made on.

## On the example data

Run from the example copy (`--store mock`), every page says "example data" and the server can name
`src/sma_console/agents/mock_data/SOURCE.md`, which lists which files were copied from where. The copied runs
use the current layout (`microscope_runtime/runs/`). The example copy holds no sample map, so the page says
"example data, not from any run" and shows none. Practice approvals in the example copy write nothing.
