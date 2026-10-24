import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { fakeTransport, TEST_ME } from "../test/fakes";
import { App } from "./App";
import { AREAS, DEFAULT_AREA, registry } from "./areas";
import { Client, ClientProvider } from "./client";
import { parseHash } from "./route";
import { STOP_ALL_PATH } from "./StopAllRuns";

/**
 * The pared-down shell (console card 008): a left sidebar of six areas and Admin for an
 * administrator, a footer on every screen with STOP, an example-data chip and the login corner.
 */

const STORE_PATH = "/api/console/store";
const MOCK_STORE = { store: "mock", writable: true };
const SMA_STORE = { store: "soft-matter-agents", writable: false };
const ADMIN = { ...TEST_ME, role: "admin", name: "Ada Admin" };

const SIX = ["Questions", "Instruments", "Experiments", "Simulation", "Library", "Results"];

const clients: Client[] = [];
beforeEach(() => {
  window.location.hash = "";
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((c) => c.events.stop());
  window.location.hash = "";
});

function app(opts: { me?: Record<string, unknown>; store?: Record<string, unknown>; hash?: string } = {}) {
  window.location.hash = opts.hash ?? "";
  const fake = fakeTransport(
    {
      [STORE_PATH]: () => ({ status: 200, body: opts.store ?? MOCK_STORE }),
      [STOP_ALL_PATH]: () => ({ status: 200, body: { message: "No run is running. Nothing was sent.", runs: [], audited: true } }),
      "/api/auth/logout": () => ({ status: 204 }),
      // an engine that says a light did not read back off: the shell does not ask, and shows nothing of it
      "/api/state": () => ({ status: 200, body: { running: [], last_shutdown_lights: { t: 1, all_off: false } } }),
    },
    { me: opts.me ?? { ...TEST_ME } },
  );
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  render(<App client={client} />);
  return fake;
}

const navLabels = () =>
  within(screen.getByRole("navigation", { name: "Areas" }))
    .getAllByRole("link")
    .map((a) => a.textContent);

const footer = () => screen.getByTestId("shell-footer");

describe("the sidebar", () => {
  it("lists exactly the six areas, in order, for a login that is not an administrator", async () => {
    app();
    await screen.findByRole("navigation", { name: "Areas" });
    expect(navLabels()).toEqual(SIX);
    expect(AREAS.map((a) => a.id)).toEqual(["questions", "instruments", "experiments", "simulation", "library", "results", "admin"]);
    expect(DEFAULT_AREA).toBe("questions");
  });

  it("adds Admin, below a rule, for an administrator only", async () => {
    app({ me: { ...ADMIN } });
    await screen.findByRole("navigation", { name: "Areas" });
    expect(navLabels()).toEqual([...SIX, "Admin"]);
    expect(registry.filter((e) => e.adminOnly).map((e) => e.id)).toEqual(["admin"]);
    const nav = screen.getByRole("navigation", { name: "Areas" });
    expect(nav.querySelector("hr, [role=separator]")).not.toBeNull();
  });

  it("an operator who opens #/admin lands on Questions and is not shown the Admin screen", async () => {
    app({ hash: "#/admin" });
    await screen.findByRole("navigation", { name: "Areas" });
    await waitFor(() => expect(screen.getByRole("link", { name: "Questions" }).getAttribute("aria-current")).toBe("page"));
    expect(screen.queryByRole("link", { name: "Admin" })).toBeNull();
  });

  it("an administrator opening #/admin is on Admin", async () => {
    app({ me: { ...ADMIN }, hash: "#/admin" });
    await screen.findByRole("navigation", { name: "Areas" });
    await waitFor(() => expect(screen.getByRole("link", { name: "Admin" }).getAttribute("aria-current")).toBe("page"));
  });

  it("has the project's name at the top and not the old title", async () => {
    app();
    const nav = await screen.findByRole("navigation", { name: "Areas" });
    expect(within(nav).getByText("Soft-matter agents")).toBeTruthy();
    expect(screen.queryByText("Takatori Lab Console")).toBeNull();
  });

  it("opens an area from the sidebar and marks it", async () => {
    app();
    await screen.findByRole("navigation", { name: "Areas" });
    fireEvent.click(screen.getByRole("link", { name: "Library" }));
    expect(window.location.hash).toBe("#/library");
    await waitFor(() => expect(screen.getByRole("link", { name: "Library" }).getAttribute("aria-current")).toBe("page"));
    await screen.findByRole("heading", { name: "Library" });
  });
});

describe("old routes", () => {
  it.each(["#/console", "#/hardware", "#/sample", "#/map", "#/objective", "#/patterns", "#/tweezers", "#/sessions", "#/accounts", "#/live", "#/nowhere", ""])(
    "%s lands on Questions",
    (hash) => {
      expect(parseHash(hash)).toEqual({ area: "questions", rest: "" });
    },
  );

  it("an old hash opens the Questions screen in the app", async () => {
    app({ hash: "#/hardware" });
    await screen.findByRole("navigation", { name: "Areas" });
    await waitFor(() => expect(screen.getByRole("link", { name: "Questions" }).getAttribute("aria-current")).toBe("page"));
  });

  it("the new names are routes, with what follows them passed through", () => {
    expect(parseHash("#/questions")).toEqual({ area: "questions", rest: "" });
    expect(parseHash("#/simulation/runs/run-20260924-001")).toEqual({ area: "simulation", rest: "runs/run-20260924-001" });
    expect(parseHash("#/instruments")).toEqual({ area: "instruments", rest: "" });
  });
});

