import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type ReactNode, useMemo } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { fakeTransport } from "../../test/fakes";
import { Client, ClientProvider } from "../client";
import { ScreenContextProvider, useScreenContext } from "../screenContext";
import { type AssistantApi, clientAssistantApi, createFakeAssistantApi, type FakeStep } from "./api";
import { AssistantApiContext, CHECKING_PERMISSIONS, PERMISSION_CHECK_UNAVAILABLE } from "./hooks";
import PromptBox, { turnsFrom } from "./index";

const MOVE: FakeStep = {
  text: ["I can move to the next tile. "],
  read: "get_snapshot",
  propose: {
    tool: "propose_move_xy",
    command: { kind: "start", op: "move_xy", args: { x_um: 1250.5, y_um: -300 } },
    summary: "Move the stage to x 1250.5 um, y -300 um",
    reason: "the next tile in the scan",
    gate: { checked: true, enabled: true, reasons: [] },
  },
};

function MapScreen() {
  const details = useMemo(() => ({ sample_id: "20260930_1849_1", region: { x_um: 10, y_um: 20 } }), []);
  useScreenContext(details);
  return null;
}

function setup({
  api = createFakeAssistantApi() as AssistantApi,
  hostname = "127.0.0.1",
  screenEl = null as ReactNode,
} = {}) {
  const fake = fakeTransport({});
  const client = new Client(fake.transport, hostname);
  render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="map">
        {screenEl}
        <AssistantApiContext.Provider value={api}>
          <PromptBox />
        </AssistantApiContext.Provider>
      </ScreenContextProvider>
    </ClientProvider>,
  );
  return { api, client, sockets: fake.sockets };
}

