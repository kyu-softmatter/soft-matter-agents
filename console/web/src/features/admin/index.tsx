// The `admin` area: an admin on the microscope PC manages the other accounts.
//
// List with a status filter; per row: approve a pending account with a role (D12), change a role,
// disable / enable, set a new password (their logins end). Accounts are switched off, never
// deleted (the audit log refers to them). The admin's own row has no actions, so nobody locks
// themselves out here. An account an older console recorded under an email is listed apart as
// "needs a login id", and the administrator gives it a plain login. The server checks all of it
// again (server/api/auth.py).

import { useCallback, useEffect, useMemo, useState } from "react";

import { useClient } from "../../app/client";
import { isPlainLogin, PLAIN_LOGIN_MESSAGE } from "../../app/login/api";
import {
  type Account,
  type AccountStatus,
  accountsApi,
  type AccountsApi,
  type Me,
  type NeedsLogin,
  type Role,
  ROLES,
} from "./api";

type Filter = AccountStatus | "all";
const FILTERS: Filter[] = ["all", "pending", "active", "disabled"];

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function RolePicker({ login, value, onChange }: { login: string; value: Role | ""; onChange: (r: Role | "") => void }) {
  return (
    <select aria-label={`Role for ${login}`} value={value} onChange={(e) => onChange(e.target.value as Role | "")}>
      <option value="">Choose a role</option>
      {ROLES.map((r) => (
        <option key={r} value={r}>
          {r}
        </option>
      ))}
    </select>
  );
}

function Actions({
  account,
  api,
  run,
}: {
  account: Account;
  api: AccountsApi;
  run: (what: string, fn: () => Promise<unknown>) => Promise<boolean>;
}) {
  const { login, status } = account;
  // a pending account gets no preset role: the admin picks one on purpose (D12)
  const [role, setRole] = useState<Role | "">(status === "active" ? account.role : "");
  const [password, setPassword] = useState<string | null>(null);

  return (
    <span className="accounts-actions">
      {status === "pending" && (
        <>
          <RolePicker login={login} value={role} onChange={setRole} />
          <button
            type="button"
            disabled={role === ""}
            onClick={() => role !== "" && void run(`${login} approved as ${role}`, () => api.approve(login, role))}
          >
            Approve
          </button>
        </>
      )}
      {status === "active" && (
        <>
          <RolePicker login={login} value={role} onChange={setRole} />
          <button
            type="button"
            disabled={role === "" || role === account.role}
            onClick={() => role !== "" && void run(`${login} is now ${role}`, () => api.setRole(login, role))}
          >
            Set role
          </button>
          <button type="button" onClick={() => void run(`${login} switched off`, () => api.disable(login))}>
            Switch off
          </button>
        </>
      )}
      {status === "disabled" && (
        <button type="button" onClick={() => void run(`${login} switched on`, () => api.enable(login))}>
          Switch on
        </button>
      )}
      {status !== "pending" &&
        (password === null ? (
          <button type="button" onClick={() => setPassword("")}>
            Reset password
          </button>
        ) : (
          <form
            className="accounts-password"
            onSubmit={(e) => {
              e.preventDefault();
              void run(`New password set for ${login}; their logins ended`, () => api.resetPassword(login, password)).then(
                (ok) => ok && setPassword(null),
              );
            }}
          >
            <input
              type="password"
              aria-label={`New password for ${login}`}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button type="submit" disabled={password === ""}>
              Set password
            </button>
            <button type="button" onClick={() => setPassword(null)}>
              Cancel
            </button>
          </form>
        ))}
    </span>
  );
}

