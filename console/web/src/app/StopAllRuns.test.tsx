import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { fakeTransport, TEST_ME } from "../test/fakes";
import { App } from "./App";
import { Client, ClientProvider, type Transport } from "./client";
import { createFakeAuthApi } from "./login/api";
import { LoginGate, useAuth } from "./login/LoginGate";
import { STOP_ALL_PATH, StopAllRuns } from "./StopAllRuns";

function Inside() {
  const auth = useAuth();
  return (
    <div>
      <p>the app</p>
      <button onClick={() => void auth?.lock()}>Lock</button>
    </div>
  );
}

const clients: Client[] = [];
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((c) => c.events.stop());
});

const USERS = [
  { name: "Otto Operator", email: "otto@example.test", password: "otto-pass-1", role: "operator" as const, status: "active" as const },
];

const ANSWER = {
  message: "2 running runs found: 2 began to abort.",
  runs: [
    { run_id: "run-20261005-002", outcome: "begun", message: "run run-20261005-002 began to abort" },
    { run_id: "run-20261005-001", outcome: "begun", message: "run run-20261005-001 began to abort" },
  ],
  audited: true,
};

const posts = (calls: { path: string; init?: RequestInit }[]) => calls.filter((c) => c.init?.method === "POST");
const stops = (calls: { path: string; init?: RequestInit }[]) => posts(calls).filter((c) => c.path === STOP_ALL_PATH);

function setup(route: () => { status: number; body?: unknown }) {
  const fake = fakeTransport({ [STOP_ALL_PATH]: route });
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  return { fake, client };
}

/** The gate over a fake login, with the real stop control in its slot. */
function gate(
  api: ReturnType<typeof createFakeAuthApi>,
  route: () => { status: number; body?: unknown } = () => ({ status: 200, body: ANSWER }),
) {
  const { fake, client } = setup(route);
  render(
    <ClientProvider client={client}>
      <LoginGate api={api} abort={<StopAllRuns />} pollMs={0}>
        <Inside />
      </LoginGate>
    </ClientProvider>,
  );
  return fake;
}

