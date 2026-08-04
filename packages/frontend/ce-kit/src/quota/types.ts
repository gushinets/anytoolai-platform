export type QuotaRequest = {
  productId: string;
  guestId: string;
  scenarioId?: string;
};

export type QuotaState = {
  guestId: string;
  productId: string;
  quotaPolicyId: string;
  quotaDimension: string;
  dimensionKey: string;
  scenarioId: string | null;
  unit: string;
  period: string;
  limitCount: number;
  usedCount: number;
  remainingCount: number;
  exhausted: boolean;
};
