import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createContext, useContext } from "react";
import { describe, expect, it, vi } from "vitest";

import { fakeTransport, type FakeOptions, type Route } from "../test/fakes";
import {
  ACTIVITY_MS,
  LoginGate,
  loginAvailable,
  pickLogin,
  seamFrom,
  type ShellAuth,
  type ShellMe,
  useActivity,
} from "./auth";
import { Client, ClientProvider } from "./client";
import { StatusBarView } from "./StatusBar";

const ME: ShellMe = {
  user_id: "kyu@example.org",
  name: "Kyu",
  role: "operator",
  locked: false,
 
  local: true,
};

function withClient(ui: React.ReactNode, routes: Record<string, Route> = {}, opts: FakeOptions = {}) {
  const t = fakeTransport(routes, opts);
  const client = new Client(t.transport, "127.0.0.1");
  render(<ClientProvider client={client}>{ui}</ClientProvider>);
  return { ...t, client };
}

// A stand-in login module: its gate shows its children only after "logging in".
function stubLoginModule() {
  const me = { ...ME, name: "Stub User" };
  const auth: ShellAuth = { me, api: {}, logout: async () => {}, lock: async () => {}, refresh: async () => {} };
  const Ctx = createContext<ShellAuth | null>(null);
  return {
    LoginGate: ({ abort, children }: { abort?: React.ReactNode; children: React.ReactNode }) => (
      <div data-testid="stub-gate">
        {abort}
        <Ctx.Provider value={auth}>{children}</Ctx.Provider>
      </div>
    ),
    useAuth: () => useContext(Ctx),
    ApprovalList: () => <p>stub approvals</p>,
  };
}

describe("login seam", () => {
  it("picks a login module only when one is in the build", () => {
    expect(pickLogin({})).toBeNull();
    const mod = stubLoginModule();
    expect(pickLogin({ "./login/index.ts": mod })).toBe(mod);
  });

  it("uses the login gate when present: its gate, its auth state, its abort slot", () => {
    const seam = seamFrom(stubLoginModule());
    function Probe() {
      return <p>user: {seam.useAuth()?.me.name ?? "none"}</p>;
    }
    withClient(
      <seam.LoginGate abort={<span>abort here</span>}>
        <Probe />
      </seam.LoginGate>,
    );
    expect(screen.getByTestId("stub-gate")).toBeTruthy();
    expect(screen.getByText("abort here")).toBeTruthy();
    expect(screen.getByText("user: Stub User")).toBeTruthy();
  });

  it("passes the app through with no auth state when there is no login module", () => {
    const seam = seamFrom(null);
    function Probe() {
      return <p>user: {seam.useAuth()?.me.name ?? "none"}</p>;
    }
    withClient(
      <seam.LoginGate abort={<span>abort here</span>}>
        <Probe />
      </seam.LoginGate>,
    );
    expect(screen.getByText("user: none")).toBeTruthy();
    expect(screen.queryByText("abort here")).toBeNull();
  });

  it("lets a logged-in test user into the app, with or without T-105 in the build", async () => {
    withClient(
      <LoginGate abort={<span>abort</span>}>
        <p>the app</p>
      </LoginGate>,
    );
    expect(await screen.findByText("the app")).toBeTruthy();
  });

  it.runIf(loginAvailable)("keeps the app behind T-105's gate when /api/auth/me says logged out", async () => {
    withClient(
      <LoginGate abort={<span>abort</span>}>
        <p>the app</p>
      </LoginGate>,
      {},
      { me: null },
    );
    await waitFor(() => expect(screen.queryByText("Checking login…")).toBeNull());
    expect(screen.queryByText("the app")).toBeNull();
  });

});

describe("activity", () => {
  function Probe({ now }: { now: () => number }) {
    useActivity(true, now);
    return null;
  }

  it("posts at most once every 30 s of input", () => {
    let t = 1_000_000;
    const { calls } = withClient(<Probe now={() => t} />, { "/api/auth/activity": () => ({ status: 204 }) });
    const posts = () => calls.filter((c) => c.path === "/api/auth/activity").length;
    act(() => {
      fireEvent.keyDown(window);
      fireEvent.pointerDown(window);
    });
    expect(posts()).toBe(1);
    t += ACTIVITY_MS - 1;
    act(() => void fireEvent.keyDown(window));
    expect(posts()).toBe(1);
    t += 1;
    act(() => void fireEvent.keyDown(window));
    expect(posts()).toBe(2);
  });
});

describe("auth failures and stale values", () => {
  it("tells listeners about 401 and 423 answers", async () => {
    const { client } = withClient(<span />, {
      "/api/state": () => ({ status: 401, body: { detail: "log in" } }),
      "/api/x": () => ({ status: 423, body: { detail: "locked" } }),
    });
    const seen = vi.fn();
    client.onAuthFailure(seen);
    await client.get("/api/state").catch(() => {});
    await client.get("/api/x").catch(() => {});
    expect(seen.mock.calls.map((c) => c[0])).toEqual([401, 423]);
  });

  it("never shows old lights or XY/Z as current while the event socket is down", () => {
    const at = new Date(2026, 9, 1, 18, 30, 5).getTime();
    render(
      <StatusBarView
        status={{
          loaded: true,
          error: null,
          connected: false,
          positions: { x_um: 1, y_um: 2, z_um: 3 },
          lights: { lights: [{ name: "DiaLamp", on: false, raw: "0" }], verified: true, error: null },
          positionsAt: at,
          lightsAt: at,
          running: [],
          lastShutdown: null,
        }}
        assistant={{ available: false, provider: null, connected: null, data_stage: null }}
        readOnly={{ readOnly: false, why: null }}
      />,
    );
    const lights = screen.getByTestId("sb-lights-stale").textContent ?? "";
    expect(lights.startsWith("lights: unknown")).toBe(true);
    expect(lights).toContain(`last known at ${new Date(at).toLocaleTimeString()}`);
    expect(screen.queryByTestId("sb-lights")).toBeNull();
    const pos = screen.getByTestId("sb-position");
    expect(pos.getAttribute("data-stale")).toBe("true");
    expect(pos.textContent?.startsWith("position: unknown")).toBe(true);
    expect(pos.querySelector(".encoder-z")).toBeNull();
    // "idle" would be a claim about now; while disconnected it is unknown
    expect(screen.getByTestId("sb-running").textContent).toBe("operation: unknown");
  });
});
