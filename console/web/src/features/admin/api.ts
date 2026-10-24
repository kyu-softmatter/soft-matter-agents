// Temporary until gen:api: the /api/auth/accounts shapes are hand-written here from
// server/api/auth.py (AccountOut, NeedsLoginOut, RoleIn, PasswordIn). An account is named by its
// login, a plain id, never an email (console card 009); accounts are switched off, never deleted. Reads and writes go through the shell's
// shared client (src/app/client.tsx: get, post); this file opens no connection of its own.

import type { Client } from "../../app/client";

export type Role = "admin" | "operator" | "viewer";
export type AccountStatus = "pending" | "active" | "disabled";

export const ROLES: Role[] = ["viewer", "operator", "admin"];

export interface Account {
  login: string;
  name: string;
  role: Role;
  status: AccountStatus;
  created_at: string;
  approved_by: string | null;
  approved_at: string | null;
}

/** An account an older console recorded under an email: it cannot log in until it is given a login. */
export interface NeedsLogin {
  email: string;
  name: string;
  role: Role;
  status: AccountStatus;
  created_at: string;
  approved_by: string | null;
  approved_at: string | null;
}

/** The fields of GET /api/auth/me this screen reads. */
export interface Me {
  user_id: string;
  role: Role;
  local: boolean;
}

const at = (login: string, action: string) => `/api/auth/accounts/${encodeURIComponent(login)}/${action}`;

/** Every route needs a live, unlocked admin on the microscope PC; the server refuses the rest. */
export function accountsApi(client: Client) {
  return {
    me: () => client.get<Me>("/api/auth/me"),
    list: () => client.get<Account[]>("/api/auth/accounts"),
    needsLogin: () => client.get<NeedsLogin[]>("/api/auth/accounts/needs-login"),
    approve: (login: string, role: Role) => client.post<Account>(at(login, "approve"), { role }),
    setRole: (login: string, role: Role) => client.post<Account>(at(login, "role"), { role }),
    disable: (login: string) => client.post<Account>(at(login, "disable")),
    enable: (login: string) => client.post<Account>(at(login, "enable")),
    /** ends every login of that account */
    resetPassword: (login: string, password: string) => client.post<Account>(at(login, "password"), { password }),
    /** the email goes in the body, never in a path; the audit line names both */
    giveLogin: (email: string, login: string) => client.post<Account>("/api/auth/accounts/give-login", { email, login }),
  };
}

export type AccountsApi = ReturnType<typeof accountsApi>;
