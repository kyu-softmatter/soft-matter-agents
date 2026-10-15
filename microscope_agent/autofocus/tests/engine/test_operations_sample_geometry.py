"""Geometry fields, validation and the geometry / loading projections (T-027, WP-H)."""

import pytest

from dino_autofocus.engine.records import model_value
from dino_autofocus.engine.sample import (
    GEOMETRY_FIELDS,
    GEOMETRY_SET,
    LOADING_STEP,
    ORIENTATIONS,
    SAFETY_KEYS,
    GeometryError,
    SampleGeometry,
    SampleInfo,
    geometry_view,
    hole_loop,
    loading_view,
    validate_geometry,
)


def geo(values, t="2026-10-01T18:00:00-07:00", user="operator@example.test", session="s1"):
    return {"kind": GEOMETRY_SET, "values": values, "t": t, "user_id": user,
            "session_id": session}


def step(name, ok=True, t="2026-10-01T18:05:00-07:00", session="s1", **kw):
    return {"kind": LOADING_STEP, "step": name, "ok": ok, "t": t,
            "user_id": "operator@example.test", "session_id": session, **kw}


def test_the_field_list_matches_the_screen_contract():
    assert [f.key for f in GEOMETRY_FIELDS] == [
        "sample_size_mm", "chamber_shape", "hole_diameter_mm", "coverslip_thickness_um",
        "sample_thickness_um", "orientation"]
    assert SAFETY_KEYS == ("coverslip_thickness_um", "sample_thickness_um", "orientation")
    no_default = {f.key for f in GEOMETRY_FIELDS if f.default is None}
    assert {"sample_thickness_um", "orientation"} <= no_default
    assert ORIENTATIONS == ("upright", "flipped")


def test_validation_normalises_and_refuses():
    assert validate_geometry({"sample_size_mm": (24, 50), "orientation": "flipped",
                              "coverslip_thickness_um": "170"}) == {
        "sample_size_mm": [24.0, 50.0], "orientation": "flipped",
        "coverslip_thickness_um": 170.0}
    for bad, why in [({"orientation": "inverted"}, "not one of"),
                     ({"sample_thickness_um": -5}, "positive"),
                     ({"sample_thickness_um": True}, "not a number"),
                     ({"sample_size_mm": [24]}, "pair"),
                     ({"wobble": 1}, "unknown geometry field"),
                     ({}, "no geometry values"),
                     ({"sample_thickness_um": model_value(80.0, "head")}, "model output")]:
        with pytest.raises(GeometryError, match=why):
            validate_geometry(bad)


def test_sample_geometry_keeps_unknown_keys():
    g = SampleGeometry.from_dict({"orientation": "upright", "collar_setting": 0.17})
    assert g.values == {"orientation": "upright"} and g.extra == {"collar_setting": 0.17}
    assert g.get("coverslip_thickness_um") == 170.0 and g.get("sample_thickness_um") is None
    info = SampleInfo.from_dict({"sample_id": "20261001_1540_1", "geometry": g.to_dict()})
    assert info.geometry == g and SampleInfo.from_dict(info.to_dict()) == info


def test_geometry_view_shows_entered_default_and_not_set():
    v = geometry_view([geo({"sample_thickness_um": 80.0}),
                       geo({"sample_thickness_um": 90.0}, t="2026-10-01T18:01:00-07:00")])
    assert v["sample_thickness_um"] == {"value": 90.0, "source": {
        "kind": "entered", "by": "operator@example.test", "t": "2026-10-01T18:01:00-07:00"}}
    assert v["coverslip_thickness_um"]["source"]["kind"] == "default"
    assert v["orientation"] == {"value": None, "source": {"kind": "not_set", "by": None,
                                                          "t": None}}


def test_loading_needs_all_three_steps_in_this_session():
    entries = [geo({"sample_thickness_um": 80.0, "orientation": "upright"}),
               step("person"), step("image", t="2026-10-01T18:06:00-07:00")]
    assert loading_view(entries, "s1")["confirmed"]
    assert not loading_view(entries, "s2")["confirmed"]  # a new session starts unconfirmed
    no_orientation = [geo({"sample_thickness_um": 80.0}), step("person"), step("image")]
    s = loading_view(no_orientation, "s1")
    assert not s["geometry"]["done"] and not s["confirmed"]
    failed = entries[:2] + [step("image", ok=False, why="no edge in view")]
    s = loading_view(failed, "s1")
    assert s["image"]["done"] and not s["image"]["ok"] and s["image"]["why"] == "no edge in view"
    assert not s["confirmed"]


def test_a_safety_change_after_confirmation_clears_steps_two_and_three():
    base = [geo({"sample_thickness_um": 80.0, "orientation": "upright"}), step("person"),
            step("image")]
    same = loading_view(base + [geo({"orientation": "upright", "hole_diameter_mm": 6.0})], "s1")
    assert same["confirmed"]  # no safety value changed
    s = loading_view(base + [geo({"orientation": "flipped"})], "s1")
    assert s["geometry"]["done"] and not s["person"]["done"] and not s["image"]["done"]
    assert not s["confirmed"]


def test_hole_loop_tells_a_partial_arc_from_a_full_fit():
    full = {"fitted_at": "2026-10-01T18:00:00", "arc_deg": 352.0,
            "trace_stop": "back where the edge was first seen: full loop"}
    assert hole_loop(full)["closed"] and hole_loop(full)["fitted_at"] == "2026-10-01T18:00:00"
    partial = {"fitted_at": "2026-10-01T18:00:00", "arc_deg": 352.0, "trace_stop": "aborted"}
    assert not hole_loop(partial)["closed"]  # a stopped trace is partial whatever its arc
    assert hole_loop({"arc_deg": 352.0})["closed"]  # 2026-09-30 fit, no trace_stop yet
    assert not hole_loop({"arc_deg": 180.0})["closed"]
    assert hole_loop(None) == {"closed": False, "why": "no hole fit", "fitted_at": None,
                               "trace_stop": None, "arc_deg": None}


def test_hole_loop_prefers_edge_traces_flag():
    # the flag wins over the stop text and the arc in both directions
    assert not hole_loop({"closed_loop": False, "arc_deg": 352.0,
                          "trace_stop": "back where the edge was first seen: full loop"})["closed"]
    assert hole_loop({"closed_loop": True, "arc_deg": 300.0, "trace_stop": "done"})["closed"]
    assert hole_loop({"closed_loop": "yes", "arc_deg": 352.0})["closed"]  # not a bool: fallback
