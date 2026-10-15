import { describe, expect, it } from "vitest";

import { fakeTransport, type Route, TEST_ME } from "./fakes";

const ok = (body: unknown): Route => () => ({ status: 200, body });

describe("fakeTransport", () => {
  it("answers from a Proxy routes table that has no own keys (map testWorld)", async () => {
    const routes = new Proxy({} as Record<string, Route>, {
      get: (_t, path) => (String(path).startsWith("/api/map/") ? ok({ path: String(path) }) : undefined),
    });
    const { transport } = fakeTransport(routes);
    const r = await transport.fetch("/api/map/s1/flags");
    expect(r.status).toBe(200);
    expect(await r.json()).toEqual({ path: "/api/map/s1/flags" });
    // the auth defaults still answer what the Proxy does not
    const me = await transport.fetch("/api/auth/me");
    expect(await me.json()).toEqual(TEST_ME);
  });

  it("lets a test route win over a default, and answers 404 for unknown paths", async () => {
    const { transport } = fakeTransport({ "/api/auth/me": ok({ name: "Someone Else" }) });
    expect(await (await transport.fetch("/api/auth/me")).json()).toEqual({ name: "Someone Else" });
    expect((await transport.fetch("/api/nowhere")).status).toBe(404);
  });

  it("answers 401 on /api/auth/me with { me: null }", async () => {
    const { transport } = fakeTransport({}, { me: null });
    expect((await transport.fetch("/api/auth/me")).status).toBe(401);
  });
});
