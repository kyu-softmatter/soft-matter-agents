import { useCallback, useEffect, useState } from "react";

/** Frames per second at speed 1. */
export const BASE_FPS = 10;
export const SPEEDS = [0.25, 0.5, 1, 2, 4, 8] as const;

export interface Playback {
  /** the frame in view, 0..nFrames-1 (0 when there are no frames) */
  index: number;
  playing: boolean;
  /** multiplier of BASE_FPS */
  speed: number;
  setIndex(i: number): void;
  play(): void;
  pause(): void;
  setSpeed(s: number): void;
}

function clamp(i: number, n: number): number {
  if (n <= 0 || !Number.isFinite(i)) return 0;
  return Math.min(Math.max(Math.trunc(i), 0), n - 1);
}

/**
 * The playback state shared by the 2D and 3D viewers: which frame, playing or not, how fast.
 * The viewers get only the frame; the controls sit outside them. Playing stops at the last
 * frame; play from the last frame starts again at 0. When `nFrames` grows (a running
 * simulation saving frames) the index stays; when it shrinks the index is clamped.
 */
export function usePlayback(nFrames: number): Playback {
  const [rawIndex, setRawIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeedState] = useState(1);
  const index = clamp(rawIndex, nFrames);
  const atEnd = nFrames <= 0 || index >= nFrames - 1;

  useEffect(() => {
    if (!playing) return;
    if (atEnd) {
      setPlaying(false);
      return;
    }
    const id = setTimeout(() => setRawIndex((i) => clamp(i, nFrames) + 1), 1000 / (BASE_FPS * speed));
    return () => clearTimeout(id);
  }, [playing, atEnd, index, nFrames, speed]);

  const setIndex = useCallback((i: number) => setRawIndex(clamp(i, nFrames)), [nFrames]);
  const play = useCallback(() => {
    if (nFrames <= 1) return;
    setRawIndex((i) => (clamp(i, nFrames) >= nFrames - 1 ? 0 : i));
    setPlaying(true);
  }, [nFrames]);
  const pause = useCallback(() => setPlaying(false), []);
  const setSpeed = useCallback((s: number) => {
    if (Number.isFinite(s) && s > 0) setSpeedState(s);
  }, []);

  return { index, playing, speed, setIndex, play, pause, setSpeed };
}
