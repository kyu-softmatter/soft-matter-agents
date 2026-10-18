import { createContext, useContext, useMemo } from "react";

import { type Client, useClient } from "../../app/client";
import { sharedFakeClient } from "./fakeClient";
import type { FrameJson } from "./frame";
import type { RunProgressJson, RunSeriesJson, SimRunInfoJson, ZipEntryJson } from "./types";

/** What the simulation screen reads. Every call is a GET, so remote viewing works too. */
export interface SimulationClient {
  /** "mock" for the in-browser fake, "server" for the API */
  readonly source: "mock" | "server";
  listRuns(): Promise<SimRunInfoJson[]>;
  getRun(runId: string): Promise<SimRunInfoJson>;
  getSeries(runId: string): Promise<RunSeriesJson>;
  getFrame(runId: string, index: number, fields?: string[]): Promise<FrameJson>;
  zipEntries(runId: string): Promise<ZipEntryJson[]>;
  /** where the run's zip downloads from; null when this client cannot serve one */
  zipUrl(runId: string, includeOptional: boolean): string | null;
  /**
   * Follow a run's progress: `onProgress` on each change, until the run is no longer running
   * or the returned function is called.
   */
  watchProgress(runId: string, onProgress: (p: RunProgressJson) => void): () => void;
}

/** The part of EventSource the progress stream uses; tests pass a fake. */
export interface EventSourceLike {
  addEventListener(type: string, listener: (ev: MessageEvent) => void): void;
  onerror: ((ev: Event) => void) | null;
  close(): void;
}

export type OpenEvents = (url: string) => EventSourceLike;

export const browserEvents: OpenEvents | null =
  typeof EventSource === "undefined" ? null : (url) => new EventSource(url);

export const SIM_BASE = "/api/simulation";
export const POLL_MS = 2000;

/**
 * The routes of server/api/simulation.py, read through the app's shared client (`get`), so a
 * 401 / 423 reaches the login gate like any other screen's. Progress comes from the server-sent
 * event stream `/runs/{id}/progress/stream`; without EventSource, or when the stream fails,
 * it is polled through `get` instead.
 */
export function serverClient(
  get: <T>(path: string) => Promise<T>,
  { base = SIM_BASE, openEvents = browserEvents, pollMs = POLL_MS }: { base?: string; openEvents?: OpenEvents | null; pollMs?: number } = {},
): SimulationClient {
  const run = (id: string) => `${base}/runs/${encodeURIComponent(id)}`;

  function poll(id: string, onProgress: (p: RunProgressJson) => void): () => void {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = () => {
      get<RunProgressJson>(`${run(id)}/progress`).then(
        (p) => {
          if (!alive) return;
          onProgress(p);
          if (p.state === "running") timer = setTimeout(tick, pollMs);
        },
        () => {
          if (alive) timer = setTimeout(tick, pollMs * 5);
        },
      );
    };
    tick();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }

  return {
    source: "server",
    listRuns: () => get(`${base}/runs`),
    getRun: (id) => get(run(id)),
    getSeries: (id) => get(`${run(id)}/series`),
    getFrame: (id, index, fields = []) => {
      const q = fields.length ? `?fields=${fields.map(encodeURIComponent).join(",")}` : "";
      return get(`${run(id)}/frames/${index}${q}`);
    },
    zipEntries: (id) => get(`${run(id)}/zip/entries`),
    zipUrl: (id, includeOptional) => `${run(id)}/zip${includeOptional ? "?trajectory=1" : ""}`,
    watchProgress: (id, onProgress) => {
      if (!openEvents) return poll(id, onProgress);
      let stopPolling: (() => void) | null = null;
      const es = openEvents(`${run(id)}/progress/stream`);
      es.addEventListener("progress", (ev) => {
        const p = JSON.parse(ev.data as string) as RunProgressJson;
        onProgress(p);
        if (p.state !== "running") es.close(); // the server ends the stream; do not reconnect
      });
      es.onerror = () => {
        // EventSource would reconnect forever (and hides 401s); poll through `get` instead
        es.close();
        stopPolling ??= poll(id, onProgress);
      };
      return () => {
        es.close();
        stopPolling?.();
      };
    },
  };
}

/** Lets a test (or a later launcher option) choose the simulation client. */
export const SimulationClientContext = createContext<SimulationClient | null>(null);

function useAppClient(): Client | null {
  try {
    return useClient();
  } catch {
    return null; // no ClientProvider: a test or a demo page without the server
  }
}

/**
 * The client the screen uses: the context's when one is given, otherwise the server through the
 * app's shared client, otherwise (no ClientProvider at all) the in-browser fake.
 */
export function useSimulationClient(): SimulationClient {
  const chosen = useContext(SimulationClientContext);
  const app = useAppClient();
  const server = useMemo(() => (app ? serverClient((p) => app.get(p)) : null), [app]);
  return chosen ?? server ?? sharedFakeClient();
}
