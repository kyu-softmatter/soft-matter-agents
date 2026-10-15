import { createContext, type ReactNode, useContext, useEffect, useState, useSyncExternalStore } from "react";

import type { components } from "../api/schema";

export type CommandIn = components["schemas"]["CommandIn"];
/** What a screen sends: `kind` and whatever differs from the server's defaults (op, op_id, args, origin). */
export type CommandInput = Pick<CommandIn, "kind"> & Partial<Omit<CommandIn, "kind">>;
export type EventOut = components["schemas"]["EventOut"];
export type EventKind = EventOut["kind"];
type WsEvent = components["schemas"]["WsEvent"];
type WsLock = components["schemas"]["WsLock"];

/**
 * Everything the shell and the screens need from the server, in one injectable
 * object: tests pass fakes, the app uses the browser's fetch and WebSocket.
 */
export interface Transport {
  fetch: (path: string, init?: RequestInit) => Promise<Response>;
  openSocket: (path: string) => WebSocket;
}

export const browserTransport: Transport = {
  fetch: (path, init) => window.fetch(path, init),
  openSocket: (path) => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return new WebSocket(`${proto}//${window.location.host}${path}`);
  },
};

// -- read-only (remote view) -----------------------------------------------------------

const LOOPBACK = new Set(["127.0.0.1", "localhost", "[::1]", "::1"]);

export function isLoopbackHost(hostname: string): boolean {
  return LOOPBACK.has(hostname) || hostname.endsWith(".localhost");
}

export interface ReadOnlyState {
  readOnly: boolean;
  why: string | null;
}

/**
 * Whether this browser may send commands. Starts from the page's host (a remote
 * viewer reaches the server by a non-loopback name) and turns on for good when
 * the server answers a command with 403. The server decides; this only greys
 * out buttons so people are not surprised.
 */
export class ReadOnlyStore {
  private state: ReadOnlyState;
  private listeners = new Set<() => void>();

  constructor(hostname: string) {
    this.state = isLoopbackHost(hostname)
      ? { readOnly: false, why: null }
      : { readOnly: true, why: "remote view" };
  }

  get = (): ReadOnlyState => this.state;

  subscribe = (fn: () => void): (() => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  refuse(why: string): void {
    if (this.state.readOnly && this.state.why === why) return;
    this.state = { readOnly: true, why };
    this.listeners.forEach((fn) => fn());
  }
}

// -- events -----------------------------------------------------------------------------

export type EventHandler = (ev: EventOut) => void;

/**
 * One `/ws/events` connection shared by the whole app. Reconnects with backoff;
 * `onStatus` says whether it is open. After a reconnect, screens should re-read
 * state (events in between are lost), so listeners get `connected` again.
 *
 * Besides engine events the server sends `{"type": "lock", "locked": bool}` (T-009c)
 * on connect and whenever the login locks or unlocks; while locked it sends no
 * events. `onLock` listeners get those (the login gate re-reads /me on them).
 */
export class EventStream {
  private socket: WebSocket | null = null;
  private handlers = new Set<EventHandler>();
  private lockListeners = new Set<(locked: boolean) => void>();
  private statusListeners = new Set<(open: boolean) => void>();
  /** the last lock state the server sent; null before any */
  locked: boolean | null = null;
  private retry = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private closed = false;
  open = false;

  constructor(
    private transport: Transport,
    private path = "/ws/events",
    private backoffMs = (n: number) => Math.min(500 * 2 ** n, 10_000),
  ) {}

  start(): void {
    if (this.socket || this.closed) return;
    const ws = this.transport.openSocket(this.path);
    this.socket = ws;
    ws.onopen = () => {
      this.retry = 0;
      this.setOpen(true);
    };
    ws.onmessage = (msg) => {
      if (typeof msg.data !== "string") return;
      let parsed: unknown;
      try {
        parsed = JSON.parse(msg.data);
      } catch {
        return;
      }
      const m = parsed as Partial<WsEvent> | Partial<WsLock>;
      if (m.type === "event" && "event" in m && m.event) {
        this.handlers.forEach((h) => h(m.event as EventOut));
      } else if (m.type === "lock" && "locked" in m && typeof m.locked === "boolean") {
        const locked = m.locked;
        this.locked = locked;
        this.lockListeners.forEach((fn) => fn(locked));
      }
    };
    ws.onclose = () => {
      this.socket = null;
      this.setOpen(false);
      if (this.closed) return;
      this.timer = setTimeout(() => this.start(), this.backoffMs(this.retry++));
    };
  }

