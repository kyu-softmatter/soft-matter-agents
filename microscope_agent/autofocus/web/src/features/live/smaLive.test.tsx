import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { fakeTransport, type Route } from "../../test/fakes";
import { type LiveState, PATHS, type RunStream } from "../console/api";
import { LIVE_OFF, LIVE_OFF_NOTE, LIVE_ON, listSummary, SmaLiveSwitch } from "./smaLive";

const SHA = "a".repeat(64);
const RUN = "run-live-001";
const LIST = {
  name: "live-view-brightfield.json",
  sha256: SHA,
  data: {
    artifact: "live_view_list",
    label: "finding the sample",
    transmitted_lamp: { device: "DiaLamp", intensity: { value: 12 } },
    camera: { device: "Kinetix_red", exposure_ms: 20, frame_ceiling: 3000 },
  },
};

function live(over: Partial<LiveState> = {}): LiveState {
  return { available: true, why_not: null, host: "127.0.0.1:6123", lists: [LIST], ...over };
}

function stream(): RunStream {
  return {
    run_id: RUN, agent: "microscope", followed: true, state: "running", ended_how: null, plan_id: null,
    revision: null, t0_wall: null, can_stop: true, stop_unavailable: null, frame_tap: true, events: [],
    total: 0, partial_tail: false, bad_lines: 0,
  };
}

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
});

function renderSwitch(state: LiveState, extra: Record<string, Route> = {}, allowed = true) {
  const ok = (body: unknown) => ({ status: 200, body });
  const posts: { path: string; body: unknown }[] = [];
  const routes: Record<string, Route> = {
    [PATHS.live]: () => ok(state),
    [PATHS.permissions(["live_on"])]: () =>
      ok({ live_on: allowed ? { allowed: true } : { allowed: false, reason: "role viewer may not live_on" } }),
    [PATHS.liveOn]: (init) => {
      posts.push({ path: PATHS.liveOn, body: JSON.parse(String(init?.body)) });
      return ok({ outcome: "started", run_id: RUN, reason: null });
    },
    [PATHS.runStream("microscope", RUN)]: () => ok(stream()),
    [PATHS.runStop("microscope", RUN)]: (init) => {
      posts.push({ path: PATHS.runStop("microscope", RUN), body: JSON.parse(String(init?.body)) });
      return ok({ run_id: RUN, outcome: "begun", message: `run ${RUN} began to abort` });
    },
    ...extra,
  };
  const fake = fakeTransport(routes);
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  render(
    <ClientProvider client={client}>
      <SmaLiveSwitch />
    </ClientProvider>,
  );
  return { posts };
}

const onButton = () => screen.getByRole("button", { name: LIVE_ON }) as HTMLButtonElement;

describe("microscope live view switch", () => {
  it("switches on by sha256 only, then Live off is the run's stop and says what it does", async () => {
    const t = renderSwitch(live());
    await waitFor(() => expect(onButton().disabled).toBe(false));
    expect(screen.getByText(/DiaLamp intensity 12 · Kinetix_red exposure 20 ms · frame ceiling 3000/)).toBeTruthy();
    await act(async () => {
      fireEvent.click(onButton());
    });
    expect(await screen.findByRole("button", { name: LIVE_OFF })).toBeTruthy();
    expect(screen.getByText(LIVE_OFF_NOTE)).toBeTruthy();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: LIVE_OFF }));
    });
    expect(await screen.findByText(`run ${RUN} began to abort`)).toBeTruthy();
    expect(t.posts).toEqual([
      { path: PATHS.liveOn, body: { sha256: SHA } },
      { path: PATHS.runStop("microscope", RUN), body: { reason: LIVE_OFF } },
    ]);
  });

  it("shows the host's refusal reason", async () => {
    renderSwitch(live(), {
      [PATHS.liveOn]: () => ({ status: 200, body: { outcome: "refused", run_id: null, reason: "a run holds the lock" } }),
    });
    await waitFor(() => expect(onButton().disabled).toBe(false));
    await act(async () => {
      fireEvent.click(onButton());
    });
    expect((await screen.findByRole("alert")).textContent).toBe("Live on refused: a run holds the lock");
  });

  it("is disabled with the reason when the host is not running or the role may not", async () => {
    renderSwitch(live({ available: false, why_not: "the live-view host is not running" }));
    expect(await screen.findByText("the live-view host is not running")).toBeTruthy();
    expect(onButton().disabled).toBe(true);
  });

  it("a viewer sees the permission reason", async () => {
    renderSwitch(live(), {}, false);
    expect(await screen.findByText("role viewer may not live_on")).toBeTruthy();
    expect(onButton().disabled).toBe(true);
  });

  it("summarises a list by the schema's fields, and says when it adds excitation", () => {
    expect(listSummary(LIST)).toBe(
      "finding the sample · DiaLamp intensity 12 · Kinetix_red exposure 20 ms · frame ceiling 3000",
    );
    expect(listSummary({ ...LIST, data: { ...LIST.data, excitation: {} } })).toMatch(/adds fluorescence excitation$/);
  });
});