function GiveLogin({
  old,
  run,
  api,
}: {
  old: NeedsLogin;
  api: AccountsApi;
  run: (what: string, fn: () => Promise<unknown>) => Promise<boolean>;
}) {
  const [login, setLogin] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  return (
    <form
      className="accounts-password"
      onSubmit={(e) => {
        e.preventDefault();
        if (!isPlainLogin(login)) {
          setProblem(PLAIN_LOGIN_MESSAGE); // refused here, so nothing is sent
          return;
        }
        setProblem(null);
        void run(`${old.name} now logs in as ${login}`, () => api.giveLogin(old.email, login));
      }}
    >
      <input
        type="text"
        aria-label={`Login for ${old.email}`}
        autoComplete="off"
        value={login}
        onChange={(e) => setLogin(e.target.value)}
      />
      <button type="submit" disabled={login === ""}>
        Give login
      </button>
      {problem && (
        <span className="warn" role="alert">
          {problem}
        </span>
      )}
    </form>
  );
}

export default function AccountsScreen() {
  const client = useClient();
  const api = useMemo(() => accountsApi(client), [client]);
  const [me, setMe] = useState<Me | null>(null);
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [needing, setNeeding] = useState<NeedsLogin[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const allowed = me !== null && me.role === "admin" && me.local;

  const load = useCallback(async () => {
    try {
      setAccounts(await api.list());
      setNeeding(await api.needsLogin());
    } catch (e) {
      setError(message(e));
    }
  }, [api]);

  useEffect(() => {
    api.me().then(setMe, (e) => setError(message(e)));
  }, [api]);

  useEffect(() => {
    if (allowed) void load();
  }, [allowed, load]);

  const run = useCallback(
    async (what: string, fn: () => Promise<unknown>) => {
      setDone(null);
      try {
        await fn();
      } catch (e) {
        setError(message(e));
        return false;
      }
      setError(null);
      setDone(what);
      await load();
      return true;
    },
    [load],
  );

  if (me === null && error === null) return <p className="muted">Loading…</p>;
  if (me !== null && me.role !== "admin") return <p className="muted">Only an administrator can manage accounts.</p>;
  if (me !== null && !me.local) return <p className="muted">Accounts are managed on the microscope PC.</p>;

  const shown = (accounts ?? []).filter((a) => filter === "all" || a.status === filter);
  return (
    <section className="accounts" aria-label="Accounts">
      <h2>Accounts</h2>
      <label>
        Show{" "}
        <select aria-label="Status filter" value={filter} onChange={(e) => setFilter(e.target.value as Filter)}>
          {FILTERS.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <p className="warn" role="alert">
          {error}
        </p>
      )}
      {done && <p role="status">{done}</p>}
      {accounts !== null && shown.length === 0 && <p className="muted">No accounts.</p>}
      {shown.length > 0 && (
        <table aria-label="Account list">
          <thead>
            <tr>
              <th>Name</th>
              <th>Login</th>
              <th>Role</th>
              <th>Status</th>
              <th>Created</th>
              <th>Approved by</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {shown.map((a) => (
              <tr key={a.login} data-status={a.status}>
                <td>{a.name}</td>
                <td>{a.login}</td>
                <td>{a.role}</td>
                <td>{a.status}</td>
                <td>{a.created_at}</td>
                <td>{a.approved_by ?? "—"}</td>
                <td>
                  {a.login === me?.user_id ? (
                    <span className="muted">you</span>
                  ) : (
                    // keyed on status and role: after a change the row starts from the new values
                    <Actions key={`${a.status}-${a.role}`} account={a} api={api} run={run} />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {needing.length > 0 && (
        <section className="accounts-needs-login" aria-label="Needs a login id">
          <h3>Needs a login id</h3>
          <p className="muted">
            An older console kept these accounts under an email. They cannot log in until you give each a plain login. Nothing
            is guessed, and nothing is deleted.
          </p>
          <table aria-label="Accounts that need a login id">
            <thead>
              <tr>
                <th>Name</th>
                <th>Was</th>
                <th>Role</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {needing.map((n) => (
                <tr key={n.email}>
                  <td>{n.name}</td>
                  <td>{n.email}</td>
                  <td>{n.role}</td>
                  <td>{n.status}</td>
                  <td>
                    <GiveLogin old={n} api={api} run={run} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </section>
  );
}
