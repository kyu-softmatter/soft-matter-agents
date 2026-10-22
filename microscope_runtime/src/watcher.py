"""The run-time watcher (card 076 parts B and D, plan.md 13.4): it records, and never acts.

IT IS HANDED DATA AND HANDS BACK EVENTS, AND THAT IS ALL IT CAN DO. It holds no
device module, no core, no reference to abort, the stop channel or dispatch, and
it imports none of them, so it can command nothing and stop nothing: plan.md
13.1 item 1 is enforced by what this object can reach and not by what it
chooses. The orchestrator hands it frames (the tee that feeds the frame tap, a
copy swapped in under a lock, nothing queued) and, at the plan's cadence, a
hardware snapshot it read itself; the watcher puts its events in an outbox and
the orchestrator records them. There is no threshold, no action on an answer
and no prompt for the person (13.1 item 3).

One question is in flight at a time. A tick that falls due while one is open
still writes its state, with `asked: false`, and is counted in `skipped_so_far`;
it is never queued. A question past its budget is `watcher_unanswered`, and its
late answer is dropped.

Backends sit behind one interface: state text, the options in order, and the two
reduced images when the plan gives them, in; per-option probabilities out. Built
now: `none` (records, asks nobody) and a deterministic test double that is named
as not a model in everything it produces and is refused on every backend but
mock. A model is a third backend on its own card. The backend is a RUN argument,
never a plan field.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import queue
import sys
import threading
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)                             # type: ignore[union-attr]
    return module


R = _load("_watcher_render_for_watcher", _HERE / "watcher_render.py")

#: What the questions the backends get are versioned by. A model backend adds its own prompt on
#: its own card; this names the question as the watcher poses it: the state text and the options.
PROMPT_VERSION = "dm3-watcher-1"


class BackendRefused(ValueError):
    """The backend asked for cannot answer on this run's device backend, or does not exist."""


class Backend:
    """The one interface. `ask` takes the state text, the options in order and the images or None."""

    name = "backend"
    version: str | None = None
    kind = "none"

    def ask(self, state_text: str, options: list[dict], images: list[dict] | None) -> dict:
        raise NotImplementedError

    def judge(self, judgement: str, prompt: str, allowed_codes: list[str], images: list[dict] | None) -> dict:
        """DM-1, DM-2 or DM-4 (plan.md 13.5, card 081): the prompt text, the plan's codes, the reduced images
        or None in; `{"status", "answer", "reason_codes" | "cause_label", "score"?, "error"?}` out."""
        raise NotImplementedError


class NoneBackend(Backend):
    name, version, kind = "none", None, "none"

    def ask(self, state_text, options, images):
        raise RuntimeError("the none backend records states and asks nobody")

    def judge(self, judgement, prompt, allowed_codes, images):
        raise RuntimeError("the none backend asks nobody")


class TestDoubleBackend(Backend):
    """Deterministic probabilities from the sha256 of the state text. NOT A MODEL, and it says so.

    Its answers exist so mock runs can exercise the whole record. It is refused on every device
    backend but mock, so no instrument run ever carries one.
    """

    __test__ = False
    name, version, kind = "test_double", "1", "test_double"

    def ask(self, state_text, options, images):
        ids = [o["id"] for o in options]
        digest = hashlib.sha256((state_text + "|" + ",".join(ids)).encode("utf-8")).digest()
        weights = [digest[i % len(digest)] + 1 for i in range(len(ids))]
        total = float(sum(weights))
        return {"probabilities": {i: w / total for i, w in zip(ids, weights)}}

    def judge(self, judgement, prompt, allowed_codes, images):
        """Deterministic from the prompt text: about one in six abstains, the rest answer. Not a model."""
        digest = hashlib.sha256((judgement + "|" + prompt + "|" + ",".join(allowed_codes)).encode("utf-8")).digest()
        if digest[0] % 6 == 0:
            return {"status": "ABSTAIN"}
        yes = digest[1] % 2 == 0
        if judgement == "DM-4":
            causes = [c for c in allowed_codes if c != "unknown"]
            if yes and causes:
                return {"status": "OK", "answer": "YES", "cause_label": causes[digest[2] % len(causes)]}
            return {"status": "OK", "answer": "NO", "cause_label": "unknown"}
        return {"status": "OK", "answer": "YES" if yes else "NO",
                "reason_codes": [allowed_codes[digest[2] % len(allowed_codes)]]}


