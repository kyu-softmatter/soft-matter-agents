import type { Transport } from "../app/client";

/** A WebSocket stand-in the test drives by hand. */
export class FakeSocket {
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  closed = false;

  constructor(public path: string) {}

  open(): void {
    this.onopen?.(new Event("open"));
  }

  send(data: unknown): void {
    this.onmessage?.(new MessageEvent("message", { data: typeof data === "string" ? data : JSON.stringify(data) }));
  }

  event(kind: string, data: Record<string, unknown> = {}, op_id = ""): void {
    this.send({ type: "event", event: { kind, op_id, data, t: 1 } });
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.onclose?.(new CloseEvent("close"));
  }
}

export type Route = (init?: RequestInit) => {
  status: number;
  body?: unknown;
  headers?: Record<string, string>;
};

/** The logged-in user every fake transport answers on /api/auth/me unless a test says otherwise. */
export const TEST_ME = {
  user_id: "operator@example.test",
  name: "Test Operator",
  role: "operator",
  locked: false,
  has_control: false,
  local: true,
  expires_at: 4102444800, // 2100-01-01: never expires during a test
} as const;

export interface FakeOptions {
  /**
   * Who `/api/auth/me` says is logged in. Default TEST_ME, so app-level tests get
   * past T-105's login gate. `null` answers 401 (logged out). A route for
   * `/api/auth/me` in `routes` wins over this.
   */
  me?: Record<string, unknown> | null;
}

/** Auth routes every fake transport has, so the real login gate (T-105) lets tests in. */
function authDefaults(opts: FakeOptions): Record<string, Route> {
  const me = opts.me === undefined ? TEST_ME : opts.me;
  return {
    "/api/auth/me": () =>
      me === null ? { status: 401, body: { detail: { code: "login_required", message: "log in first" } } } : { status: 200, body: me },
    "/api/auth/setup": () => ({ status: 200, body: { state: "ready" } }),
    "/api/auth/control": () => ({ status: 200, body: { holder: null } }),
    "/api/auth/activity": () => ({ status: 204 }),
  };
}

/**
 * A transport whose fetch answers from a table of paths and whose sockets are
 * FakeSockets. Unknown paths answer 404. The auth routes above are there by default
 * (opt out with `{ me: null }`, or override a route in `routes`).
 */
export function fakeTransport(routes: Record<string, Route>, opts: FakeOptions = {}) {
  const sockets: FakeSocket[] = [];
  const calls: { path: string; init?: RequestInit }[] = [];
  // Look routes up, never spread them: a test may pass a Proxy that answers any path
  // (the map screen's testWorld), and spreading a Proxy copies nothing.
  const defaults = authDefaults(opts);
  const transport: Transport = {
    fetch: async (path, init) => {
      calls.push({ path, init });
      const route = routes[path] ?? defaults[path];
      const { status, body, headers } = route
        ? route(init)
        : { status: 404, body: { detail: "Not Found" }, headers: undefined };
      return new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json", ...headers },
      });
    },
    openSocket: (path) => {
      const s = new FakeSocket(path);
      sockets.push(s);
      return s as unknown as WebSocket;
    },
  };
  return { transport, sockets, calls };
}