  stop(): void {
    this.closed = true;
    if (this.timer) clearTimeout(this.timer);
    this.socket?.close();
    this.socket = null;
  }

  on(handler: EventHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  /** Lock / unlock messages from the server (T-009c). Returns the unsubscribe. */
  onLock(fn: (locked: boolean) => void): () => void {
    this.lockListeners.add(fn);
    return () => {
      this.lockListeners.delete(fn);
    };
  }

  onStatus(fn: (open: boolean) => void): () => void {
    this.statusListeners.add(fn);
    return () => this.statusListeners.delete(fn);
  }

  private setOpen(open: boolean): void {
    this.open = open;
    this.statusListeners.forEach((fn) => fn(open));
  }
}

// -- the client -------------------------------------------------------------------------

/**
 * A refused request. `code` is the server's refusal code when it sends one
 * (`detail.code` or the `X-DinoAF-Refusal` header, T-009b), e.g. "remote_view".
 */
export class CommandRefused extends Error {
  constructor(
    public status: number,
    public detail: string,
    public code: string | null = null,
  ) {
    super(detail);
  }
}

/** The refusal code that means "this browser is a remote viewer" (T-009b). */
export const REMOTE_VIEW = "remote_view";

export class Client {
  readonly readOnly: ReadOnlyStore;
  readonly events: EventStream;

  constructor(
    readonly transport: Transport,
    hostname: string,
  ) {
    this.readOnly = new ReadOnlyStore(hostname);
    this.events = new EventStream(transport);
  }

  private authListeners = new Set<(status: number) => void>();

  /**
   * Called on any 401 (logged out) or 423 (locked) answer. The login gate uses it
   * to re-read /me and show the login or lock screen.
   */
  onAuthFailure(fn: (status: number) => void): () => void {
    this.authListeners.add(fn);
    return () => this.authListeners.delete(fn);
  }

  private check(r: Response): void {
    if (r.status === 401 || r.status === 423) this.authListeners.forEach((fn) => fn(r.status));
  }

  async get<T = unknown>(path: string): Promise<T> {
    const r = await this.transport.fetch(path, { headers: { Accept: "application/json" } });
    this.check(r);
    if (!r.ok) throw await refusalOf(r);
    return (await r.json()) as T;
  }

  /**
   * POST JSON to an area's own route (console submit, map writes, sessions, auth...).
   * The same rules as `command`: a 401 / 423 re-reads the login; a 403 marked
   * `remote_view` switches the whole app to read-only. Any other 403 (D16, session
   * owner, role...) is only this action's refusal: it is thrown to the caller with
   * its reason and code and changes no global state. Returns the JSON reply, or
   * null for an empty one (204). Engine commands go through `command`, not here.
   */
  async post<T = unknown>(path: string, body?: unknown): Promise<T | null> {
    const r = await this.send(path, body, "application/json");
    if (r.status === 204) return null;
    const text = await r.text();
    return text === "" ? null : (JSON.parse(text) as T);
  }

  /**
   * POST JSON and get the raw Response back for a streamed reply (NDJSON: one JSON
   * object per line), e.g. the prompt box (T-014b). The same rules as `post` run
   * before the body is touched: a 401 / 423 re-reads the login, a 403 marked
   * `remote_view` turns the app read-only, and any refusal is thrown as
   * CommandRefused. On success the body is unread; the caller reads
   * `response.body` and cancels it when done.
   */
  async postStream(path: string, body?: unknown): Promise<Response> {
    return this.send(path, body, "application/x-ndjson");
  }