def make_backend(name: str, device_backend: str) -> Backend:
    """The backend the run's command line names. The test double only beside the mock."""
    if name == "none":
        return NoneBackend()
    if name == "test_double":
        if device_backend != "mock":
            raise BackendRefused("the test double is refused on every backend but mock, so no "
                                 f"instrument run ever carries its answer; this run's backend is {device_backend!r}")
        return TestDoubleBackend()
    raise BackendRefused(f"unknown watcher backend {name!r}; the built ones are 'none' and 'test_double'")


def dm3_reading(choice: str) -> dict:
    """How a watcher answer reads as DM-3 (plan.md 13.5): NO is as_planned, ABSTAIN is unsure."""
    if choice == "as_planned":
        return {"judgement": "DM-3", "status": "OK", "answer": "NO"}
    if choice == "unsure":
        return {"judgement": "DM-3", "status": "ABSTAIN"}
    return {"judgement": "DM-3", "status": "OK", "answer": "YES", "class": choice}


def _backend_record(backend: Backend) -> dict:
    return {"name": backend.name, "version": backend.version, "kind": backend.kind}


def build(plan: dict, backend: Backend, run_folder, clock, light_command):
    """A started-able watcher and the event to record right after run_started, or None and the off event.

    `clock()` is the run's t_mono. `light_command(event)` says whether a log event is a command to a
    light source (a plain function, so the watcher holds nothing of the orchestrator). A plan with no
    watcher block, or one the renderer cannot render, is `watcher_off` and the run goes on: in shadow
    mode nothing depends on the watcher, and refusing would turn an advisory signal into a gate.
    """
    block = plan.get("watcher")
    if block is None:
        return None, {"event": "watcher_off", "t_mono": clock(),
                      "watcher": {"why": "plan_declares_no_watcher"}}
    try:
        R.check_plan_block(block)
        ceiling, gap = R.resolve_ceiling(block, plan)
    except R.RenderRefused as exc:
        return None, {"event": "watcher_off", "t_mono": clock(),
                      "watcher": {"why": "did_not_start", "detail": str(exc)}}
    watcher = Watcher(block, backend, Path(run_folder), clock, light_command, ceiling, gap)
    started = {"event": "watcher_started", "from": "watcher", "t_mono": clock(),
               "watcher": {"backend": _backend_record(backend), "renderer_version": R.RENDERER_VERSION,
                           "options": [o["id"] for o in block["options"]], "cadence_s": block["cadence_s"],
                           "question_budget_s": block["question_budget_s"]}}
    return watcher, started


