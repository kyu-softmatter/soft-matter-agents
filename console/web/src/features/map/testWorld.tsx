/**
 * Test harness: the map screen on the shell's client over src/test/fakes.ts. The fake server
 * answers the map routes, /api/state and /api/permissions from a FakeData world, numbers every
 * POST as op-1, op-2, ... and records it; events are scripted on the FakeSocket. No network, no
 * window.
 */

import { act, render } from "@testing-library/react";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider, useCurrentScreenContext } from "../../app/screenContext";
import { fakeTransport, type FakeSocket, type Route } from "../../test/fakes";
import type { Permissions } from "./api";
import { fixture, type FakeData } from "./fixture";
import MapScreen from "./index";

export interface Sent {
  route: string;
  body: Record<string, unknown>;
}

export interface World {
  data: FakeData;
  sent: Sent[];
  shown: () => Record<string, unknown>;
  socket: () => FakeSocket;
  /** push an engine event on /ws/events */
  emit: (kind: string, data?: Record<string, unknown>, op_id?: string) => Promise<void>;
}

const PREFIX = "/api/map/";

function answer(data: FakeData, path: string): { status: number; body?: unknown } {
  const [p, q = ""] = path.split("?");
  const query = new URLSearchParams(q);
  if (p === "/api/state") return { status: 200, body: data.snapshot };
  if (p === "/api/permissions") {
    if (data.permissionsFail) return { status: 503, body: { detail: "permission check failed" } };
    const ops = (query.get("ops") ?? "").split(",").filter((op) => !data.permissionsOmit?.includes(op));
    const out: Permissions = Object.fromEntries(ops.map((op) => [op, data.permissions[op] ?? { allowed: true, reason: null }]));
    return { status: 200, body: out };
  }
  if (!p.startsWith(PREFIX)) return { status: 404, body: { detail: "Not Found" } };
  const [id, area, rid] = p.slice(PREFIX.length).split("/").map(decodeURIComponent);
  const ok = (body: unknown) => (body === undefined ? { status: 404, body: { detail: `no ${p}` } } : { status: 200, body });
  if (area === undefined) return ok(data.maps[id]);
  if (area === "results") return ok(rid === undefined ? (data.results[id] ?? []) : data.details[rid]);
  if (area === "flags") {
    const all = query.get("include_retired") === "true";
    return ok((data.flags[id] ?? []).filter((f) => all || !(f.retired === true || f.retired_at != null)));
  }
  if (area === "candidates") {
    const all = query.get("include_rejected") === "true";
    return ok((data.candidates[id] ?? []).filter((c) => all || c.source !== "person_rejected"));
  }
  return { status: 404, body: { detail: "Not Found" } };
}

export async function mountMap(
  over: Partial<FakeData> = {},
  opts: {
    hostname?: string;
    permissionsGate?: Promise<void>;
    /** answer a POST to this path instead of accepting it */
    postAnswer?: (path: string) => { status: number; body?: unknown } | null;
  } = {},
): Promise<World> {
  const data = fixture(over);
  const sent: Sent[] = [];
  let n = 0;
  const route = (path: string): Route => (init) => {
    if (init?.method === "POST") {
      const forced = opts.postAnswer?.(path);
      if (forced) return forced;
      sent.push({ route: path, body: init.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {} });
      n += 1;
      return { status: 200, body: { op_id: `op-${n}` } };
    }
    return answer(data, path);
  };
  // any path: the fake answers from the world
  const routes = new Proxy({} as Record<string, Route>, { get: (_t, path) => route(String(path)) });
  const t = fakeTransport(routes);
  if (opts.permissionsGate) {
    const inner = t.transport.fetch;
    const gate = opts.permissionsGate;
    t.transport.fetch = async (path, init) => {
      if (path.startsWith("/api/permissions")) await gate;
      return inner(path, init);
    };
  }
  const client = new Client(t.transport, opts.hostname ?? "127.0.0.1");
  let shown: Record<string, unknown> = {};
  function Probe() {
    shown = useCurrentScreenContext();
    return null;
  }
  render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="map">
        <MapScreen />
        <Probe />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  const socket = () => t.sockets[t.sockets.length - 1];
  await act(async () => socket().open());
  return {
    data,
    sent,
    shown: () => shown,
    socket,
    emit: (kind, d = {}, op_id = "") => act(async () => socket().event(kind, d, op_id)),
  };
}
