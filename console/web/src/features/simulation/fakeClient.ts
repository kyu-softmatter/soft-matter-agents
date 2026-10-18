import type { SimulationClient } from "./client";
import type { FrameJson } from "./frame";
import type { ProgressState, RunProgressJson, RunSeriesJson, SimRunInfoJson, ZipEntryJson } from "./types";

/**
 * An in-browser stand-in for the simulation API until server/api/simulation.py lands. Its runs
 * mirror `agents.mock_sim.make_mock_runs`: a finished 2D run, a 3D run that faulted, and a 2D run
 * that keeps going while the screen is open. Data is drawn from a seeded generator, so a run
 * looks the same each time; the temperature, energy and pressure columns are made up.
 */

/** A refusal of the fake, shaped like the shared client's (`status`). */
export class ClientError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ClientError";
  }
}

export const FAKE_PROGRESS_MS = 1000;

interface Spec {
  runId: string;
  dimensions: 2 | 3;
  n: number;
  frames: number;
  stepsPerFrame: number;
  stepsPerSecond: number;
  startedAgoS: number;
  faultAtStep?: number;
  seed: number;
}

const SPECS: Spec[] = [
  { runId: "mock-sim-2d-done", dimensions: 2, n: 64, frames: 200, stepsPerFrame: 50, stepsPerSecond: 2000, startedAgoS: 7200, seed: 1 },
  { runId: "mock-sim-3d-fault", dimensions: 3, n: 128, frames: 200, stepsPerFrame: 50, stepsPerSecond: 2000, startedAgoS: 3600, faultAtStep: 6000, seed: 2 },
  { runId: "mock-sim-2d-running", dimensions: 2, n: 200, frames: 600, stepsPerFrame: 100, stepsPerSecond: 100, startedAgoS: 30, seed: 3 },
];

const BOX = 20e-6; // m
const TIMESTEP = 0.002; // s
const DIFFUSIVITY = 2e-13; // m^2/s
const PROGRESS_EVERY_FRAMES = 10;

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gaussian(rand: () => number): number {
  const u = Math.max(rand(), 1e-12);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rand());
}

class FakeRun {
  readonly startedAt: number;
  private traj: Float32Array[] | null = null;
  private thermo: { temperature: number[]; potential_energy: number[]; pressure: number[] } | null = null;

  constructor(
    readonly spec: Spec,
    t0: number,
  ) {
    this.startedAt = t0 - spec.startedAgoS * 1000;
  }

  get totalSteps() {
    return this.spec.frames * this.spec.stepsPerFrame;
  }

  get lastStep() {
    return Math.min(this.spec.faultAtStep ?? this.totalSteps, this.totalSteps);
  }

  stepsAt(now: number): number {
    const s = Math.floor(((now - this.startedAt) / 1000) * this.spec.stepsPerSecond);
    return Math.min(Math.max(s, 0), this.lastStep);
  }

  framesAt(now: number): number {
    return Math.floor(this.stepsAt(now) / this.spec.stepsPerFrame) + 1;
  }

  private draw() {
    if (this.traj) return;
    const { n, frames, dimensions, stepsPerFrame, seed } = this.spec;
    const rand = mulberry32(seed);
    const typeScale = (i: number) => (i % 2 === 0 ? 1 : Math.sqrt(0.4));
    const sigma = Math.sqrt(2 * DIFFUSIVITY * TIMESTEP * stepsPerFrame);
    let pos = new Float32Array(3 * n);
    for (let i = 0; i < n; i++) {
      pos[3 * i] = (rand() - 0.5) * BOX;
      pos[3 * i + 1] = (rand() - 0.5) * BOX;
      pos[3 * i + 2] = dimensions === 3 ? (rand() - 0.5) * BOX : 0;
    }
    const traj = [pos];
    for (let f = 1; f <= frames; f++) {
      const next = new Float32Array(pos);
      for (let i = 0; i < n; i++) {
        const s = sigma * typeScale(i);
        next[3 * i] += s * gaussian(rand);
        next[3 * i + 1] += s * gaussian(rand);
        if (dimensions === 3) next[3 * i + 2] += s * gaussian(rand);
      }
      traj.push(next);
      pos = next;
    }
    this.traj = traj;
    const t = { temperature: [] as number[], potential_energy: [] as number[], pressure: [] as number[] };
    for (let f = 0; f <= frames; f++) {
      t.temperature.push(293 + 1.5 * gaussian(rand));
      t.potential_energy.push(-1e-19 * (1 - Math.exp(-f / (frames / 5 + 1))) + 2e-22 * gaussian(rand));
      t.pressure.push(1000 + 20 * gaussian(rand));
    }
    this.thermo = t;
  }

