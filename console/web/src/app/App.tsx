import { useEffect } from "react";

import { LoginGate, useActivity, useAuth } from "./auth";
import { type Client, ClientProvider, useClient } from "./client";
import { ShellFooter } from "./Footer";
import { Shell } from "./Shell";
import { StopAllRuns } from "./StopAllRuns";

function Connected() {
  const client = useClient();
  const auth = useAuth();

  // any later 401 / 423 sends the app back to the login or lock screen
  useEffect(() => {
    if (!auth) return;
    return client.onAuthFailure(() => void auth.refresh());
  }, [client, auth]);

  // the server says whether this browser is on the microscope PC
  const remote = auth?.me && auth.me.local === false;
  useEffect(() => {
    if (remote) client.readOnly.refuse("remote view");
  }, [client, remote]);

  useActivity(!!auth?.me);

  return <Shell admin={auth?.me?.role === "admin"} footer={<ShellFooter />} />;
}

/**
 * The whole app: the server client, the login gate (T-105; a pass-through until
 * its web part is in the build) with Abort kept reachable under it, then the
 * shell with its footer.
 */
export function App({ client }: { client: Client }) {
  return (
    <ClientProvider client={client}>
      <LoginGate abort={<StopAllRuns />}>
        <Connected />
      </LoginGate>
    </ClientProvider>
  );
}
