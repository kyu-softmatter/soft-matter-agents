import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { fakeTransport } from "../../test/fakes";
import {
  ASSUMED_PIXEL_UM,
  FocusGauge,
  type FocusSample,
  FpsMeter,
  FramePairer,
  frameScale,
  gaugeY,
  heightOf,
  LiveView,
  pushSample,
  sampleOf,
} from "../../app/live";
import LiveScreen from "./index";

const META = {
  type: "frame",
  seq: 7,
  t: 1759300000.5,
  width: 800,
  height: 800,
  binning: 3,
  source_width: 2400,
  source_height: 2400,
  display_min: 102,
  display_max: 3435,
  jpeg_bytes: 4,
  meta: { z_um: 2989.42 },
};

const jpeg = () => new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xd9])], { type: "image/jpeg" });

describe("FramePairer", () => {
  it("pairs the metadata text with the next binary message", () => {
    const p = new FramePairer();
    expect(p.feed(JSON.stringify(META))).toBeNull();
    const got = p.feed(jpeg());
    expect(got).toMatchObject({ kind: "frame", meta: { seq: 7, binning: 3 } });
  });

  it("drops a JPEG with no metadata before it, or of the wrong length", () => {
    const p = new FramePairer();
    expect(p.feed(jpeg())).toBeNull();
    p.feed(JSON.stringify({ ...META, jpeg_bytes: 99 }));
    expect(p.feed(jpeg())).toBeNull();
  });

  it("reports a server error message", () => {
    expect(new FramePairer().feed(JSON.stringify({ type: "error", status: 501, detail: "this engine provides no frames" })))
      .toEqual({ kind: "error", status: 501, detail: "this engine provides no frames" });
  });
});

describe("FpsMeter", () => {
  it("measures the receive rate over recent frames", () => {
    const m = new FpsMeter(5);
    expect(m.tick(0)).toBeNull();
    for (let i = 1; i <= 4; i++) m.tick(i * 100);
    expect(m.tick(500)).toBeCloseTo(10);
  });
});

