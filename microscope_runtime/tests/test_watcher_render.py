"""Card 076 part A: the watcher's renderer and the reduced-image conversion.

    python -m unittest microscope_runtime/tests/test_watcher_render.py

Pure and on synthetic frames. No device, no core, no clock: the same inputs
give the same bytes, and a value with no input is absent and never zero.
Written AFTER the renderer, and watched failing by switching each rule of it
off in turn, not before the code existed (said so in the commit).
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import struct
import sys
import unittest
import zlib
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


R = _load("_watcher_render_under_test", SRC / "watcher_render.py")

OPTIONS = [{"id": "as_planned"}, {"id": "particles_lost", "about": "particle_count"},
           {"id": "drifting", "about": "drift_px"}, {"id": "focus_lost", "about": "focus_score"},
           {"id": "unsure"}]
CONVERSION = {"downscale": {"longest_side_px": 16, "method": "area_mean"},
              "stretch": {"method": "percentile", "low_percentile": 1, "high_percentile": 99},
              "saturated": {"marked_as": "red"}}


def block(given=False, ceiling=None, drift=True, particles=True):
    image = {"frame_stats": {"metric": "vollath4", "bin_px": 4,
                             "camera_ceiling": {"gap": "full_scale_gap"} if ceiling is None
                             else {"number": "camera_full_scale"}},
             "intensity": {"settle_after_s": 5},
             "frames": {"given": given}}
    if given:
        image["frames"]["conversion"] = copy.deepcopy(CONVERSION)
    if drift:
        image["drift"] = {"reference_frame": 0, "method": "phase_correlation", "arguments": {"upsample": 10}}
    if particles:
        image["particles"] = {"detector": "log_blob",
                              "arguments": {"sigma_px": 2, "threshold": 0.1, "min_separation_px": 5}}
    return {"options": copy.deepcopy(OPTIONS), "cadence_s": 5, "question_budget_s": 2, "image": image}


def blobs(shape=(64, 64), centres=((16, 16), (16, 48), (48, 32)), seed=1, amp=3000.0, noise=20.0):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:shape[0], 0:shape[1]]
    a = 500.0 + rng.normal(0, noise, shape)
    for cy, cx in centres:
        a += amp * np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / (2 * 2.0 ** 2))
    return np.clip(a, 0, 65535).astype(np.uint16)


def state_input(**over):
    inp = {"seq": 3, "block": block(), "ceiling": 65535, "ceiling_gap": None,
           "frame": blobs(), "frame_index": 12, "frame_t_mono": 10.0,
           "reference": blobs(seed=1), "reference_frame_index": 0,
           "level": 1000.0, "level_absent_because": None,
           "snapshot": {"t_mono": 9.9, "states": {"stand_ti2e": {"state": {"PFS": {"State": "Off"}}}}},
           "tick_t_mono": 10.5, "events": [], "channels": {"stand_ti2e": {"read_back": True}}}
    inp.update(over)
    return inp


class T1ThePlanBlockIsChecked(unittest.TestCase):
    def refused(self, mutate, pattern):
        b = block(given=True, ceiling=65535)
        mutate(b)
        with self.assertRaisesRegex(R.RenderRefused, pattern):
            R.check_plan_block(b)

    def test_a_good_block_passes(self):
        R.check_plan_block(block(given=True, ceiling=65535))
        R.check_plan_block(block(given=False))

    def test_an_option_about_a_value_that_is_not_rendered_is_refused_and_named(self):
        self.refused(lambda b: b["options"].insert(1, {"id": "blurry", "about": "blur_amount"}),
                     "blur_amount")

    def test_an_unknown_metric_is_refused(self):
        self.refused(lambda b: b["image"]["frame_stats"].update(metric="sharpness9"), "sharpness9")

    def test_an_unknown_drift_method_is_refused(self):
        self.refused(lambda b: b["image"]["drift"].update(method="optical_flow"), "optical_flow")

    def test_drift_arguments_must_be_exactly_upsample(self):
        self.refused(lambda b: b["image"]["drift"].update(arguments={"upsample": 10, "window": 3}),
                     "exactly")

    def test_an_unknown_detector_is_refused(self):
        self.refused(lambda b: b["image"]["particles"].update(detector="cellpose"), "cellpose")

    def test_detector_arguments_have_no_defaults(self):
        self.refused(lambda b: b["image"]["particles"].update(arguments={"sigma_px": 2, "threshold": 0.1}),
                     "log_blob arguments")

    def test_detector_arguments_with_a_key_the_detector_does_not_take_are_refused(self):
        self.refused(lambda b: b["image"]["particles"]["arguments"].update(gain=3), "log_blob arguments")

    def test_whether_images_are_given_is_not_guessed(self):
        self.refused(lambda b: b["image"].pop("frames"), "not stated")

    def test_images_given_without_a_conversion_is_refused(self):
        self.refused(lambda b: b["image"]["frames"].pop("conversion"), "no conversion")

    def test_an_unknown_saturated_mark_is_refused(self):
        self.refused(lambda b: b["image"]["frames"]["conversion"]["saturated"].update(marked_as="blue"),
                     "blue")

    def test_the_ceiling_is_a_number_of_the_plan_or_a_named_gap(self):
        plan = {"numbers": [{"name": "camera_full_scale", "value": 65535, "unit": "ADU"}]}
        self.assertEqual(R.resolve_ceiling(block(ceiling=65535), plan), (65535, None))
        self.assertEqual(R.resolve_ceiling(block(ceiling=None), plan), (None, "full_scale_gap"))
        with self.assertRaisesRegex(R.RenderRefused, "not in the plan"):
            R.resolve_ceiling(block(ceiling=65535), {"numbers": []})


class T2TheTextIsPureAndVersioned(unittest.TestCase):
    def test_the_same_inputs_give_the_same_bytes(self):
        a = R.render(state_input())[0]
        b = R.render(state_input())[0]
        self.assertEqual(a, b)
        self.assertEqual(hashlib.sha256(a.encode()).hexdigest(), hashlib.sha256(b.encode()).hexdigest())

    def test_the_text_names_the_renderer_version(self):
        self.assertIn(R.RENDERER_VERSION, R.render(state_input())[0])

    def test_inputs_are_not_changed(self):
        inp = state_input()
        before = inp["frame"].copy()
        R.render(inp)
        self.assertTrue(np.array_equal(before, inp["frame"]))

    def test_every_frame_statistic_is_rendered_with_the_plans_arguments(self):
        inp = state_input()
        text, values = R.render(inp)
        want = R.fc.frame_stats(inp["frame"], "vollath4", ceiling=65535, bin_px=4)
        for name, got in (("focus_score", want.score), ("mean", want.mean), ("median", want.median),
                          ("p999", want.p999), ("max", float(want.max)),
                          ("saturated_fraction", want.saturated_fraction)):
            self.assertEqual(values[name]["value"], got, name)
            self.assertEqual(values[name]["frame_index"], 12)
            self.assertIn(name, text)
        self.assertEqual(values["focus_score"]["arguments"], {"metric": "vollath4", "bin_px": 4,
                                                              "ceiling": 65535})

    def test_a_gap_ceiling_makes_the_saturated_fraction_absent_and_names_the_gap(self):
        _, values = R.render(state_input(ceiling=None, ceiling_gap="full_scale_gap"))
        v = values["saturated_fraction"]
        self.assertIsNone(v["value"])
        self.assertIn("full_scale_gap", v["absent_because"])
        self.assertIsNotNone(values["mean"]["value"])               # the rest is still rendered

    def test_with_no_frame_every_image_value_is_absent_and_none_is_zero(self):
        _, values = R.render(state_input(frame=None, frame_index=None, frame_t_mono=None))
        for name, v in values.items():
            self.assertIsNone(v["value"], name)
            self.assertIn("absent_because", v, name)

    def test_a_value_that_is_a_real_zero_is_not_called_absent(self):
        flat = np.full((32, 32), 100, dtype=np.uint16)
        _, values = R.render(state_input(frame=flat, reference=flat))
        self.assertEqual(values["particle_count"]["value"], 0)
        self.assertNotIn("absent_because", values["particle_count"])

    def test_no_value_is_ever_zero_and_absent_at_once(self):
        for inp in (state_input(), state_input(frame=None, frame_index=None, frame_t_mono=None),
                    state_input(level=None, ceiling=None, ceiling_gap="g", reference=None)):
            for name, v in R.render(inp)[1].items():
                self.assertEqual("absent_because" in v, v["value"] is None, name)


class T3Intensity(unittest.TestCase):
    def test_before_the_light_settles_the_value_is_absent_and_says_settling(self):
        _, values = R.render(state_input(level=None, level_absent_because="settling: 2.0 s of 5 s"))
        v = values["intensity_normalised"]
        self.assertIsNone(v["value"])
        self.assertIn("settling", v["absent_because"])

    def test_it_is_the_whole_frame_total_over_the_settled_level(self):
        inp = state_input(level=2.0e6)
        _, values = R.render(inp)
        self.assertAlmostEqual(values["intensity_normalised"]["value"],
                               float(inp["frame"].astype(np.float64).sum()) / 2.0e6)

    def test_it_is_not_normalised_to_the_frame_that_is_being_rendered(self):
        a = state_input(level=1.0e6)
        b = state_input(level=1.0e6, frame=(blobs() // 2))
        self.assertLess(R.render(b)[1]["intensity_normalised"]["value"],
                        R.render(a)[1]["intensity_normalised"]["value"])


class T4Drift(unittest.TestCase):
    def test_a_whole_pixel_shift_is_found(self):
        ref = blobs()
        self.assertEqual(R.phase_correlation(ref, np.roll(ref, (3, -2), axis=(0, 1)), 10), (3.0, -2.0))

    def test_no_shift_is_zero_and_a_real_zero(self):
        ref = blobs()
        _, values = R.render(state_input(frame=ref, reference=ref))
        self.assertEqual(values["drift_px"]["value"], 0.0)
        self.assertNotIn("absent_because", values["drift_px"])

    def test_the_magnitude_is_the_hypotenuse(self):
        ref = blobs()
        _, values = R.render(state_input(frame=np.roll(ref, (3, 4), axis=(0, 1)), reference=ref))
        self.assertAlmostEqual(values["drift_px"]["value"], 5.0, places=6)

    def test_without_the_reference_frame_it_is_absent_and_names_which(self):
        _, values = R.render(state_input(reference=None))
        self.assertIsNone(values["drift_px"]["value"])
        self.assertIn("reference frame 0", values["drift_px"]["absent_because"])

    def test_frames_of_different_shapes_are_refused(self):
        with self.assertRaisesRegex(R.RenderRefused, "shape"):
            R.phase_correlation(np.zeros((8, 8)), np.zeros((9, 9)), 1)


class T5Particles(unittest.TestCase):
    def count(self, centres):
        return R.log_blob_count(blobs(centres=centres), 2, 0.1, 5)

    def test_three_separate_blobs_are_three(self):
        self.assertEqual(self.count(((16, 16), (16, 48), (48, 32))), 3)

    def test_one_blob_is_one(self):
        self.assertEqual(self.count(((32, 32),)), 1)

    def test_the_count_is_repeatable(self):
        self.assertEqual(self.count(((16, 16), (48, 48))), self.count(((16, 16), (48, 48))))

    def test_a_flat_frame_has_no_blobs(self):
        self.assertEqual(R.log_blob_count(np.full((32, 32), 7, dtype=np.uint16), 2, 0.1, 5), 0)


def decode_png(data: bytes):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, chunks = 8, {}
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        chunks.setdefault(tag, b"")
        chunks[tag] += data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        assert crc == zlib.crc32(tag + data[pos + 8:pos + 8 + length]) & 0xFFFFFFFF
        pos += 12 + length
    w, h, depth, ctype = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
    raw = zlib.decompress(chunks[b"IDAT"])
    rows = [raw[y * (1 + 3 * w) + 1:(y + 1) * (1 + 3 * w)] for y in range(h)]
    img = np.frombuffer(b"".join(rows), dtype=np.uint8).reshape(h, w, 3)
    return w, h, depth, ctype, img


class T6TheReducedImage(unittest.TestCase):
    def setUp(self):
        self.frame = blobs(shape=(64, 64), amp=20000.0)

    def make(self, frame=None, ceiling=65535, **kw):
        return R.convert_frame(self.frame if frame is None else frame, CONVERSION, ceiling, **kw)

    def test_the_image_is_an_ordinary_8_bit_png_no_larger_than_the_plan_says(self):
        data, info = self.make()
        w, h, depth, ctype, img = decode_png(data)
        self.assertEqual((depth, ctype), (8, 2))
        self.assertLessEqual(max(w, h), CONVERSION["downscale"]["longest_side_px"])
        self.assertEqual(info["shape"], [h, w])
        self.assertEqual(img.dtype, np.uint8)

    def test_the_same_frame_and_parameters_give_the_same_bytes_and_hash(self):
        a, ia = self.make()
        b, ib = self.make()
        self.assertEqual(a, b)
        self.assertEqual(ia["sha256"], ib["sha256"])
        self.assertEqual(ia["sha256"], hashlib.sha256(a).hexdigest())

    def test_the_recorded_stretch_limits_reproduce_the_image_from_the_raw_frame(self):
        a, info = self.make()
        b, _ = self.make(limits=info["stretch_limits"])
        self.assertEqual(a, b)
        c, _ = self.make(limits={"low": info["stretch_limits"]["low"], "high": info["stretch_limits"]["high"] * 2})
        self.assertNotEqual(a, c)

    def test_the_limits_are_in_raw_adu_and_come_from_the_raw_frame(self):
        _, info = self.make()
        self.assertAlmostEqual(info["stretch_limits"]["low"], float(np.percentile(self.frame, 1)))
        self.assertAlmostEqual(info["stretch_limits"]["high"], float(np.percentile(self.frame, 99)))

    def test_a_gap_ceiling_refuses_rather_than_marking_against_an_assumed_count(self):
        with self.assertRaisesRegex(R.RenderRefused, "gap"):
            R.convert_frame(self.frame, CONVERSION, None)

    def test_a_flat_frame_has_no_contrast_to_stretch(self):
        with self.assertRaisesRegex(R.RenderRefused, "flat"):
            R.convert_frame(np.full((32, 32), 5, dtype=np.uint16), CONVERSION, 65535)

    def test_saturated_pixels_are_counted_on_the_raw_frame_and_marked_red(self):
        frame = self.frame.copy()
        frame[0:2, 0:2] = 65535
        data, info = R.convert_frame(frame, CONVERSION, 65535)
        self.assertEqual(info["saturated_pixels"], int((frame >= 65535).sum()))
        *_, img = decode_png(data)
        self.assertEqual(tuple(img[0, 0]), (255, 0, 0))

    def test_no_saturation_means_no_red(self):
        data, info = self.make(ceiling=65535)
        *_, img = decode_png(data)
        self.assertEqual(info["saturated_pixels"], 0)
        self.assertFalse(((img[..., 0] == 255) & (img[..., 1] == 0) & (img[..., 2] == 0)).any())

    def test_nothing_returned_holds_the_raw_frame(self):
        data, info = self.make()
        self.assertIsInstance(data, bytes)
        self.assertFalse([k for k, v in info.items() if isinstance(v, np.ndarray)])
        self.assertLess(len(data), self.frame.nbytes)

    def test_the_conversion_is_versioned(self):
        self.assertEqual(self.make()[1]["conversion_version"], R.CONVERSION_VERSION)


class T7Hardware(unittest.TestCase):
    def test_a_channel_this_run_did_not_open_is_rendered_as_not_open(self):
        snap = {"t_mono": 9.9, "states": {"camera_blue": {"not_open": True, "why": "no interface was opened"}}}
        text, _ = R.render(state_input(snapshot=snap, channels={"camera_blue": {"read_back": True}}))
        self.assertIn("camera_blue: not open in this run (no interface was opened)", text)

    def test_a_channel_that_could_not_be_read_at_once_is_not_given_its_last_value(self):
        snap = {"t_mono": 9.9, "states": {"stand_ti2e": {"not_read": True, "why": "a command holds it"}}}
        text, _ = R.render(state_input(snapshot=snap))
        self.assertIn("stand_ti2e: not read at this tick (a command holds it)", text)
        self.assertNotIn("PFS", text)

    def test_a_channel_with_no_read_back_is_unreadable_and_its_command_is_labelled_commanded(self):
        snap = {"t_mono": 9.9, "states": {"optical_tweezers": {"read_back": False,
                                                                "commanded": {"trap": 1}}}}
        text, _ = R.render(state_input(snapshot=snap, channels={"optical_tweezers": {"read_back": False}}))
        self.assertIn("optical_tweezers: unreadable, no read-back exists", text)
        self.assertIn('{"trap":1} (commanded, not read)', text)

    def test_an_unreadable_channel_that_was_never_commanded_says_nothing_was(self):
        snap = {"t_mono": 9.9, "states": {"laser_combiner": {"commanded": None}}}
        text, _ = R.render(state_input(snapshot=snap, channels={"laser_combiner": {"read_back": False}}))
        self.assertIn("last commanded nothing (commanded, not read)", text)

    def test_a_readable_channel_carries_its_age_and_its_values(self):
        text, _ = R.render(state_input())
        self.assertIn('stand_ti2e: {"state":{"PFS":{"State":"Off"}}} (read at snapshot t_mono 9.9 s)', text)
        self.assertIn("snapshot: t_mono 9.9 s (age 0.6 s)", text)

    def test_no_snapshot_yet_is_said(self):
        text, _ = R.render(state_input(snapshot=None))
        self.assertIn("no snapshot has been taken yet", text)


class T8RecentEvents(unittest.TestCase):
    def test_commands_and_monitor_results_are_listed_in_order_with_their_keys(self):
        events = [{"event": "apply", "t_mono": 10.1, "channel": "stand_ti2e", "action": "set",
                   "verification": "readback", "params": {"z": 1}},
                  {"event": "stop_criterion_violated", "t_mono": 10.2, "criterion": "readback"}]
        text, _ = R.render(state_input(events=events))
        a = text.index("apply; channel=stand_ti2e")
        b = text.index("stop_criterion_violated; criterion=readback")
        self.assertLess(a, b)
        self.assertIn('params={"z":1}', text)

    def test_snapshots_and_the_watchers_own_events_are_not_listed(self):
        events = [{"event": "snapshot", "t_mono": 10.0}, {"event": "watcher_state", "t_mono": 10.0},
                  {"event": "watcher_flag", "t_mono": 10.0}]
        text, _ = R.render(state_input(events=events))
        self.assertIn("RECENT EVENTS (since the previous tick)\nnone", text)


if __name__ == "__main__":
    unittest.main()
