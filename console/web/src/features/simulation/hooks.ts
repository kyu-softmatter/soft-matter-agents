import { useEffect, useRef, useState } from "react";

import type { SimulationClient } from "./client";
import { type Frame, frameFromJson } from "./frame";

export interface Loaded<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/**
 * Load `fetcher()` when `key` changes, again every `everyMs` while `everyMs` is set (a running
 * simulation), and once more when `refresh` changes (keeping what is shown meanwhile). Stale
 * answers for an old key are dropped.
 */
export function usePolled<T>(key: string | null, fetcher: () => Promise<T>, everyMs: number | null, refresh: unknown = null): Loaded<T> {
  const [state, setState] = useState<Loaded<T> & { key: string | null }>({ data: null, error: null, loading: false, key: null });
  const fetchRef = useRef(fetcher);
  fetchRef.current = fetcher;

  useEffect(() => {
    if (key === null) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () => {
      setState((s) => (s.key === key ? { ...s, loading: true } : { data: null, error: null, loading: true, key }));
      fetchRef.current().then(
        (data) => alive && setState({ data, error: null, loading: false, key }),
        (e: unknown) => alive && setState((s) => ({ ...s, error: String(e instanceof Error ? e.message : e), loading: false, key })),
      ).finally(() => {
        if (alive && everyMs) timer = setTimeout(load, everyMs);
      });
    };
    load();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [key, everyMs, refresh]);

  if (state.key !== key) return { data: null, error: null, loading: key !== null };
  return { data: state.data, error: state.error, loading: state.loading };
}

const CACHE_FRAMES = 64;

/**
 * The frame at `index` of a run. The last frame shown stays until the next one arrives, so
 * playback does not flash. Frames are cached per run (a recent few).
 */
export function useFrame(client: SimulationClient, runId: string | null, index: number, enabled: boolean): { frame: Frame | null; error: string | null } {
  const cache = useRef(new Map<string, Frame>());
  const [shown, setShown] = useState<{ runId: string | null; frame: Frame | null; error: string | null }>({ runId: null, frame: null, error: null });

  useEffect(() => {
    if (!runId || !enabled) return;
    const key = `${runId}:${index}`;
    const hit = cache.current.get(key);
    if (hit) {
      setShown({ runId, frame: hit, error: null });
      return;
    }
    let alive = true;
    client.getFrame(runId, index).then(
      (json) => {
        if (!alive) return;
        try {
          const f = frameFromJson(json);
          cache.current.set(key, f);
          if (cache.current.size > CACHE_FRAMES) cache.current.delete(cache.current.keys().next().value!);
          setShown({ runId, frame: f, error: null });
        } catch (e) {
          setShown((s) => ({ ...s, runId, error: String(e instanceof Error ? e.message : e) }));
        }
      },
      (e: unknown) => alive && setShown((s) => ({ ...s, runId, error: String(e instanceof Error ? e.message : e) })),
    );
    return () => {
      alive = false;
    };
  }, [client, runId, index, enabled]);

  if (shown.runId !== runId) return { frame: null, error: null };
  return { frame: shown.frame, error: shown.error };
}
