# dino-autofocus

Autofocus and a local web interface for a Nikon Ti2 microscope driven through Micro-Manager.
Focus is judged from deterministic image metrics, with frozen DINOv2 features and a small head
(focus score / signed z-error) as a helper. The verdict is one of `in_focus`, `step_up`,
`step_down`, `no_sample_here` or `unsure`; the code never invents a Z target on its own.

> **Moved and frozen (2026-10-15).** This repository has moved into
> [soft-matter-agents](https://github.com/kyu-softmatter/soft-matter-agents) at
> `microscope_agent/autofocus/`, with its history. This repository is frozen as a read-only
> record: no new commits land here, and development continues in soft-matter-agents.
> The plan that led here: [`docs/integration-sma.md`](docs/integration-sma.md) and
> [`docs/integration-sma-workplan.md`](docs/integration-sma-workplan.md).

## Layout

| Path | What |
|---|---|
| `microscope_agent/` | Files laid out as they will sit in soft-matter-agents (focus verdict, focus search, map tiles) |
| `src/dino_autofocus/focus/` | Classical focus metrics, DINO focus head |
| `src/dino_autofocus/engine/` | Mock-first engine, motion guards, Micro-Manager backend |
| `src/dino_autofocus/server/`, `web/` | Local web app (FastAPI + React/TypeScript) |
| `src/dino_autofocus/synth/` | Synthetic PSF image simulator for training data |
| `scripts/` | Bench and training scripts |
| `docs/` | Design, specs, runbooks and bench run records |

## Install

Needs [uv](https://docs.astral.sh/uv/) and Python 3.12.

```
uv sync
```

The core package depends only on numpy and scipy; heavy parts are extras (`ml`, `hw`, `synth`,
`server`, `plot`). Full setup, the DINOv2 clone and the desktop launcher: [`docs/setup-new-pc.md`](docs/setup-new-pc.md).

Run the web app (binds to `127.0.0.1` only):

```
uv run python -m dino_autofocus.server
```

## Safety

Real-stage motion is locked by default (`BENCH_MOTION` in `engine/backends/mm_real.py`), and every
move goes through the guards in `engine/guards.py`. Every feature runs against the mock backend first. Do not
forward or proxy the server port: requests from loopback are treated as the microscope PC itself.

## Credits

Uses [DINOv2](https://github.com/facebookresearch/dinov2) (Apache-2.0) as a frozen backbone; it is
not vendored, see `docs/setup-new-pc.md`.

## License

MIT, see [`LICENSE`](LICENSE).
