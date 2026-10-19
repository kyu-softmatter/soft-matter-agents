import { Retired, RETIRED_AREAS } from "../../app/Retired";

/** Area screen for `map`: its routes were retired with dino's engine command path (console card 003). */
export default function MapScreen() {
  return <Retired {...RETIRED_AREAS.map} />;
}
