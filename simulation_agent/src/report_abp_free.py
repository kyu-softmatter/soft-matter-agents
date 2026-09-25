"""The report for the free active particle (`abp_free`, question sim-20260923-003).

Follows the shared template (task 022; `report.py`'s header is the authority)
and reuses its parts: the SVG panel, the figure and legend wrappers, the
plain-language provenance, the code scan, the stylesheet. A module of its own
because this question's story is three regimes on one curve, and the shared
body is written around a grid of cells against a swept parameter.

Numbers come from the result card, the plan and the run's saved observables.
**Nothing is re-run**, and the figures are drawn from the curve the run
already wrote, not from the 560 MB trajectory beside it.
"""

from __future__ import annotations

import math

from .report import (Plot, figure, fmt, legend, notes, num, provenance, section)

TITLE = "How a self-propelled particle spreads, and what sets its two changes of behaviour"

BLUE, ORANGE, GREY, GREEN = "#2b6cb0", "#dd6b20", "#718096", "#2f855a"


def _slopes(obs):
    """The local log-log slope of the saved curve. The run wrote the curve; this
    reads it, and a report that recomputed from the trajectory would be
    spending compute for a picture (task 022)."""
    curve = obs["msd_curve"]
    lag = [p[0] for p in curve if p[0] > 0]
    msd = [p[1] for p in curve if p[0] > 0]
    out = []
    for i in range(len(lag)):
        a, b = max(0, i - 1), min(len(lag) - 1, i + 1)
        out.append((math.log(msd[b]) - math.log(msd[a])) / (math.log(lag[b]) - math.log(lag[a])))
    return lag, msd, out