describe("the footer, on every screen", () => {
  it.each([...SIX, "Admin"])("%s shows STOP, the login and Log out", async (label) => {
    app({ me: { ...ADMIN }, hash: `#/${label.toLowerCase()}` });
    await screen.findByRole("navigation", { name: "Areas" });
    await waitFor(() => expect(screen.getByRole("link", { name: label }).getAttribute("aria-current")).toBe("page"));
    const f = within(footer());
    expect(f.getByRole("button", { name: "Stop all runs" })).toBeTruthy();
    expect(f.getByText("Ada Admin")).toBeTruthy();
    expect(f.getByRole("button", { name: "Log out" })).toBeTruthy();
    await waitFor(() => expect(screen.queryByText(`Loading ${label}…`)).toBeNull()); // the screen itself has loaded
  });

  it("STOP is the first thing in the footer and the login corner the last", async () => {
    app();
    await screen.findByRole("navigation", { name: "Areas" });
    const f = footer();
    const buttons = within(f).getAllByRole("button");
    expect(buttons[0].textContent).toBe("Stop all runs");
    expect(buttons[buttons.length - 1].textContent).toBe("Log out");
  });

  it("a press of STOP makes one request to the stop route and no other write", async () => {
    const fake = app({ hash: "#/library" });
    await screen.findByRole("navigation", { name: "Areas" });
    fireEvent.click(within(footer()).getByRole("button", { name: "Stop all runs" }));
    await screen.findByTestId("stop-all-result");
    const posts = fake.calls.filter((c) => c.init?.method === "POST").map((c) => c.path);
    expect(posts).toEqual([STOP_ALL_PATH]);
  });

  it("says Example data when the store is the mock, and nothing when it is not", async () => {
    app();
    await waitFor(() => expect(within(footer()).getByText("Example data")).toBeTruthy());
    cleanup();
    app({ store: SMA_STORE });
    await screen.findByRole("navigation", { name: "Areas" });
    await waitFor(() => expect(screen.queryByText("Loading Questions…")).toBeNull());
    expect(within(footer()).queryByText("Example data")).toBeNull();
  });

  it("says so when the server says this browser is not on the microscope computer", async () => {
    app({ me: { ...TEST_ME, local: false } });
    const chip = await screen.findByTestId("remote-chip");
    expect(chip.textContent).toBe("viewing from another computer · read only");
    expect(within(footer()).getByTestId("remote-chip")).toBe(chip);
  });

  it("shows no such chip on the microscope computer", async () => {
    app();
    await screen.findByRole("navigation", { name: "Areas" });
    expect(screen.queryByTestId("remote-chip")).toBeNull();
  });

  it("has a Lock button beside Log out, Lock first, and it locks the screen", async () => {
    let locked = false;
    window.location.hash = "";
    const fake = fakeTransport(
      {
        [STORE_PATH]: () => ({ status: 200, body: MOCK_STORE }),
        "/api/auth/lock": () => {
          locked = true;
          return { status: 204 };
        },
        "/api/auth/me": () => ({ status: 200, body: { ...TEST_ME, locked } }),
      },
      { me: { ...TEST_ME } },
    );
    const client = new Client(fake.transport, "127.0.0.1");
    clients.push(client);
    render(<App client={client} />);
    await screen.findByRole("navigation", { name: "Areas" });
    const names = within(footer()).getAllByRole("button").map((b) => b.textContent);
    expect(names.slice(-2)).toEqual(["Lock", "Log out"]);
    fireEvent.click(within(footer()).getByRole("button", { name: "Lock" }));
    await screen.findByRole("dialog", { name: "Locked" });
    expect(fake.calls.filter((c) => c.init?.method === "POST").map((c) => c.path)).toContain("/api/auth/lock");
    // STOP stays reachable on the lock screen (card 004)
    expect(screen.getAllByRole("button", { name: "Stop all runs" }).length).toBeGreaterThan(0);
  });

  it("Log out is the login's own control and makes the logout call", async () => {
    const fake = app();
    await screen.findByRole("navigation", { name: "Areas" });
    fireEvent.click(within(footer()).getByRole("button", { name: "Log out" }));
    await waitFor(() => expect(fake.calls.some((c) => c.path === "/api/auth/logout")).toBe(true));
  });

  it("shows no password, filled or empty", async () => {
    app({ me: { ...ADMIN }, hash: "#/admin" });
    await screen.findByRole("navigation", { name: "Areas" });
    await waitFor(() => expect(screen.queryByText("Loading Admin…")).toBeNull());
    expect(document.querySelector("input[type=password]")).toBeNull();
  });
});

