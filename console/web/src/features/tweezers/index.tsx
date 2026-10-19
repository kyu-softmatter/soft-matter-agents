import { Retired, RETIRED_AREAS } from "../../app/Retired";

/** Area screen for `tweezers`: its routes were retired with dino's engine command path (console card 003). */
export default function TweezersScreen() {
  return <Retired {...RETIRED_AREAS.tweezers} />;
}
