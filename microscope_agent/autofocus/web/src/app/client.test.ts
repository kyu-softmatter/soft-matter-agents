import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeTransport } from "../test/fakes";
import { Client, CommandRefused, EventStream, isLoopbackHost, ReadOnlyStore, type Transport } from "./client";

afterEach(() => {
  vi.useRealTimers();
});

describe("read-only", () => {
  it("starts writable on the microscope PC and read-only from another host", () => {
    for (const h of ["127.0.0.1", "localhost", "[::1]", "app.localhost"]) expect(isLoopbackHost(h)).toBe(true);
    expect(isLoopbackHost("192.168.1.20")).toBe(false);
    expect(new ReadOnlyStore("127.0.0.1").get()).toEqual({ readOnly: false, why: null });
    expect(new ReadOnlyStore("lab-pc").get()).toEqual({ readOnly: true, why: "remote view" });
  });

  it("turns read-only on a command 403 marked remote_view in detail.code", async () => {
    const { transport, calls } = fakeTransport({
      "/api/commands": () => ({
        status: 403,
        body: { detail: { code: "remote_view", message: "remote viewers may send abort only" } },
      }),
    });
    const client = new Client(transport, "127.0.0.1");
    const seen = vi.fn();
    client.readOnly.subscribe(seen);
    await expect(client.command({ kind: "start", op: "status" })).rejects.toMatchObject({
      status: 403,
      code: "remote_view",
      detail: "remote viewers may send abort only",
    });
    expect(client.readOnly.get()).toEqual({ readOnly: true, why: "remote viewers may send abort only" });
    expect(seen).toHaveBeenCalledTimes(1);
    expect(calls[0].init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ kind: "start", op: "status" });
  });

  it("turns read-only on a 403 marked by the X-DinoAF-Refusal header only", async () => {
    const { transport } = fakeTransport({
      "/api/commands": () => ({
        status: 403,
        body: { detail: "remote viewers may send abort only" },
        headers: { "X-DinoAF-Refusal": "remote_view" },
      }),
    });
    const client = new Client(transport, "127.0.0.1");
    await expect(client.command({ kind: "start", op: "status" })).rejects.toMatchObject({ code: "remote_view" });
    expect(client.readOnly.get().readOnly).toBe(true);
  });

  it("returns any other command 403 to the caller and keeps the app writable", async () => {
    const { transport } = fakeTransport({
      "/api/commands": () => ({
        status: 403,
        body: { detail: { code: "not_session_owner", message: "the session belongs to Bea" } },
      }),
    });
    const client = new Client(transport, "127.0.0.1");
    const seen = vi.fn();
    client.readOnly.subscribe(seen);
    const err = await client.command({ kind: "start", op: "scan_4x" }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(CommandRefused);
    expect(err).toMatchObject({ status: 403, code: "not_session_owner", detail: "the session belongs to Bea" });
    expect(client.readOnly.get()).toEqual({ readOnly: false, why: null });
    expect(seen).not.toHaveBeenCalled();
  });

  it("returns the op_id of an accepted command", async () => {
    const { transport } = fakeTransport({ "/api/commands": () => ({ status: 200, body: { op_id: "op-1" } }) });
    await expect(new Client(transport, "127.0.0.1").command({ kind: "lights_off" })).resolves.toBe("op-1");
  });
});

