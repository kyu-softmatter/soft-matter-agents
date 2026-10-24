import { useEffect, useState } from "react";

import type { components } from "../api/schema";
import { useAuth } from "./auth";
import { useClient } from "./client";
import { StopAllRuns } from "./StopAllRuns";

type StoreOut = components["schemas"]["StoreOut"];

/** `GET /api/console/store` names the store behind the console; "mock" is example data. */
export const STORE_PATH = "/api/console/store";

/**
 * Whether what the screens show is example data: true only when the server has said the store is
 * the mock. Unknown, unreachable or any other store is false, so the chip never claims it.
 */
export function useExampleData(): boolean {
  const client = useClient();
  const [example, setExample] = useState(false);
  useEffect(() => {
    let live = true;
    client.get<StoreOut>(STORE_PATH).then(
      (s) => live && setExample(s.store === "mock"),
      () => live && setExample(false),
    );
    return () => {
      live = false;
    };
  }, [client]);
  return example;
}

/**
 * The footer of every screen (console card 008): STOP at the left, the same stop the lock screen
 * has; an "Example data" chip while the store is the mock; a chip when the server says this browser
 * is not on the microscope computer (the screens are then read only); at the right who is logged
 * in, Lock, and Log out.
 * Nothing about lights, the assistant, or who holds control of an engine: the console has none.
 */
export function ShellFooter() {
  const auth = useAuth();
  const example = useExampleData();
  const me = auth?.me ?? null;
  return (
    <>
      <StopAllRuns />
      <span className="muted footer-note">Stops every running run.</span>
      <span className="footer-spacer" />
      {example && <span className="chip">Example data</span>}
      {me && me.local === false && (
        <span className="chip warn" data-testid="remote-chip">
          viewing from another computer · read only
        </span>
      )}
      {me && <span className="footer-user">{me.name}</span>}
      {auth && me && (
        <>
          <button type="button" onClick={() => void auth.lock()}>
            Lock
          </button>
          <button type="button" onClick={() => void auth.logout()}>
            Log out
          </button>
        </>
      )}
    </>
  );
}
