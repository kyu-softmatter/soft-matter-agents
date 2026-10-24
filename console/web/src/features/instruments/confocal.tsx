/**
 * Confocal (canvas `PConfocal`, console card 012): state only, from the status file's spinning-disk
 * channel. Nothing here is a control.
 */

import { type IdleView, type StatusOut } from "./api";
import { ReadingsTable, StatusHead } from "./status";

export const SHUTTER_NOTE = "read back; which value means closed is not recorded";
export const DISK_CHANNEL = "confocal_csuw1";

export function Confocal({ status, view }: { status: StatusOut; view: IdleView | null }) {
  const disk = view?.snapshot.filter((r) => r.channel === DISK_CHANNEL) ?? [];
  return (
    <section aria-label="Confocal" className="inst-confocal">
      <StatusHead status={status} view={view} />
      {view !== null && (disk.length > 0 ? (
        <ReadingsTable label="Spinning disk" readings={disk} />
      ) : (
        <p>The spinning disk is unknown: the last run did not read it.</p>
      ))}
      <p>Shutter: <span>{SHUTTER_NOTE}</span></p>
    </section>
  );
}
