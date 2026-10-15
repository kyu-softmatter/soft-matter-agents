from __future__ import annotations

import asyncio
import io
import json
import threading
import time

import numpy as np
import pytest
from PIL import Image
from server_fakes import FakeFrameEngine

from dino_autofocus.focus import vollath4
from dino_autofocus.server.ws import FrameBridge, encode_frame


@pytest.mark.parametrize(
    ("shape", "binning", "out"),
    [((3200, 3200), 4, (800, 800)), ((1200, 1600), 2, (600, 800)), ((300, 400), 1, (300, 400)),
     ((2048, 2048), 3, (682, 682))],
)
def test_encode_frame_size(shape, binning, out):
    rng = np.random.default_rng(1)
    frame, jpeg = encode_frame(rng.integers(0, 4096, shape, dtype=np.uint16), {"t": 1.0}, 3)
    assert (frame.binning, frame.height, frame.width) == (binning, *out)
    assert (frame.source_height, frame.source_width) == shape
    assert max(frame.width, frame.height) <= 800
    img = Image.open(io.BytesIO(jpeg))
    assert (img.format, img.mode, img.size) == ("JPEG", "L", (out[1], out[0]))
    assert frame.seq == 3 and frame.jpeg_bytes == len(jpeg)


def test_encode_frame_display_range():
    a = np.zeros((100, 100), np.uint16)
    a[:, 50:] = 4000
    frame, jpeg = encode_frame(a, {}, 1)
    assert (frame.display_min, frame.display_max) == (0.0, 4000.0)
    flat, _ = encode_frame(np.full((10, 10), 7, np.uint16), {}, 1)
    assert flat.display_max > flat.display_min  # no division by zero on a blank frame
    with pytest.raises(ValueError):
        encode_frame(np.zeros((4, 4, 3), np.uint8), {}, 1)


def test_encode_frame_live_focus_score():
    a = np.random.default_rng(1).integers(0, 4096, (120, 160), dtype=np.uint16)
    frame, _ = encode_frame(a, {}, 1)  # binning 1: the score of the frame itself
    assert frame.focus_metric == "vollath4"
    assert frame.focus_score == pytest.approx(vollath4(a.astype(np.float32)))
    tiny, _ = encode_frame(np.zeros((2, 2), np.uint16), {}, 1)
    assert tiny.focus_score is None and tiny.focus_metric is None


def test_encode_frame_gauge_reading():
    a = np.zeros((8, 8), np.uint16)
    dz = {"dz_dof": 2.5, "sigma_dof": None, "source": "mock_truth", "note": "mock truth",
          "sign_known": True}
    frame, _ = encode_frame(a, {"focus_dz": dz}, 1)
    assert frame.focus_dz is not None and frame.focus_dz.model_dump() == dz
    assert encode_frame(a, {"focus_dz": None}, 1)[0].focus_dz is None
    assert encode_frame(a, {"focus_dz": {"source": "guess"}}, 1)[0].focus_dz is None  # dropped


def test_bridge_rate_limit_and_latest_only(frame_engine):
    """200 frame_ready/s for 1 s from an engine thread: at most ~10 encodes, and a client that
    does not read keeps only the newest frame."""
    frame_engine.frame = (np.zeros((64, 64), np.uint16), {"t": 0.0})

    async def scenario():
        bridge = FrameBridge(frame_engine, max_fps=10.0)
        reader: asyncio.Queue = asyncio.Queue(maxsize=1)
        idle: asyncio.Queue = asyncio.Queue(maxsize=1)
        bridge.add(reader)
        bridge.add(idle)
        got = []

        async def read():
            while True:
                (meta, _), = await reader.get()  # one camera: one frame per batch
                got.append(json.loads(meta)["seq"])

        stop = threading.Event()

        def produce():
            while not stop.is_set():
                frame_engine.frame = (frame_engine.frame[0], {"t": time.time()})
                frame_engine.emit("frame_ready")
                time.sleep(0.005)

        t = threading.Thread(target=produce)
        task = asyncio.ensure_future(read())
        t.start()
        await asyncio.sleep(1.0)
        stop.set()
        t.join()
        await asyncio.sleep(0.25)  # let the last encode land
        task.cancel()
        assert idle.qsize() == 1
        last_idle = json.loads(idle.get_nowait()[0][0])["seq"]
        bridge.remove(reader)
        bridge.remove(idle)
        assert frame_engine.sinks == []
        return got, last_idle, bridge.seq

    got, last_idle, seq = asyncio.run(scenario())
    assert 5 <= len(got) <= 12
    assert frame_engine.frame_reads <= 12
    assert got == sorted(got)
    assert last_idle == seq  # the idle client holds the newest frame, not the first