async function ask(text: string) {
  const box = await screen.findByRole("textbox", { name: "Question" });
  await waitFor(() => expect((box as HTMLTextAreaElement).disabled).toBe(false));
  fireEvent.change(box, { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
}

afterEach(() => sessionStorage.clear());

describe("PromptBox", () => {
  it("sends the question with the context of the screen in view", async () => {
    const { api } = setup({ screenEl: <MapScreen /> });
    await ask("What is in this region?");
    await screen.findByText(/No model was called/);
    const fakeApi = api as ReturnType<typeof createFakeAssistantApi>;
    expect(fakeApi.asked[0]).toEqual({
      question: "What is in this region?",
      context: { area: "map", sample_id: "20260930_1849_1", region: { x_um: 10, y_um: 20 } },
      conversation_id: null,
    });
  });

  it("streams the answer, marks it model, lists tool calls and shows tokens", async () => {
    setup({ api: createFakeAssistantApi({ script: [MOVE] }) });
    await ask("Next tile please");
    const turn = (await screen.findByText("I can move to the next tile.", { exact: false })).closest("li")!;
    expect(within(turn).getAllByText("model").length).toBeGreaterThan(0);
    expect(within(turn).getByRole("list", { name: "Tool calls" }).textContent).toContain("read: get_snapshot");
    expect(within(turn).getByText(/Tokens: 2200 in, 1000 cached · 80 out/)).toBeTruthy();
  });

  it("continues the same conversation on the next question", async () => {
    const api = createFakeAssistantApi();
    setup({ api });
    await ask("first");
    await screen.findByText(/No model was called/);
    await ask("second");
    await waitFor(() => expect(api.asked).toHaveLength(2));
    expect(api.asked[1].conversation_id).toBe("conv-fake1");
    expect(sessionStorage.getItem("dino_af_conversation")).toBe("conv-fake1");
  });

  it("shows a proposal card and confirms it through the server", async () => {
    const api = createFakeAssistantApi({ script: [MOVE] });
    const { sockets } = setup({ api });
    await ask("Next tile please");
    const card = await screen.findByRole("article", { name: /Proposal: Move the stage/ });
    expect(card.textContent).toContain("move_xy");
    expect(card.textContent).toContain("1250.5");
    expect(card.textContent).toContain("Gate now: open");
    expect(within(card).getAllByText("model").length).toBeGreaterThanOrEqual(3); // two args, the reason
    const confirm = within(card).getByRole("button", { name: "Confirm" }) as HTMLButtonElement;
    await waitFor(() => expect(confirm.disabled).toBe(false));
    fireEvent.click(confirm);
    expect((await within(card).findByRole("status")).textContent).toContain("Sent to the engine as op-prop-");
    expect(api.decisions).toEqual([{ proposal_id: expect.stringMatching(/^prop-/), decision: "confirm" }]);
    // progress comes from engine events for that op
    act(() => {
      sockets[0].open();
      sockets[0].event("started", {}, api.decisions[0] && `op-${api.decisions[0].proposal_id}`);
    });
    await waitFor(() => expect(within(card).getByRole("status").textContent).toContain("started"));
    expect(within(card).queryByRole("button", { name: "Confirm" })).toBeNull();
  });

  it("rejects a proposal", async () => {
    const api = createFakeAssistantApi({ script: [MOVE] });
    setup({ api });
    await ask("Next tile please");
    const card = await screen.findByRole("article", { name: /Proposal/ });
    const reject = within(card).getByRole("button", { name: "Reject" }) as HTMLButtonElement;
    await waitFor(() => expect(reject.disabled).toBe(false));
    fireEvent.click(reject);
    expect((await within(card).findByRole("status")).textContent).toContain("Rejected");
    expect(api.decisions[0].decision).toBe("reject");
  });

  it("in read-only (remote) view the question box and the card buttons are off", async () => {
    const api = createFakeAssistantApi({ script: [MOVE] });
    // a proposal already exists in this tab's conversation
    await api.ask({ question: "earlier", context: { area: "map" }, conversation_id: null }, () => {});
    sessionStorage.setItem("dino_af_conversation", "conv-fake1");
    setup({ api, hostname: "lab-pc.example.test" });
    const card = await screen.findByRole("article", { name: /Proposal/ });
    expect((within(card).getByRole("button", { name: "Confirm" }) as HTMLButtonElement).disabled).toBe(true);
    expect((within(card).getByRole("button", { name: "Reject" }) as HTMLButtonElement).disabled).toBe(true);
    expect(within(card).getByText(/Read only: remote view/)).toBeTruthy();
    expect((screen.getByRole("textbox", { name: "Question" }) as HTMLTextAreaElement).disabled).toBe(true);
    expect(screen.getByText("earlier")).toBeTruthy(); // the history is still visible
  });

  it("disables with the server's reason, and says so while checking or when the check fails", async () => {
    const refused = createFakeAssistantApi({
      permissions: { submit_question: { allowed: false, reason: "viewers may not ask (D16)" } },
    });
    setup({ api: refused });
    expect(await screen.findByText("viewers may not ask (D16)")).toBeTruthy();
    expect((screen.getByRole("textbox", { name: "Question" }) as HTMLTextAreaElement).disabled).toBe(true);
  });

  it("shows the shared texts for a pending or failed permission check", async () => {
    let release: () => void = () => {};
    const slow: AssistantApi = {
      ...createFakeAssistantApi(),
      permissions: () => new Promise((resolve) => (release = () => resolve({ submit_question: { allowed: true, reason: "" } }))),
    };
    setup({ api: slow });
    expect(await screen.findByText(CHECKING_PERMISSIONS)).toBeTruthy();
    await act(async () => release());
    await waitFor(() => expect(screen.queryByText(CHECKING_PERMISSIONS)).toBeNull());
  });

  it("says Permission check unavailable when /api/permissions fails", async () => {
    setup({ api: createFakeAssistantApi({ permissions: "unavailable" }) });
    expect(await screen.findByText(PERMISSION_CHECK_UNAVAILABLE)).toBeTruthy();
  });

  it("shows fake and not connected clearly", async () => {
    setup();
    const line = await screen.findByText(/Assistant:/, { selector: "p" });
    await waitFor(() => expect(line.textContent).toContain("not connected"));
    expect(within(line).getByText("fake")).toBeTruthy();
    expect(line.textContent).toContain("data sent: text");
  });

  it("shows not connected when the assistant endpoints do not answer", async () => {
    setup({ api: createFakeAssistantApi({ status: null }) });
    expect((await screen.findByText(/not connected \(the server does not answer\)/)).textContent).toBeTruthy();
  });

  it("shows connected without a fake badge for a connected provider", async () => {
    setup({ api: createFakeAssistantApi({ status: { provider: "anthropic", connected: true, data_stage: "text" } }) });
    const line = await screen.findByText(/connected to Claude/);
    expect(line.closest("p")!.querySelector(".pb-badge")).toBeNull();
  });
});

describe("turnsFrom", () => {
  it("drops the screen context and tool results from the stored history", () => {
    const turns = turnsFrom({
      conversation_id: "c",
      usage: {},
      proposals: [],
      messages: [
        { role: "user", content: [{ type: "text", text: "<screen_context>\n{}\n</screen_context>" }, { type: "text", text: "hi" }] },
        { role: "assistant", content: [{ type: "text", text: "Looking. " }, { type: "tool_use" }] },
        { role: "user", content: [{ type: "tool_result" }] },
        { role: "assistant", content: [{ type: "text", text: "Done." }] },
      ],
    });
    expect(turns).toHaveLength(1);
    expect(turns[0]).toMatchObject({ question: "hi", text: "Looking. Done." });
  });
});

describe("clientAssistantApi over the shared client", () => {
  const ANSWER = { conversation_id: "c1", text: "ab", stop_reason: "end_turn", provider: "fake", usage: {}, tool_calls: [], proposals: [], grade: "model" };
  const refused = (status: number, code: string, message: string) => () => ({ status, body: { detail: { code, message } } });

  function streaming(routes: Parameters<typeof fakeTransport>[0], ask: () => Response) {
    const fake = fakeTransport(routes);
    const fetch = fake.transport.fetch;
    fake.transport.fetch = async (path, init) => {
      if (path === "/api/assistant/ask") {
        fake.calls.push({ path, init });
        return ask();
      }
      return fetch(path, init);
    };
    return fake;
  }

  it("reads the NDJSON answer stream over the shared transport", async () => {
    const lines = [{ type: "text", text: "a" }, { type: "text", text: "b" }, { type: "done", answer: ANSWER }]
      .map((l) => JSON.stringify(l))
      .join("\n");
    const fake = streaming({}, () => new Response(lines, { status: 200 }));
    const api = clientAssistantApi(new Client(fake.transport, "127.0.0.1"));
    const seen: string[] = [];
    const answer = await api.ask({ question: "q", context: { area: "map" }, conversation_id: null }, (e) => seen.push(e.type));
    expect(answer.text).toBe("ab");
    expect(seen).toEqual(["text", "text", "done"]);
    expect(fake.sockets).toHaveLength(0); // no socket of its own
  });

  it("a 401 on ask starts the shared re-login through postStream", async () => {
    const fake = streaming(
      { "/api/auth/me": refused(401, "login_required", "log in first") },
      () => new Response(JSON.stringify({ detail: { code: "login_required", message: "log in first" } }), { status: 401 }),
    );
    const client = new Client(fake.transport, "127.0.0.1");
    const failures: number[] = [];
    client.onAuthFailure((s) => failures.push(s));
    const err = await clientAssistantApi(client)
      .ask({ question: "q", context: { area: "map" }, conversation_id: null }, () => {})
      .catch((e) => e);
    expect(err.status).toBe(401);
    expect(failures).toEqual([401]); // straight from postStream: no extra /api/auth/me read
    expect(fake.calls.map((c) => c.path)).toEqual(["/api/assistant/ask"]);
  });

  it("a remote_view refusal on confirm turns the app read-only; another 403 does not", async () => {
    const fake = fakeTransport({
      "/api/assistant/proposals/p1/confirm": refused(403, "remote_view", "remote view: confirm on the microscope PC"),
      "/api/assistant/proposals/p2/confirm": refused(403, "role", "role viewer may not run move_xy"),
    });
    const client = new Client(fake.transport, "127.0.0.1");
    const api = clientAssistantApi(client);
    const role = await api.confirm("p2").catch((e) => e);
    expect(role.message).toContain("may not run move_xy");
    expect(client.readOnly.get().readOnly).toBe(false);
    await api.confirm("p1").catch(() => {});
    expect(client.readOnly.get().readOnly).toBe(true);
  });

  it("a remote_view refusal on ask turns the app read-only too", async () => {
    const fake = streaming({}, () =>
      new Response(JSON.stringify({ detail: { code: "remote_view", message: "remote view" } }), {
        status: 403,
        headers: { "X-DinoAF-Refusal": "remote_view" },
      }),
    );
    const client = new Client(fake.transport, "127.0.0.1");
    await clientAssistantApi(client).ask({ question: "q", context: { area: "map" }, conversation_id: null }, () => {}).catch(() => {});
    expect(client.readOnly.get().readOnly).toBe(true);
  });
});
