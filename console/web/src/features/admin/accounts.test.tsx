import { configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { fakeTransport, type Route } from "../../test/fakes";
import type { Account, NeedsLogin } from "./api";
import AccountsScreen from "./index";

configure({ asyncUtilTimeout: 8000 });

const ADMIN = { user_id: "ada", name: "Ada", role: "admin", locked: false, local: true, expires_at: 4102444800 };

function acc(p: Partial<Account> & Pick<Account, "login" | "status">): Account {
  return { name: `${p.login} Name`, role: "viewer", created_at: "2026-10-01T09:00:00+00:00", approved_by: null, approved_at: null, ...p };
}

/** A fake /api/auth/accounts following server/api/auth.py; plain logins, and example.test addresses for old accounts. */
function server(accounts: Account[], needing: NeedsLogin[] = []) {
  const calls: { path: string; body: unknown }[] = [];
  const no = (status: number, message: string, code = "account_state") => ({ status, body: { detail: { code, message } } });
  const routes: Record<string, Route> = new Proxy({} as Record<string, Route>, {
    get(_t, path: string) {
      if (path === "/api/auth/accounts") return () => ({ status: 200, body: accounts });
      if (path === "/api/auth/accounts/needs-login") return () => ({ status: 200, body: needing });
      if (path === "/api/auth/accounts/give-login")
        return (init?: RequestInit) => {
          const body = JSON.parse(String(init?.body));
          calls.push({ path, body });
          const i = needing.findIndex((n) => n.email === body.email);
          if (i < 0) return no(404, `no account for ${body.email}`, "no_account");
          const n = needing.splice(i, 1)[0];
          const made = acc({ login: body.login, status: n.status, role: n.role, name: n.name });
          accounts.push(made);
          return { status: 200, body: made };
        };
      const m = /^\/api\/auth\/accounts\/([^/]+)\/(\w+)$/.exec(path);
      if (!m) return undefined;
      const login = decodeURIComponent(m[1]);
      const action = m[2];
      return (init?: RequestInit) => {
        const body = init?.body ? JSON.parse(String(init.body)) : undefined;
        calls.push({ path, body });
        const i = accounts.findIndex((a) => a.login === login);
        if (i < 0) return no(404, `no account for ${login}`, "no_account");
        const a = accounts[i];
        if (action === "approve") accounts[i] = { ...a, status: "active", role: body.role, approved_by: ADMIN.user_id };
        else if (action === "role") accounts[i] = { ...a, role: body.role };
        else if (action === "disable") accounts[i] = { ...a, status: "disabled" };
        else if (action === "enable") accounts[i] = { ...a, status: "active" };
        else if (action === "password") {
          if (String(body.password).length < 10) return no(422, "password is too short", "password_policy");
        } else if (action === "delete") {
          return { status: 404, body: { detail: "Not Found" } }; // there is no such route
        }
        return { status: 200, body: accounts[i] };
      };
    },
  });
  return { routes, calls, accounts };
}

function show(accounts: Account[], me: Record<string, unknown> = ADMIN, needing: NeedsLogin[] = []) {
  const s = server(accounts, needing);
  const t = fakeTransport(s.routes, { me });
  render(
    <ClientProvider client={new Client(t.transport, "127.0.0.1")}>
      <AccountsScreen />
    </ClientProvider>,
  );
  return s;
}

const row = (login: string) => screen.getByText(login).closest("tr") as HTMLElement;

describe("accounts screen", () => {
  it("lists every account and filters by status", async () => {
    show([
      acc({ login: "ada", status: "active", role: "admin" }),
      acc({ login: "pat", status: "pending" }),
      acc({ login: "dee", status: "disabled" }),
    ]);
    const table = await screen.findByRole("table", { name: "Account list" });
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    fireEvent.change(screen.getByRole("combobox", { name: "Status filter" }), { target: { value: "pending" } });
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    expect(within(table).getByText("pat")).toBeTruthy();
  });

  it("gives the admin's own row no actions", async () => {
    show([acc({ login: "ada", status: "active", role: "admin" })]);
    await screen.findByText("ada");
    expect(within(row("ada")).queryAllByRole("button")).toHaveLength(0);
    expect(within(row("ada")).getByText("you")).toBeTruthy();
  });

  it("approves a pending account only once a role is chosen", async () => {
    const s = show([acc({ login: "pat", status: "pending" })]);
    await screen.findByText("pat");
    const approve = within(row("pat")).getByRole("button", { name: "Approve" }) as HTMLButtonElement;
    expect(approve.disabled).toBe(true);
    fireEvent.change(screen.getByRole("combobox", { name: "Role for pat" }), { target: { value: "operator" } });
    fireEvent.click(approve);
    await waitFor(() => expect(s.accounts[0].status).toBe("active"));
    expect(s.calls[0].body).toEqual({ role: "operator" });
    expect((await screen.findByRole("status")).textContent).toContain("approved as operator");
  });

  it("changes a role, switches off and on", async () => {
    const s = show([acc({ login: "vera", status: "active" })]);
    await screen.findByText("vera");
    fireEvent.change(screen.getByRole("combobox", { name: "Role for vera" }), { target: { value: "operator" } });
    fireEvent.click(within(row("vera")).getByRole("button", { name: "Set role" }));
    await waitFor(() => expect(s.accounts[0].role).toBe("operator"));
    fireEvent.click(await within(row("vera")).findByRole("button", { name: "Switch off" }));
    await waitFor(() => expect(s.accounts[0].status).toBe("disabled"));
    fireEvent.click(await within(row("vera")).findByRole("button", { name: "Switch on" }));
    await waitFor(() => expect(s.accounts[0].status).toBe("active"));
  });

  it("sets a new password and shows the policy refusal", async () => {
    const s = show([acc({ login: "vera", status: "active" })]);
    await screen.findByText("vera");
    fireEvent.click(within(row("vera")).getByRole("button", { name: "Reset password" }));
    const input = screen.getByLabelText("New password for vera");
    fireEvent.change(input, { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: "Set password" }));
    expect((await screen.findByRole("alert")).textContent).toContain("too short");
    fireEvent.change(input, { target: { value: "fresh-pass-word-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Set password" }));
    expect((await screen.findByRole("status")).textContent).toContain("logins ended");
    expect(s.calls.at(-1)?.body).toEqual({ password: "fresh-pass-word-1" });
    expect(screen.queryByLabelText("New password for vera")).toBeNull();
  });

  it("has no delete at all: accounts are switched off, never deleted", async () => {
    show([acc({ login: "dee", status: "disabled" }), acc({ login: "vera", status: "active" }), acc({ login: "pat", status: "pending" })]);
    await screen.findByText("dee");
    expect(screen.queryAllByRole("button", { name: /delete/i })).toHaveLength(0);
    expect(within(row("dee")).getByRole("button", { name: "Switch on" })).toBeTruthy();
    expect(within(row("vera")).getByRole("button", { name: "Switch off" })).toBeTruthy();
  });

  it("lists an account from an older console as needing a login id, and gives it one", async () => {
    const old: NeedsLogin = {
      email: "old.member@example.test", name: "Old Member", role: "operator", status: "active",
      created_at: "2026-09-01T09:00:00+00:00", approved_by: null, approved_at: null,
    };
    const s = show([acc({ login: "ada", status: "active", role: "admin" })], ADMIN, [old]);
    const section = await screen.findByRole("region", { name: "Needs a login id" });
    expect(within(section).getByText("old.member@example.test")).toBeTruthy();
    // the account list is of logins: the old one is not in it, and cannot be switched on or off
    expect(within(screen.getByRole("table", { name: "Account list" })).queryByText("Old Member")).toBeNull();
    const input = within(section).getByLabelText("Login for old.member@example.test");
    fireEvent.change(input, { target: { value: "old.member" } });
    fireEvent.click(within(section).getByRole("button", { name: "Give login" }));
    await waitFor(() => expect(s.calls.at(-1)?.path).toBe("/api/auth/accounts/give-login"));
    expect(s.calls.at(-1)?.body).toEqual({ email: "old.member@example.test", login: "old.member" });
    expect((await screen.findByRole("status")).textContent).toContain("now logs in as old.member");
    await waitFor(() => expect(screen.queryByRole("region", { name: "Needs a login id" })).toBeNull());
    expect(await screen.findByText("old.member")).toBeTruthy();
  });

  it("refuses an email as the new login, in words, and sends nothing", async () => {
    const old: NeedsLogin = {
      email: "old.member@example.test", name: "Old Member", role: "viewer", status: "active",
      created_at: "2026-09-01T09:00:00+00:00", approved_by: null, approved_at: null,
    };
    const s = show([], ADMIN, [old]);
    const section = await screen.findByRole("region", { name: "Needs a login id" });
    fireEvent.change(within(section).getByLabelText("Login for old.member@example.test"), { target: { value: "old@example.test" } });
    fireEvent.click(within(section).getByRole("button", { name: "Give login" }));
    expect((await within(section).findByRole("alert")).textContent).toContain("plain id");
    expect(s.calls).toHaveLength(0);
  });

  it("shows no section when no account needs a login id", async () => {
    show([acc({ login: "vera", status: "active" })]);
    await screen.findByText("vera");
    expect(screen.queryByRole("region", { name: "Needs a login id" })).toBeNull();
  });

  it("tells a non-admin and a remote admin why there is nothing here", async () => {
    show([], { ...ADMIN, role: "operator" });
    expect(await screen.findByText("Only an administrator can manage accounts.")).toBeTruthy();
  });

  it("tells a remote admin to use the microscope PC", async () => {
    show([], { ...ADMIN, local: false });
    expect(await screen.findByText("Accounts are managed on the microscope PC.")).toBeTruthy();
  });
});