describe("LiveView", () => {
  beforeEach(() => {
    let n = 0;
    URL.createObjectURL = vi.fn(() => `blob:frame-${++n}`);
    URL.revokeObjectURL = vi.fn();
  });
  afterEach(() => vi.useRealTimers());

  function mount() {
    const t = fakeTransport({});
    const client = new Client(t.transport, "127.0.0.1");
    let clock = 0;
    const now = () => (clock += 100);
    render(
      <ClientProvider client={client}>
        <LiveView now={now} />
      </ClientProvider>,
    );
    return t.sockets.find((s) => s.path === "/ws/frames")!;
  }

  function sendBinary(ws: { onmessage: ((e: MessageEvent) => void) | null }, b: Blob) {
    ws.onmessage?.(new MessageEvent("message", { data: b }));
  }

  it("draws frames with their time, size and the receive rate", () => {
    const ws = mount();
    act(() => {
      ws.open();
      for (let i = 0; i < 3; i++) {
        ws.send(META);
        sendBinary(ws, jpeg());
      }
    });
    expect(screen.getByTestId("live-conn").textContent).toBe("frames: connected");
    expect(screen.getByRole("img", { name: "Live camera frame" }).getAttribute("src")).toBe("blob:frame-3");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:frame-2");
    expect(screen.getByTestId("live-fps").textContent).toBe("10.0 fps");
    expect(screen.getByTestId("live-size").textContent).toContain("bin 3 of 2400×2400");
    expect(screen.getByText("Z 2989.42 µm")).toBeTruthy();
    expect(screen.getByTestId("live-z").getAttribute("title")).toContain("camera buffer");
  });

  it("shows two cameras side by side, one at a time, or merged", () => {
    const ws = mount();
    act(() => {
      ws.open();
      for (const camera of ["Kinetix_red", "Kinetix_blue"]) {
        ws.send({ ...META, camera });
        sendBinary(ws, jpeg());
      }
    });
    expect(screen.queryByRole("img", { name: "Live camera frame" })).toBeNull();
    expect(screen.getByRole("img", { name: "Live frame Kinetix_blue" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "Live frame Kinetix_red" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Side by side" }).getAttribute("aria-pressed")).toBe("true");
    // P-01: two cameras on screen always carry the software-time-base note
    expect(screen.getByTestId("live-timebase").textContent).toContain("display only");

    act(() => screen.getByRole("button", { name: "Kinetix_red" }).click());
    expect(screen.getByRole("img", { name: "Live frame Kinetix_red" })).toBeTruthy();
    expect(screen.queryByRole("img", { name: "Live frame Kinetix_blue" })).toBeNull();

    act(() => screen.getByRole("button", { name: "Merged" }).click());
    expect(screen.getByRole("img", { name: "Merged camera frame" })).toBeTruthy();
    expect(screen.getByRole("figure", { name: "Merged cameras" }).textContent).toContain("Kinetix_blue");
  });

  it("keeps each camera's newest frame and frees only that camera's old one", () => {
    const ws = mount();
    act(() => {
      ws.open();
      ws.send({ ...META, camera: "Kinetix_blue" });
      sendBinary(ws, jpeg()); // frame-1
      ws.send({ ...META, camera: "Kinetix_red" });
      sendBinary(ws, jpeg()); // frame-2
      ws.send({ ...META, camera: "Kinetix_red", seq: 9 });
      sendBinary(ws, jpeg()); // frame-3
    });
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:frame-2");
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith("blob:frame-1");
    expect(screen.getByRole("img", { name: "Live frame Kinetix_blue" }).getAttribute("src")).toBe("blob:frame-1");
    expect(screen.getByRole("img", { name: "Live frame Kinetix_red" }).getAttribute("src")).toBe("blob:frame-3");
  });

  it("says so, and does not retry, when the engine provides no frames", () => {
    vi.useFakeTimers();
    const ws = mount();
    act(() => {
      ws.send({ type: "error", status: 501, detail: "this engine provides no frames" });
      ws.close();
    });
    expect(screen.getByTestId("live-conn").textContent).toBe("frames: not available");
    expect(screen.getByText("this engine provides no frames")).toBeTruthy();
    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByTestId("live-conn").textContent).toBe("frames: not available");
  });

  it("reconnects after the socket drops", () => {
    vi.useFakeTimers();
    const t = fakeTransport({});
    const client = new Client(t.transport, "127.0.0.1");
    render(
      <ClientProvider client={client}>
        <LiveView />
      </ClientProvider>,
    );
    const frames = () => t.sockets.filter((s) => s.path === "/ws/frames");
    act(() => frames()[0].close());
    expect(screen.getByTestId("live-conn").textContent).toBe("frames: closed");
    act(() => vi.advanceTimersByTime(2000));
    expect(frames()).toHaveLength(2);
  });
});

describe("pattern overlay", () => {
  const PATTERN = {
    id: "square",
    name: "Square",
    version: 1,
    loop: false,
    notes: "",
    meta: {},
    duration_s: 4,
    tracks: [{ target: "trap:0", points: [[0, 0, 0, 0], [4, 5, 5, 0]] }],
  };

  beforeEach(() => {
    let n = 0;
    URL.createObjectURL = vi.fn(() => `blob:frame-${++n}`);
    URL.revokeObjectURL = vi.fn();
  });

  it("reads the scale from the frame, else assumes one and says so", () => {
    expect(frameScale({ ...META, binning: 2, meta: { pixel_um: 0.108 } } as never)).toEqual({ umPerPx: 0.216, known: true });
    expect(frameScale({ ...META, binning: 3, meta: {} } as never)).toEqual({ umPerPx: ASSUMED_PIXEL_UM * 3, known: false });
  });

  it("draws the pattern named in the route over the frame, with a time slider", async () => {
    window.location.hash = "#/live?pattern=square";
    const t = fakeTransport({
      "/api/patterns": () => ({ status: 200, body: [{ id: "square", name: "Square", duration_s: 4, targets: ["trap:0"] }] }),
      "/api/patterns/square": () => ({ status: 200, body: PATTERN }),
    });
    render(
      <ClientProvider client={new Client(t.transport, "127.0.0.1")}>
        <LiveScreen />
      </ClientProvider>,
    );
    const ws = t.sockets.find((s) => s.path === "/ws/frames")!;
    act(() => {
      ws.open();
      ws.send(META);
      ws.onmessage?.(new MessageEvent("message", { data: jpeg() }));
    });
    expect(await screen.findByRole("img", { name: "Pattern Square over the frame" })).toBeTruthy();
    expect(screen.getByRole("slider", { name: "Pattern time" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Edit" }).getAttribute("href")).toBe("#/patterns/square");
    expect((screen.getByRole("combobox", { name: "Pattern overlay" }) as HTMLSelectElement).value).toBe("square");
  });
});

describe("focus panel", () => {
  beforeEach(() => {
    let n = 0;
    URL.createObjectURL = vi.fn(() => `blob:frame-${++n}`);
    URL.revokeObjectURL = vi.fn();
  });

  it("adds the piezo z to the stage z and keeps the last minute", () => {
    const s = (t: number, stageZ: number | null, piezoZ: number | null): FocusSample => ({
      t, camera: "", score: 1, metric: "vollath4", stageZ, piezoZ, dz: null,
    });
    expect(heightOf(s(0, 1200, 50.5))).toBe(1250.5);
    expect(heightOf(s(0, 1200, null))).toBe(1200); // no piezo: the stage alone
    expect(heightOf(s(0, null, 50))).toBeNull();
    let list: FocusSample[] = [];
    for (const t of [0, 30, 59, 61]) list = pushSample(list, s(t, 1, 0));
    expect(list.map((x) => x.t)).toEqual([30, 59, 61]);
    expect(sampleOf({ camera: "a", url: "", jpeg: jpeg(), fps: null, meta: { ...META, focus_score: 0.42, focus_metric: "vollath4", meta: { z_um: 10, piezo_z_um: 2 } } } as never))
      .toMatchObject({ camera: "a", score: 0.42, stageZ: 10, piezoZ: 2 });
  });

  it("shows each camera's focus score and the stage + piezo height beside the frames", () => {
    window.location.hash = "#/live";
    const t = fakeTransport({ "/api/patterns": () => ({ status: 200, body: [] }) });
    render(
      <ClientProvider client={new Client(t.transport, "127.0.0.1")}>
        <LiveScreen />
      </ClientProvider>,
    );
    const ws = t.sockets.find((s) => s.path === "/ws/frames")!;
    act(() => {
      ws.open();
      for (const [camera, score, dt] of [["Kinetix_blue", 0.5123, 0], ["Kinetix_red", 0.25, 0.1], ["Kinetix_blue", 0.75, 1]] as const) {
        ws.send({ ...META, camera, t: META.t + dt, focus_score: score, focus_metric: "vollath4", meta: { z_um: 2989.42 + dt, piezo_z_um: 50 } });
        ws.onmessage?.(new MessageEvent("message", { data: jpeg() }));
      }
    });
    const panel = screen.getByRole("complementary", { name: "Focus" });
    expect(screen.getByTestId("focus-score-Kinetix_blue").textContent).toBe("0.7500");
    expect(screen.getByTestId("focus-score-Kinetix_red").textContent).toBe("0.2500");
    expect(panel.textContent).toContain("vollath4");
    expect(screen.getByTestId("focus-z").textContent).toContain("3040.42 µm");
    expect(screen.getByTestId("focus-z").textContent).toContain("piezo 50.00 µm");
    expect(screen.getByRole("img", { name: "Z height over time" })).toBeTruthy();
    expect(screen.getByTestId("z-line").getAttribute("d")).toMatch(/^M.* L.* L/);
  });
});

describe("Z score gauge", () => {
  beforeEach(() => {
    let n = 0;
    URL.createObjectURL = vi.fn(() => `blob:frame-${++n}`);
    URL.revokeObjectURL = vi.fn();
  });

  it("maps +10 to the top, 0 to the middle and -10 to the bottom, clipping beyond", () => {
    expect(gaugeY(10)).toBeLessThan(gaugeY(0));
    expect(gaugeY(0)).toBeCloseTo((gaugeY(10) + gaugeY(-10)) / 2);
    expect(gaugeY(-10)).toBeGreaterThan(gaugeY(0));
    expect(gaugeY(250)).toBe(gaugeY(10));
    expect(gaugeY(-250)).toBe(gaugeY(-10));
  });

  it("shows the value, marker and sigma bar of a model reading", () => {
    render(<FocusGauge reading={{ dz_dof: 1.24, sigma_dof: 0.8, source: "model", note: "box: 3/4 tiles", sign_known: true }} />);
    expect(screen.getByTestId("gauge-value").textContent).toBe("+1.2");
    expect(screen.getByTestId("gauge-marker")).toBeTruthy();
    expect(screen.getByTestId("gauge-sigma")).toBeTruthy();
    expect(screen.getByTestId("gauge-note").textContent).toBe("box: 3/4 tiles");
    expect(screen.getByText("model")).toBeTruthy();
    expect(screen.getByText("0 focus")).toBeTruthy();
  });

  it("says when nothing is loaded and when a value is off scale", () => {
    const { unmount } = render(<FocusGauge reading={null} />);
    expect(screen.getByTestId("gauge-value").textContent).toBe("--");
    expect(screen.queryByTestId("gauge-marker")).toBeNull();
    expect(screen.getByTestId("gauge-note").textContent).toBe("No DINO head loaded (--head)");
    unmount();
    render(<FocusGauge reading={{ dz_dof: -42.5, sigma_dof: null, source: "mock_truth", note: "mock truth, not a measurement", sign_known: true }} />);
    expect(screen.getByTestId("gauge-value").textContent).toBe("−42.5");
    expect(screen.getByText(/off scale/)).toBeTruthy();
    expect(screen.queryByTestId("gauge-sigma")).toBeNull(); // the truth has no sigma
  });

  it("follows the newest frame that carries a reading, not the laser camera's", () => {
    window.location.hash = "#/live";
    const t = fakeTransport({ "/api/patterns": () => ({ status: 200, body: [] }) });
    render(
      <ClientProvider client={new Client(t.transport, "127.0.0.1")}>
        <LiveScreen />
      </ClientProvider>,
    );
    const ws = t.sockets.find((s) => s.path === "/ws/frames")!;
    const dz = (v: number) => ({ dz_dof: v, sigma_dof: null, source: "mock_truth", note: "mock truth, not a measurement", sign_known: true });
    act(() => {
      ws.open();
      for (const [camera, focus_dz, dt] of [["Kinetix_red", dz(3.04), 0], ["Kinetix_red", dz(-0.46), 0.1], ["Kinetix_blue", null, 0.2]] as const) {
        ws.send({ ...META, camera, t: META.t + dt, focus_dz, meta: { z_um: 10 } });
        ws.onmessage?.(new MessageEvent("message", { data: jpeg() }));
      }
    });
    expect(screen.getByRole("img", { name: "Focus gauge, depths of field" })).toBeTruthy();
    expect(screen.getByTestId("gauge-value").textContent).toBe("−0.5");
    expect(screen.getByText("mock truth")).toBeTruthy();
  });
});