  state(now: number): ProgressState {
    if (this.stepsAt(now) < this.lastStep) return "running";
    return this.lastStep < this.totalSteps ? "fault" : "complete";
  }

  progress(now: number): RunProgressJson {
    const steps = this.stepsAt(now);
    const state = this.state(now);
    const rate = this.spec.stepsPerSecond;
    const doneAt = this.startedAt + (this.lastStep / rate) * 1000;
    const end = state === "running" ? now : doneAt;
    const etaMs = this.startedAt + (this.totalSteps / rate) * 1000;
    const iso = (ms: number) => new Date(ms).toISOString();
    return {
      run_id: this.spec.runId,
      state,
      source: "log",
      steps_taken: steps,
      steps_total: this.totalSteps,
      fraction: steps / this.totalSteps,
      frames_saved: this.framesAt(now),
      frames_expected: this.spec.frames,
      simulated_time: steps * TIMESTEP,
      started_at: iso(this.startedAt),
      updated_at: iso(Math.min(now, doneAt)),
      finished_at: state === "running" ? null : iso(doneAt),
      elapsed_s: (end - this.startedAt) / 1000,
      remaining_s: state === "running" ? Math.max((etaMs - now) / 1000, 0) : null,
      eta: state === "running" ? iso(etaMs) : null,
      stopped_by:
        state === "fault" ? "step_displacement_diverged" : state === "complete" ? "planned_duration_reached" : null,
      failure: null,
    };
  }

  info(now: number): SimRunInfoJson {
    const frames = this.framesAt(now);
    return {
      run_id: this.spec.runId,
      qid: null,
      backend: "mock_sim",
      progress: this.progress(now),
      files: [
        { name: "config.json", size: 612 },
        { name: "log.json", size: 2_000 + 400 * Math.floor(frames / PROGRESS_EVERY_FRAMES) },
        ...(this.state(now) === "running" ? [] : [{ name: "observables.json", size: 4_000 }]),
        { name: "trajectory.npz", size: frames * this.spec.n * 16 + 600 },
        { name: "trajectory_meta.json", size: 300 },
      ],
      trajectory: "npz:trajectory.npz",
      trajectory_unavailable: null,
      source: "mock",
    };
  }

  series(now: number): RunSeriesJson {
    this.draw();
    const steps = this.stepsAt(now);
    const every = PROGRESS_EVERY_FRAMES * this.spec.stepsPerFrame;
    const marks: number[] = [];
    for (let s = 0; s <= steps; s += every) marks.push(s);
    if (marks[marks.length - 1] !== steps) marks.push(steps);
    const frame = (s: number) => Math.floor(s / this.spec.stepsPerFrame);
    const t = this.thermo!;
    const log = {
      t_mono: marks.map((s) => s / this.spec.stepsPerSecond),
      steps_taken: marks,
      simulated_time: marks.map((s) => s * TIMESTEP),
      frames_saved: marks.map((s) => frame(s) + 1),
      fraction_of_planned_steps: marks.map((s) => s / this.totalSteps),
      temperature: marks.map((s) => t.temperature[frame(s)]),
      potential_energy: marks.map((s) => t.potential_energy[frame(s)]),
      pressure: marks.map((s) => t.pressure[frame(s)]),
    };
    if (this.state(now) === "running") {
      return { run_id: this.spec.runId, log, observable: null, curves: [], scalars: {}, observables: null };
    }
    const msd = this.msd(this.framesAt(now));
    const observables = {
      run_id: this.spec.runId,
      observable: "mean_squared_displacement",
      msd_curve: msd,
      fit: { diffusivity_declared: DIFFUSIVITY, lags_used: msd.length },
    };
    return {
      run_id: this.spec.runId,
      log,
      observable: "mean_squared_displacement",
      curves: [{ path: "msd_curve", x_name: null, x: msd.map((p) => p[0]), y: msd.map((p) => p[1]), kind: "line" }],
      scalars: { "fit.diffusivity_declared": DIFFUSIVITY, "fit.lags_used": msd.length },
      observables,
    };
  }

