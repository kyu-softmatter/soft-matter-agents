import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import SampleScreen from "../features/sample/index";
import SessionsScreen from "../features/sessions/index";
import { fakeTransport } from "../test/fakes";
import { Client, ClientProvider, CommandRefused } from "./client";
import { ScreenContextProvider } from "./screenContext";
import { PLACEHOLDER_NOTICE, placeholderNotice } from "./unavailable";

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
});

/** Every request answers as the placeholder engine's server does for these areas. */
function noRecords(code: string) {
  const answer = () => ({ status: 503, body: { detail: { code, message: "no store" } }, headers: { "X-DinoAF-Refusal": code } });
  return new Proxy({}, { get: () => answer });
}

function renderArea(area: "sample" | "sessions", code: string) {
  window.location.hash = `#/${area}`;
  const fake = fakeTransport(noRecords(code));
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  render(
    <ClientProvider client={client}>
      <ScreenContextProvider area={area}>{area === "sample" ? <SampleScreen /> : <SessionsScreen />}</ScreenContextProvider>
    </ClientProvider>,
  );
}

describe("areas without dino's records under the placeholder engine", () => {
  it("maps only the two no-records codes", () => {
    expect(placeholderNotice(new CommandRefused(503, "x", "no_sample_store"))).toBe(PLACEHOLDER_NOTICE);
    expect(placeholderNotice(new CommandRefused(503, "x", "no_records"))).toBe(PLACEHOLDER_NOTICE);
    expect(placeholderNotice(new CommandRefused(503, "x", "shutting_down"))).toBeNull();
    expect(placeholderNotice(new Error("boom"))).toBeNull();
  });

  it("the Sample area says so in words, with no controls", async () => {
    renderArea("sample", "no_sample_store");
    expect((await screen.findByRole("status")).textContent).toBe(PLACEHOLDER_NOTICE);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("the Sessions area says so in words, with no controls", async () => {
    renderArea("sessions", "no_records");
    expect((await screen.findByRole("status")).textContent).toBe(PLACEHOLDER_NOTICE);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });
});
