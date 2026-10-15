import { useEffect, useState } from "react";

import type { SimulationClient } from "./client";
import { Graphs } from "./Graphs";
import { useFrame, usePolled } from "./hooks";
import { usePlayback } from "./playback";
import { ProgressPanel } from "./Progress";
import type { RunProgressJson, ZipEntryJson } from "./types";
import { Viewers } from "./Viewers";

/**
 * While a run is running its progress is pushed (`client.watchProgress`); the run's files and
 * its series are read again at these intervals, and once more when it stops.
 */
export const INFO_MS = 10000;
export const SERIES_MS = 10000;

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} kB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

/** F6.2: the run folder as one zip; the trajectory goes in only when ticked. */
function Download({ client, runId, entries }: { client: SimulationClient; runId: string; entries: ZipEntryJson[] | null }) {
  const [withOptional, setWithOptional] = useState(false);
  const optional = entries?.filter((e) => e.optional) ?? [];
  const total = (entries ?? []).filter((e) => withOptional || !e.optional).reduce((s, e) => s + e.size, 0);
  const href = client.zipUrl(runId, withOptional);
  return (
    <section className="sim-panel" aria-label="Download">
      <div className="sim-row">
        {href ? (
          <a className="sim-button" href={href} download={`${runId}.zip`}>
            Download {runId}.zip
          </a>
        ) : (
          <button type="button" disabled title="The mock has no files to send; the server serves the zip">
            Download {runId}.zip
          </button>
        )}
        {entries ? <span className="muted">about {size(total)}</span> : null}
        {optional.length ? (
          <label>
            <input type="checkbox" checked={withOptional} onChange={(e) => setWithOptional(e.target.checked)} /> include{" "}
            {optional.map((e) => `${e.name.split("/").pop()} (${size(e.size)})`).join(", ")}
          </label>
        ) : null}
      </div>
    </section>
  );
}

export function RunDetail({ client, runId, onBack }: { client: SimulationClient; runId: string; onBack: () => void }) {
  const [running, setRunning] = useState(false);
  const [live, setLive] = useState<RunProgressJson | null>(null);
  const ended = live !== null && live.state !== "running"; // read the files once more then
  const info = usePolled(runId, () => client.getRun(runId), running ? INFO_MS : null, ended);
  const series = usePolled(runId, () => client.getSeries(runId), running ? SERIES_MS : null, ended);
  const entries = usePolled(`${runId}:${info.data?.files.length ?? 0}`, () => client.zipEntries(runId), null);

  // the pushed progress is newer while the files say running; once they say it stopped, they win
  const fromFiles = info.data?.progress ?? null;
  const progress = fromFiles && fromFiles.state === "running" && live ? live : fromFiles;
  const isRunning = progress?.state === "running";
  if (isRunning !== running && progress) setRunning(isRunning);

  useEffect(() => {
    if (!running) return;
    return client.watchProgress(runId, setLive);
  }, [client, runId, running]);

  const hasTrajectory = !!info.data?.trajectory;
  const nFrames = hasTrajectory ? (progress?.frames_saved ?? 0) : 0;
  const playback = usePlayback(nFrames);
  const { frame, error: frameError } = useFrame(client, runId, playback.index, hasTrajectory && nFrames > 0);

  return (
    <div className="sim-detail">
      <p>
        <a
          href="#/simulation"
          onClick={(e) => {
            e.preventDefault();
            onBack();
          }}
        >
          ← all runs
        </a>
      </p>
      <h2>{runId}</h2>
      {info.error ? <p role="alert">{info.error}</p> : null}
      {info.data ? (
        <>
          <p className="muted">
            {info.data.backend ?? "unknown backend"}
            {info.data.qid ? ` · question ${info.data.qid}` : ""} · from {info.data.source}
          </p>
          <ProgressPanel p={progress ?? info.data.progress} />
          <Download client={client} runId={runId} entries={entries.data} />
          {hasTrajectory ? (
            <Viewers frame={frame} nFrames={nFrames} playback={playback} error={frameError} />
          ) : (
            <section className="sim-panel" aria-label="Trajectory">
              <p className="muted">No trajectory to show: {info.data.trajectory_unavailable ?? "none recorded"}.</p>
            </section>
          )}
          {series.data ? <Graphs series={series.data} /> : series.error ? <p role="alert">{series.error}</p> : null}
        </>
      ) : info.loading ? (
        <p className="muted">Loading…</p>
      ) : null}
    </div>
  );
}
