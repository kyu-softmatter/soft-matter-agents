"""Folding append-only sample events: rules, order independence, cross-session merge."""

import random

import pytest

from dino_autofocus.records import SampleEvent, fold
from dino_autofocus.records.events import make_event


def ev(kind, t, session="a", seq=0, sample="s1", **payload):
    return make_event(kind, sample, session, f"{session}@example.test", seq, t=t, **payload)


T = "2026-10-01T10:00:{:02d}-07:00"


def test_fold_rules():
    events = [
        ev("hole_fit", T.format(1), seq=0, centre_um=[1.0, 2.0], diameter_mm=6.0),
        ev("boundary_point", T.format(2), seq=1, x_um=1, y_um=1),
        ev("boundary_clear", T.format(3), seq=2),
        ev("boundary_point", T.format(4), seq=3, x_um=2, y_um=2),
        ev("hole_fit", T.format(5), seq=4, centre_um=[8026.0, 571.6], diameter_mm=6.144),
        ev("flag_set", T.format(6), seq=5, flag_id="f1", name="good"),
        ev("flag_set", T.format(7), seq=6, flag_id="f2", name="debris"),
        ev("flag_remove", T.format(8), seq=7, flag_id="f2"),
        ev("particle", T.format(9), seq=8, particle_id="p1", status="candidate", z_um=3010.0),
        ev("particle", T.format(10), seq=9, particle_id="p1", status="confirmed", z_um=3012.9),
        ev("field_visit", T.format(11), seq=10, x_um=5, y_um=5, objective="4x"),
        ev("note", T.format(12), seq=11, text="oil added"),
        ev("future_kind", T.format(13), seq=12, anything=1),
        ev("note", T.format(14), seq=13, sample="other", text="not this sample"),
    ]
    st = fold(events, "s1")
    assert st.hole["diameter_mm"] == 6.144
    assert [(p["x_um"], p["y_um"]) for p in st.boundary] == [(2, 2)]
    assert set(st.flags) == {"f1", "f2"} and st.flags["f2"]["retired"]  # T-027c: kept
    assert {k for k, f in st.flags.items() if not f["retired"]} == {"f1"}
    assert st.particles["p1"]["status"] == "confirmed" and st.particles["p1"]["z_um"] == 3012.9
    assert len(st.visits) == 1 and [n["text"] for n in st.notes] == ["oil added"]
    assert st.other[0]["kind"] == "future_kind"
    assert st.n_events == 13 and st.updated == T.format(13)


def test_fold_does_not_depend_on_read_order():
    a = [ev("flag_set", T.format(i), session="a", seq=i, flag_id=f"a{i}", name="x")
         for i in range(5)]
    b = [ev("flag_set", T.format(i), session="b", seq=i, flag_id="shared", name=f"b{i}")
         for i in range(5)]
    ref = fold(a + b, "s1").as_dict()
    rng = random.Random(0)
    for _ in range(20):
        mixed = a + b
        rng.shuffle(mixed)
        assert fold(mixed, "s1").as_dict() == ref
    assert ref["flags"]["shared"]["name"] == "b4" and ref["sessions"] == ["a", "b"]


def test_same_second_events_are_ordered_by_session_then_seq():
    t = T.format(0)
    e = [ev("flag_set", t, session="b", seq=0, flag_id="f", name="from b"),
         ev("flag_set", t, session="a", seq=1, flag_id="f", name="from a, later seq"),
         ev("flag_set", t, session="a", seq=0, flag_id="f", name="from a")]
    assert fold(e, "s1").flags["f"]["name"] == "from b"


def test_offsets_are_compared_as_times_not_strings():
    # DST ends 2026-11-01 02:00 in California: 01:30 PDT (08:30Z) comes before 01:10 PST
    # (09:10Z), although the strings sort the other way.
    early = ev("flag_set", "2026-11-01T01:30:00-07:00", session="a", flag_id="f", name="early")
    late = ev("flag_set", "2026-11-01T01:10:00-08:00", session="b", flag_id="f", name="late")
    assert fold([late, early], "s1").flags["f"]["name"] == "late"


def test_round_trip_and_validation():
    e = ev("particle", T.format(0), particle_id="p1", status="candidate")
    assert SampleEvent.from_dict(e.as_dict()) == e
    with pytest.raises(ValueError):
        ev("flag_remove", T.format(0))
    with pytest.raises(ValueError):
        ev("particle", T.format(0))
    with pytest.raises(ValueError):
        ev("", T.format(0))
