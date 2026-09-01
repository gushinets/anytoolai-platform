import type { QuotaDimension, QuotaPeriod, QuotaUnit } from "../quota/quotaEnums";
import type { FrontendType } from "./frontendType";

export type RuntimeRendererHint = {
  renderer: "json_schema";
  schemaRef: string;
  schemaVersion: number | null;
};

export type RuntimeFrontend = {
  frontendId: string;
  type: FrontendType;
  enabled: boolean;
};

export type RuntimeScenario = {
  scenarioId: string;
  version: number;
  allowedNextActions: string[];
  inputRendererHint: RuntimeRendererHint;
  outputRendererHint: RuntimeRendererHint;
};

export type RuntimeQuotaSummary = {
  quotaPolicyId: string;
  unit: QuotaUnit;
  limitCount: number;
  period: QuotaPeriod;
  dimension: QuotaDimension;
};

export type RuntimeConfig = {
  productId: string;
  frontendIds: string[];
  frontends: RuntimeFrontend[];
  scenarioIds: string[];
  scenarios: RuntimeScenario[];
  quotaSummary: RuntimeQuotaSummary | null;
  allowedUiCapabilities: string[];
};