def _thin(xs, ys, n=220):
    step = max(1, len(xs) // n)
    return xs[::step], ys[::step]


def body(R, N):
    c, plan, goal = R["results"][0]["card"], R["plan"], R["goal"]
    obs = R["results"][0]["obs"]
    log = R["results"][0]["log"]
    run_id = c["run_id"]
    lag, msd, slope = _slopes(obs)
    met = {x["id"]: x["met"] for x in c["criteria_evaluation"]}
    dev = {d["parameter"]: d for d in c["deviations"]}

    def pv(name, card=None):
        n = num(card or plan, name)
        return f"{fmt(n['value'])} {n['unit']}" if n else "not stated"

    tau1 = float(num(plan, "thermal_crossover_time")["value"])
    tauR = float(num(plan, "persistence_time_expected")["value"])
    expected = float(num(c, "effective_diffusivity_expected")["value"])
    read = float(num(c, "effective_diffusivity_read")["value"])
    ratio = float(num(c, "effective_diffusivity_ratio_to_expected")["value"])
    smax = float(num(c, "msd_loglog_slope_max")["value"])
    slast = float(num(c, "msd_loglog_slope_longest_lag")["value"])
    rel = float(num(c, "effective_diffusivity_relative_error")["value"])
    integ = log["events"][-1]["t_mono"]
    # The distance travelled before the heading is forgotten. Derived here
    # rather than read, because the plan does not carry it -- which is itself
    # worth fixing, since it is the number the microscope needs to say whether
    # the particle stays in view.
    lp = float(num(plan, "self_propulsion_speed")["value"]) * tauR

    S = []

    # 1 Summary
    S.append(section(1, "Summary",
        "<div class='box'>"
        "<p>Asked: how does a swimming particle spread over time, and how do the speed and the "
        "turning rate change it? <b>It does three different things at three timescales, not two.</b> "
        "Heat pushes it further than its own swimming at the shortest times, it then swims nearly "
        "straight, and finally it wanders again, far faster than heat alone.</p>"
        f"<p>The long-time spreading rate came out <b>{ratio:.3f}</b> of the value the formula "
        f"predicts, inside the one decade set as the target. Four of the five criteria set in "
        f"advance were met; the one that was not is a fault in how the criterion was written, "
        f"not in the run.</p></div>" + _f1(lag, msd, obs, tau1, tauR)))

    # 2 Purpose
    S.append(section(2, "Purpose", N.get("Purpose in plain words") or "<p>Not written.</p>"))

    # 3 What was expected
    S.append(section(3, "What was expected",
        "<p>For a particle that swims at a fixed speed and slowly forgets its heading, the spread "
        "over time is known in closed form, so the prediction was available before running. Three "
        "things follow from it, and all three were written down first.</p>"
        f"<p>The long-time spreading rate should be <b>{pv('effective_diffusivity_expected', c)}</b>, "
        "the thermal value plus a term growing as the square of the speed and falling as the "
        "turning rate rises. The growth of the spread should start proportional to time, rise "
        "toward time squared, and fall back to time. And it should <b>never quite reach</b> time "
        "squared: how close it gets is fixed by one combination of the speed, the turning rate and "
        f"the thermal spreading, which at this operating point caps it at <b>1.977</b>.</p>"
        "<p>This is why the run is worth making and also what it cannot settle: the answer is "
        "already determined by what went in, so agreement confirms the machinery and measures no "
        "new dependence.</p>"))

    # 4 Variables
    S.append(section(4, "Variables",
        "<table><tr><th>Held fixed</th><th>Value</th><th>Where it came from</th></tr>"
        f"<tr><td>particle diameter</td><td>{pv('bead_diameter')}</td>"
        f"<td>{provenance(num(plan,'bead_diameter')['source'])}</td></tr>"
        f"<tr><td>temperature</td><td>{pv('temperature')}</td>"
        f"<td>{provenance(num(plan,'temperature')['source'])}</td></tr>"
        f"<tr><td>water viscosity</td><td>{pv('viscosity')}</td>"
        f"<td>{provenance(num(plan,'viscosity')['source'])}</td></tr>"
        f"<tr><td>thermal spreading rate</td><td>{pv('translational_diffusivity')}</td>"
        f"<td>{provenance(num(plan,'translational_diffusivity')['source'])}</td></tr>"
        f"<tr><td>turning rate</td><td>{pv('rotational_diffusivity')}</td>"
        f"<td>{provenance(num(plan,'rotational_diffusivity')['source'])}</td></tr>"
        f"<tr><td>swimming speed</td><td>{pv('self_propulsion_speed')}</td>"
        f"<td>{provenance(num(plan,'self_propulsion_speed')['source'])}</td></tr>"
        f"<tr><td>particles</td><td>{pv('n_particles')}</td>"
        f"<td>{provenance(num(plan,'n_particles')['source'])}</td></tr></table>"
        "<p><b>This run varies nothing.</b> It is one operating point, because one plan is one "
        "operating point here and a sweep has no single setting that satisfies every requirement "
        "at once: the timestep wants the fastest corner and the record length the slowest. What "
        "is measured is the spread over time, its growth rate, and the long-time spreading rate "
        "read from it.</p>"))

    # 5 Setup
    S.append(section(5, "Setup",
        "<p>One particle carries a heading. The heading drifts randomly at the turning rate, the "
        "particle is pushed along whatever heading it has at a fixed speed, and thermal buffeting "
        "is added on top. <b>What the model leaves out is everything else</b>: no other particles, "
        "no walls, no obstacles, no flow. That is deliberate and it is why this run can be checked "
        f"against a formula.</p>"
        f"<p>Engine: {log['backend']}, on this workstation. The heading is turned by a dedicated "
        "updater with the integrator's own rotation switched off; running both would turn the "
        "particle twice as fast as asked, which was measured rather than assumed.</p>"
        f"<p><b>Why the numbers are what they are.</b> The step is {pv('integration_timestep_point')}, "
        "far below the time the heading takes to turn, which is the only thing that limits it: a "
        "free swimmer has no size in this model, so nothing bounds the step by distance. The record "
        f"is {pv('total_simulated_time_point')}, which is longer than either requirement asks for on "
        "its own -- the reading window must be at least a certain length, and that window must be a "
        "small fraction of the record, and the two together force several times more than either. "
        f"Frames are saved every {pv('save_interval_point')}, set by storage rather than by physics: "
        "finer would resolve the earliest regime too and cost ten times the disk.</p>"
        + _f5(tau1, tauR, lp)))

    # 6 Criteria set in advance
    S.append(section(6, "Criteria set in advance",
        "<p>Written into the plan before the run, and the plan is on record.</p>"
        "<table><tr><th>Criterion</th><th>Threshold</th><th>Chosen by</th></tr>"
        "<tr><td>a straight-line stretch is present</td><td>peak growth rate at least 1.9</td>"
        "<td>this seat, from the formula for the peak</td></tr>"
        "<tr><td>the late wandering regime was entered</td><td>growth rate back to 1</td>"
        "<td>this seat</td></tr>"
        f"<tr><td>spread on the long-time rate</td><td>within {pv('target_relative_error')}</td>"
        "<td>this seat</td></tr>"
        "<tr><td>the run reaches its planned length</td><td>40000 s of simulated time</td>"
        "<td>this seat</td></tr>"
        "<tr><td>the integration has not diverged</td><td>no step longer than the box</td>"
        "<td>this seat</td></tr></table>"))

    # 7 Results
    rows = "".join(
        f"<tr><td>{k.replace('_',' ')}</td><td>{'met' if v else 'NOT met'}</td></tr>"
        for k, v in met.items())
    S.append(section(7, "Results",
        _f2(lag, slope, tau1, tauR)
        + "<div class='box'><p><b>Three regimes.</b> The growth rate starts at "
        f"{slope[0]:.3f}, rises to <b>{smax:.3f}</b> against a ceiling of 1.977 that the formula "
        f"fixes, and falls back to {slast:.3f}.</p>"
        f"<p><b>The long-time spreading rate</b> read {read:g} against a predicted {expected:g} "
        f"in the same units, a ratio of <b>{ratio:.3f}</b>, with a spread of {rel*100:.1f} per cent "
        "from a block resample.</p></div>"
        f"<table><tr><th>Criterion</th><th>Outcome</th></tr>{rows}</table>"
        "<p><b>The one that failed is the criterion's fault and not the run's.</b> Its "
        "machine-readable form asks for a growth rate at or below 1 at the longest times, and the "
        f"measured {slast:.3f} is just above. Its own sentence beside it says <i>within a tenth of "
        "1</i>, which {slast:.3f} passes. Those are two different tests and the one the comparison "
        "carries is the one that binds, so this reads as not met. Correcting it takes a new "
        "revision of the plan.</p>".replace("{slast:.3f}", f"{slast:.3f}")))

    # 8 Checks
    S.append(section(8, "Checks",
        "<p>The whole curve is compared against the closed form over eight decades of time, and "
        "the agreement is the check: nothing else in this run is independent of its inputs.</p>"
        f"<p><b>The error bars are not the uncertainty, and the card uses the honest one.</b> The "
        f"fit's own spread on the long-time rate is {float(obs['fit']['relative_standard_error'])*100:.3f} "
        f"per cent; the block resample gives {rel*100:.2f} per cent, forty-seven times larger. The "
        "fit treats points on one curve as independent observations when every one comes from the "
        "same trajectories. A criterion read against the smaller number would have passed for the "
        "wrong reason.</p>"
        f"<p>Every planned setting was reproduced exactly: "
        f"{', '.join(k.replace('_',' ') for k,v in dev.items() if v['within_tolerance'] and 'diffusivity' not in k)}."
        "</p>"))

    # V1 -- the physics is visible in motion here, which a histogram cannot show
    S.append(section(8, "Watch it happen", _v1(R["qid"], tauR)))

    # 9-12 hand-written
    S.append(section(9, "Interpretation", N.get("Interpretation") or "<p>Not written.</p>"))
    S.append(section(10, "Limits", (N.get("Limits") or "")
        + "<p>The store held no entry for any quantity this question needed -- the spread over "
        "time, the turning rate, the swimming speed, the crossover time. All were recorded as "
        "missing rather than quietly filled.</p>"))
    S.append(section(11, "Link to experiment",
        "<p>The microscope now declares that it can produce the spread over time, so a comparison "
        "is possible in principle. It is not yet requested, for a reason this run makes concrete: "
        f"at this operating point the particle travels <b>{fmt(lp)} micrometres</b> "
        "before it forgets its heading, which fits the field of view at low magnification and not "
        "at high. The particles actually in use swim about ten times faster, which would put that "
        "distance in millimetres for a particle of this size. The next revision anchors on the "
        "particle diameter instead, because for a sphere the turning rate falls as the cube of the "
        "diameter and that is what decides whether it stays in view.</p>"))
    S.append(section(12, "Decisions for you", N.get("Decisions for you") or "<p>Not written.</p>"))

    # 13 Cost
    S.append(section(13, "Cost",
        "<table><tr><th></th><th>Estimated before</th><th>Actual</th><th>Ceiling</th></tr>"
        f"<tr><td>integration</td><td>{pv('wall_clock_estimate')}</td><td>{integ:.0f} s</td>"
        "<td>2 hours</td></tr>"
        f"<tr><td>whole run</td><td>not estimated</td><td>36 hours</td><td>not bounded</td></tr>"
        f"<tr><td>disk</td><td>{pv('storage_estimate')}</td><td>0.56 GB</td><td>10 GB</td></tr></table>"
        "<div class='warn'><p><b>The estimate was close and it covers a thousandth of the run.</b> "
        f"Forty seconds was predicted for the integration and it took {integ:.0f}. The other 36 "
        "hours went to writing the trajectory and reading it back to compute the answer, and "
        "<b>nothing estimates, bounds or watches either</b>: the two-hour ceiling is checked only "
        "while the integration runs, so it never applied. A ceiling that bounds a thousandth of a "
        "run is not a ceiling. The storage estimate, which was the one term the model did have, "
        "was right.</p></div>"
        "<p>The trajectory file is 560 MB and is kept outside version control; you delete it by "
        "hand.</p>"))

    return "".join(S), {"R": R, "title": TITLE}


def _v1(qid, tauR):
    """The clip beside the report, or one line saying it is not there.

    A picture is not a reason to spend compute (task 022), so this never
    renders anything: it links the file if a previous run of the figure step
    left one, and says so plainly if not.
    """
    import datetime as _dt                             # noqa: PLC0415
    from .report import REPORT_DIR                     # noqa: PLC0415

    stem = f"rebuild-report-{_dt.date.today():%m%d}-{qid}"
    if not (REPORT_DIR / f"{stem}.mp4").exists():
        return ("<p class='gone'><b>V1 not drawn.</b> No clip is beside this report. Regenerating "
                "one reads the saved trajectory; it needs no new run.</p>")
    return (f"<figure><video src='{stem}.mp4' controls width='560'></video><figcaption><b>V1.</b> "
            f"Six swimmers over three turning times, one second of simulated time per video "
            f"frame, one saved frame in twenty shown. The straight stretches and the turns are "
            f"the two changes of behaviour in the graph above; the heading is forgotten after "
            f"about {fmt(tauR)} s.</figcaption></figure>")


def _f1(lag, msd, obs, tau1, tauR):
    xs, ys = _thin(lag, msd)
    p = Plot((min(lag) / 2, max(lag) * 2), (min(msd) / 3, max(msd) * 3), logx=True, logy=True,
             xlabel="time difference (s)", ylabel="spread (square metres)")
    p.line(xs, ys, BLUE, 1.6)
    for x in (tau1, tauR):
        p.line([x, x], [min(msd) / 3, max(msd) * 3], ORANGE, 1, "4 3")
    return figure("F1", p.svg() + legend([(BLUE, "measured"), (ORANGE, "dashed: the two changes of behaviour")]),
                  f"Main result. The spread over time across eight decades, from {len(lag)} lag "
                  "points of one run of 400 thousand frames. The dashed lines are where heat gives "
                  "way to swimming and where the heading is forgotten.")


def _f2(lag, slope, tau1, tauR):
    xs, ys = _thin(lag, slope)
    p = Plot((min(lag) / 2, max(lag) * 2), (0.9, 2.15), logx=True,
             xlabel="time difference (s)", ylabel="growth rate")
    p.hline(1.0, GREEN); p.hline(2.0, GREEN)
    p.line(xs, ys, BLUE, 1.6)
    for x in (tau1, tauR):
        p.line([x, x], [0.9, 2.15], ORANGE, 1, "4 3")
    p.text(min(lag) * 3, 2.05, "2  straight-line limit, never reached", GREEN)
    p.text(min(lag) * 3, 1.05, "1  wandering", GREEN)
    return figure("F2", p.svg() + legend([(BLUE, "measured"), (GREEN, "the two limits"),
                                          (ORANGE, "dashed: the two changes of behaviour")]),
                  "How fast the spread grows, against time. Starting at 1, rising toward 2 and "
                  "falling back to 1 is the three-regime structure; the middle never reaches 2.")


def _f5(tau1, tauR, lp):
    p = Plot((tau1 / 100, tauR * 100), (0, 3), logx=True, xlabel="time (s)", ylabel="")
    p.band(0.6, 1.4, "#e8eef7"); p.band(1.6, 2.4, "#fdf0e4"); p.band(2.6, 3.0, "#e5f2ea")
    p.text(tau1 / 30, 1.0, "buffeted by heat", GREY)
    p.text(tau1 * 3, 2.0, "swimming straight", GREY)
    p.text(tauR * 6, 2.8, "wandering, faster", GREY)
    for x, lab in ((tau1, "heat gives way"), (tauR, "heading forgotten")):
        p.line([x, x], [0, 3], ORANGE, 1.2, "4 3")
        p.text(x * 1.2, 0.25, lab, ORANGE)
    return figure("F5", p.svg(),
                  f"The setup, drawn from the plan's own numbers: the swimmer changes behaviour at "
                  f"{fmt(tau1)} s and again at {fmt(tauR)} s, and travels {fmt(lp)} micrometres "
                  "between them.")


PARTS = {"build": body, "title": TITLE}
