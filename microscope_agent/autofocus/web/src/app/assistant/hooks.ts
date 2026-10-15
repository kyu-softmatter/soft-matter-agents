import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { useClient } from "../client";
import { type AssistantApi, type Permission, clientAssistantApi } from "./api";

/** Tests (and the fake mode before the router) put an api here; the app uses the shell's client. */
export const AssistantApiContext = createContext<AssistantApi | null>(null);

export function useAssistantApi(): AssistantApi {
  const given = useContext(AssistantApiContext);
  const client = useClient();
  return useMemo(() => given ?? clientAssistantApi(client), [given, client]);
}

// shared wording for pre-click permission state (ui-spec 7.0, T-009b /api/permissions)
export const CHECKING_PERMISSIONS = "Checking permissions…";
export const PERMISSION_CHECK_UNAVAILABLE = "Permission check unavailable";

export type Permissions =
  | { state: "checking" }
  | { state: "unavailable" }
  | { state: "ready"; table: Record<string, Permission> };

/** Why a button for `op` is off, or null when it may be pressed. */
export function blockedReason(p: Permissions, op: string): string | null {
  if (p.state === "checking") return CHECKING_PERMISSIONS;
  if (p.state === "unavailable") return PERMISSION_CHECK_UNAVAILABLE;
  const entry = p.table[op];
  if (!entry) return PERMISSION_CHECK_UNAVAILABLE;
  return entry.allowed ? null : entry.reason || "not allowed";
}

/** Ask the server which of `ops` this browser may do now; re-asked when `ops` or `epoch` change. */
export function usePermissions(api: AssistantApi, ops: string[], epoch = 0): Permissions {
  const key = [...new Set(ops)].sort().join(",");
  const [p, setP] = useState<Permissions>({ state: "checking" });
  useEffect(() => {
    if (!key) {
      setP({ state: "ready", table: {} });
      return;
    }
    let live = true;
    setP({ state: "checking" });
    api
      .permissions(key.split(","))
      .then((table) => live && setP({ state: "ready", table }))
      .catch(() => live && setP({ state: "unavailable" }));
    return () => {
      live = false;
    };
  }, [api, key, epoch]);
  return p;
}

const CONVERSATION_KEY = "dino_af_conversation";

/** The one conversation every screen continues; kept for the browser tab's life. */
export function useConversationId(): [string | null, (id: string | null) => void] {
  const [id, setId] = useState<string | null>(() => sessionStorage.getItem(CONVERSATION_KEY));
  const set = (next: string | null) => {
    if (next) sessionStorage.setItem(CONVERSATION_KEY, next);
    else sessionStorage.removeItem(CONVERSATION_KEY);
    setId(next);
  };
  return [id, set];
}
