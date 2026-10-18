import { configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import type { PatternOut } from "../../app/patterns";
import { fakeTransport, type Route } from "../../test/fakes";
import { idFromName } from "./api";
import PatternsScreen from "./index";

configure({ asyncUtilTimeout: 8000 });

const notFound = (id: string) => ({ status: 404, body: { detail: { code: "not_found", message: `no pattern ${id}` } } });

/** A fake /api/patterns following server/api/patterns.py. */
function server(start: PatternOut[] = []) {
  const store = new Map(start.map((p) => [p.id, p]));
  const saves: { id: string; body: Record<string, unknown> }[] = [];
  const routes: Record<string, Route> = new Proxy({} as Record<string, Route>, {
    get(_t, path: string) {
      if (path === "/api/patterns")
        return () => ({
          status: 200,
          body: [...store.values()].map((p) => ({
            id: p.id,
            name: p.name,
            duration_s: p.duration_s,
            targets: p.tracks.map((t) => t.target),
          })),
        });
      const m = /^\/api\/patterns\/([^/]+)(\/delete)?$/.exec(path);
      if (!m) return undefined;
      const id = decodeURIComponent(m[1]);
      return (init?: RequestInit) => {
        if (m[2]) return store.delete(id) ? { status: 204 } : notFound(id);
        if (init?.method === "POST") {
          const body = JSON.parse(String(init.body));
          saves.push({ id, body });
          const tracks = body.tracks as PatternOut["tracks"];
          const duration_s = Math.max(...tracks.map((t) => t.points[t.points.length - 1][0]));
          const out: PatternOut = { ...body, id, version: 1, meta: {}, duration_s };
          store.set(id, out);
          return { status: 200, body: out };
        }
        const p = store.get(id);
        return p ? { status: 200, body: p } : notFound(id);
      };
    },
  });
  return { routes, saves, store };
}

function show(s = server()) {
  const t = fakeTransport(s.routes);
  render(
    <ClientProvider client={new Client(t.transport, "127.0.0.1")}>
      <PatternsScreen />
    </ClientProvider>,
  );
  return s;
}

const SQUARE: PatternOut = {
  id: "square",
  name: "Square",
  version: 1,
  loop: true,
  notes: "kept",
  meta: {},
  duration_s: 4,
  tracks: [{ target: "trap:2", points: [[0, 0, 0, 0], [1, 5, 0, 0], [2, 5, 5, 0], [3, 0, 5, 0], [4, 0, 0, 0]] }],
};

describe("pattern designer", () => {
  beforeEach(() => {
    window.location.hash = "#/patterns";
  });

  it("makes an id from the name", () => {
    expect(idFromName("  Helix 2 um / turn ")).toBe("helix-2-um-turn");
    expect(idFromName("***")).toBe("pattern");
  });

  it("generates a piezo helix and a trap circle, then saves both tracks", async () => {
    const s = show();
    fireEvent.change(screen.getByLabelText("Pattern name"), { target: { value: "Helix test" } });
    const piezo = screen.getByRole("group", { name: "Track 1: Piezo XYZ" });
    fireEvent.change(within(piezo).getByLabelText(/z end/), { target: { value: "4" } });
    fireEvent.change(within(piezo).getByLabelText(/duration s/), { target: { value: "2" } });
    fireEvent.change(within(piezo).getByLabelText(/points \/ s/), { target: { value: "5" } });
    fireEvent.click(within(piezo).getByRole("button", { name: "Generate points" }));
    expect(within(piezo).getByText(/11 points · 2.00 s/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Add track" }));
    expect(screen.getByRole("group", { name: "Track 2: Trap 0" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(s.saves).toHaveLength(1));
    const { id, body } = s.saves[0];
    expect(id).toBe("helix-test");
    const tracks = body.tracks as PatternOut["tracks"];
    expect(tracks.map((t) => t.target)).toEqual(["piezo", "trap:0"]);
    expect(tracks[0].points[tracks[0].points.length - 1]).toEqual([2, 10, 0, 4]);
    expect((await screen.findByRole("status")).textContent).toContain("Saved helix-test");
    expect(window.location.hash).toBe("#/patterns/helix-test");
  });

  it("will not save a track outside the provisional range and says why", () => {
    show();
    const piezo = screen.getByRole("group", { name: "Track 1: Piezo XYZ" });
    fireEvent.change(within(piezo).getByLabelText(/radius/), { target: { value: "150" } });
    fireEvent.click(within(piezo).getByRole("button", { name: "Generate points" }));
    expect((screen.getByRole("button", { name: "Save" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/x 150 .m is outside -100\.\.100/)).toBeTruthy();
  });

  it("opens a saved pattern, links it to the live view and deletes it after a confirm", async () => {
    window.location.hash = "#/patterns/square";
    const s = show(server([SQUARE]));
    expect(await screen.findByRole("group", { name: "Track 1: Trap 2" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Show on live view" }).getAttribute("href")).toBe("#/live?pattern=square");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(s.saves).toHaveLength(1));
    expect(s.saves[0].body.notes).toBe("kept");
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    await waitFor(() => expect(s.store.has("square")).toBe(false));
    await waitFor(() => expect(window.location.hash).toBe("#/patterns"));
  });
});
