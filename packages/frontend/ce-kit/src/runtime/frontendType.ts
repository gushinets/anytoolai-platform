import type { components } from "../api/generated/platformApi";

export type FrontendType = components["schemas"]["FrontendType"];

const FRONTEND_TYPE_VALUES = {
  chrome_extension: true,
  web: true,
} satisfies Record<FrontendType, true>;

export function isFrontendType(value: string): value is FrontendType {
  return Object.hasOwn(FRONTEND_TYPE_VALUES, value);
}
