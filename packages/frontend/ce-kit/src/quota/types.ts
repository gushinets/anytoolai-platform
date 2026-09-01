import type { QuotaDimension, QuotaPeriod, QuotaUnit } from "./quotaEnums";

export type QuotaRequest = {
  productId: string;
  guestId: string;
  scenarioId?: string;
};

export type QuotaState = {
  guestId: string;
  productId: string;
  quotaPolicyId: string;
  quotaDimension: QuotaDimension;
  dimensionKey: string;
  scenarioId: string | null;
  unit: QuotaUnit;
  period: QuotaPeriod;
  limitCount: number;
  usedCount: number;
  remainingCount: number;
  exhausted: boolean;
};
