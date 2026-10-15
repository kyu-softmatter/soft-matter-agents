import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { AreaId } from "./areas";

/**
 * What the screen in view is about, sent with every prompt (PLAN X1). The shell
 * fills `area`; a screen adds short ids and names only (PLAN D7 prompt_only:
 * no frames, no file contents).
 */
export interface ScreenContext {
  area: AreaId;
  sample_id?: string;
  run_id?: string;
  op_id?: string;
  /** e.g. a clicked map region, in stage um */
  region?: { x_um: number; y_um: number; w_um?: number; h_um?: number };
  [key: string]: unknown;
}

export type ScreenDetails = Omit<ScreenContext, "area">;

interface Store {
  current: ScreenContext;
  setDetails: (details: ScreenDetails) => void;
}

const Ctx = createContext<Store | null>(null);

export function ScreenContextProvider({ area, children }: { area: AreaId; children: ReactNode }) {
  // Details are stored with the area they were registered under, so a new area
  // starts with none without a reset effect (a parent's effect would run after
  // the new screen's own and wipe it).
  const areaRef = useRef(area);
  areaRef.current = area;
  const [stored, setStored] = useState<{ area: AreaId; details: ScreenDetails }>({
    area,
    details: {},
  });
  const setDetails = useCallback(
    (details: ScreenDetails) => setStored({ area: areaRef.current, details }),
    [],
  );
  const value = useMemo<Store>(
    () => ({
      current: stored.area === area ? { ...stored.details, area } : { area },
      setDetails,
    }),
    [area, stored, setDetails],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

function useStore(): Store {
  const s = useContext(Ctx);
  if (s === null) throw new Error("ScreenContextProvider is missing (the shell provides it)");
  return s;
}

/**
 * For area screens: register what this screen is about. Pass a value that only
 * changes when the details change (e.g. built with useMemo). Cleared on unmount.
 */
export function useScreenContext(details: ScreenDetails): void {
  const { setDetails } = useStore();
  useEffect(() => {
    setDetails(details);
    return () => setDetails({});
  }, [details, setDetails]);
}

/** For the prompt box (T-014): the context of the screen in view. */
export function useCurrentScreenContext(): ScreenContext {
  return useStore().current;
}