  /** The one POST path: request, then the auth and refusal rules shared by post / postStream. */
  private async send(path: string, body: unknown, accept: string): Promise<Response> {
    const r = await this.transport.fetch(path, {
      method: "POST",
      headers: body === undefined ? { Accept: accept } : { "Content-Type": "application/json", Accept: accept },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    this.check(r);
    if (!r.ok) {
      const refused = await refusalOf(r);
      if (refused.status === 403 && refused.code === REMOTE_VIEW) this.readOnly.refuse(refused.detail);
      throw refused;
    }
    return r;
  }

  /** POST /api/commands (engine commands), with the rules of `post`. */
  async command(cmd: CommandInput): Promise<string> {
    const reply = await this.post<components["schemas"]["CommandAccepted"]>("/api/commands", cmd);
    if (!reply) throw new CommandRefused(502, "the server accepted the command but gave no op_id");
    return reply.op_id;
  }
}

type ApiError = components["schemas"]["ApiError"];
type ValidationError = components["schemas"]["ValidationError"];

/**
 * The reason and code of a refused request. The server's refusals are `ApiError`
 * with `detail: RefusalDetail` = `{code, message}` (T-009b); the header
 * `X-DinoAF-Refusal` also carries the code. FastAPI's own answers still use a
 * plain string (404 "Not Found") or a validation list (422), so those are read
 * too, with no code.
 */
export async function refusalOf(r: Response): Promise<CommandRefused> {
  let code = r.headers.get("X-DinoAF-Refusal");
  let text = `HTTP ${r.status}`;
  try {
    const body = (await r.json()) as Partial<ApiError> | { detail?: string | ValidationError[] };
    const d: unknown = body.detail;
    if (typeof d === "string") {
      text = d;
    } else if (Array.isArray(d)) {
      const first = d[0] as Partial<ValidationError> | undefined;
      if (first && typeof first.msg === "string") text = first.msg;
    } else if (d && typeof d === "object") {
      const rd = d as Partial<components["schemas"]["RefusalDetail"]>;
      if (typeof rd.code === "string") code = code ?? rd.code;
      if (typeof rd.message === "string") text = rd.message;
      else if (typeof rd.code === "string") text = rd.code;
    }
  } catch {
    // no JSON body: keep the status line
  }
  return new CommandRefused(r.status, text, code);
}

const ClientCtx = createContext<Client | null>(null);

export function ClientProvider({ client, children }: { client: Client; children: ReactNode }) {
  useEffect(() => {
    client.events.start();
  }, [client]);
  return <ClientCtx.Provider value={client}>{children}</ClientCtx.Provider>;
}

export function useClient(): Client {
  const c = useContext(ClientCtx);
  if (c === null) throw new Error("ClientProvider is missing (main.tsx provides it)");
  return c;
}

/** For screens: grey out command buttons when this is true. The server refuses anyway. */
export function useReadOnly(): ReadOnlyState {
  const { readOnly } = useClient();
  return useSyncExternalStore(readOnly.subscribe, readOnly.get);
}

/** For screens: call `handler` for engine events (optionally only some kinds). */
export function useEngineEvents(handler: EventHandler, kinds?: readonly EventKind[]): void {
  const { events } = useClient();
  const key = kinds?.join(",") ?? "";
  useEffect(() => {
    const only = key ? new Set(key.split(",")) : null;
    return events.on((ev) => {
      if (!only || only.has(ev.kind)) handler(ev);
    });
  }, [events, handler, key]);
}

/** Whether the event socket is open. */
export function useEventsConnected(): boolean {
  const { events } = useClient();
  const [open, setOpen] = useState(events.open);
  useEffect(() => events.onStatus(setOpen), [events]);
  return open;
}

/**
 * Whether the server says the login is locked (WsLock on /ws/events, T-009c).
 * While locked the server sends no events, so values on screen are not live.
 */
export function useEventsLocked(): boolean {
  const { events } = useClient();
  const [locked, setLocked] = useState(events.locked === true);
  useEffect(() => {
    setLocked(events.locked === true);
    return events.onLock(setLocked);
  }, [events]);
  return locked;
}
