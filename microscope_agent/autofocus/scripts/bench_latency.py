"""Backbone latency on this GPU: batch 1 (closed-loop autofocus) and batch 8, fp32 vs fp16.

uv run python scripts/bench_latency.py
"""

from __future__ import annotations

import os
import warnings

import torch

from dino_autofocus.backbone import DEFAULT_REPO

os.environ.setdefault("XFORMERS_DISABLED", "1")
warnings.filterwarnings("ignore", message="xFormers")


def time_ms(fn, n=30, warmup=10) -> float:
    for _ in range(warmup):
        fn()
    start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    torch.cuda.synchronize()
    start.record()
    for _ in range(n):
        fn()
    end.record()
    torch.cuda.synchronize()
    return start.elapsed_time(end) / n


@torch.no_grad()
def bench(name: str, model: torch.nn.Module) -> None:
    for px in (224, 448, 518):
        for batch in (1, 8):
            torch.cuda.reset_peak_memory_stats()
            x = torch.randn(batch, 3, px, px, device="cuda")

            def f32(x=x):
                return model(x)

            def f16(x=x):
                with torch.autocast("cuda", dtype=torch.float16):
                    return model(x)

            t32, t16 = time_ms(f32), time_ms(f16)
            diff = (f32() - f16().float()).abs().max().item()
            mib = torch.cuda.max_memory_allocated() / 2**20
            print(f"{name:<18}{px:>5}{batch:>6}{t32:>9.1f}{t16:>9.1f}{diff:>9.4f}{mib:>6.0f}")


def main() -> None:
    print(torch.cuda.get_device_name(0), torch.__version__)
    print(f"{'model':<18}{'px':>5}{'batch':>6}{'fp32 ms':>9}{'fp16 ms':>9}{'max|d|':>9}{'MiB':>6}")
    for name in ("dinov2_vits14", "dinov2_vitb14"):
        bench(name, torch.hub.load(str(DEFAULT_REPO), name, source="local").cuda().eval())
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
