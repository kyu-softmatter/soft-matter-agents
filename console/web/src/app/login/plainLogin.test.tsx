import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeTransport } from "../../test/fakes";
import { Client } from "../client";
import { clientAuthApi, createFakeAuthApi, isPlainLogin, PLAIN_LOGIN_MESSAGE } from "./api";
import { LoginGate } from "./LoginGate";

/** Plain login ids, never an email (console card 009): the login screens. */

afterEach(cleanup);

const USERS = [
  { name: "Otto Operator", login: "otto", password: "otto-pass-1", role: "operator" as const, status: "active" as const },
];

function gate(api = createFakeAuthApi({ users: USERS })) {
  render(
    <LoginGate api={api} pollMs={0}>
      <p>the app</p>
    </LoginGate>,
  );
  return api;
}

const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

const ADVICE =
  "Choose one you have never written anywhere else, a chat window included. The console cannot tell if a password has been seen.";

describe("what a login is", () => {
  it.each(["softmatter", "kim.lee", "kim-lee", "kim_lee", "A1", "a".repeat(64)])("%s is a plain login", (v) => {
    expect(isPlainLogin(v)).toBe(true);
  });
  it.each(["kim@example.test", "", " kim", "kim ", ".kim", "a".repeat(65), "kim\n", "kiño"])("%j is not", (v) => {
    expect(isPlainLogin(v)).toBe(false);
  });
  it("the message says so in plain words", () => {
    expect(PLAIN_LOGIN_MESSAGE).toContain("plain id");
    expect(PLAIN_LOGIN_MESSAGE).toContain("not an email");
  });
});

describe("the login screen", () => {
  it("asks for a login and a password, not an email", async () => {
    gate();
    const form = await screen.findByRole("form", { name: "Log in" });
    expect(form.querySelector('input[type="email"]')).toBeNull();
    expect((screen.getByLabelText("Login") as HTMLInputElement).type).toBe("text");
    expect((screen.getByLabelText("Password") as HTMLInputElement).value).toBe("");
    expect(screen.queryByLabelText("Email")).toBeNull();
  });

  it("logs in with a login and a password", async () => {
    gate();
    await screen.findByRole("form", { name: "Log in" });
    fill("Login", "otto");
    fill("Password", "otto-pass-1");
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("the app")).toBeTruthy();
  });

  it("refuses an email as a login, in words, and sends nothing", async () => {
    const api = gate();
    const login = vi.spyOn(api, "login");
    await screen.findByRole("form", { name: "Log in" });
    fill("Login", "otto@example.test");
    fill("Password", "otto-pass-1");
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect((await screen.findByRole("alert")).textContent).toBe(PLAIN_LOGIN_MESSAGE);
    expect(login).not.toHaveBeenCalled();
  });

  it("says Wrong login or password", async () => {
    gate();
    await screen.findByRole("form", { name: "Log in" });
    fill("Login", "otto");
    fill("Password", "nope-nope-1");
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Wrong login or password");
  });
});

describe("Create an account", () => {
  async function open() {
    const api = gate();
    fireEvent.click(await screen.findByRole("button", { name: "Create one" }));
    return api;
  }

  it("takes a name, a login and a password, and says what a login is", async () => {
    await open();
    const form = screen.getByRole("form", { name: "Create an account" });
    expect(form.querySelector('input[type="email"]')).toBeNull();
    expect(screen.getByLabelText("Login")).toBeTruthy();
    expect(screen.getByText("Letters, digits, dot, dash or underscore. Not an email.")).toBeTruthy();
  });

  it("refuses an email as a login and sends nothing", async () => {
    const api = await open();
    const signup = vi.spyOn(api, "signup");
    fill("Name", "Kim Lee");
    fill("Login", "kim@example.test");
    fill("Password", "kim-pass-12");
    fill("Password again", "kim-pass-12");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect((await screen.findByRole("alert")).textContent).toBe(PLAIN_LOGIN_MESSAGE);
    expect(signup).not.toHaveBeenCalled();
    expect(api.users).toHaveLength(1);
  });

  it("sends a plain login, and the result says the administrator approves it and sets what it may do", async () => {
    const api = await open();
    fill("Name", "Kim Lee");
    fill("Login", "kim.lee");
    fill("Password", "kim-pass-12");
    fill("Password again", "kim-pass-12");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    const text = (await screen.findByRole("status")).textContent ?? "";
    expect(text).toContain("The administrator approves it and sets what it may do");
    expect(text).toContain("cannot log in");
    expect(api.users.find((u) => u.login === "kim.lee")).toMatchObject({ status: "pending", role: "viewer" });
  });
});

