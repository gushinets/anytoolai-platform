import type { components } from "../api/generated/platformApi";

export type HandoffStatus = components["schemas"]["HandoffStatus"];

const HANDOFF_STATUS_VALUES = {
  created: true,
  viewed: true,
  accepted: true,
  declined: true,
  consumed: true,
  expired: true,
  failed: true,
} satisfies Record<HandoffStatus, true>;

export function isHandoffStatus(value: string): value is HandoffStatus {
  return Object.hasOwn(HANDOFF_STATUS_VALUES, value);
}