class TwoCameraEngine(FakeFrameEngine):
    def __init__(self) -> None:
        super().__init__()
        self.frames: dict = {}

    def latest_frames(self):
        return dict(self.frames)


def test_encode_frame_declares_a_software_time_base():
    """P-01: the frame says its time came from the host clock, so two cameras' frames are
    paired by arrival and a merged view is display only (no timing physics from it)."""
    frame, _ = encode_frame(np.zeros((8, 8), np.uint16), {"t": 1.0, "camera": "Kinetix_blue"}, 1)
    assert frame.time_base == "software"
    assert json.loads(frame.model_dump_json())["time_base"] == "software"


def test_encode_frame_names_the_camera():
    frame, _ = encode_frame(np.zeros((8, 8), np.uint16), {"camera": "Kinetix_blue"}, 1)
    assert frame.camera == "Kinetix_blue"
    assert encode_frame(np.zeros((8, 8), np.uint16), {}, 2)[0].camera is None


def test_bridge_sends_each_camera_and_skips_one_that_did_not_change():
    eng = TwoCameraEngine()
    img = np.zeros((32, 32), np.uint16)
    eng.frames = {"Kinetix_blue": (img, {"t": 1.0, "camera": "Kinetix_blue"}),
                  "Kinetix_red": (img, {"t": 1.0, "camera": "Kinetix_red"})}

    async def scenario():
        bridge = FrameBridge(eng, max_fps=50.0)
        slot: asyncio.Queue = asyncio.Queue(maxsize=1)
        bridge.add(slot)
        eng.emit("frame_ready")
        first = await asyncio.wait_for(slot.get(), 2)
        eng.frames = {**eng.frames, "Kinetix_red": (img, {"t": 2.0, "camera": "Kinetix_red"})}
        eng.emit("frame_ready")
        second = await asyncio.wait_for(slot.get(), 2)
        bridge.remove(slot)
        return first, second

    first, second = asyncio.run(scenario())
    assert [json.loads(m)["camera"] for m, _ in first] == ["Kinetix_blue", "Kinetix_red"]
    assert [json.loads(m)["camera"] for m, _ in second] == ["Kinetix_red"]
    assert eng.frame_reads == 0  # a multi-camera engine is read through latest_frames


def test_a_client_that_joins_later_gets_an_idle_camera_at_once():
    eng = TwoCameraEngine()
    img = np.zeros((32, 32), np.uint16)
    eng.frames = {"Kinetix_blue": (img, {"t": 1.0, "camera": "Kinetix_blue"})}

    async def scenario():
        bridge = FrameBridge(eng, max_fps=50.0)
        first: asyncio.Queue = asyncio.Queue(maxsize=1)
        bridge.add(first)
        await asyncio.wait_for(first.get(), 2)
        late: asyncio.Queue = asyncio.Queue(maxsize=1)
        bridge.add(late)  # no new frame_ready: the blue camera is idle
        got = await asyncio.wait_for(late.get(), 2)
        bridge.remove(first)
        bridge.remove(late)
        return got

    got = asyncio.run(scenario())
    assert [json.loads(m)["camera"] for m, _ in got] == ["Kinetix_blue"]


def test_encode_frame_takes_the_runner_frame_time():
    img = np.zeros((8, 8), np.uint16)
    assert encode_frame(img, {"t_read": 1759300000.25}, 1)[0].t == 1759300000.25
    assert encode_frame(img, {"t": 5.0, "t_read": 9.0}, 1)[0].t == 5.0
