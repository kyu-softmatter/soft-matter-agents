import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { isLoopbackHost, useClient } from "../client";
import { type AuthApi, clientAuthApi, type Me, type SetupState } from "./api";
import { isNotice, LoginForm, Notice, SetupForm, SignupForm } from "./forms";
import { LockScreen } from "./LockScreen";
import "./login.css";

export interface AuthState {
  me: Me;
  api: AuthApi;
  logout(): Promise<void>;
  lock(): Promise<void>;
  /**
   * Counts unlocks. While locked the server sends lock state only (T-009c), so the shell
   * re-reads its state (e.g. /api/state) when this changes.
   */
  resumed: number;
  /** re-read /me; call it when any other request answers 401 or 423 */
  refresh(): Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

/** The logged-in user inside `LoginGate`; null outside it. */
export function useAuth(): AuthState | null {
  return useContext(AuthContext);
}

type Phase =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "setup"; state: SetupState; local: boolean }
  | { kind: "out"; view: "login" | "signup" | "signed_up" | "pending_approval" | "disabled" }
  | { kind: "in"; me: Me };

/**
 * The shell wraps the app in this (docs/screens/login.md 5.4). Without a login it shows the
 * setup, login or sign-up screens instead of the app. While the login is locked it keeps the
 * app mounted (work and guards go on) under the lock screen, with the shell's Abort control.
 */
function GateWith({
  api,
  abort,
  pollMs = 30_000,
  onLockState,
  local = isLoopbackHost(window.location.hostname),
  children,
}: {
  api: AuthApi;
  abort?: ReactNode;
  /** how often /me is re-read so an idle lock shows without user input */
  pollMs?: number;
  /** lock-state messages from /ws/events (T-009c): the gate re-reads /me on each one */
  onLockState?: (fn: (locked: boolean) => void) => () => void;
  /** before login the server has not said; guessed from the page host (a remote viewer uses a non-loopback name) */
  local?: boolean;
  children: ReactNode;
}) {
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [resumed, setResumed] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const me = await api.me();
      if (me) {
        setPhase({ kind: "in", me });
        return;
      }
      const state = await api.setup();
      setPhase(state === "ready" ? { kind: "out", view: "login" } : { kind: "setup", state, local });
    } catch (e) {
      setPhase({ kind: "error", message: e instanceof Error ? e.message : String(e) });
    }
  }, [api, local]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const loggedIn = phase.kind === "in";
  useEffect(() => {
    if (!loggedIn || pollMs <= 0) return;
    const id = setInterval(() => void refresh(), pollMs);
    return () => clearInterval(id);
  }, [loggedIn, pollMs, refresh]);

  useEffect(() => {
    if (!loggedIn || !onLockState) return;
    return onLockState(() => void refresh());
  }, [loggedIn, onLockState, refresh]);

  const auth = useMemo<AuthState | null>(
    () =>
      phase.kind === "in"
        ? {
            me: phase.me,
            api,
            refresh,
            resumed,
            logout: async () => {
              await api.logout();
              setPhase({ kind: "out", view: "login" });
            },
            lock: async () => {
              await api.lock();
              await refresh();
            },
          }
        : null,
    [phase, api, refresh, resumed],
  );

  const out = (view: Extract<Phase, { kind: "out" }>["view"]) => setPhase({ kind: "out", view });

  if (phase.kind === "loading") return <p className="muted login-wait">Checking login…</p>;
  if (phase.kind === "error")
    return (
      <div className="login-page">
        <div className="login-card" role="alert">
          <p>Cannot reach the server: {phase.message}</p>
          <button type="button" onClick={() => void refresh()}>
            Try again
          </button>
        </div>
      </div>
    );
  if (phase.kind === "setup")
    return (
      <div className="login-page">
        <SetupForm
          needsEmail={phase.state === "needs_admin_email"}
          local={phase.local}
          onCreate={async (body) => setPhase({ kind: "in", me: await api.createAdmin(body) })}
        />
      </div>
    );
  if (phase.kind === "out")
    return (
      <div className="login-page">
        {phase.view === "login" && (
          <LoginForm
            onSignup={() => out("signup")}
            onLogin={async (email, password) => {
              try {
                setPhase({ kind: "in", me: await api.login({ email, password }) });
              } catch (e) {
                if (isNotice(e)) out(e.outcome);
                else throw e;
              }
            }}
          />
        )}
        {phase.view === "signup" && (
          <SignupForm
            onCancel={() => out("login")}
            onSignup={async (body) => {
              await api.signup(body);
              out("signed_up");
            }}
          />
        )}
        {(phase.view === "signed_up" || phase.view === "pending_approval" || phase.view === "disabled") && (
          <Notice kind={phase.view} onBack={() => out("login")} />
        )}
      </div>
    );

  const { me } = phase;
  return (
    <AuthContext.Provider value={auth}>
      <div className={me.locked ? "login-under-lock" : undefined} inert={me.locked} aria-hidden={me.locked || undefined}>
        {children}
      </div>
      {me.locked && (
        <LockScreen
          name={me.name}
          abort={abort}
          onUnlock={async (password) => {
            setPhase({ kind: "in", me: await api.unlock({ password }) });
            await refresh(); // events were not sent while locked: read everything again
            setResumed((n) => n + 1);
          }}
          onLogout={() => void auth?.logout()}
        />
      )}
    </AuthContext.Provider>
  );
}

type GateProps = Omit<Parameters<typeof GateWith>[0], "api">;

function GateOverClient(props: GateProps) {
  const client = useClient();
  const api = useMemo(() => clientAuthApi(client), [client]);
  // T-009c sends lock state on /ws/events; the shared stream exposes it once T-010 adds onLock
  const events = client.events as typeof client.events & {
    onLock?: (fn: (locked: boolean) => void) => () => void;
  };
  const onLockState = useMemo(() => events.onLock?.bind(events), [events]);
  return <GateWith api={api} onLockState={onLockState} {...props} />;
}

/**
 * The shell wraps the app in this (docs/screens/login.md 5.4), inside the ClientProvider. It
 * talks to the server through the shared client; tests pass a fake `api` instead.
 */
export function LoginGate({ api, ...props }: GateProps & { api?: AuthApi }) {
  return api ? <GateWith api={api} {...props} /> : <GateOverClient {...props} />;
}
