// Temporary until gen:api, T-009: the auth API types are written by hand from
// docs/screens/login.md section 1 and server/api/auth.py. Once `npm run gen:api` has run with
// the router in, the types come from src/api/ and this file keeps only the clients.

import { type Client, CommandRefused } from "../client";

export type Role = "admin" | "operator" | "viewer";
export type SetupState = "needs_admin_email" | "needs_admin" | "ready";
export type LoginFailure = "bad_credentials" | "pending_approval" | "disabled";

export interface Me {
  user_id: string;
  name: string;
  role: Role;
  locked: boolean;
  has_control: boolean;
  /** the browser runs on the microscope PC; write controls work only then (D16) */
  local: boolean;
  expires_at: number;
}

export interface Account {
  email: string;
  name: string;
  role: Role;
  status: "pending" | "active" | "disabled";
  created_at: string;
  approved_by: string | null;
  approved_at: string | null;
}

/** A failed call. `status` is the HTTP status; `outcome` is set on a failed login. */
export class AuthError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly outcome?: LoginFailure,
  ) {
    super(message);
  }
}

export interface AuthApi {
  setup(): Promise<SetupState>;
  createAdmin(body: { name: string; password: string; email?: string }): Promise<Me>;
  signup(body: { name: string; email: string; password: string }): Promise<void>;
  login(body: { email: string; password: string }): Promise<Me>;
  logout(): Promise<void>;
  lock(): Promise<void>;
  unlock(body: { password: string }): Promise<Me>;
  /** null when not logged in (401) */
  me(): Promise<Me | null>;
  pending(): Promise<Account[]>;
  approve(email: string, role: Role): Promise<Account>;
}

// -- the real client: the app's shared client (cookie rides along, same origin) ---------------

const OUTCOMES: readonly string[] = ["bad_credentials", "pending_approval", "disabled"];

function authError(e: unknown): unknown {
  if (!(e instanceof CommandRefused)) return e;
  const outcome = e.code && OUTCOMES.includes(e.code) ? (e.code as LoginFailure) : undefined;
  return new AuthError(e.status, e.detail, outcome);
}

/**
 * Over `useClient()`: writes go through `client.post` (a remote_view 403 turns the app
 * read-only, a 401 / 423 re-reads the login). `/me` and `/setup` read the transport directly,
 * because their 401 is an answer here ("not logged in"), not a login failure to report.
 */
export function clientAuthApi(client: Client): AuthApi {
  const post = async <T>(path: string, body?: unknown): Promise<T> => {
    try {
      return (await client.post<T>(`/api/auth${path}`, body)) as T;
    } catch (e) {
      throw authError(e);
    }
  };
  const read = async <T>(path: string): Promise<T | null> => {
    const r = await client.transport.fetch(`/api/auth${path}`, { headers: { Accept: "application/json" } });
    if (r.status === 401) return null;
    if (!r.ok) throw new AuthError(r.status, `HTTP ${r.status}`);
    return (await r.json()) as T;
  };
  return {
    setup: async () => {
      const s = await read<{ state: SetupState }>("/setup");
      if (s === null) throw new AuthError(401, "setup state not readable");
      return s.state;
    },
    createAdmin: (body) => post("/setup/admin", body),
    signup: async (body) => {
      await post("/signup", body);
    },
    login: (body) => post("/login", body),
    logout: async () => {
      await post("/logout");
    },
    lock: async () => {
      await post("/lock");
    },
    unlock: (body) => post("/unlock", body),
    me: () => read<Me>("/me"),
    pending: async () => {
      try {
        return await client.get<Account[]>("/api/auth/accounts?status=pending");
      } catch (e) {
        throw authError(e);
      }
    },
    approve: (email, role) => post(`/accounts/${encodeURIComponent(email)}/approve`, { role }),
  };
}

// -- the fake client: in memory, for tests and for building the screen before the router ------

interface FakeUser {
  name: string;
  email: string;
  password: string;
  role: Role;
  status: Account["status"];
  created_at: string;
}

export interface FakeAuthApi extends AuthApi {
  /** test hook: lock the current session as the idle timer would */
  lockNow(): void;
  readonly users: FakeUser[];
}

/** Users are example.test addresses only. `local` is what `me()` reports for this browser. */
export function createFakeAuthApi(
  opts: { users?: Omit<FakeUser, "created_at">[]; setup?: SetupState; local?: boolean } = {},
): FakeAuthApi {
  const users: FakeUser[] = (opts.users ?? []).map((u) => ({ ...u, created_at: "2026-10-01T09:00:00+00:00" }));
  let setup: SetupState = opts.setup ?? "ready";
  let current: { email: string; locked: boolean } | null = null;
  const local = opts.local ?? true;
  const find = (email: string) => users.find((u) => u.email === email.trim().toLowerCase());
  const meOf = (u: FakeUser, locked: boolean): Me => ({
    user_id: u.email,
    name: u.name,
    role: u.role,
    locked,
    has_control: false,
    local,
    expires_at: Date.now() / 1000 + 12 * 3600,
  });
  const account = (u: FakeUser): Account => ({
    email: u.email,
    name: u.name,
    role: u.role,
    status: u.status,
    created_at: u.created_at,
    approved_by: null,
    approved_at: null,
  });
  const admin = () => {
    const u = current && find(current.email);
    if (!u || u.role !== "admin" || !local) throw new AuthError(403, "only an admin on the microscope PC");
    return u;
  };

  return {
    users,
    lockNow() {
      if (current) current.locked = true;
    },
    async setup() {
      return setup;
    },
    async createAdmin({ name, password, email }) {
      if (setup === "ready") throw new AuthError(409, "an admin account already exists");
      if (!local) throw new AuthError(403, "set up on the microscope PC");
      const u: FakeUser = {
        name,
        email: (email ?? "admin@example.test").toLowerCase(),
        password,
        role: "admin",
        status: "active",
        created_at: new Date().toISOString(),
      };
      users.push(u);
      setup = "ready";
      current = { email: u.email, locked: false };
      return meOf(u, false);
    },
    async signup({ name, email, password }) {
      // as the server (audit S1): an existing email gets the same answer and changes nothing
      if (find(email)) return;
      users.push({ name, email: email.trim().toLowerCase(), password, role: "viewer", status: "pending", created_at: new Date().toISOString() });
    },
    async login({ email, password }) {
      const u = find(email);
      if (!u || u.password !== password) throw new AuthError(401, "Wrong email or password.", "bad_credentials");
      if (u.status === "pending")
        throw new AuthError(401, "Your account is waiting for an administrator's approval.", "pending_approval");
      if (u.status === "disabled") throw new AuthError(401, "This account is disabled.", "disabled");
      current = { email: u.email, locked: false };
      return meOf(u, false);
    },
    async logout() {
      current = null;
    },
    async lock() {
      if (current) current.locked = true;
    },
    async unlock({ password }) {
      const u = current && find(current.email);
      if (!u || !current) throw new AuthError(401, "not logged in");
      if (u.password !== password) throw new AuthError(401, "Wrong password.");
      current.locked = false;
      return meOf(u, false);
    },
    async me() {
      const u = current && find(current.email);
      return u && current ? meOf(u, current.locked) : null;
    },
    async pending() {
      admin();
      return users.filter((u) => u.status === "pending").map(account);
    },
    async approve(email, role) {
      admin();
      const u = find(email);
      if (!u || u.status !== "pending") throw new AuthError(409, `${email} is not waiting for approval`);
      u.status = "active";
      u.role = role;
      return account(u);
    },
  };
}