  private msd(frames: number): [number, number][] {
    const traj = this.traj!;
    const { n, stepsPerFrame } = this.spec;
    const out: [number, number][] = [];
    const maxLag = Math.min(Math.max(2, Math.floor(frames / 4)), 50);
    for (let k = 1; k < maxLag && k < frames; k++) {
      let sum = 0;
      let count = 0;
      for (let f = k; f < frames; f++) {
        for (let i = 0; i < 3 * n; i++) {
          const d = traj[f][i] - traj[f - k][i];
          sum += d * d;
        }
        count += n;
      }
      out.push([k * TIMESTEP * stepsPerFrame, sum / count]);
    }
    return out;
  }

  frame(now: number, index: number, fields: string[]): FrameJson {
    this.draw();
    const frames = this.framesAt(now);
    const i = index < 0 ? frames + index : index;
    if (!Number.isInteger(i) || i < 0 || i >= frames) {
      throw new ClientError(`frame ${index} out of range, ${frames} frames`, 404);
    }
    const { n, dimensions, stepsPerFrame } = this.spec;
    const extra: Record<string, number[]> = {};
    for (const f of fields) {
      if (f !== "diameter") throw new ClientError(`no per-particle field '${f}'`, 404);
      extra.diameter = Array.from({ length: n }, () => 1e-6);
    }
    return {
      index: i,
      step: i * stepsPerFrame,
      n,
      dimensions,
      units: "m",
      box: [BOX, BOX, dimensions === 3 ? BOX : 0, 0, 0, 0],
      types: ["A", "B"],
      typeid: Array.from({ length: n }, (_, k) => k % 2),
      positions: Array.from(this.traj![i]),
      fields: extra,
    };
  }
}

/** A fake client; `now` is injectable so tests can move time. */
export function fakeClient(now: () => number = Date.now): SimulationClient {
  const t0 = now();
  const runs = new Map(SPECS.map((s) => [s.runId, new FakeRun(s, t0)]));
  const find = (id: string) => {
    const r = runs.get(id);
    if (!r) throw new ClientError(`no simulation run ${id}`, 404);
    return r;
  };
  const later = <T>(f: () => T) => Promise.resolve().then(f);
  return {
    source: "mock",
    listRuns: () => later(() => [...runs.values()].sort((a, b) => b.startedAt - a.startedAt).map((r) => r.info(now()))),
    getRun: (id) => later(() => find(id).info(now())),
    getSeries: (id) => later(() => find(id).series(now())),
    getFrame: (id, index, fields = []) => later(() => find(id).frame(now(), index, fields)),
    zipEntries: (id) =>
      later((): ZipEntryJson[] =>
        find(id)
          .info(now())
          .files.map((f) => ({ name: `${id}/${f.name}`, size: f.size, optional: f.name.startsWith("trajectory.") })),
      ),
    zipUrl: () => null,
    watchProgress: (id, onProgress) => {
      let timer: ReturnType<typeof setTimeout> | undefined;
      const tick = () => {
        const r = runs.get(id);
        if (!r) return;
        const p = r.progress(now());
        onProgress(p);
        if (p.state === "running") timer = setTimeout(tick, FAKE_PROGRESS_MS);
      };
      timer = setTimeout(tick, 0);
      return () => clearTimeout(timer);
    },
  };
}

let shared: SimulationClient | null = null;

/** One fake per page, so runs keep their start times across screen visits. */
export function sharedFakeClient(): SimulationClient {
  shared ??= fakeClient();
  return shared;
}
