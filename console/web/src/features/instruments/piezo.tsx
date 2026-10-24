/**
 * Piezo stage (canvas `PPiezo`, console card 012): x, y and z from a run's snapshots, with the time each
 * was read; the person's own range, read from the safety file and never written into code; a time window
 * and a refresh that change only this screen. The pattern generator is designed later.
 */

import { useEffect, useState } from "react";

import { useClient } from "../../app/client";
import { shortTime } from "../questions/ui";
import { type LatestRun, type LimitsOut, PATHS, piezoRange } from "./api";

export const SCREEN_ONLY =
  "The window and refresh change only this screen. How often the stage is read is part of the plan you sign.";
const WINDOWS = [["30", "30 s"], ["120", "2 min"], ["600", "10 min"]] as const;
const REFRESHES = [["off", "Off"], ["1000", "1 s"], ["5000", "5 s"]] as const;
const AXES = ["x", "y", "z"] as const;

export function PiezoRange({ limits }: { limits: LimitsOut }) {
  return (
    <div role="group" aria-label="Your range" className="inst-allowed">
      <strong>Your range</strong>
      <ul>
        {AXES.map((a) => {
          const r = piezoRange(limits, a);
          const unit = r?.max.unit === "um" ? "µm" : (r?.max.unit ?? "");
          return <li key={a}>{a}: {r === null ? "no range in your safety file" : `${r.min.value} to ${r.max.value} ${unit}`}</li>;
        })}
      </ul>
      <p className="console-muted">{limits.state === "present" ? "from your safety file" : "your safety file could not be read"}</p>
    </div>
  );
}

export function Piezo({ run: first, limits }: { run: LatestRun; limits: LimitsOut }) {
  const client = useClient();
  const [run, setRun] = useState(first);
  const [windowS, setWindowS] = useState("600");
  const [refresh, setRefresh] = useState("off");
  useEffect(() => setRun(first), [first]);
  useEffect(() => {
    if (refresh === "off") return;
    const timer = setInterval(() => {
      client.get<LatestRun>(PATHS.latestRun).then(setRun, () => undefined);
    }, Number(refresh));
    return () => clearInterval(timer);
  }, [client, refresh]);

  const points = run.piezo;
  const last = points.length > 0 ? points[points.length - 1] : null;
  const kept = last === null || last.t_s === null ? points : points.filter((p) => p.t_s !== null && p.t_s >= (last.t_s as number) - Number(windowS));
  const cell = (v: number | null) => (v === null ? "unknown" : String(v));
  return (
    <section aria-label="Piezo stage" className="inst-piezo">
      <div role="group" aria-label="Position now">
        <strong>Position now</strong>
        {last === null ? (
          <p>no position read yet</p>
        ) : (
          <>
            <p>
              <span>x {cell(last.x_um)} µm</span>, <span>y {cell(last.y_um)} µm</span>, <span>z {cell(last.z_um)} µm</span>
            </p>
            <p className="console-muted">as of {shortTime(last.t_wall)}, from {run.run_id}</p>
          </>
        )}
      </div>
      <PiezoRange limits={limits} />
      <div className="inst-form">
        <label className="inst-field">
          Time window
          <select value={windowS} onChange={(e) => setWindowS(e.target.value)}>
            {WINDOWS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="inst-field">
          Screen refresh
          <select value={refresh} onChange={(e) => setRefresh(e.target.value)}>
            {REFRESHES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>
      <p className="console-muted">{SCREEN_ONLY}</p>
      {kept.length > 0 && (
        <table className="console-table" aria-label="Piezo positions">
          <thead><tr><th>t (s)</th><th>x (µm)</th><th>y (µm)</th><th>z (µm)</th></tr></thead>
          <tbody>
            {kept.map((p, i) => (
              <tr key={i}><td>{cell(p.t_s)}</td><td>{cell(p.x_um)}</td><td>{cell(p.y_um)}</td><td>{cell(p.z_um)}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      <p>Pattern generator: <span>designed later</span></p>
    </section>
  );
}
