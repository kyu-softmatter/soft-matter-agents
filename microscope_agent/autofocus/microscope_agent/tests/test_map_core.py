# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/tests/test_map_core.py
# body-sha256: 08fd53006181c876aff7da398058cd65b319d9c722cddbaaa04b9cd15fba323e
"""The flat map files in the soft-matter-agents style: loaded by path, stdlib + numpy only.

map_geometry (stage <-> camera, sample geometry, hole loop), map_mosaic (mosaic, filters,
candidates), map_tiles (serpentine tiles, focus plane), map_edge (edge, circle fit).
Runs with `python -m unittest` from this folder and under pytest. Data are built inline."""

import importlib.util
import math
import sys
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


geometry = _load("_mic_map_geometry", SRC / "map_geometry.py")
mosaic = _load("_mic_map_mosaic", SRC / "map_mosaic.py")
tiles = _load("_mic_map_tiles", SRC / "map_tiles.py")
edge = _load("_mic_map_edge", SRC / "map_edge.py")

BENCH_M = [[0.61602, 0.00236], [0.00126, -0.61456]]  # 2026-09-30 4x, mirrored in y


class Graded:
    def __init__(self, value, grade):
        self.value, self.grade = value, grade


class Geometry(unittest.TestCase):
    def test_pixel_stage_round_trip_and_mirror(self):
        shape = (100, 120)
        x, y = geometry.tile_pixel_to_stage(BENCH_M, (1000.0, 2000.0), 10.0, 20.0, shape)
        col, row = geometry.stage_to_tile_pixel(BENCH_M, (1000.0, 2000.0), x, y, shape)
        self.assertAlmostEqual(col, 10.0, places=9)
        self.assertAlmostEqual(row, 20.0, places=9)
        # the centre pixel images the tile's stage point; +col runs to -x (mirrored image)
        cx, cy = geometry.tile_pixel_to_stage(BENCH_M, (0.0, 0.0), 59.5, 49.5, shape)
        self.assertAlmostEqual(cx, 0.0)
        self.assertAlmostEqual(cy, 0.0)
        self.assertLess(geometry.tile_pixel_to_stage(BENCH_M, (0, 0), 69.5, 49.5, shape)[0], 0)

    def test_um_per_px_and_calibration_of(self):
        cal = geometry.calibration_of(np.asarray(BENCH_M))
        self.assertAlmostEqual(cal["um_per_px"], geometry.um_per_px(BENCH_M))
        self.assertAlmostEqual(cal["um_per_px"], 1.6252, places=3)
        self.assertAlmostEqual(cal["angle_deg"], 0.117, places=2)

    def test_validate_geometry(self):
        out = geometry.validate_geometry({"sample_thickness_um": 120, "orientation": "upright",
                                          "sample_size_mm": (24, 50)})
        self.assertEqual(out, {"sample_thickness_um": 120.0, "orientation": "upright",
                               "sample_size_mm": [24.0, 50.0]})
        for bad in ({"sample_thickness_um": -1}, {"sample_thickness_um": True},
                    {"orientation": "sideways"}, {"nope": 1}, {}):
            with self.assertRaises(geometry.GeometryError):
                geometry.validate_geometry(bad)
        with self.assertRaisesRegex(geometry.GeometryError, "model output"):
            geometry.validate_geometry({"sample_thickness_um": Graded(120.0, "model")})
        self.assertEqual(geometry.validate_geometry(
            {"sample_thickness_um": Graded(120.0, "measured")}), {"sample_thickness_um": 120.0})

    def test_geometry_and_loading_views(self):
        events = [{"kind": "geometry_set", "values": {"sample_thickness_um": 100.0},
                   "user_id": "u", "t": "t1"},
                  {"kind": "loading_step", "step": "person", "session_id": "s", "user_id": "u"},
                  {"kind": "loading_step", "step": "image", "ok": True, "session_id": "s"}]
        view = geometry.geometry_view(events)
        self.assertEqual(view["sample_thickness_um"]["source"]["kind"], "entered")
        self.assertEqual(view["coverslip_thickness_um"]["source"]["kind"], "default")
        self.assertEqual(view["orientation"]["source"]["kind"], "not_set")
        self.assertFalse(geometry.loading_view(events, "s")["confirmed"])  # no orientation
        events.insert(0, {"kind": "geometry_set", "values": {"orientation": "upright"}})
        self.assertTrue(geometry.loading_view(events, "s")["confirmed"])
        # a safety change after the checks clears them (G6)
        events.append({"kind": "geometry_set", "values": {"sample_thickness_um": 90.0}})
        self.assertFalse(geometry.loading_view(events, "s")["person"]["done"])

    def test_hole_loop(self):
        self.assertFalse(geometry.hole_loop(None)["closed"])
        self.assertTrue(geometry.hole_loop({"closed_loop": True})["closed"])
        self.assertTrue(geometry.hole_loop({"arc_deg": 352})["closed"])
        self.assertFalse(geometry.hole_loop({"arc_deg": 200})["closed"])
        self.assertTrue(geometry.hole_loop({"trace_stop": "back where ...: full loop"})["closed"])
        self.assertFalse(geometry.hole_loop({"trace_stop": "edge lost"})["closed"])

    def test_sample_geometry_keeps_unknown_keys(self):
        g = geometry.SampleGeometry.from_dict({"orientation": "flipped", "future": 1})
        self.assertEqual(g.get("orientation"), "flipped")
        self.assertEqual(g.get("coverslip_thickness_um"), 170.0)
        self.assertEqual(g.to_dict(), {"future": 1, "orientation": "flipped"})


