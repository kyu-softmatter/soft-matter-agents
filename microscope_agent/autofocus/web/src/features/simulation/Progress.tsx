import type { RunProgressJson } from "./types";

export function StateBadge({ state }: { state: RunProgressJson["state"] }) {
  return <span className={`sim-state sim-state-${state}`}>{state}</span>;
}

export function duration(s: number | null): string {
  if (s == null || !Number.isFinite(s)) return "–";
  const t = Math.round(s);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const sec = t % 60;
  if (h) return `${h} h ${m} min`;
  if (m) return `${m} min ${sec} s`;
  return `${sec} s`;
}

function when(iso: string | null): string {
  if (!iso) return "–";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

/** A bar with the fraction done; an unknown fraction is said, not guessed. */
export function ProgressBar({ p }: { p: RunProgressJson }) {
  const pct = p.fraction == null ? null : Math.round(p.fraction * 1000) / 10;
  return (
    <div
      className="sim-bar"
      role="progressbar"
      aria-label={`${p.run_id} progress`}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct ?? undefined}
      aria-valuetext={pct == null ? "unknown" : `${pct}%`}
    >
      <div className={`sim-bar-fill sim-state-${p.state}`} style={{ width: `${pct ?? 0}%` }} />
      <span className="sim-bar-label">{pct == null ? "?" : `${pct}%`}</span>
    </div>
  );
}

/** F6.1: current / total steps, elapsed, expected end. */
export function ProgressPanel({ p }: { p: RunProgressJson }) {
  return (
    <section className="sim-panel" aria-label="Progress">
      <div className="sim-row">
        <StateBadge state={p.state} />
        <ProgressBar p={p} />
      </div>
      {p.state === "unknown" ? (
        <p className="muted">This run's files do not say how far it is.</p>
      ) : null}
      <dl className="sim-facts">
        <dt>steps</dt>
        <dd>
          {p.steps_taken ?? "–"} / {p.steps_total ?? "–"}
        </dd>
        <dt>frames</dt>
        <dd>
          {p.frames_saved ?? "–"}
          {p.frames_expected != null ? ` of ${p.frames_expected + 1}` : ""}
        </dd>
        <dt>simulated time</dt>
        <dd>{p.simulated_time != null ? `${p.simulated_time} s` : "–"}</dd>
        <dt>started</dt>
        <dd>{when(p.started_at)}</dd>
        <dt>elapsed</dt>
        <dd>{duration(p.elapsed_s)}</dd>
        {p.state === "running" ? (
          <>
            <dt>expected end</dt>
            <dd>
              {when(p.eta)} ({duration(p.remaining_s)} left)
            </dd>
            <dt>last update</dt>
            <dd>{when(p.updated_at)}</dd>
          </>
        ) : (
          <>
            <dt>finished</dt>
            <dd>{when(p.finished_at)}</dd>
            <dt>stopped by</dt>
            <dd>{p.stopped_by ?? "–"}</dd>
          </>
        )}
        <dt>read from</dt>
        <dd>{p.source}</dd>
      </dl>
    </section>
  );
}
