"""The goal card for sim-20260923-101 revision 2: the person's double well, on its declared model.

    cd simulation_agent && python -m src.double_well_goal

Revision 1 was a DRAFT on an undeclared `min(U1, U2)` and could not pass
screening. Revision 2 moves it onto `bd_overdamped_gaussian_double_well_2d`,
declared at 4ab86d9, and drops `min` -- the person chose two additive Gaussian
wells. Everything on the card is in SI; the reduced units stay in the engine.

The operating point is ONE point of the map task 024 computes, and the card
says why this one: soft enough that the tolerances are liveable, and near the
middle of the barrier window. The map itself, and the ask built on it, are the
answer to the person's question; this card is what puts the configuration
through the pipeline and gives the engine its first run record.

The librarian answers were taken under `sim-20260923-101:v2:s2` at
kbv-a1bb4a5acf25 on 2026-09-25 (UTC) and are written here as they came back.
"""

from __future__ import annotations

from . import cards

QID = "sim-20260923-101"
REVISION = 2
KBV = "kbv-a1bb4a5acf25"
CREATED = "2026-09-25T04:10:00Z"


def gap(name: str) -> dict:
    return {"gap_id": f"{name}_absent", "observable": name, "kind": "absent",
            "searched": ["kb/entries", "kb/exports"], "nearest": [], "near_names": [], "kb_version": KBV}


