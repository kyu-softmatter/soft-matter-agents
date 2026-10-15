import { useEffect, useState } from "react";

import { AbortButton, LoginGate, useActivity, useAuth } from "./auth";
import { type Client, ClientProvider, useClient, useReadOnly } from "./client";
import { Shell } from "./Shell";
import { useAssistantStatus, useEngineStatus } from "./status";
import { ShutdownNoticeView, StatusBarView, UserPart } from "./StatusBar";

function Connected() {
  const client = useClient();
  const auth = useAuth();
  const status = useEngineStatus(auth?.resumed);
  const assistant = useAssistantStatus();
  const readOnly = useReadOnly();
  const [dismissed, setDismissed] = useState(false);

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

  return (
    <Shell
      admin={auth?.me?.role === "admin"}
      statusBar={
        <StatusBarView
          status={status}
          assistant={assistant}
          readOnly={readOnly}
          user={<UserPart auth={auth} />}
        />
      }
      notice={
        dismissed ? null : (
          <ShutdownNoticeView last={status.lastShutdown} onDismiss={() => setDismissed(true)} />
        )
      }
    />
  );
}

/**
 * The whole app: the server client, the login gate (T-105; a pass-through until
 * its web part is in the build) with Abort kept reachable under it, then the
 * shell with the live status bar.
 */
export function App({ client }: { client: Client }) {
  return (
    <ClientProvider client={client}>
      <LoginGate abort={<AbortButton />}>
        <Connected />
      </LoginGate>
    </ClientProvider>
  );
}
