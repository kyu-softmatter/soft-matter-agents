import { type FormEvent, type ReactNode, useState } from "react";

/**
 * Shown over the app while the login is locked. Running work and guards keep going (PLAN 5절),
 * so the app stays mounted underneath and the stop control passed in `abort` stays live here.
 */
export function LockScreen({
  name,
  abort,
  onUnlock,
  onLogout,
}: {
  name: string;
  /** the shell's Abort control; it needs no login state (design rule 12) */
  abort?: ReactNode;
  onUnlock: (password: string) => Promise<void>;
  onLogout: () => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    setError(null);
    try {
      await onUnlock(password);
      setPassword("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  return (
    <div className="login-lock" role="dialog" aria-modal="true" aria-label="Locked">
      <div className="login-lock-stop">{abort}</div>
      <form className="login-card" aria-label="Unlock" onSubmit={submit}>
        <h2>Locked</h2>
        <p>Enter your password to continue, {name}. Running work goes on while the screen is locked.</p>
        <label className="login-field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            autoComplete="current-password"
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit">Unlock</button>
        <button type="button" className="link" onClick={onLogout}>
          Log out instead
        </button>
      </form>
    </div>
  );
}
