// Temporary until gen:api, T-009: the auth API types are written by hand from
// docs/screens/login.md section 1 and server/api/auth.py. Once `npm run gen:api` has run with
// the router in, the types come from src/api/ and this file keeps only the clients.

import { type Client, CommandRefused } from "../client";

export type Role = "admin" | "operator" | "viewer";
export type SetupState = "needs_admin" | "ready";
export type LoginFailure = "bad_credentials" | "pending_approval" | "disabled" | "not_a_login";

/**
 * A login is a plain id, never an email (console card 009): `signed_through.login` in
 * plan_approval.schema.json, character for character. The server checks it again; this is so the
 * screen can say so before it sends anything.
 */
export const LOGIN_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
export const isPlainLogin = (value: string): boolean => LOGIN_PATTERN.test(value);
export const PLAIN_LOGIN_MESSAGE = "A login is a plain id, not an email address.";

/** The first-start state, and the login the first administrator will have (a name, not a secret). */
export interface SetupInfo {
  state: SetupState;
  /** null when the settings name something that is not a plain id */
  adminLogin: string | null;
}

export interface Me {
  user_id: string;
  name: string;
  role: Role;
  locked: boolean;
  /** the browser runs on the microscope PC; write controls work only then (D16) */
  local: boolean;
  expires_at: number;
}

export interface Account {
  login: string;
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
  setup(): Promise<SetupInfo>;
  /** the login is the settings', never sent from here: only the password the person typed */
  createAdmin(body: { password: string; name?: string }): Promise<Me>;
  signup(body: { name: string; login: string; password: string }): Promise<void>;
  login(body: { login: string; password: string }): Promise<Me>;
  logout(): Promise<void>;
  lock(): Promise<void>;
  unlock(body: { password: string }): Promise<Me>;
  /** null when not logged in (401) */
  me(): Promise<Me | null>;
  pending(): Promise<Account[]>;
  approve(login: string, role: Role): Promise<Account>;
}

// -- the real client: the app's shared client (cookie rides along, same origin) ---------------

const OUTCOMES: readonly string[] = ["bad_credentials", "pending_approval", "disabled", "not_a_login"];

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
      const s = await read<{ state: SetupState; admin_login?: string | null }>("/setup");
      if (s === null) throw new AuthError(401, "setup state not readable");
      return { state: s.state, adminLogin: s.admin_login ?? null };
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
    approve: (login, role) => post(`/accounts/${encodeURIComponent(login)}/approve`, { role }),
  };
}

// -- the fake client: in memory, for tests and for building the screen before the router ------

interface FakeUser {
  name: string;
  login: string;
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

/**
 * Plain logins and test passwords only. `local` is what `me()` reports for this browser;
 * `adminLogin` is what the first-start screen is told (null: the settings name a bad one).
 */
export function createFakeAuthApi(
  opts: { users?: Omit<FakeUser, "created_at">[]; setup?: SetupState; local?: boolean; adminLogin?: string | null } = {},
): FakeAuthApi {
  const users: FakeUser[] = (opts.users ?? []).map((u) => ({ ...u, created_at: "2026-10-01T09:00:00+00:00" }));
  let setup: SetupState = opts.setup ?? "ready";
  const adminLogin = opts.adminLogin === undefined ? "softmatter" : opts.adminLogin;
  let current: { login: string; locked: boolean } | null = null;
  const local = opts.local ?? true;
  const find = (login: string) => users.find((u) => u.login === login);
  const notPlain = () => new AuthError(422, PLAIN_LOGIN_MESSAGE, "not_a_login");
  const meOf = (u: FakeUser, locked: boolean): Me => ({
    user_id: u.login,
    name: u.name,
    role: u.role,
    locked,
    local,
    expires_at: Date.now() / 1000 + 12 * 3600,
  });
  const account = (u: FakeUser): Account => ({
    login: u.login,
    name: u.name,
    role: u.role,
    status: u.status,
    created_at: u.created_at,
    approved_by: null,
    approved_at: null,
  });
  const admin = () => {
    const u = current && find(current.login);
    if (!u || u.role !== "admin" || !local) throw new AuthError(403, "only an admin on the microscope PC");
    return u;
  };

  return {
    users,
    lockNow() {
      if (current) current.locked = true;
    },
    async setup() {
      return { state: setup, adminLogin: setup === "ready" ? null : adminLogin };
    },
    async createAdmin({ name, password }) {
      if (setup === "ready") throw new AuthError(409, "an admin account already exists");
      if (!local) throw new AuthError(403, "set up on the microscope PC");
      if (adminLogin === null || !isPlainLogin(adminLogin)) throw new AuthError(409, `admin_login is not usable. ${PLAIN_LOGIN_MESSAGE}`);
      const u: FakeUser = {
        name: name?.trim() ? name : adminLogin,
        login: adminLogin,
        password,
        role: "admin",
        status: "active",
        created_at: new Date().toISOString(),
      };
      users.push(u);
      setup = "ready";
      current = { login: u.login, locked: false };
      return meOf(u, false);
    },
    async signup({ name, login, password }) {
      if (!isPlainLogin(login)) throw notPlain();
      // as the server (audit S1): an existing login gets the same answer and changes nothing
      if (users.some((u) => u.login.toLowerCase() === login.toLowerCase())) return;
      users.push({ name, login, password, role: "viewer", status: "pending", created_at: new Date().toISOString() });
    },
    async login({ login, password }) {
      if (!isPlainLogin(login)) throw notPlain();
      const u = find(login);
      if (!u || u.password !== password) throw new AuthError(401, "Wrong login or password.", "bad_credentials");
      if (u.status === "pending")
        throw new AuthError(401, "Your account is waiting for an administrator's approval.", "pending_approval");
      if (u.status === "disabled") throw new AuthError(401, "This account is disabled.", "disabled");
      current = { login: u.login, locked: false };
      return meOf(u, false);
    },
    async logout() {
      current = null;
    },
    async lock() {
      if (current) current.locked = true;
    },
    async unlock({ password }) {
      const u = current && find(current.login);
      if (!u || !current) throw new AuthError(401, "not logged in");
      if (u.password !== password) throw new AuthError(401, "Wrong password.");
      current.locked = false;
      return meOf(u, false);
    },
    async me() {
      const u = current && find(current.login);
      return u && current ? meOf(u, current.locked) : null;
    },
    async pending() {
      admin();
      return users.filter((u) => u.status === "pending").map(account);
    },
    async approve(login, role) {
      admin();
      const u = find(login);
      if (!u || u.status !== "pending") throw new AuthError(409, `${login} is not waiting for approval`);
      u.status = "active";
      u.role = role;
      return account(u);
    },
  };
}
