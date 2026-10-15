"""Generate the 5 um particle dataset for all six Ti2 objectives, sharing GPU and CPU.

    uv run python scripts/farm_p5.py --scenes 3000            # per objective
    uv run python scripts/farm_p5.py --scenes 3000 --dry-run

Work is cut into chunks of --chunk scenes, interleaved across objectives so the
dataset stays balanced whenever it is stopped. Two lanes pull from one queue:

  gpu  --gpu-procs make_dataset processes, --gpu-workers each, complex64 on CUDA
  cpu  one process with --cpu-workers, CPU path, only the small-grid objectives

A chunk whose manifest.json exists is skipped, and a chunk cut off part-way keeps its
finished shards (make_dataset resumes it), so re-running continues where it stopped.
To pause gracefully, create data/p5_farm.STOP: lanes finish their current chunk and
exit (delete the file before resuming). Output:
data/p5_<obj>/chunk_<seed0>/shard_*.npz, log in data/p5_farm.log.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).parents[1]

# objective: (raster pad for +-15 DoF with a 5 um bead, depth bin um); see the run notes
PLAN = {
    "4x": (2, 2.0),
    "10x": (2, 1.0),
    "20x": (2, 1.0),
    "40x": (4, 0.5),
    "60x": (4, 0.5),
    "100x": (5, 0.5),
}
CPU_OK = {"4x", "10x", "20x"}          # small grids: the CPU path is competitive
SEED_BASE = {obj: 1_000_000 * (i + 1) for i, obj in enumerate(PLAN)}


def command(obj: str, seed0: int, n: int, out: Path, device: str, workers: int) -> list[str]:
    pad, depth_bin = PLAN[obj]
    cmd = [sys.executable, str(ROOT / "scripts" / "make_dataset.py"),
           "--out", str(out), "--scenes", str(n), "--seed0", str(seed0),
           "--fov", "224", "--planes", "21", "--span", "15", "--pad", str(pad),
           "--system-config", str(ROOT / "configs" / f"ti2_{obj}.yaml"),
           "--particle-um", "5", "--particle-per-mm2", "30", "500",
           "--base-depth", "0.05", "0.5", "--min-prominence", "2.0",
           "--depth-bin", str(depth_bin), "--focus-plane",
           "--device", device, "--workers", str(workers), "--psf-cache", "8"]
    if device != "cpu":
        cmd += ["--gpu-dtype", "complex64"]
    return cmd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", type=int, default=3000, help="per objective")
    ap.add_argument("--chunk", type=int, default=200)
    ap.add_argument("--gpu-procs", type=int, default=3)
    ap.add_argument("--gpu-workers", type=int, default=2)
    ap.add_argument("--cpu-workers", type=int, default=30, help="0 disables the CPU lane")
    ap.add_argument("--out", type=Path, default=ROOT / "data")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    queue: deque = deque()
    for i in range(0, args.scenes, args.chunk):
        for obj in PLAN:
            seed0 = SEED_BASE[obj] + i
            out = args.out / f"p5_{obj}" / f"chunk_{seed0}"
            if not (out / "manifest.json").exists():
                queue.append((obj, seed0, min(args.chunk, args.scenes - i), out))
    log_path = args.out / "p5_farm.log"
    args.out.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    def log(msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
        with lock:
            print(line, flush=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    log(f"{len(queue)} chunks queued ({args.scenes} scenes/objective, chunk {args.chunk}); "
        f"gpu {args.gpu_procs}x{args.gpu_workers}, cpu {args.cpu_workers}")
    if args.dry_run:
        for c in list(queue)[:8]:
            print(" ".join(command(c[0], c[1], c[2], c[3], "cuda", args.gpu_workers)))
        return

    stop = args.out / "p5_farm.STOP"

    def take(cpu: bool):
        if stop.exists():
            return None
        with lock:
            for k, c in enumerate(queue):
                if not cpu or c[0] in CPU_OK:
                    del queue[k]
                    return c
        return None

    def lane(name: str, device: str, workers: int) -> None:
        while (c := take(device == "cpu")) is not None:
            obj, seed0, n, out = c
            t = time.time()
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out.parent / f"chunk_{seed0}.log", "w", encoding="utf-8") as f:
                rc = subprocess.call(command(obj, seed0, n, out, device, workers),
                                     stdout=f, stderr=subprocess.STDOUT, cwd=ROOT)
            el = time.time() - t
            ok = rc == 0 and (out / "manifest.json").exists()
            log(f"{name:5s} {obj:5s} seeds {seed0}+{n}: {'ok' if ok else f'FAILED rc={rc}'} "
                f"in {el / 60:5.1f} min ({el / max(n, 1):5.1f} s/scene)")

    lanes = [threading.Thread(target=lane, args=(f"gpu{k}", "cuda", args.gpu_workers))
             for k in range(args.gpu_procs)]
    if args.cpu_workers > 0:
        lanes.append(threading.Thread(target=lane, args=("cpu", "cpu", args.cpu_workers)))
    for th in lanes:
        th.start()
    for th in lanes:
        th.join()
    log("stopped by p5_farm.STOP" if stop.exists() and queue else "all lanes finished")


if __name__ == "__main__":
    main()
