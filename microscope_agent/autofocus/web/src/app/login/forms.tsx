import { type FormEvent, useState } from "react";

import { AuthError } from "./api";

const MIN_PASSWORD = 8; // T-018 passwords.MIN_PASSWORD_LENGTH

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function useSubmit(action: () => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, setError, submit };
}

function Field({
  label,
  type = "text",
  value,
  onChange,
  autoComplete,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
}) {
  return (
    <label className="login-field">
      <span>{label}</span>
      <input type={type} value={value} autoComplete={autoComplete} onChange={(e) => onChange(e.target.value)} required />
    </label>
  );
}

function ErrorLine({ error }: { error: string | null }) {
  return error ? (
    <p className="login-error" role="alert">
      {error}
    </p>
  ) : null;
}

function passwordProblem(password: string, again: string): string | null {
  if (password.length < MIN_PASSWORD) return `The password needs at least ${MIN_PASSWORD} characters.`;
  if (password !== again) return "The two passwords differ.";
  return null;
}

export function LoginForm({
  onLogin,
  onSignup,
}: {
  /** rejects with AuthError; a pending or disabled outcome is handled by the caller */
  onLogin: (email: string, password: string) => Promise<void>;
  onSignup: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { busy, error, submit } = useSubmit(() => onLogin(email, password));
  return (
    <form className="login-card" aria-label="Log in" onSubmit={submit}>
      <h2>Log in</h2>
      <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="username" />
      <Field label="Password" type="password" value={password} onChange={setPassword} autoComplete="current-password" />
      <ErrorLine error={error} />
      <button type="submit" disabled={busy}>
        Log in
      </button>
      <p className="muted">
        No account yet?{" "}
        <button type="button" className="link" onClick={onSignup}>
          Create one
        </button>
      </p>
    </form>
  );
}

export function SignupForm({
  onSignup,
  onCancel,
}: {
  onSignup: (body: { name: string; email: string; password: string }) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const { busy, error, submit } = useSubmit(async () => {
    const problem = passwordProblem(password, again);
    if (problem) throw new Error(problem);
    await onSignup({ name, email, password });
  });
  return (
    <form className="login-card" aria-label="Create an account" onSubmit={submit}>
      <h2>Create an account</h2>
      <p className="muted">An administrator approves new accounts and sets what they may do.</p>
      <Field label="Name" value={name} onChange={setName} autoComplete="name" />
      <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="username" />
      <Field label="Password" type="password" value={password} onChange={setPassword} autoComplete="new-password" />
      <Field label="Password again" type="password" value={again} onChange={setAgain} autoComplete="new-password" />
      <ErrorLine error={error} />
      <button type="submit" disabled={busy}>
        Create account
      </button>
      <button type="button" className="link" onClick={onCancel}>
        Back to log in
      </button>
    </form>
  );
}

export function SetupForm({
  needsEmail,
  local,
  onCreate,
}: {
  needsEmail: boolean;
  local: boolean;
  onCreate: (body: { name: string; password: string; email?: string }) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const { busy, error, submit } = useSubmit(async () => {
    const problem = passwordProblem(password, again);
    if (problem) throw new Error(problem);
    await onCreate(needsEmail ? { name, password, email } : { name, password });
  });
  if (!local) {
    return (
      <div className="login-card" role="status">
        <h2>First run</h2>
        <p>Set up the administrator account on the microscope PC.</p>
      </div>
    );
  }
  return (
    <form className="login-card" aria-label="Create the administrator account" onSubmit={submit}>
      <h2>First run: create the administrator account</h2>
      <Field label="Name" value={name} onChange={setName} autoComplete="name" />
      {needsEmail && <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="username" />}
      <Field label="Password" type="password" value={password} onChange={setPassword} autoComplete="new-password" />
      <Field label="Password again" type="password" value={again} onChange={setAgain} autoComplete="new-password" />
      <ErrorLine error={error} />
      <button type="submit" disabled={busy}>
        Create administrator
      </button>
    </form>
  );
}

export function Notice({ kind, onBack }: { kind: "signed_up" | "pending_approval" | "disabled"; onBack: () => void }) {
  const text = {
    signed_up: "Account created. An administrator must approve it before you can log in.",
    pending_approval: "Your account is waiting for an administrator's approval.",
    disabled: "This account is disabled. Ask an administrator.",
  }[kind];
  return (
    <div className="login-card" role="status">
      <p>{text}</p>
      <button type="button" className="link" onClick={onBack}>
        Back to log in
      </button>
    </div>
  );
}

export function isNotice(e: unknown): e is AuthError & { outcome: "pending_approval" | "disabled" } {
  return e instanceof AuthError && (e.outcome === "pending_approval" || e.outcome === "disabled");
}