def build_r2() -> dict:
    n = cards.num
    numbers = [
        {"name": "bead_diameter", "value": 5, "unit": "um", "source": "kb:tracer_diameter_measured",
         "grade": "E2", "precision": "significant_figures", "note": "the tracer in the bottle in use"},
        {"name": "temperature", "value": 293, "unit": "K", "source": "kb:lab_ambient_temperature",
         "grade": "E3", "precision": "significant_figures",
         "note": "the room's reading, not established to be the sample's. In this model it is a coordinate "
                 "-- the noise amplitude -- and citing the room records why this value was chosen"},
        {"name": "viscosity", "value": 0.001, "unit": "Pa*s", "source": "kb:water_viscosity_293k",
         "grade": "E3", "precision": "significant_figures",
         "note": "pure water; asked over 292-294 K and the entry's validity covers it. The bench's in-situ "
                 "diffusivity, near the coverslip, replaces the Stokes drag in the re-prediction"},
        n("trap_stiffness_1", 1e-6, "N/m", "assumed:a_holding_stiffness", precision="order_of_magnitude",
          note="1 pN/um. Nothing in the store gives a trap stiffness; the experiment calibrates each trap "
               "after it is set. Chosen at the soft end, where the stiffness-matching tolerance is about "
               "five per cent at this width"),
        n("trap_stiffness_2", 1e-6, "N/m", "assumed:a_holding_stiffness", precision="order_of_magnitude",
          note="EQUAL to trap 1, and that is the finding rather than a simplification: with wells hundreds "
               "of kT deep, any ratio of 0.5 or below leaves a barrier from the deeper well of tens to "
               "thousands of kT at every separation, so the person's 1-to-100 range holds no hops at all"),
        n("trap_width_1", 1e-6, "m", "assumed:a_trap_width", precision="order_of_magnitude",
          note="the Gaussian width of each well. Unknown; the store holds none. Near the bead radius is "
               "the microscope side's estimate, and the lower end of the map's 1-2.5 um"),
        n("trap_width_2", 1e-6, "m", "assumed:a_trap_width", precision="order_of_magnitude",
          note="equal to trap 1's"),
        n("barrier_target", 4, "1", "assumed:a_barrier_target", precision="order_of_magnitude",
          note="the barrier from the deeper well in units of k_B*T -- a ratio, so the operator can pass it through: kT has no fixed SI factor. Inside the 1-10 kT window. "
               "THE SEPARATION IS NOT ON THIS CARD, AND THAT IS DELIBERATE: the barrier moves by about "
               "0.55 kT per 10 nm here, so the separation that gives 4 kT has to be known to about a per "
               "cent, which an explore-mode number cannot state and a bench cannot dial. The engine "
               "solves the separation from this barrier and reports it in the run record, and the bench "
               "tunes its separation the same way -- by the histogram, not by a number"),
        n("record_length", 600, "s", "assumed:a_bench_record", precision="order_of_magnitude",
          note="ten minutes, the short end of the 10-60 min the experiment might record. Assumed; the "
               "spread over records at 10, 30 and 60 min is a separate study"),
        n("save_interval", 0.01, "s", "assumed:a_bench_record", precision="order_of_magnitude",
          note="10 ms, the middle of the 1-50 ms a camera might frame at. Assumed"),
        n("milestone_core_fraction", 0.2, "1", "assumed:a_core_fraction", precision="order_of_magnitude",
          note="the core radius around each histogram peak, as a fraction of the peak spacing. Near "
               "merging the minima sit far inside the trap centres (+-0.67 w against +-1.08 w at the stiff "
               "point), so cores on the trap centres would miss the wells; the experiment applies the same "
               "rule to its own histogram"),
        n("smoke_record_fraction", 0.1, "1", "assumed:a_bench_record", precision="order_of_magnitude",
          note="the smoke run records a tenth of the record, so it is a small job and not the same job under a "
               "tighter ceiling"),
        n("walkers", 200, "1", "assumed:a_bench_record", precision="significant_figures",
          note="independent single-bead records in one engine run, each as long as the bench record"),
    ]
    assumptions = [
        {"rationale_id": "a_holding_stiffness",
         "statement": "1 pN/um for both traps: the soft end of what the tweezers hold a 5 um bead at, where "
                      "the matching tolerance is about five per cent. Nothing measured picks it.",
         "numbers": ["trap_stiffness_1", "trap_stiffness_2"],
         "falsifier": "the experiment's calibrated stiffness of each trap, returned after the traps are set, "
                      "replaces both and the simulation re-predicts at them",
         "gap_ref": "trap_stiffness_absent"},
        {"rationale_id": "a_trap_width",
         "statement": "A Gaussian width of 1 um, near the bead radius. Unknown, and the map spans 1-2.5 um to "
                      "show how much the answer depends on it.",
         "numbers": ["trap_width_1", "trap_width_2"],
         "falsifier": "the width read off the calibrated single-trap histogram's departure from a Gaussian, "
                      "or off the separation at which the two wells merge",
         "gap_ref": "trap_potential_width_absent"},
        {"rationale_id": "a_barrier_target",
         "statement": "4 kT, inside the 1-10 kT window where hops are frequent enough to count and rare enough "
                      "to be hops.",
         "numbers": ["barrier_target"],
         "falsifier": "a run returning under a handful of hops per record lowers it",
         "gap_ref": "interwell_barrier_height_absent"},
        # a_record_length onward: none of these stands on a store entry that could exist;
        # they are the bench's choices, and its actual values replace them
        {"rationale_id": "a_bench_record",
         "statement": "The record as the bench might take it, and the ensemble that stands for it: ten minutes, "
                      "the short end of what the bench may record; 10 ms between frames, the middle of the "
                      "camera's likely range; two hundred independent records, enough to see the spread one "
                      "record shows; and a smoke run of a tenth of the record, one minute, enough to time the "
                      "engine.",
         "numbers": ["record_length", "save_interval", "walkers", "smoke_record_fraction"],
         "falsifier": "the bench's actual record length and frame interval replace the first two, and the "
                      "thousand-record spread study replaces the ensemble",
         "gap_ref": "record_length_absent"},
        {"rationale_id": "a_core_fraction",
         "statement": "Cores a fifth of the peak spacing around each histogram peak; the occupancy moved by "
                      "under 0.001 between a tenth and three tenths in the engine validation.",
         "numbers": ["milestone_core_fraction"],
         "falsifier": "a record whose rate moves by more than its scatter between 0.1 and 0.3 needs a stated "
                      "choice rather than this default",
         "gap_ref": "milestone_core_fraction_absent"},
    ]
    card = cards.head("goal", f"goal-{QID}-r{REVISION}", QID, CREATED, revision=REVISION,
                      status="DRAFT", requested_by="human", purpose="characterize", intent="explore",
                      observable={"name": "well_occupancy"},
                      targets=[{"metric": "well_occupancy", "kind": "decade_resolution", "value": 1,
                                "unit": "count",
                                "note": "one decade on each of the four observables, measured from the "
                                        "same trajectory: well_residence_time, interwell_transition_rate and "
                                        "interwell_barrier_height belong to the same question"}],
                      constraint_notes=[
                          "THE MODEL IS DECLARED: bd_overdamped_gaussian_double_well_2d, two additive "
                          "Gaussian wells in two dimensions, each exactly 0.5*k_i*dr^2 at its centre. The "
                          "person chose it on 2026-09-24; revision 1's min(U1, U2) is dropped",
                          "the person's stiffness ratio of 1 to 100 is not taken over: computed from the "
                          "potential, with wells hundreds of kT deep, a ratio of 0.5 or below holds no "
                          "barrier in 1-10 kT at any separation. The asymmetry is stated instead as a depth "
                          "difference of a few kT, which is a stiffness trim of a few per cent",
                          "all four observables are read from the trajectory projected onto the line "
                          "joining the traps, with cores around the two histogram peaks -- the estimator "
                          "the experiment applies to its own record",
                      ],
                      priority=["physical_feasibility", "target_accuracy", "evidence_grade", "cost"])
    refs = [
        {"entry_id": "lab_ambient_temperature", "grade": "E3", "kb_version": KBV,
         "claim": "The laboratory's ambient temperature is 20 degrees Celsius, read off a thermometer by the "
                  "operator. It is a reading and not a setpoint, and it is the room's rather than the sample's."},
        {"entry_id": "tracer_diameter_measured", "grade": "E2", "kb_version": KBV,
         "claim": "The particles in the bottle in use have a diameter of 5 micrometres, with a coefficient of "
                  "variation no greater than 2 per cent, measured directly by the operator on 2026-09-19."},
        {"entry_id": "water_viscosity_293k", "grade": "E3", "kb_version": KBV,
         "claim": "Dynamic viscosity of pure water near 293 K is of order one millipascal second, and it "
                  "changes by roughly two percent per kelvin in that neighbourhood."},
    ]
    card.update(cards.tail(numbers, assumptions=assumptions, kb_refs=refs,
                           kb_gaps=[gap(x) for x in ("trap_stiffness", "trap_potential_width", "trap_separation", "record_length", "camera_frame_interval", "milestone_core_fraction", "interwell_barrier_height")],
                           degraded=[]))
    card["caller_id"] = "sim-20260923-101:v2:s2"
    return card


