import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BASE_FPS, usePlayback } from "./playback";

const FRAME_MS = 1000 / BASE_FPS;

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

function tick(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}

describe("usePlayback", () => {
  it("starts at frame 0, paused, speed 1", () => {
    const { result } = renderHook(() => usePlayback(5));
    expect(result.current).toMatchObject({ index: 0, playing: false, speed: 1 });
  });

  it("plays at BASE_FPS x speed and stops on the last frame", () => {
    const { result } = renderHook(() => usePlayback(4));
    act(() => result.current.play());
    expect(result.current.playing).toBe(true);
    tick(FRAME_MS);
    expect(result.current.index).toBe(1);
    act(() => result.current.setSpeed(2));
    tick(FRAME_MS / 2);
    expect(result.current.index).toBe(2);
    tick(FRAME_MS * 10);
    expect(result.current.index).toBe(3);
    expect(result.current.playing).toBe(false);
  });

  it("replays from 0 when played at the end, and pauses", () => {
    const { result } = renderHook(() => usePlayback(3));
    act(() => result.current.setIndex(2));
    act(() => result.current.play());
    expect(result.current.index).toBe(0);
    tick(FRAME_MS);
    act(() => result.current.pause());
    tick(FRAME_MS * 5);
    expect(result.current.index).toBe(1);
    expect(result.current.playing).toBe(false);
  });

  it("clamps setIndex and follows a changing frame count", () => {
    const { result, rerender } = renderHook(({ n }) => usePlayback(n), { initialProps: { n: 5 } });
    act(() => result.current.setIndex(99));
    expect(result.current.index).toBe(4);
    act(() => result.current.setIndex(-3));
    expect(result.current.index).toBe(0);
    act(() => result.current.setIndex(4));
    rerender({ n: 8 }); // a running simulation saved more frames
    expect(result.current.index).toBe(4);
    rerender({ n: 2 });
    expect(result.current.index).toBe(1);
    rerender({ n: 0 });
    expect(result.current.index).toBe(0);
  });

  it("does not play with one frame or none, and ignores a bad speed", () => {
    const { result } = renderHook(() => usePlayback(1));
    act(() => result.current.play());
    expect(result.current.playing).toBe(false);
    act(() => result.current.setSpeed(0));
    act(() => result.current.setSpeed(Number.NaN));
    expect(result.current.speed).toBe(1);
  });
});