class Mosaic(unittest.TestCase):
    def test_filters_keep_a_constant_image_and_the_light(self):
        a = np.full((40, 33), 7.0)
        np.testing.assert_allclose(mosaic.gaussian_filter(a, 25.0), 7.0, rtol=1e-12)
        np.testing.assert_allclose(mosaic.gaussian_laplace(a, 1.5), 0.0, atol=0.01)  # truncated
        rng = np.random.default_rng(1)
        b = rng.normal(size=(30, 31))
        m = mosaic.maximum_filter(b, 3)
        self.assertEqual(m[10, 10], b[9:12, 9:12].max())
        self.assertEqual(m[0, 0], b[0:2, 0:2].max())  # reflect: the edge row repeats

    def test_dark_blob_is_a_candidate_at_its_stage_point(self):
        yy, xx = np.mgrid[0:96, 0:96]
        img = 1000 - 400 * np.exp(-((yy - 40) ** 2 + (xx - 60) ** 2) / (2 * 2.0 ** 2))
        img = img + np.random.default_rng(2).normal(0, 2, img.shape)
        blobs = mosaic.detect_blobs(img)
        self.assertTrue(blobs)
        self.assertEqual((blobs[0]["col"], blobs[0]["row"]), (60.0, 40.0))
        tile = mosaic.Tile("tile_r0c0", 500.0, 600.0, img)
        found = mosaic.find_candidates([tile], BENCH_M)
        x, y = geometry.tile_pixel_to_stage(BENCH_M, (500.0, 600.0), 60.0, 40.0, img.shape)
        self.assertAlmostEqual(found[0]["x_um"], round(x, 2))
        self.assertAlmostEqual(found[0]["y_um"], round(y, 2))
        self.assertEqual(found[0]["source"], "classical_candidate")
        self.assertEqual(found[0]["grade"], "computed")

    def test_mosaic_is_in_stage_orientation(self):
        img = np.zeros((64, 64))
        img[:, :8] = 100.0  # bright on the left of the camera frame
        mos, meta = mosaic.build_mosaic([mosaic.Tile("t", 0.0, 0.0, img)], BENCH_M)
        self.assertTrue(meta.flip_cols and not meta.transpose)
        self.assertEqual(mos.shape, (8, 8))
        self.assertGreater(mos[:, -1].mean(), mos[:, 0].mean())  # left of the image = +x
        col, row = mosaic.stage_to_mosaic(meta, 0.0, 0.0)
        self.assertEqual(mosaic.mosaic_to_stage(meta, col, row), (0.0, 0.0))


