// Temporary until gen:api: the /api/auth/accounts shapes are hand-written here from
// server/api/auth.py (AccountOut, RoleIn, PasswordIn). Reads and writes go through the shell's
// shared client (src/app/client.tsx: get, post); this file opens no connection of its own.

import type { Client } from "../../app/client";

export type Role = "admin" | "operator" | "viewer";
export type AccountStatus = "pending" | "active" | "disabled";

export const ROLES: Role[] = ["viewer", "operator", "admin"];

export interface Account {
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

const at = (email: string, action: string) => `/api/auth/accounts/${encodeURIComponent(email)}/${action}`;

/** Every route needs a live, unlocked admin on the microscope PC; the server refuses the rest. */
export function accountsApi(client: Client) {
  return {
    me: () => client.get<Me>("/api/auth/me"),
    list: () => client.get<Account[]>("/api/auth/accounts"),
    approve: (email: string, role: Role) => client.post<Account>(at(email, "approve"), { role }),
    setRole: (email: string, role: Role) => client.post<Account>(at(email, "role"), { role }),
    disable: (email: string) => client.post<Account>(at(email, "disable")),
    enable: (email: string) => client.post<Account>(at(email, "enable")),
    /** ends every login of that account */
    resetPassword: (email: string, password: string) => client.post<Account>(at(email, "password"), { password }),
    /** pending or disabled accounts only; the audit log keeps the history */
    remove: (email: string) => client.post<Account>(at(email, "delete")),
  };
}

export type AccountsApi = ReturnType<typeof accountsApi>;
