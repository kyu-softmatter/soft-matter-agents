import { type ComponentType, type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { CommandRefused, useClient } from "./client";

/**
 * The seam to the login screen (T-105, `src/app/login/`, not part of the shell).
 * When that folder exists the real `LoginGate`, `useAuth` and `ApprovalList` are
 * used; until then these stand-ins with the same names let the app run with no
 * login. No shell edit is needed when T-105 merges.
 */

export type Role = "admin" | "operator" | "viewer";

/** The fields of T-105's `Me` the shell reads (docs/screens/login.md). */
export interface ShellMe {
  user_id: string;
  name: string;
  role: Role;
  locked: boolean;
  has_control: boolean;
  local: boolean;
}

export interface ShellAuth {
  me: ShellMe;
  api: unknown;
  logout(): Promise<void>;
  lock(): Promise<void>;
  refresh(): Promise<void>;
  /** T-105: changes after each unlock, so state read before the lock is re-read */
  resumed?: number;
}

interface LoginModule {
  LoginGate: ComponentType<{ abort?: ReactNode; children: ReactNode }>;
  useAuth: () => ShellAuth | null;
  ApprovalList: ComponentType<{ api: unknown; me: ShellMe }>;
}

const found = import.meta.glob<LoginModule>("./login/index.ts", { eager: true });

export function pickLogin(modules: Record<string, LoginModule>): LoginModule | null {
  const m = Object.values(modules)[0];
  return m && typeof m.LoginGate === "function" && typeof m.useAuth === "function" ? m : null;
}

function PassThroughGate({ children }: { abort?: ReactNode; children: ReactNode }) {
  return <>{children}</>;
}

/** The three names the shell uses, from a login module or the pass-through stand-ins. */
export function seamFrom(mod: LoginModule | null): Pick<LoginModule, "LoginGate" | "useAuth" | "ApprovalList"> {
  return {
    LoginGate: mod?.LoginGate ?? PassThroughGate,
    useAuth: mod?.useAuth ?? (() => null),
    ApprovalList: mod?.ApprovalList ?? (() => null),
  };
}

const login = pickLogin(found);
const seam = seamFrom(login);

/** True once T-105's login screen is in the build. */
export const loginAvailable = login !== null;

export const LoginGate: LoginModule["LoginGate"] = seam.LoginGate;
export const useAuth: () => ShellAuth | null = seam.useAuth;
export const ApprovalList: LoginModule["ApprovalList"] = seam.ApprovalList;

// -- activity (idle lock) ---------------------------------------------------------------

export const ACTIVITY_MS = 30_000;

/**
 * Tell the server someone is working so the idle lock does not fire: POST
 * /api/auth/activity on input, at most every 30 s. Only while logged in.
 */
export function useActivity(enabled: boolean, now: () => number = Date.now): void {
  const client = useClient();
  const last = useRef(-Infinity);
  useEffect(() => {
    if (!enabled) return;
    const onInput = () => {
      const t = now();
      if (t - last.current < ACTIVITY_MS) return;
      last.current = t;
      void client.transport.fetch("/api/auth/activity", { method: "POST" }).catch(() => {});
    };
    const kinds = ["pointerdown", "keydown", "wheel"] as const;
    kinds.forEach((k) => window.addEventListener(k, onInput, { passive: true }));
    return () => kinds.forEach((k) => window.removeEventListener(k, onInput));
  }, [client, enabled, now]);
}

// -- control token holder ---------------------------------------------------------------

export interface Holder {
  user_id: string;
  name: string;
  since?: string | number;
}

/** GET /api/auth/control, and Take / Release for the local operator. */
export function useControl(me: ShellMe | null) {
  const client = useClient();
  const [holder, setHolder] = useState<Holder | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!me) return;
    try {
      const r = await client.get<{ holder: Holder | null }>("/api/auth/control");
      setHolder(r.holder);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [client, me]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const post = useCallback(
    async (path: string) => {
      const r = await client.transport.fetch(path, { method: "POST" });
      if (!r.ok) {
        const body = (await r.json().catch(() => ({}))) as { detail?: string; holder?: Holder };
        if (body.holder) setHolder(body.holder);
        setError(body.detail ?? `HTTP ${r.status}`);
        throw new CommandRefused(r.status, body.detail ?? `HTTP ${r.status}`);
      }
      setError(null);
      await reload();
    },
    [client, reload],
  );

  return {
    holder,
    error,
    take: () => post("/api/auth/control/acquire").catch(() => {}),
    release: () => post("/api/auth/control/release").catch(() => {}),
  };
}

// -- abort, reachable while logged out or locked ----------------------------------------

/**
 * Stops whatever runs. Needs no login and no control (PLAN 5): the gate keeps
 * it on screen under the lock. Reads the running operations at click time.
 */
export function AbortButton() {
  const client = useClient();
  const [msg, setMsg] = useState<string | null>(null);
  const onClick = async () => {
    try {
      const snap = await client.get<{ running?: { op_id?: string }[] }>("/api/state");
      const ids = (snap.running ?? []).map((o) => o.op_id).filter((x): x is string => !!x);
      if (ids.length === 0) {
        setMsg("nothing running");
        return;
      }
      await Promise.all(ids.map((op_id) => client.command({ kind: "abort", op_id })));
      setMsg(`abort sent (${ids.length})`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };
  return (
    <span className="abort">
      <button type="button" className="abort-button" onClick={() => void onClick()}>
        Abort
      </button>
      {msg && <span className="muted"> {msg}</span>}
    </span>
  );
}