describe("the first start", () => {
  it("shows the administrator's login from the server, fixed, and one place to type the password", async () => {
    gate(createFakeAuthApi({ setup: "needs_admin", adminLogin: "softmatter" }));
    const form = await screen.findByRole("form", { name: "Create the administrator account" });
    const login = screen.getByLabelText("Administrator login") as HTMLInputElement;
    expect(login.value).toBe("softmatter");
    expect(login.readOnly).toBe(true);
    expect(form.querySelector('input[type="email"]')).toBeNull();
    const passwords = form.querySelectorAll('input[type="password"]');
    expect(passwords).toHaveLength(2); // the password, and again
    passwords.forEach((p) => expect((p as HTMLInputElement).value).toBe(""));
    expect(screen.getByText(ADVICE)).toBeTruthy();
    expect(screen.getByText(/Type the administrator's password here yourself\. No password comes with the console\./)).toBeTruthy();
  });

  it("shows whatever login the settings name", async () => {
    gate(createFakeAuthApi({ setup: "needs_admin", adminLogin: "labadmin" }));
    await screen.findByRole("form", { name: "Create the administrator account" });
    expect((screen.getByLabelText("Administrator login") as HTMLInputElement).value).toBe("labadmin");
  });

  it("creates the administrator with the typed password and no login in the request", async () => {
    const api = createFakeAuthApi({ setup: "needs_admin", adminLogin: "softmatter" });
    const create = vi.spyOn(api, "createAdmin");
    gate(api);
    await screen.findByRole("form", { name: "Create the administrator account" });
    fill("Password", "typed-by-me-1");
    fill("Password again", "typed-by-me-1");
    fireEvent.click(screen.getByRole("button", { name: "Create the administrator" }));
    expect(await screen.findByText("the app")).toBeTruthy();
    expect(create).toHaveBeenCalledOnce();
    expect(create.mock.calls[0][0]).toEqual({ password: "typed-by-me-1" });
    expect(api.users[0]).toMatchObject({ login: "softmatter", role: "admin" });
  });

  it("checks the two passwords first and sends nothing when they differ", async () => {
    const api = createFakeAuthApi({ setup: "needs_admin", adminLogin: "softmatter" });
    const create = vi.spyOn(api, "createAdmin");
    gate(api);
    await screen.findByRole("form", { name: "Create the administrator account" });
    fill("Password", "typed-by-me-1");
    fill("Password again", "typed-by-me-2");
    fireEvent.click(screen.getByRole("button", { name: "Create the administrator" }));
    expect((await screen.findByRole("alert")).textContent).toContain("differ");
    expect(create).not.toHaveBeenCalled();
  });

  it("when the settings name something that is not a plain id, says so and offers no form", async () => {
    gate(createFakeAuthApi({ setup: "needs_admin", adminLogin: null }));
    const status = await screen.findByRole("status");
    expect(status.textContent).toContain("admin_login");
    expect(status.textContent).toContain(PLAIN_LOGIN_MESSAGE);
    expect(screen.queryByRole("form")).toBeNull();
  });
});

describe("clientAuthApi over the shared client", () => {
  const api = (routes: Parameters<typeof fakeTransport>[0]) => {
    const fake = fakeTransport(routes);
    return { fake, api: clientAuthApi(new Client(fake.transport, "127.0.0.1")) };
  };

  it("reads the first-start state with the administrator's login", async () => {
    const { api: a } = api({
      "/api/auth/me": () => ({ status: 401, body: { detail: { code: "login_required", message: "log in" } } }),
      "/api/auth/setup": () => ({ status: 200, body: { state: "needs_admin", admin_login: "softmatter" } }),
    });
    expect(await a.setup()).toEqual({ state: "needs_admin", adminLogin: "softmatter" });
  });

  it("posts a login and a password, never an email", async () => {
    const { fake, api: a } = api({
      "/api/auth/login": () => ({
        status: 200,
        body: { user_id: "otto", name: "Otto", role: "operator", locked: false, local: true, expires_at: 1 },
      }),
    });
    await a.login({ login: "otto", password: "otto-pass-1" });
    const sent = JSON.parse(String(fake.calls.find((c) => c.path === "/api/auth/login")!.init!.body));
    expect(sent).toEqual({ login: "otto", password: "otto-pass-1" });
  });

  it("posts the first administrator's password and nothing else of an identity", async () => {
    const { fake, api: a } = api({
      "/api/auth/setup/admin": () => ({
        status: 200,
        body: { user_id: "softmatter", name: "softmatter", role: "admin", locked: false, local: true, expires_at: 1 },
      }),
    });
    await a.createAdmin({ password: "typed-by-me-1" });
    const sent = JSON.parse(String(fake.calls.find((c) => c.path === "/api/auth/setup/admin")!.init!.body));
    expect(sent).toEqual({ password: "typed-by-me-1" });
  });

  it("turns the server's not_a_login into the same words", async () => {
    const { api: a } = api({
      "/api/auth/login": () => ({
        status: 422,
        body: { detail: { code: "not_a_login", message: "A login is a plain id, not an email address." } },
      }),
    });
    const err = await a.login({ login: "x", password: "y" }).catch((e) => e);
    expect(err).toMatchObject({ status: 422, outcome: "not_a_login" });
  });

  it("names an account to approve by its login", async () => {
    const { fake, api: a } = api({
      "/api/auth/accounts/kim.lee/approve": () => ({ status: 200, body: { login: "kim.lee" } }),
    });
    await a.approve("kim.lee", "operator");
    expect(fake.calls.at(-1)?.path).toBe("/api/auth/accounts/kim.lee/approve");
  });
});

describe("the fake keeps the same rules", () => {
  it("refuses an email at login, signup and first start", async () => {
    const api = createFakeAuthApi({ users: USERS, setup: "ready" });
    await expect(api.login({ login: "otto@example.test", password: "otto-pass-1" })).rejects.toMatchObject({ outcome: "not_a_login" });
    await expect(api.signup({ name: "K", login: "k@example.test", password: "kim-pass-12" })).rejects.toMatchObject({ status: 422 });
    const fresh = createFakeAuthApi({ setup: "needs_admin", adminLogin: "boss@example.test" });
    await expect(fresh.createAdmin({ password: "typed-by-me-1" })).rejects.toMatchObject({ status: 409 });
  });
});

describe("no password is shown", () => {
  it("is never a visible value on the login screens", async () => {
    gate();
    await screen.findByRole("form", { name: "Log in" });
    await waitFor(() => expect(document.querySelectorAll('input[type="password"]').length).toBeGreaterThan(0));
    document.querySelectorAll('input[type="password"]').forEach((p) => expect((p as HTMLInputElement).value).toBe(""));
  });
});
