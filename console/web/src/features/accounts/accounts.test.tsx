import { configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { fakeTransport, type Route } from "../../test/fakes";
import type { Account } from "./api";
import AccountsScreen from "./index";

configure({ asyncUtilTimeout: 8000 });

const ADMIN = { user_id: "admin@example.test", name: "Ada", role: "admin", locked: false, has_control: false, local: true, expires_at: 4102444800 };

function acc(p: Partial<Account> & Pick<Account, "email" | "status">): Account {
  return { name: p.email.split("@")[0], role: "viewer", created_at: "2026-10-01T09:00:00+00:00", approved_by: null, approved_at: null, ...p };
}

/** A fake /api/auth/accounts following server/api/auth.py; example.test addresses only. */
function server(accounts: Account[]) {
  const calls: { path: string; body: unknown }[] = [];
  const no = (status: number, message: string, code = "account_state") => ({ status, body: { detail: { code, message } } });
  const routes: Record<string, Route> = new Proxy({} as Record<string, Route>, {
    get(_t, path: string) {
      if (path === "/api/auth/accounts") return () => ({ status: 200, body: accounts });
      const m = /^\/api\/auth\/accounts\/([^/]+)\/(\w+)$/.exec(path);
      if (!m) return undefined;
      const email = decodeURIComponent(m[1]);
      const action = m[2];
      return (init?: RequestInit) => {
        const body = init?.body ? JSON.parse(String(init.body)) : undefined;
        calls.push({ path, body });
        const i = accounts.findIndex((a) => a.email === email);
        if (i < 0) return no(404, `no account for ${email}`, "no_account");
        const a = accounts[i];
        if (action === "approve") accounts[i] = { ...a, status: "active", role: body.role, approved_by: ADMIN.user_id };
        else if (action === "role") accounts[i] = { ...a, role: body.role };
        else if (action === "disable") accounts[i] = { ...a, status: "disabled" };
        else if (action === "enable") accounts[i] = { ...a, status: "active" };
        else if (action === "password") {
          if (String(body.password).length < 10) return no(422, "password is too short", "password_policy");
        } else if (action === "delete") {
          if (a.status === "active") return no(409, `${email} is active; disable it before deleting`);
          accounts.splice(i, 1);
          return { status: 200, body: a };
        }
        return { status: 200, body: accounts[i] };
      };
    },
  });
  return { routes, calls, accounts };
}

function show(accounts: Account[], me: Record<string, unknown> = ADMIN) {
  const s = server(accounts);
  const t = fakeTransport(s.routes, { me });
  render(
    <ClientProvider client={new Client(t.transport, "127.0.0.1")}>
      <AccountsScreen />
    </ClientProvider>,
  );
  return s;
}

const row = (email: string) => screen.getByText(email).closest("tr") as HTMLElement;

describe("accounts screen", () => {
  it("lists every account and filters by status", async () => {
    show([
      acc({ email: "admin@example.test", status: "active", role: "admin" }),
      acc({ email: "pat@example.test", status: "pending" }),
      acc({ email: "dee@example.test", status: "disabled" }),
    ]);
    const table = await screen.findByRole("table", { name: "Account list" });
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    fireEvent.change(screen.getByRole("combobox", { name: "Status filter" }), { target: { value: "pending" } });
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    expect(within(table).getByText("pat@example.test")).toBeTruthy();
  });

  it("gives the admin's own row no actions", async () => {
    show([acc({ email: "admin@example.test", status: "active", role: "admin" })]);
    await screen.findByText("admin@example.test");
    expect(within(row("admin@example.test")).queryAllByRole("button")).toHaveLength(0);
    expect(within(row("admin@example.test")).getByText("you")).toBeTruthy();
  });

  it("approves a pending account only once a role is chosen", async () => {
    const s = show([acc({ email: "pat@example.test", status: "pending" })]);
    await screen.findByText("pat@example.test");
    const approve = within(row("pat@example.test")).getByRole("button", { name: "Approve" }) as HTMLButtonElement;
    expect(approve.disabled).toBe(true);
    fireEvent.change(screen.getByRole("combobox", { name: "Role for pat@example.test" }), { target: { value: "operator" } });
    fireEvent.click(approve);
    await waitFor(() => expect(s.accounts[0].status).toBe("active"));
    expect(s.calls[0].body).toEqual({ role: "operator" });
    expect((await screen.findByRole("status")).textContent).toContain("approved as operator");
  });

  it("changes a role, disables and enables", async () => {
    const s = show([acc({ email: "vera@example.test", status: "active" })]);
    await screen.findByText("vera@example.test");
    fireEvent.change(screen.getByRole("combobox", { name: "Role for vera@example.test" }), { target: { value: "operator" } });
    fireEvent.click(within(row("vera@example.test")).getByRole("button", { name: "Set role" }));
    await waitFor(() => expect(s.accounts[0].role).toBe("operator"));
    fireEvent.click(await within(row("vera@example.test")).findByRole("button", { name: "Disable" }));
    await waitFor(() => expect(s.accounts[0].status).toBe("disabled"));
    fireEvent.click(await within(row("vera@example.test")).findByRole("button", { name: "Enable" }));
    await waitFor(() => expect(s.accounts[0].status).toBe("active"));
  });

  it("sets a new password and shows the policy refusal", async () => {
    const s = show([acc({ email: "vera@example.test", status: "active" })]);
    await screen.findByText("vera@example.test");
    fireEvent.click(within(row("vera@example.test")).getByRole("button", { name: "Reset password" }));
    const input = screen.getByLabelText("New password for vera@example.test");
    fireEvent.change(input, { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: "Set password" }));
    expect((await screen.findByRole("alert")).textContent).toContain("too short");
    fireEvent.change(input, { target: { value: "fresh-pass-word-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Set password" }));
    expect((await screen.findByRole("status")).textContent).toContain("logins ended");
    expect(s.calls.at(-1)?.body).toEqual({ password: "fresh-pass-word-1" });
    expect(screen.queryByLabelText("New password for vera@example.test")).toBeNull();
  });

  it("deletes a disabled account after a confirm, and offers no delete for an active one", async () => {
    const s = show([acc({ email: "dee@example.test", status: "disabled" }), acc({ email: "vera@example.test", status: "active" })]);
    await screen.findByText("dee@example.test");
    expect(within(row("vera@example.test")).queryByRole("button", { name: "Delete" })).toBeNull();
    fireEvent.click(within(row("dee@example.test")).getByRole("button", { name: "Delete" }));
    expect(s.calls).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    await waitFor(() => expect(screen.queryByText("dee@example.test")).toBeNull());
    expect(s.accounts.map((a) => a.email)).toEqual(["vera@example.test"]);
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
