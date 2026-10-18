import { act, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { Client, ClientProvider, type Transport } from "../../app/client";
import { ScreenContextProvider } from "../../app/screenContext";
import { fakeTransport } from "../../test/fakes";
import { type Permissions, SESSION_OPS, type SessionDetail } from "./api";
import SessionsScreen from "./index";

// Each render goes through several fetches; on a loaded desktop 1 s (the default) is too short.
configure({ asyncUtilTimeout: 8000 });

// -- a fake /api/sessions server following docs/screens/sessions.md section 2 -----------------

function detailOf(p: Partial<SessionDetail> & Pick<SessionDetail, "session_id" | "sample_id">): SessionDetail {
  return {
    user_id: "operator@example.test",
    user_name: "Operator",
    status: "closed",
    started_at: "2026-10-01T09:05:00-07:00",
    closed_at: "2026-10-01T11:40:00-07:00",
    continues: null,
    reflected: null,
    code: { repo: "D:/AutoFocus/dino-autofocus", commit: "0".repeat(40), dirty: false, error: null },
    hardware_profile: null,
    sma_run_id: null,
    close_note: "",
    log_tail: [],
    records: [],
    manifest: { files: 0, bytes: 0, by_where: {}, entries: [] },
    ...p,
  };
}

const ALLOWED: Permissions = Object.fromEntries(SESSION_OPS.map((op) => [op, { allowed: true, reason: null }]));

interface World {
  sessions: SessionDetail[];
  sample: string | null;
  user: { user_id: string; role: "admin" | "operator" | "viewer" };
  /** null: /api/permissions answers 404 (cannot be read) */
  permissions: Permissions | null;
}

function server(w: World) {
  let n = 0;
  const json = (status: number, body: unknown) => ({ status, body });
  // T-009b refusals: detail = {code, message}
  const no = (status: number, message: string, code = "refused") => json(status, { detail: { code, message } });
  const summary = ({ log_tail: _l, records: _r, manifest: _m, code: _c, hardware_profile: _h, ...s }: SessionDetail) => s;
  const openFor = (sampleId: string, continues: string | null) => {
    const open = w.sessions.find((s) => s.status === "open");
    if (open) return no(409, `${open.session_id} is open; close it first`);
    n += 1;
    const d = detailOf({
      session_id: `fake-${n}`,
      sample_id: sampleId,
      user_id: w.user.user_id,
      status: "open",
      closed_at: null,
      continues,
    });
    w.sessions.push(d);
    return json(201, d);
  };

  return (path: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const [p, q = ""] = path.split("?");
    const query = new URLSearchParams(q);
    if (p === "/api/permissions") return w.permissions ? json(200, w.permissions) : no(404, "Not Found");
    if (p === "/api/state") return json(200, { sample: { sample_id: w.sample, reserved: false, session_id: null } });
    if (p === "/api/sessions" && method === "GET") {
      const rows = w.sessions.filter(
        (s) =>
          (!query.get("user") || s.user_id === query.get("user")) &&
          (!query.get("sample") || s.sample_id === query.get("sample")) &&
          (!query.get("status") || s.status === query.get("status")),
      );
      return json(200, rows.map(summary));
    }
    if (p === "/api/sessions/current") {
      const open = w.sessions.filter((s) => s.status === "open");
      return json(200, open.length ? summary(open[open.length - 1]) : null);
    }
    if (p === "/api/sessions" && method === "POST") {
      if (!w.sample) return no(409, "Open or create a sample first");
      return openFor(w.sample, null);
    }
    const m = /^\/api\/sessions\/([^/]+)(?:\/(close|continue))?$/.exec(p);
    if (!m) return no(404, "Not Found");
    const s = w.sessions.find((x) => x.session_id === decodeURIComponent(m[1]));
    if (!s) return no(404, `No experiment session ${m[1]}`);
    if (!m[2]) return json(200, s);
    if (m[2] === "close") {
      if (s.status === "closed") return no(409, `Session ${s.session_id} is closed (read-only)`);
      if (w.user.role !== "admin" && s.user_id !== w.user.user_id) {
        return no(403, `Only ${s.user_id} or an admin can close this session`, "not_owner");
      }
      s.status = "closed";
      s.closed_at = "2026-10-01T12:00:00-07:00";
      s.close_note = String(JSON.parse(String(init?.body ?? "{}")).note ?? "");
      return json(200, s);
    }
    w.sample = s.sample_id; // the router runs sample_open first
    return openFor(s.sample_id, s.session_id);
  };
}

function show(o: Partial<World> = {}, hash = "#/sessions", hostname = "127.0.0.1") {
  const world: World = {
    sessions: [],
    sample: null,
    user: { user_id: "operator@example.test", role: "operator" },
    permissions: ALLOWED,
    ...o,
  };
  const answer = server(world);
  // the shared fake for sockets and the call log; every fetch goes to this file's fake server
  // (its paths carry ids and queries, so no fixed route table fits them)
  const t = fakeTransport({});
  const transport: Transport = {
    ...t.transport,
    fetch: async (path, init) => {
      t.calls.push({ path, init });
      const { status, body } = answer(path, init);
      return new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    },
  };
  window.location.hash = hash;
  render(
    <ClientProvider client={new Client(transport, hostname)}>
      <ScreenContextProvider area="sessions">
        <SessionsScreen />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  return { world, ...t };
}

const button = (name: RegExp | string) => screen.getByRole("button", { name }) as HTMLButtonElement;

async function enabled(name: RegExp | string) {
  return waitFor(
    () => {
      const b = button(name);
      expect(b.disabled).toBe(false);
      return b;
    },
    { timeout: 8000 },
  );
}

const CLOSED = detailOf({
  session_id: "20261001-0905-operator-1",
  sample_id: "20260930_1849_1",
  code: { repo: "r", commit: "abcdef1234567890".padEnd(40, "0"), dirty: true, error: null },
  hardware_profile: { path: "hardware_profile.json", sha256: "1234567890ab".padEnd(64, "f") },
  records: [{ name: "scan_4x.jsonl", lines: 5 }],
  manifest: { files: 2, bytes: 11_520_100, by_where: { data: 1, session: 1 }, entries: [] },
  log_tail: [{ t: "2026-10-01T09:05:00-07:00", level: "info", msg: "session opened" }],
  reflected: true,
});

const copy = (d: SessionDetail): SessionDetail => JSON.parse(JSON.stringify(d));

describe("sessions screen", { timeout: 30_000 }, () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("lists sessions and shows a detail as recorded", async () => {
    show({ sessions: [copy(CLOSED)] }, `#/sessions/${CLOSED.session_id}`);
    const table = await screen.findByRole("table", { name: "Sessions" });
    await within(table).findByText(CLOSED.session_id);
    const detail = await screen.findByRole("article", { name: "Session detail" });
    expect(within(detail).getByText("abcdef123456")).toBeTruthy(); // code commit, as recorded
    expect(within(detail).getByText(/uncommitted changes/)).toBeTruthy();
    expect(within(detail).getByText("1234567890ab")).toBeTruthy(); // hardware sha256
    expect(within(detail).getByText("scan_4x.jsonl: 5 lines")).toBeTruthy();
    expect(screen.getByTestId("current").textContent).toBe("No experiment session");
  });

  it("filters the list by status through the query string", async () => {
    const open = detailOf({ session_id: "s-open", sample_id: "x", status: "open", closed_at: null });
    const t = show({ sessions: [copy(CLOSED), open] });
    await screen.findByText("s-open");
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "closed" } });
    await waitFor(() => expect(screen.queryByText("s-open")).toBeNull());
    expect(screen.getByText(CLOSED.session_id)).toBeTruthy();
    expect(t.calls.some((c) => c.path === "/api/sessions?status=closed")).toBe(true);
  });

  it("opens a session for the current sample and closes it", async () => {
    const t = show({ sample: "20260930_1849_1" });
    const open = await enabled("Open experiment session for 20260930_1849_1"); // wait outside act()
    await act(async () => fireEvent.click(open));
    await waitFor(() => expect(screen.getByTestId("current").textContent).toBe("Open: fake-1 · 20260930_1849_1"));
    expect(button(/Open experiment session/).disabled).toBe(true);
    expect(screen.getByText("fake-1 is open; close it first")).toBeTruthy();
    expect(window.location.hash).toBe("#/sessions/fake-1");

    fireEvent.change(await screen.findByLabelText("Note"), { target: { value: "done" } });
    await act(async () => fireEvent.click(button("Close")));
    await waitFor(() => expect(screen.getByTestId("current").textContent).toBe("No experiment session"));
    expect(button("Close").disabled).toBe(true);
    expect(screen.getByText("Session fake-1 is closed (read-only)")).toBeTruthy();
    const close = t.calls.find((c) => c.path === "/api/sessions/fake-1/close");
    expect(close?.init?.method).toBe("POST");
    expect(JSON.parse(String(close?.init?.body))).toEqual({ note: "done" });
    expect(t.calls.some((c) => c.path === "/api/commands")).toBe(false); // router POSTs, not commands
  });

  it("says why opening is off when no sample is current", async () => {
    show({ sample: null });
    await waitFor(() => expect(screen.getByText("Open or create a sample first")).toBeTruthy());
    expect(button("Open experiment session").disabled).toBe(true);
  });

  it("continues a closed session with the same sample", async () => {
    show({ sessions: [copy(CLOSED)] }, `#/sessions/${CLOSED.session_id}`);
    const cont = await enabled("Continue with this sample");
    await act(async () => fireEvent.click(cont));
    await waitFor(() => expect(screen.getByTestId("current").textContent).toBe(`Open: fake-1 · ${CLOSED.sample_id}`));
    const detail = await screen.findByRole("article", { name: "Session detail" });
    await within(detail).findByText("fake-1");
    expect(within(detail).getAllByText(CLOSED.session_id).length).toBeGreaterThan(0); // continues
  });

  it("is read-only on a remote screen, with the shell's reason", async () => {
    const open = detailOf({ session_id: "s-open", sample_id: "x", status: "open", closed_at: null });
    show({ sessions: [copy(CLOSED), open], sample: "x" }, "#/sessions/s-open", "192.168.1.20");
    await screen.findByRole("article", { name: "Session detail" });
    await waitFor(() => expect(screen.getAllByText("Read-only: remote view").length).toBe(3));
    expect(button(/Open experiment session/).disabled).toBe(true);
    expect(button("Close").disabled).toBe(true);
    expect(button("Continue with this sample").disabled).toBe(true);
  });

  it("shows the shared check's reason for a viewer", async () => {
    const viewer = Object.fromEntries(SESSION_OPS.map((op) => [op, { allowed: false, reason: "Needs the operator role" }]));
    show({ sample: "x", permissions: viewer });
    await waitFor(() => expect(screen.getByText("Needs the operator role")).toBeTruthy());
    expect(button(/Open experiment session/).disabled).toBe(true);
  });

  it("turns every control off when the permission check cannot be read, keeping list and detail", async () => {
    show({ sessions: [copy(CLOSED)], sample: "x", permissions: null }, `#/sessions/${CLOSED.session_id}`);
    const detail = await screen.findByRole("article", { name: "Session detail" });
    expect(within(detail).getByText("abcdef123456")).toBeTruthy();
    expect(within(screen.getByRole("table", { name: "Sessions" })).getByText(CLOSED.session_id)).toBeTruthy();
    await waitFor(() => expect(screen.getAllByText("Permission check unavailable").length).toBe(3));
    expect(button(/Open experiment session/).disabled).toBe(true);
    expect(button("Close").disabled).toBe(true);
    expect(button("Continue with this sample").disabled).toBe(true);
  });

  it("treats an op missing from the answer as unavailable", async () => {
    show({ sample: "x", permissions: { session_close: { allowed: true, reason: null } } });
    await waitFor(() => expect(screen.getByText("Permission check unavailable")).toBeTruthy());
    expect(button(/Open experiment session/).disabled).toBe(true);
  });

  it("shows the loading reason until the first check answers", () => {
    show({ sample: "x" });
    expect(screen.getByText("Checking permissions\u2026")).toBeTruthy();
  });

  it("refuses closing someone else's session with the router's reason", async () => {
    const other = detailOf({
      session_id: "s-other",
      sample_id: "x",
      status: "open",
      closed_at: null,
      user_id: "second@example.test",
    });
    show({ sessions: [other] }, "#/sessions/s-other");
    await screen.findByRole("article", { name: "Session detail" });
    const close = await enabled("Close"); // ownership is the router's 403, not a screen rule
    await act(async () => fireEvent.click(close));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Only second@example.test or an admin can close this session",
    );
    expect(button("Close").disabled).toBe(false); // an area 403 does not switch the app to read-only
  });
});
