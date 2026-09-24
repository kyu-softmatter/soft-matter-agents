# 022 — reports to the person: one template, generated from the records, with figures

**For:** window 2 (`simulation-8`) first. It has written the most reports and
has a finished grid to report: `sim-20260923-201` v5, six cells on HOOMD. The
other windows report through the same generator once it lands, each adding the
figures its own problem needs.

Written by `manager-simulation-20260923-1`. You read this; you do not edit it
(§6.2-2).

## What the person asked (2026-09-23)

Reports carry graphs, and pictures and video where possible. They cover the
purpose, the variables, the setup, the results and the interpretation. And
there should be a template that produces them. The person also asked what else
belongs; the sections marked *added* below are the answer they were given.

## What is wrong with how reports are made now

Measured on the two reports window 2 wrote into `~/Desktop/report/` on 09-23
and 09-24: **neither has a figure**, and the two use different headings. Both
were written by hand, so every number in them was retyped from a card. A
retyped number is one fact in two places, and P3 already rules on that for
Markdown: generated from the JSON, or it drifts. A report is in the same
position.

## The generator — `src/report.py`

`report.py <qid>` reads the question folder and the runs its result cards name,
and writes one report. It **re-runs nothing.** Figures come from files on disk:
`trajectory.txt` through the reuse path of 021, `result*.json`, the cards. If a
trajectory a figure needs is gone, the figure is replaced by one line saying so
and naming the rerun, the way the 021 reader already refuses. A picture is not
a reason to spend compute.

**Numbers come from the records, not from the seat.** Values, uncertainties,
sweep points, criteria and outcomes are read from the plan, result and
synthesis cards. The seat writes by hand only what no card holds: the purpose
in plain words, the interpretation, the limits, and the decisions put to the
person. Those live in a notes file beside the report (see Output).

## Sections, in this order

1. **Summary** — two or three sentences: what was asked, the headline number
   with its uncertainty, and whether it met the criterion set in advance. The
   main figure as a thumbnail.
2. **Purpose** — the question and why it matters, and what answer would settle
   it. From the goal card.
3. **What was expected** *(added)* — the prediction before running: the formula
   or limiting case, and where it comes from. A number with nothing to compare
   against says nothing.
4. **Variables** — what was varied (range and points), what was held fixed,
   what was measured. One table.
5. **Setup** — the model in words, including what it leaves out; engine and
   version; every parameter with where it came from; the timestep, run length
   and seeds, and **why** — the plain version of the axis intervals, never
   their codes. A picture of the setup (F5).
6. **Criteria set in advance** *(added)* — the accuracy and convergence
   criteria and who chose them, shown **before** any result. The order is the
   point: a reader who meets a criterion after the result cannot tell whether
   it was chosen after.
7. **Results** — figures first, then the table. Every value with its
   statistical uncertainty. Runs that did not converge, or diverged, are shown
   and labelled, not dropped.
8. **Checks** *(added)* — whether the machinery reproduced a case with a known
   answer, and the residuals against the prediction in units of each point's
   own uncertainty (F2).
9. **Interpretation** — what the numbers mean, kept apart from the numbers.
   Judgment is marked as judgment.
