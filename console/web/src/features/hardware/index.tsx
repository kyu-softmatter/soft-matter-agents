import { Retired, RETIRED_AREAS } from "../../app/Retired";

/** Area screen for `hardware`: its routes were retired with dino's engine command path (console card 003). */
export default function HardwareScreen() {
  return <Retired {...RETIRED_AREAS.hardware} />;
}