describe("post", () => {
  it("posts JSON to an area route and returns the reply", async () => {
    const { transport, calls } = fakeTransport({
      "/api/console/questions": () => ({ status: 201, body: { qid: "q-1" } }),
    });
    const client = new Client(transport, "127.0.0.1");
    await expect(client.post("/api/console/questions", { text: "hi" })).resolves.toEqual({ qid: "q-1" });
    expect(calls[0].init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ text: "hi" });
  });

  it("returns null for 204 and sends no body when given none", async () => {
    const { transport, calls } = fakeTransport({ "/api/sessions/s1/close": () => ({ status: 204 }) });
    await expect(new Client(transport, "127.0.0.1").post("/api/sessions/s1/close")).resolves.toBeNull();
    expect(calls[0].init?.body).toBeUndefined();
  });

  it("keeps the app writable on a D16 403 and returns its reason", async () => {
    const { transport } = fakeTransport({
      "/api/map/flags": () => ({ status: 403, body: { detail: { code: "d16_map_write", message: "map writes need control" } } }),
    });
    const client = new Client(transport, "127.0.0.1");
    await expect(client.post("/api/map/flags", {})).rejects.toMatchObject({
      status: 403,
      code: "d16_map_write",
      detail: "map writes need control",
    });
    expect(client.readOnly.get().readOnly).toBe(false);
  });

  it("turns read-only on a post 403 marked remote_view", async () => {
    const { transport } = fakeTransport({
      "/api/map/flags": () => ({ status: 403, body: { detail: { code: "remote_view", message: "read only" } } }),
    });
    const client = new Client(transport, "127.0.0.1");
    await expect(client.post("/api/map/flags", {})).rejects.toMatchObject({ code: "remote_view" });
    expect(client.readOnly.get()).toEqual({ readOnly: true, why: "read only" });
  });

  it("re-reads the login on 401 / 423, like command", async () => {
    const { transport } = fakeTransport({
      "/api/sessions/open": () => ({ status: 401, body: { detail: "log in" } }),
      "/api/sample/open-folder": () => ({ status: 423, body: { detail: "locked" } }),
    });
    const client = new Client(transport, "127.0.0.1");
    const auth = vi.fn();
    client.onAuthFailure(auth);
    await expect(client.post("/api/sessions/open", {})).rejects.toMatchObject({ status: 401 });
    await expect(client.post("/api/sample/open-folder")).rejects.toMatchObject({ status: 423 });
    expect(auth.mock.calls.map((c) => c[0])).toEqual([401, 423]);
    expect(client.readOnly.get().readOnly).toBe(false);
  });

  it("reads the server's ApiError {detail: {code, message}}", async () => {
    const { transport } = fakeTransport({
      "/api/auth/control/acquire": () => ({
        status: 409,
        body: { detail: { code: "control_held", message: "held by Bea" } },
      }),
    });
    await expect(new Client(transport, "127.0.0.1").post("/api/auth/control/acquire")).rejects.toMatchObject({
      status: 409,
      code: "control_held",
      detail: "held by Bea",
    });
  });

  it("reads FastAPI's own errors: a plain string (404) and a validation list (422), with no code", async () => {
    const { transport } = fakeTransport({
      "/api/x": () => ({ status: 404, body: { detail: "Not Found" } }),
      "/api/commands": () => ({
        status: 422,
        body: { detail: [{ loc: ["body", "kind"], msg: "Input should be 'start' or 'abort'", type: "literal_error" }] },
      }),
    });
    const client = new Client(transport, "127.0.0.1");
    await expect(client.post("/api/x")).rejects.toMatchObject({ status: 404, code: null, detail: "Not Found" });
    await expect(client.command({ kind: "start" })).rejects.toMatchObject({
      status: 422,
      code: null,
      detail: "Input should be 'start' or 'abort'",
    });
    expect(client.readOnly.get().readOnly).toBe(false);
  });
});