describe("Stop all runs, on the screens a login does not reach (console card 004)", () => {
  it("is on the login screen, before anyone logs in", async () => {
    gate(createFakeAuthApi({ users: USERS }));
    await screen.findByRole("form", { name: "Log in" });
    expect(screen.getByRole("button", { name: "Stop all runs" })).toBeTruthy();
  });

  it("is on the first-run setup screen", async () => {
    gate(createFakeAuthApi({ setup: "needs_admin" }));
    await screen.findByRole("form");
    expect(screen.getByRole("button", { name: "Stop all runs" })).toBeTruthy();
  });

  it("is on the lock screen", async () => {
    const api = createFakeAuthApi({ users: USERS });
    gate(api);
    await screen.findByRole("form", { name: "Log in" });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "otto@example.test" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "otto-pass-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    await screen.findByText("the app");
    expect(screen.queryByRole("button", { name: "Stop all runs" })).toBeNull(); // unlocked: the Console area stops
    fireEvent.click(screen.getByRole("button", { name: "Lock" }));
    await screen.findByRole("dialog", { name: "Locked" });
    expect(screen.getByRole("button", { name: "Stop all runs" })).toBeTruthy();
  });

  it("one press sends one request to the stop route, with nothing in it, and no confirmation", async () => {
    const fake = gate(createFakeAuthApi({ users: USERS }));
    await screen.findByRole("form", { name: "Log in" });
    fireEvent.click(screen.getByRole("button", { name: "Stop all runs" }));
    expect(screen.queryByRole("dialog")).toBeNull(); // no "are you sure"
    await screen.findByTestId("stop-all-result");
    expect(stops(fake.calls)).toHaveLength(1);
    expect(posts(fake.calls)).toHaveLength(1); // no other write
    const sent = stops(fake.calls)[0].init;
    expect(sent?.body).toBeUndefined();
    expect(sent?.headers).toEqual({ Accept: "application/json" }); // no body, so no content type
  });

  it("lists nothing before it stops: it reads no route at all", async () => {
    const fake = gate(createFakeAuthApi({ users: USERS }));
    await screen.findByRole("form", { name: "Log in" });
    const before = fake.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Stop all runs" }));
    await screen.findByTestId("stop-all-result");
    const added = fake.calls.slice(before).map((c) => `${c.init?.method ?? "GET"} ${c.path}`);
    expect(added).toEqual([`POST ${STOP_ALL_PATH}`]);
  });

  it("shows what came back, run by run, in the server's words", async () => {
    gate(createFakeAuthApi({ users: USERS }));
    await screen.findByRole("form", { name: "Log in" });
    fireEvent.click(screen.getByRole("button", { name: "Stop all runs" }));
    const out = await screen.findByTestId("stop-all-result");
    expect(out.textContent).toContain("2 running runs found: 2 began to abort.");
    expect(out.textContent).toContain("run run-20261005-001 began to abort");
    expect(out.textContent).toContain("run run-20261005-002 began to abort");
  });

  it("says when nothing was running, and when the audit log did not take the stop", async () => {
    gate(createFakeAuthApi({ users: USERS }), () => ({
      status: 200,
      body: { message: "No run is running. Nothing was sent.", runs: [], audited: true },
    }));
    await screen.findByRole("form", { name: "Log in" });
    fireEvent.click(screen.getByRole("button", { name: "Stop all runs" }));
    expect((await screen.findByTestId("stop-all-result")).textContent).toBe("No run is running. Nothing was sent.");
    cleanup();
    gate(createFakeAuthApi({ users: USERS }), () => ({ status: 200, body: { ...ANSWER, audited: false } }));
    await screen.findByRole("form", { name: "Log in" });
    fireEvent.click(screen.getByRole("button", { name: "Stop all runs" }));
    expect((await screen.findByTestId("stop-all-result")).textContent).toContain("could not be written to the audit log");
  });

  it("says in words when the server refuses, and when the console is not connected", async () => {
    gate(createFakeAuthApi({ users: USERS }), () => ({
      status: 409,
      body: { detail: { code: "not_connected", message: "the console is not connected to the soft-matter-agents files (start it with --store sma)" } },
    }));
    await screen.findByRole("form", { name: "Log in" });
    fireEvent.click(screen.getByRole("button", { name: "Stop all runs" }));
    expect((await screen.findByRole("alert")).textContent).toContain("not connected to the soft-matter-agents files");
    cleanup();
    gate(createFakeAuthApi({ users: USERS }), () => ({
      status: 401,
      body: { detail: { code: "login_required", message: "log in first" } },
    }));
    await screen.findByRole("form", { name: "Log in" });
    fireEvent.click(screen.getByRole("button", { name: "Stop all runs" }));
    expect((await screen.findByRole("alert")).textContent).toContain("log in first");
  });

  it("cannot be pressed twice while the first press is in flight", async () => {
    const calls: { path: string; init?: RequestInit }[] = [];
    let release: (r: Response) => void = () => undefined;
    const held = new Promise<Response>((resolve) => (release = resolve));
    const transport: Transport = {
      fetch: async (path, init) => {
        calls.push({ path, init });
        if (path === STOP_ALL_PATH) return held;
        return new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 });
      },
      openSocket: () => ({ close: () => undefined }) as unknown as WebSocket,
    };
    const client = new Client(transport, "127.0.0.1");
    clients.push(client);
    render(
      <ClientProvider client={client}>
        <StopAllRuns />
      </ClientProvider>,
    );
    const button = screen.getByRole("button", { name: "Stop all runs" });
    fireEvent.click(button);
    fireEvent.click(button);
    fireEvent.click(button);
    expect(stops(calls)).toHaveLength(1);
    expect((button as HTMLButtonElement).disabled).toBe(true);
    release(new Response(JSON.stringify(ANSWER), { status: 200, headers: { "Content-Type": "application/json" } }));
    await screen.findByTestId("stop-all-result");
    expect((button as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(button); // after it has answered it can be pressed again
    await waitFor(() => expect(stops(calls)).toHaveLength(2));
  });
});

describe("in the real app", () => {
  function app(me: Record<string, unknown> | null) {
    const fake = fakeTransport({ [STOP_ALL_PATH]: () => ({ status: 200, body: ANSWER }) }, { me });
    const client = new Client(fake.transport, "127.0.0.1");
    clients.push(client);
    render(<App client={client} />);
    return fake;
  }

  it("a logged-out console has the button, and a press makes one request", async () => {
    const fake = app(null);
    fireEvent.click(await screen.findByRole("button", { name: "Stop all runs" }));
    await screen.findByTestId("stop-all-result");
    expect(stops(fake.calls)).toHaveLength(1);
    expect(posts(fake.calls)).toHaveLength(1);
  });

  it("a locked console has the button, and a press makes one request", async () => {
    const fake = app({ ...TEST_ME, locked: true });
    await screen.findByRole("dialog", { name: "Locked" });
    fireEvent.click(screen.getByRole("button", { name: "Stop all runs" }));
    await screen.findByTestId("stop-all-result");
    expect(stops(fake.calls)).toHaveLength(1);
    expect(posts(fake.calls)).toHaveLength(1);
  });

  it("a console in use has no stop-all control: the Console area stops a followed run", async () => {
    app({ ...TEST_ME });
    await screen.findByRole("navigation", { name: "Areas" });
    expect(screen.queryByRole("button", { name: "Stop all runs" })).toBeNull();
  });
});
