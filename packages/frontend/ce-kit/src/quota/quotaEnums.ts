import { makeEnumGuard } from "../api/parsing";
import type { components } from "../api/generated/platformApi";

export type QuotaUnit = components["schemas"]["QuotaUnit"];
export type QuotaPeriod = components["schemas"]["QuotaPeriod"];
export type QuotaDimension = components["schemas"]["QuotaDimension"];

export const isQuotaUnit = makeEnumGuard<QuotaUnit>({
  scenario_run: true,
});

export const isQuotaPeriod = makeEnumGuard<QuotaPeriod>({
  lifetime: true,
});

export const isQuotaDimension = makeEnumGuard<QuotaDimension>({
  product: true,
  scenario: true,
});