describe("postStream", () => {
  /** A transport whose one route answers with a given Response (a stream, or an error). */
  function streamTransport(answer: () => Response): { transport: Transport; calls: RequestInit[] } {
    const calls: RequestInit[] = [];
    return {
      calls,
      transport: {
        fetch: async (_path, init) => {
          calls.push(init ?? {});
          return answer();
        },
        openSocket: () => {
          throw new Error("no sockets in this test");
        },
      },
    };
  }

  function ndjson(lines: unknown[]): Response {
    const enc = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        for (const l of lines) c.enqueue(enc.encode(`${JSON.stringify(l)}\n`));
        c.close();
      },
    });
    return new Response(stream, { status: 200, headers: { "Content-Type": "application/x-ndjson" } });
  }

  const refusal = (status: number, code: string, message: string) => () =>
    new Response(JSON.stringify({ detail: { code, message } }), {
      status,
      headers: { "Content-Type": "application/json" },
    });

  it("returns the raw streamed body, unread, after a JSON POST asking for NDJSON", async () => {
    const lines = [{ type: "text", text: "Hel" }, { type: "text", text: "lo" }, { type: "done", tokens: 12 }];
    const { transport, calls } = streamTransport(() => ndjson(lines));
    const r = await new Client(transport, "127.0.0.1").postStream("/api/assistant/ask", { q: "hi" });
    expect(r.bodyUsed).toBe(false);
    expect(calls[0].method).toBe("POST");
    expect(JSON.parse(String(calls[0].body))).toEqual({ q: "hi" });
    expect(new Headers(calls[0].headers).get("Accept")).toBe("application/x-ndjson");
    const text = await r.text();
    expect(text.trim().split("\n").map((l) => JSON.parse(l))).toEqual(lines);
  });

  it.each([
    [401, "login_required", "log in first"],
    [423, "locked", "the login is locked"],
  ])("re-reads the login on %i and throws, without touching read-only", async (status, code, message) => {
    const { transport } = streamTransport(refusal(status, code, message));
    const client = new Client(transport, "127.0.0.1");
    const auth = vi.fn();
    client.onAuthFailure(auth);
    await expect(client.postStream("/api/assistant/ask", {})).rejects.toMatchObject({ status, code, detail: message });
    expect(auth).toHaveBeenCalledWith(status);
    expect(client.readOnly.get().readOnly).toBe(false);
  });

  it("turns the app read-only on a 403 marked remote_view", async () => {
    const { transport } = streamTransport(refusal(403, "remote_view", "remote viewers may only read"));
    const client = new Client(transport, "127.0.0.1");
    await expect(client.postStream("/api/assistant/ask", {})).rejects.toBeInstanceOf(CommandRefused);
    expect(client.readOnly.get()).toEqual({ readOnly: true, why: "remote viewers may only read" });
  });

  it("returns any other 403 to the caller and keeps the app writable", async () => {
    const { transport } = streamTransport(refusal(403, "assistant_off", "the assistant is turned off"));
    const client = new Client(transport, "127.0.0.1");
    await expect(client.postStream("/api/assistant/ask", {})).rejects.toMatchObject({ code: "assistant_off" });
    expect(client.readOnly.get().readOnly).toBe(false);
  });
});

describe("EventStream", () => {
  it("delivers engine events and ignores other messages", () => {
    const { transport, sockets } = fakeTransport({});
    const es = new EventStream(transport);
    const got = vi.fn();
    es.on(got);
    es.start();
    expect(sockets[0].path).toBe("/ws/events");
    sockets[0].open();
    sockets[0].event("position", { z_um: 3048.7 });
    sockets[0].send({ type: "accepted", op_id: "x" });
    sockets[0].send("not json");
    expect(got).toHaveBeenCalledTimes(1);
    expect(got.mock.calls[0][0]).toMatchObject({ kind: "position", data: { z_um: 3048.7 } });
  });

  it("reports open/closed and reconnects with backoff", () => {
    vi.useFakeTimers();
    const { transport, sockets } = fakeTransport({});
    const es = new EventStream(transport, "/ws/events", () => 1000);
    const status = vi.fn();
    es.onStatus(status);
    es.start();
    sockets[0].open();
    sockets[0].close();
    expect(status.mock.calls.map((c) => c[0])).toEqual([true, false]);
    expect(sockets).toHaveLength(1);
    vi.advanceTimersByTime(1000);
    expect(sockets).toHaveLength(2);
    es.stop();
    expect(sockets[1].closed).toBe(true);
    vi.advanceTimersByTime(5000);
    expect(sockets).toHaveLength(2);
  });

  it("delivers lock messages to onLock listeners, not to event handlers (T-009c)", () => {
    const { transport, sockets } = fakeTransport({});
    const es = new EventStream(transport);
    const events = vi.fn();
    const lock = vi.fn();
    es.on(events);
    const off = es.onLock(lock);
    es.start();
    sockets[0].open();
    expect(es.locked).toBeNull();
    sockets[0].send({ type: "lock", locked: true });
    sockets[0].send({ type: "lock", locked: "yes" }); // not a boolean: ignored
    sockets[0].send({ type: "lock", locked: false });
    expect(lock.mock.calls.map((c) => c[0])).toEqual([true, false]);
    expect(es.locked).toBe(false);
    expect(events).not.toHaveBeenCalled();
    off();
    sockets[0].send({ type: "lock", locked: true });
    expect(lock).toHaveBeenCalledTimes(2);
    expect(es.locked).toBe(true);
  });
});
