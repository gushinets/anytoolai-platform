import type { components } from "../api/generated/platformApi";

export type QuotaUnit = components["schemas"]["QuotaUnit"];
export type QuotaPeriod = components["schemas"]["QuotaPeriod"];
export type QuotaDimension = components["schemas"]["QuotaDimension"];

const QUOTA_UNIT_VALUES = {
  scenario_run: true,
} satisfies Record<QuotaUnit, true>;

const QUOTA_PERIOD_VALUES = {
  lifetime: true,
} satisfies Record<QuotaPeriod, true>;

const QUOTA_DIMENSION_VALUES = {
  product: true,
  scenario: true,
} satisfies Record<QuotaDimension, true>;

export function isQuotaUnit(value: string): value is QuotaUnit {
  return Object.hasOwn(QUOTA_UNIT_VALUES, value);
}

export function isQuotaPeriod(value: string): value is QuotaPeriod {
  return Object.hasOwn(QUOTA_PERIOD_VALUES, value);
}

export function isQuotaDimension(value: string): value is QuotaDimension {
  return Object.hasOwn(QUOTA_DIMENSION_VALUES, value);
}
