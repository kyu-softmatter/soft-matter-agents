import { NotBuilt } from "../../app/NotBuilt";

/** The instruments area, until its own card builds it (console card 008). Requests nothing. */
export default function InstrumentsScreen() {
  return (
    <NotBuilt
      title="Instruments"
      shows="Shown, drafted and stopped from here. Nothing moves or lights from these screens."
    />
  );
}