describe("what the shell leaves out", () => {
  it("renders no lights, assistant, control or focus reading, and no side panel", async () => {
    app({ me: { ...ADMIN } });
    await screen.findByRole("navigation", { name: "Areas" });
    const f = footer().textContent ?? "";
    expect(f).not.toMatch(/lights?|assistant|control|focus|position|server:|running:|idle/i);
    expect(screen.queryByRole("button", { name: "Take" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Release" })).toBeNull();
    expect(screen.queryByRole("button", { name: "User menu" })).toBeNull();
    expect(document.querySelector("aside")).toBeNull();
    expect(screen.queryByLabelText("Prompt")).toBeNull();
    expect(screen.queryByTestId("shutdown-notice")).toBeNull();
    expect(screen.queryByTestId("sb-lights")).toBeNull();
    expect(screen.queryByTestId("sb-assistant")).toBeNull();
  });

  it("asks the server for no light, assistant or engine state", async () => {
    const fake = app({ me: { ...ADMIN } });
    await screen.findByRole("navigation", { name: "Areas" });
    await waitFor(() => expect(screen.queryByText("Loading Questions…")).toBeNull());
    const paths = fake.calls.map((c) => c.path);
    expect(paths).not.toContain("/api/state");
    expect(paths).not.toContain("/api/assistant/status");
    expect(paths).not.toContain("/api/auth/control");
  });
});

describe("the seven retired areas are gone", () => {
  const RETIRED = ["hardware", "sample", "map", "objective", "patterns", "tweezers", "sessions"];
  const sources = import.meta.glob("../**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
  const nonTest = Object.entries(sources).filter(([f]) => !/\.test\.(ts|tsx)$/.test(f));

  it("reads every non-test source file", () => {
    expect(nonTest.length).toBeGreaterThan(50);
  });

  it("none of the seven is an area, and none has a screen folder", () => {
    const ids = AREAS.map((a) => a.id) as string[];
    const folders = Object.keys(import.meta.glob("../features/*/index.tsx"));
    for (const id of RETIRED) {
      expect(ids).not.toContain(id);
      expect(folders).not.toContain(`../features/${id}/index.tsx`);
    }
  });

  it("the notice component is gone and no file imports it", () => {
    expect(Object.keys(sources).filter((f) => /\/Retired(\.test)?\.tsx$/.test(f))).toEqual([]);
    const importers = nonTest.filter(([, text]) => /from\s+["'][^"']*\/Retired["']/.test(text)).map(([f]) => f);
    expect(importers).toEqual([]);
  });

  it("the guard itself fires on an import of it", () => {
    expect(/from\s+["'][^"']*\/Retired["']/.test('import { Retired } from "../../app/Retired";')).toBe(true);
    expect(/from\s+["'][^"']*\/Retired["']/.test('import { x } from "./RetiredThing";')).toBe(false);
  });
});

describe("the retired routes are still named by no source", () => {
  const sources = import.meta.glob("../**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
  // a route, not a module path such as `server/api/hardware.GateRow` in a model's docstring
  const ROUTE = /(?<![\w/])\/api\/(commands|hardware|map|objective|patterns|sample|sessions)\b/;

  it("finds none, in the schema or in any screen", () => {
    const hits = Object.entries(sources)
      .filter(([f]) => !/\.test\.(ts|tsx)$/.test(f))
      .filter(([, text]) => ROUTE.test(text))
      .map(([f]) => f);
    expect(hits).toEqual([]);
  });

  it("the guard itself fires on a retired route", () => {
    expect(ROUTE.test('client.post("/api/commands", cmd)')).toBe(true);
    expect(ROUTE.test("`/api/sample/${id}`")).toBe(true);
    expect(ROUTE.test("/api/console/runs")).toBe(false);
    expect(ROUTE.test("server/api/hardware.GateRow")).toBe(false);
  });
});

describe("the new plain screens", () => {
  const modules = import.meta.glob<{ default: ComponentType }>("../features/*/index.tsx");
  const CASES = [
    { id: "experiments", title: "Experiments", sentence: "Runs on the microscope, and drafts waiting for your signature." },
    { id: "library", title: "Library", sentence: "Send the librarian a request. The librarian decides, and nothing is ever erased." },
  ];

  it.each(CASES)("$title shows its title, one sentence and 'not built yet', and requests nothing", async ({ id, title, sentence }) => {
    const load = modules[`../features/${id}/index.tsx`];
    expect(load, `features/${id}/index.tsx exists`).toBeTypeOf("function");
    const Screen = (await load()).default;
    const fake = fakeTransport({});
    const client = new Client(fake.transport, "127.0.0.1");
    clients.push(client);
    render(
      <ClientProvider client={client}>
        <Screen />
      </ClientProvider>,
    );
    expect(screen.getByRole("heading", { name: title })).toBeTruthy();
    expect(screen.getByText(sentence)).toBeTruthy();
    expect(screen.getByText("not built yet")).toBeTruthy();
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    await new Promise((r) => setTimeout(r, 20)); // a request made in an effect would be here by now
    expect(fake.calls).toEqual([]);
  });
});