CREATED_R3 = "2026-09-25T05:30:00Z"

# Revision 3: what ONE record shows (task 024 stage 4). Five points, a thousand
# records each where storage allows, on the engine through the operator. Every
# number below is a bench choice or a stated asymmetry; none is measured.
R3_EXTRA = [
    ("trap_stiffness_soft", 1e-7, "N/m", "a_holding_stiffness", "order_of_magnitude",
     "0.1 pN/um, the soft end, where the matching tolerance is about 40 per cent at this width"),
    ("barrier_soft", 2, "1", "a_barrier_target", "order_of_magnitude",
     "the barrier at the soft point, in units of k_B*T: soft traps hop more slowly at a given barrier"),
    ("depth_difference_none", 0, "1", "a_barrier_target", "significant_figures",
     "equal wells: no trim"),
    ("depth_difference_mild", 1, "1", "a_barrier_target", "order_of_magnitude",
     "well 2 one k_B*T shallower than well 1 -- about a 0.4 per cent stiffness trim at 1 pN/um, which "
     "the bench makes by watching the occupancy rather than by dialling a stiffness"),
    ("record_length_long", 2000, "s", "a_bench_record", "order_of_magnitude",
     "about half an hour, to one figure: the sensitivity of the spread to the record length"),
    ("save_interval_coarse", 0.05, "s", "a_bench_record", "order_of_magnitude",
     "50 ms: the sensitivity to the frame interval, at the slow end of the camera's likely range"),
    ("walkers_long", 500, "1", "a_bench_record", "significant_figures",
     "five hundred records for the thirty-minute point, which keeps its text trajectory inside the "
     "storage ceiling; a thousand would put it at the ceiling"),
]


def build(revision: int = REVISION) -> dict:
    card = build_r2()
    if revision == 2:
        return card
    if revision != 3:
        raise SystemExit(f"revision {revision} of {QID} is not written here")
    nums = {x["name"]: x for x in card["numbers"]}
    nums["barrier_target"]["value"] = 3
    nums["barrier_target"]["note"] = ("the barrier from the deeper well at the three 1 pN/um points, in units of "
                                      "k_B*T. The engine solves the separation from it, as in revision 2")
    nums["walkers"]["value"] = 1000
    for name, v, u, rid, prec, note in R3_EXTRA:
        card["numbers"].append(cards.num(name, v, u, f"assumed:{rid}", precision=prec, note=note))
    for a in card["assumptions"]:
        extra = [x[0] for x in R3_EXTRA if x[3] == a["rationale_id"]]
        a["numbers"] = list(a["numbers"]) + extra
        if a["rationale_id"] == "a_bench_record":
            a["statement"] = ("The records as the bench might take them, and the ensembles that stand for them: "
                              "ten minutes at a 10 ms frame as the base, thirty minutes and a 50 ms frame at one "
                              "point to show what the spread is sensitive to, a thousand independent records a "
                              "point (five hundred for the long one, for storage), and a smoke run of a tenth.")
    for a in card["assumptions"]:
        if a["rationale_id"] == "a_barrier_target":
            a["statement"] = ("The landscape the bench tunes to, stated in k_B*T rather than in separations and "
                              "stiffness ratios: 3 kT from the deeper well at 1 pN/um and 2 kT at 0.1 pN/um, inside the "
                              "1-10 kT window, and an asymmetry of 0 or 1 kT of depth difference. With wells hundreds "
                              "of kT deep a stiffness ratio of 0.5 or below holds no barrier in that window, so one kT "
                              "of depth is the mildest asymmetry the person can ask for.")
    card["id"] = f"goal-{QID}-r3"
    card["revision"] = 3
    card["created_at"] = CREATED_R3
    card["caller_id"] = f"{QID}:v3:s2"
    card["targets"][0]["note"] = ("one decade on the MEAN of each of the four observables, and beside it the "
                                  "spread one record shows -- the 5th to 95th percentile over records -- which is "
                                  "what a single bench record is compared against")
    card["constraint_notes"] = list(card["constraint_notes"]) + [
        "REVISION 3 IS THE SPREAD STUDY: five points of the same configuration, each read as many independent "
        "single-bead records through the experiment's own estimator, so the comparison has a distribution to "
        "place one bench record in, not only a mean"]
    for r in card["kb_refs"]:
        r["kb_version"] = KBV
    return card


if __name__ == "__main__":
    import sys
    rev = int(sys.argv[1]) if len(sys.argv) > 1 else REVISION
    path = cards.question_dir(QID) / cards.artifact_name("goal.json", rev)
    cards.write(path, build(rev))
    print(path.relative_to(cards.REPO))