class Watcher:
    def __init__(self, block, backend, folder, clock, light_command, ceiling, ceiling_gap) -> None:
        self._block = copy.deepcopy(block)
        self._backend = backend
        self._folder = Path(folder)
        self._clock = clock
        self._light = light_command
        self._ceiling, self._gap = ceiling, ceiling_gap
        image = self._block["image"]
        self._settle_after = image["intensity"]["settle_after_s"]
        self._drift_ref_index = image["drift"]["reference_frame"] if image.get("drift") else None
        self._images_given = image["frames"]["given"]
        self._budget = float(self._block["question_budget_s"])
        self.cadence_s = float(self._block["cadence_s"])        # the orchestrator ticks at this
        self._cv = threading.Condition()
        self._out: queue.Queue = queue.Queue()
        self._frames_seen = 0
        self._unusable = 0             # frames that arrived and are not 2-D images
        self.failure: str | None = None
        self._latest = None            # (frame copy, index, t_mono)
        self._drift_ref = None
        self._image_ref = None         # (frame copy, index) -- the first frame a tick saw after the light settled
        self._settle_time = None
        self._level = None
        self._level_for = None
        self._pending: list = []
        self._seq = 0
        self._qseq = 0
        self._skipped = 0
        self._inflight = None
        self._results: list = []
        self._closed = False
        self._thread = None

    # -- what the orchestrator hands over ----------------------------------- #

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="watcher", daemon=True)
        self._thread.start()

    def put_frame(self, image, metadata, t_mono: float) -> None:
        """Copy one frame in, replacing the last. Nothing queues."""
        usable = isinstance(image, np.ndarray) and image.ndim == 2 and image.dtype.kind in "uif"
        copy_ = np.array(image, copy=True) if usable else None
        with self._cv:
            if self._closed:
                return
            index = self._frames_seen
            self._frames_seen += 1
            if not usable:
                self._unusable += 1
                return
            self._latest = (copy_, index, t_mono)
            if index == self._drift_ref_index:
                self._drift_ref = copy_

    def tick(self, snapshot: dict, events: list, channels: dict, t_mono: float) -> None:
        """Hand over one tick's data: the snapshot the orchestrator read and the log since the last tick."""
        data = (copy.deepcopy(snapshot), copy.deepcopy(list(events)), dict(channels), t_mono)
        with self._cv:
            if self._closed:
                return
            self._pending.append(data)
            self._cv.notify_all()

    def drain(self) -> list[dict]:
        out = []
        while True:
            try:
                out.append(self._out.get_nowait())
            except queue.Empty:
                return out

    def close(self) -> None:
        """Stop, join, and turn a question still open into watcher_unanswered, run_ended."""
        with self._cv:
            already = self._closed
            self._closed = True
            self._cv.notify_all()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(3.0)
        if already:
            return
        with self._cv:
            open_question, self._inflight = self._inflight, None
        if open_question is not None:
            self._unanswered(open_question["qseq"], open_question["state_seq"], open_question["state_sha"],
                             open_question["asked_t"], "run_ended")

    # -- the thread --------------------------------------------------------- #

    def _loop(self) -> None:
        while True:
            action = None
            with self._cv:
                if self._closed:
                    return
                now = self._clock()
                if self._results:
                    action = ("result", self._results.pop(0))
                elif self._inflight is not None and now >= self._inflight["deadline"]:
                    action = ("expired", self._inflight)
                    self._inflight = None
                elif self._pending:
                    action = ("tick", self._pending.pop(0))
                else:
                    wait = 0.05 if self._inflight is None else max(0.0, min(0.05, self._inflight["deadline"] - now))
                    self._cv.wait(wait)
            if action is None:
                continue
            kind, payload = action
            if kind == "result":
                self._handle_result(payload)
            elif kind == "expired":
                self._unanswered(payload["qseq"], payload["state_seq"], payload["state_sha"],
                                 payload["asked_t"], "time_budget")
            else:
                try:
                    self._process(*payload)
                except Exception as exc:                # noqa: BLE001 - kept for the orchestrator to say
                    self.failure = f"{type(exc).__name__}: {exc}"

    def _emit(self, event: dict) -> None:
        self._out.put(event)

    def _unanswered(self, qseq, state_seq, state_sha, asked_t, why, detail=None) -> None:
        body = {"seq": qseq, "state_seq": state_seq, "state_sha256": state_sha,
                "asked_t_mono": asked_t, "why": why}
        if detail is not None:
            body["detail"] = detail
        self._emit({"event": "watcher_unanswered", "from": "watcher", "t_mono": self._clock(), "watcher": body})

    def _handle_result(self, result) -> None:
        token, outcome, payload = result
        with self._cv:
            current = self._inflight
            if current is None or current["token"] != token:
                return                                          # a late answer to a question already given up on
            self._inflight = None
        options = self._block["options"]
        ids = [o["id"] for o in options]
        if outcome == "err":
            self._unanswered(current["qseq"], current["state_seq"], current["state_sha"], current["asked_t"],
                             "backend_failed", payload)
            return
        probs = (payload or {}).get("probabilities")
        problem = None
        if not isinstance(probs, dict) or set(probs) != set(ids):
            problem = f"probabilities must cover exactly the options {ids}, and came as {probs!r}"
        elif not all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 <= v <= 1.0 for v in probs.values()):
            problem = f"probabilities must each be between 0 and 1: {probs!r}"
        elif abs(sum(probs.values()) - 1.0) > 1e-3:
            problem = f"probabilities must sum to 1 and sum to {sum(probs.values())!r}"
        if problem is not None:
            self._unanswered(current["qseq"], current["state_seq"], current["state_sha"], current["asked_t"],
                             "backend_failed", problem)
            return
        best = max(ids, key=lambda i: (probs[i], -ids.index(i)))
        self._emit({"event": "watcher_flag", "from": "watcher", "t_mono": self._clock(), "watcher": {
            "seq": current["qseq"], "state_seq": current["state_seq"], "state_sha256": current["state_sha"],
            "asked_t_mono": current["asked_t"], "answered_t_mono": self._clock(),
            "options": ids,
            "signals": {"probabilities": {i: float(probs[i]) for i in ids}, "choice": best,
                        "confidence": float(probs[best])},
            "backend": _backend_record(self._backend), "renderer_version": R.RENDERER_VERSION,
            "prompt_version": PROMPT_VERSION, "judgement": dm3_reading(best)}})

    def _settle(self, events: list, frame) -> tuple[float | None, str | None]:
        """The settled level and, when there is none, why. Light commands come from the log."""
        for event in events:
            if (event.get("event") == "apply" and event.get("verification") == "readback"
                    and self._light(event)):
                self._settle_time = float(event["t_mono"]) + float(self._settle_after)
        if self._settle_time is None:
            return None, "no light-source command with a matching read-back has been seen in this run"
        if frame is None:
            return None, "no frame has arrived in this run yet"
        array, index, t = frame
        if t < self._settle_time:
            return None, (f"settling: the light settles at t_mono {self._settle_time:.3f} s and the latest "
                          f"frame is at {t:.3f} s")
        if self._level_for != self._settle_time:
            self._level = float(np.asarray(array, dtype=np.float64).sum())
            self._level_for = self._settle_time
        if self._image_ref is None:
            self._image_ref = (array, index)
        return self._level, None

    def _process(self, snapshot, events, channels, t_mono) -> None:
        with self._cv:
            latest = self._latest
            drift_ref = self._drift_ref
        level, level_why = self._settle(events, latest)
        no_frame_because = None
        if latest is None and self._unusable:
            no_frame_because = (f"{self._unusable} frame(s) arrived and none is a 2-D image "
                                "(this run's frames are not images the renderer can read)")
        self._seq += 1
        seq = self._seq
        inp = {"seq": seq, "block": self._block, "ceiling": self._ceiling, "ceiling_gap": self._gap,
               "frame": None if latest is None else latest[0],
               "frame_index": None if latest is None else latest[1],
               "frame_t_mono": None if latest is None else latest[2],
               "reference": drift_ref, "reference_frame_index": self._drift_ref_index,
               "level": level, "level_absent_because": level_why, "no_frame_because": no_frame_because,
               "snapshot": snapshot, "tick_t_mono": t_mono, "events": events, "channels": channels}
        try:
            text, values = R.render(inp)
        except Exception as exc:                        # noqa: BLE001 - the tick is still written, said so
            inp.update(frame=None, frame_index=None, frame_t_mono=None, reference=None, level=None,
                       no_frame_because=f"rendering this tick's frame failed: {type(exc).__name__}: {exc}",
                       level_absent_because=f"rendering this tick's frame failed: {type(exc).__name__}: {exc}")
            latest = None
            text, values = R.render(inp)
        data = text.encode("utf-8")
        sha = "sha256:" + hashlib.sha256(data).hexdigest()       # the schema writes a hash with its algorithm
        path = f"watcher_state_{seq:06d}.txt"
        (self._folder / path).write_bytes(data)
        images, refused = None, None
        if self._images_given:
            images, refused = self._images(seq, latest)
        state = {"seq": seq, "frame_index": inp["frame_index"], "frame_t_mono": inp["frame_t_mono"],
                 "snapshot_t_mono": None if snapshot is None else snapshot.get("t_mono"),
                 "image": values, "state_sha256": sha, "state_path": path,
                 "renderer_version": R.RENDERER_VERSION}
        if images is not None:
            state["images"] = [{k: v for k, v in image.items() if k != "png"} for image in images]
        if refused is not None:
            state["images_not_given_because"] = refused
        with self._cv:
            in_flight = self._inflight is not None
            if in_flight:
                self._skipped += 1
        asking = (self._backend.kind != "none") and not in_flight
        state["asked"] = bool(asking and refused is None)
        state["skipped_so_far"] = self._skipped
        self._emit({"event": "watcher_state", "from": "watcher", "t_mono": self._clock(), "watcher": state})
        if not asking:
            return
        self._qseq += 1
        qseq = self._qseq
        asked_t = self._clock()
        if refused is not None:
            # THE TICK IS NOT ASKED TEXT-ONLY: an answer from the text alone under a plan that gives
            # images would land in the wrong column of the comparison that decides whether the
            # picture adds anything (plan.md 13.4 item 4).
            self._unanswered(qseq, seq, sha, asked_t, "image_conversion_refused", refused)
            return
        token = object()
        with self._cv:
            self._inflight = {"token": token, "qseq": qseq, "state_seq": seq, "state_sha": sha,
                              "asked_t": asked_t, "deadline": asked_t + self._budget}
        threading.Thread(target=self._ask, args=(token, text, copy.deepcopy(self._block["options"]), images),
                         name=f"watcher-question-{qseq}", daemon=True).start()

    def _images(self, seq: int, latest):
        """The two reduced images, written whole, or None and the reason they were not made."""
        conversion = self._block["image"]["frames"]["conversion"]
        if latest is None:
            return None, "no frame has arrived in this run yet, so there is no current image"
        if self._image_ref is None:
            return None, ("no reference frame yet: the first frame after the light settles has not been "
                          "seen, so no pair of images can be made")
        pairs = (("current", latest[0], latest[1]), ("reference", self._image_ref[0], self._image_ref[1]))
        made = []
        try:
            for role, array, index in pairs:
                data, info = R.convert_frame(array, conversion, self._ceiling)
                made.append((role, index, data, info))
        except R.RenderRefused as exc:
            return None, str(exc)
        out = []
        for role, index, data, info in made:
            name = f"watcher_image_{seq:06d}_{role}.png"
            (self._folder / name).write_bytes(data)
            out.append({"role": role, "frame_index": index, "sha256": "sha256:" + info["sha256"], "path": name,
                        "conversion_version": info["conversion_version"], "shape": info["shape"],
                        "stretch_limits": info["stretch_limits"], "saturated_pixels": info["saturated_pixels"],
                        "png": data})
        return out, None

    def _ask(self, token, text, options, images) -> None:
        try:
            payload = self._backend.ask(text, options, images)
            result = (token, "ok", payload)
        except Exception as exc:                                # noqa: BLE001 - a backend failure is a record
            result = (token, "err", f"{type(exc).__name__}: {exc}")
        with self._cv:
            self._results.append(result)
            self._cv.notify_all()