10. **Limits** *(added)* — what the model assumes, what the store did not have
    (the card's gaps, in words), and what the result does not show.
11. **Link to experiment** *(added)* — whether the microscope can measure this,
    what the bridge plan asks for, or why there is none yet.
12. **Decisions for you** *(added)* — what the person has to decide next, each
    with its options and what each costs.
13. **Cost** *(added)* — wall clock and disk against the ceilings, and the
    trajectory files kept with their sizes, since the person deletes those by
    hand.
14. **Footer** — the only place references appear: date, seat, question id, run
    ids, commit, the validator's tree line, and the command that regenerates
    the report.

## Figures

- **F1 main result** — the observable against the varied parameter, with error
  bars and the prediction overlaid. Log axes when the range spans a decade.
- **F2 residuals** — (result − prediction) / uncertainty for each point, with
  the acceptance band set in advance shaded. For 201 that band is the person's
  ±3 of each cell's own standard error.
- **F3 raw data** — a stretch of one trajectory, and the position histogram
  against the distribution expected.
- **F4 convergence** — the running estimate against simulated time, with the
  declared criterion marked.
- **F5 setup** — the potential or geometry, drawn from the plan's parameters.
- **V1 video** — where the physics is visible in motion (a hop between wells, a
  swimmer turning): a short clip from `trajectory.txt`, time in physical units
  on screen, a scale bar, and the frame subsampling stated in the caption.
  Optional where nothing moves that a histogram does not already show.

Every caption says which runs made it, from how many frames and seeds. F1, F2
and F4 are the same for every problem and belong in the shared part. F3, F5 and
V1 differ by model, so the generator takes them from a per-configuration
function that each window writes for its own configuration.

## Plain language, enforced where it is cheap

The body carries none of the codes listed under "Talking to the person" in the
root `CLAUDE.md`, and no `kb:` entry ids. Provenance goes in words, and **the
generator does the translation, not the seat**: a `simulated:` source reads
*read off the run*, a store entry reads as its description and where it came
from, a person's choice reads *chosen by you on <date>*, an assumption reads
*assumed*.

**Make the generator refuse** — exit non-zero, naming the offending string —
when the rendered body outside the footer matches a code pattern. A rule that
depends on the writer remembering is the kind this repository keeps finding
broken. Test the patterns against physics notation before trusting them: `2D`,
`D_R`, `1E6` and `P = 0.5` must pass.

## Output

- `~/Desktop/report/rebuild-report-<MMDD>-<qid>.html`: one file, figures
  embedded; the video beside it as `<same stem>.mp4`, referenced by a `<video>`
  tag.
- The notes file (purpose in words, interpretation, limits, decisions) at
  `~/Desktop/report/notes/<qid>.md`. Outside the tree on purpose: a report is a
  view for the person, not a record, and reports here are never committed.
- English, like the reports so far. The template lives in the repository, and
  everything in the repository is English.

## One dependency is not yet yours to use

The `sim` environment has numpy, scipy, hoomd and gsd, and **no plotting
library**. `matplotlib` and an `ffmpeg` binary have been requested from
architecture for `[tool.pixi.feature.sim.dependencies]`, on the person's
instruction, the route scipy took. Until they land, `import matplotlib` in
`src/` is refused by check 82. Build the section extraction first; it needs
neither.

## Done when

- `report.py sim-20260923-201` writes the v5 report with F1–F5 and every section
  above, and its numbers match the cards they came from — spot-check three;
- with the notes file deleted it still writes a report, and the hand-written
  sections say they are empty rather than vanishing;
- a planted `check 45` in the notes makes the generator refuse — watch it
  refuse;
- pointed at a run whose trajectory was deleted, F3 is replaced by the rerun
  line and nothing is re-run;
- `python3 contracts/validate.py` ends `0 failed`.

Report the report's path, and what you would change in this card after
building it.

## Amended after the first report (window 1, 2026-09-23)

Window 1 built the double-well report to this order by hand, before the
generator existed — `~/Desktop/report/rebuild-report-0923-sim-20260923-101.html`,
14 sections, F1–F5 and a 20 s V1. Scanned by the manager with embedded data
removed: every seat name and hash sits in the footer, none in the body. Its
two findings, and a third the scan turned up, change this card:

**1. Section 6 has three states, and the generator renders each differently.**
The section cannot always be filled truthfully, and rendering an empty one as
"none" hides a difference that matters:

- *set on a card* — quote it, with who chose it and when;
- *stated before the data but only in prose* — a message, a notes line, a
  goal's rationale: quote it with its source and its time, judge it
  separately, and say it was not on a card;
- *none* — say so. Any band then drawn on F2 is labelled **shown for reading,
  not set in advance**, never shaded as if it were a criterion.

Prose criteria are the case to design for, not the exception: window 1's
occupancy-definition test was written before its replicates and lived nowhere
a card could carry it.

**2. The code scan skips embedded data.** Window 1's own grep hit `A5` and
`E4` inside base64 PNG strings, so a generator that embeds figures and scans the
rendered body refuses its own images. Scan the text after removing `data:`
URIs, `<style>` and `<script>`, and add an embedded figure to the tests beside
`2D`, `D_R` and `1E6`.

**3. The footer is a `<footer>` element.** The manager's scan of window 1's
report could find the footer only by its heading text. The one place references
are allowed has to be found by structure, or a renamed heading silently widens
it to the whole page.

## Closed at fbc5342, and amended again from building it (window 2)

`src/report.py` exists and every done-condition was watched: three values
spot-checked against their cards, four sections reading "Not written yet" with
the notes removed, exit 2 on a planted `check 45`, and the rerun line in place
of F3 for a deleted trajectory. The report is
`~/Desktop/report/rebuild-report-0923-sim-20260923-201.html`. **From here the
generator's header is the authority** and this card is its history. Window 2's
five changes:

**4. Static figures are SVG written directly, with no plotting library.** The
report stays one self-contained file. `matplotlib` and `ffmpeg` stay declared
anyway, **for V1**: a video is raster frames, and that is where they are used.
Check 82 reports both until a V1 is written, which is true.

**5. F4 plots the deviation in units of the standard error at that record
length**, not a relative deviation. A ±1 % band drew a passing cell as
failing: whether a running estimate has settled is only meaningful against
its own uncertainty at that length.

**6. Run files are a source, cited by run.** Some values a report needs are
held only in `runs/*/observables.json` — the signed offset, the predicted
standard error, the equipartition and relaxation-time ratios. "Numbers come
from the records" includes those files; the caption or table says which run.
What stays forbidden is retyping.

**7. Text a card holds for the person is written without codes.** Plan skip
reasons carried things like "exceeds A5's step budget", which the generator
had to paraphrase, falling back to "not run" for a reason it did not know. The
code there added nothing: write "exceeds the step budget". Where a reason
still carries one, the generator shows **"not run — the reason is not worded
for you yet"** and puts the raw reason in the footer, so the gap is visible
rather than silent.

**8. The file name carries the person's local date, and the header says so.**
Card timestamps are UTC, and on the evening of 09-23 local they already read
09-24. The person reads by their own day.
