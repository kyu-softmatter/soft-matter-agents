import { useCallback, useEffect, useState } from "react";

import type { Account, AuthApi, Me, Role } from "./api";

const ROLES: Role[] = ["viewer", "operator", "admin"];

function Row({ account, onApprove }: { account: Account; onApprove: (role: Role) => Promise<void> }) {
  // no role is chosen for the admin: they pick one on purpose (D12)
  const [role, setRole] = useState<Role | "">("");
  const [busy, setBusy] = useState(false);
  return (
    <tr>
      <td>{account.name}</td>
      <td>{account.email}</td>
      <td>{account.created_at}</td>
      <td>
        <select aria-label={`Role for ${account.email}`} value={role} onChange={(e) => setRole(e.target.value as Role | "")}>
          <option value="">Choose a role</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </td>
      <td>
        <button
          type="button"
          disabled={role === "" || busy}
          onClick={async () => {
            if (role === "") return;
            setBusy(true);
            try {
              await onApprove(role);
            } finally {
              setBusy(false);
            }
          }}
        >
          Approve
        </button>
      </td>
    </tr>
  );
}

/** Pending accounts with a role picker. Rendered only for an admin on the microscope PC. */
export function ApprovalList({ api, me }: { api: AuthApi; me: Me }) {
  const allowed = me.role === "admin" && me.local;
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setAccounts(await api.pending());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [api]);

  useEffect(() => {
    if (allowed) void load();
  }, [allowed, load]);

  if (!allowed) return null;
  return (
    <section className="login-approvals" aria-label="Accounts waiting for approval">
      <h3>Accounts waiting for approval</h3>
      {error && (
        <p className="login-error" role="alert">
          {error}
        </p>
      )}
      {accounts !== null && accounts.length === 0 && <p className="muted">No accounts are waiting.</p>}
      {accounts !== null && accounts.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Created</th>
              <th>Role</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <Row
                key={a.email}
                account={a}
                onApprove={async (role) => {
                  try {
                    await api.approve(a.email, role);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e));
                    return;
                  }
                  await load();
                }}
              />
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