class Tiles(unittest.TestCase):
    def test_grid_is_serpentine(self):
        pts, pitch, n = tiles.grid((0.0, 0.0), 3000.0, 3900.0, 0.15)
        self.assertEqual(n, 2)
        self.assertAlmostEqual(pitch, 3315.0)
        self.assertEqual([(r, c) for _, _, r, c in pts], [(0, 0), (0, 1), (1, 1), (1, 0)])
        names = [t["name"] for t in tiles.tile_list(pts)]
        self.assertEqual(names, ["tile_r0c0", "tile_r0c1", "tile_r1c1", "tile_r1c0"])
        self.assertEqual(tiles.square_box_um((1.0, 2.0), tiles.half_side_um(4.0, 500.0)),
                         [-2499.0, 2501.0, -2498.0, 2502.0])

    def test_fit_plane(self):
        pts = [(x, y, 2950 + 0.002 * x - 0.001 * y) for x in (0, 1000, 2000) for y in (0, 3000)]
        plane = tiles.fit_plane(pts)
        self.assertEqual(plane["kind"], "plane")
        self.assertAlmostEqual(plane["slope_x_um_per_mm"], 2.0)
        self.assertAlmostEqual(tiles.plane_z(plane, 500, 500), 2950.5)
        self.assertEqual(tiles.fit_plane([(0, 0, 1.0), (1, 1, 3.0)])["z0_um"], 2.0)
        self.assertIsNone(tiles.fit_plane([]))

    def test_camera_calibration(self):
        bench = {"default_um_per_px": 1.625, "default_m_px_per_um": BENCH_M,
                 "default_source": "2026-09-30 4x calibration"}
        um, m, src = tiles.camera_calibration(None, **bench)
        self.assertEqual((um, src), (1.625, "2026-09-30 4x calibration"))
        self.assertEqual(m, [[float(v) for v in r] for r in BENCH_M])
        self.assertEqual(tiles.camera_calibration({"M_px_per_um": [[1, 0], [0, 1]]}, **bench)[1],
                         [[1.0, 0.0], [0.0, 1.0]])


class Edge(unittest.TestCase):
    def test_remove_small_regions(self):
        mask = np.zeros((20, 20), bool)
        mask[:, 10:] = True  # the chamber's bright side
        mask[3:5, 2:4] = True  # debris, 4 px
        mask[12, 15] = False  # a hole in the bright side, 1 px
        mask[8, 2:10] = True  # touches the bright side: part of it
        out = edge.remove_small_regions(mask, 5)
        self.assertFalse(out[3:5, 2:4].any())
        self.assertTrue(out[12, 15])
        self.assertTrue(out[8, 2:10].all())
        diag = np.zeros((6, 6), bool)
        diag[1, 1] = diag[2, 2] = True  # diagonal: two regions of 1 (4-neighbour)
        self.assertFalse(edge.remove_small_regions(diag, 2).any())

    def test_find_edge_on_a_half_dark_frame(self):
        img = np.full((300, 300), 1000.0)
        img[:, :170] = 200.0
        img += np.random.default_rng(3).normal(0, 5, img.shape)
        e = edge.find_edge(img)
        self.assertIsNotNone(e)
        self.assertAlmostEqual(e["p"][0], 170.0, delta=3)
        self.assertGreater(e["n"][0], 0.9)  # dark -> bright points to +x

    def test_hole_fit(self):
        a = np.radians(np.arange(0, 350, 10))
        pts = np.c_[1000 + 2500 * np.cos(a), -500 + 2500 * np.sin(a)]
        fit = edge.hole_fit(pts)
        self.assertEqual(fit["centre_um"], [1000.0, -500.0])
        self.assertEqual(fit["diameter_mm"], 5.0)
        self.assertEqual(fit["n_points"], len(pts))
        self.assertAlmostEqual(fit["arc_deg"], 340.0)
        self.assertIsNone(edge.hole_fit(pts[:5]))
        self.assertTrue(math.isclose(edge.arc_degrees(pts, np.array([1000, -500])), 340.0))


if __name__ == "__main__":
    unittest.main()
