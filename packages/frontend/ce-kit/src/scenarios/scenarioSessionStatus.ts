import { makeEnumGuard } from "../api/parsing";
import type { components } from "../api/generated/platformApi";

export type ScenarioSessionStatus = components["schemas"]["ScenarioSessionStatus"];

export const isScenarioSessionStatus = makeEnumGuard<ScenarioSessionStatus>({
  started: true,
  waiting_for_user: true,
  running: true,
  completed: true,
  failed: true,
  expired: true,
});
