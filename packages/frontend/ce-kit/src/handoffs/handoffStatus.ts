import { makeEnumGuard } from "../api/parsing";
import type { components } from "../api/generated/platformApi";

export type HandoffStatus = components["schemas"]["HandoffStatus"];

export const isHandoffStatus = makeEnumGuard<HandoffStatus>({
  created: true,
  viewed: true,
  accepted: true,
  declined: true,
  consumed: true,
  expired: true,
  failed: true,
});
