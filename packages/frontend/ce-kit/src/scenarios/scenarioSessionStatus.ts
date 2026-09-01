import type { components } from "../api/generated/platformApi";

export type ScenarioSessionStatus = components["schemas"]["ScenarioSessionStatus"];

const SCENARIO_SESSION_STATUS_VALUES = {
  started: true,
  waiting_for_user: true,
  running: true,
  completed: true,
  failed: true,
  expired: true,
} satisfies Record<ScenarioSessionStatus, true>;

export function isScenarioSessionStatus(value: string): value is ScenarioSessionStatus {
  return Object.hasOwn(SCENARIO_SESSION_STATUS_VALUES, value);
}
