export type RuntimeRendererHint = {
  renderer: "json_schema";
  schemaRef: string;
  schemaVersion: number | null;
};

export type RuntimeFrontend = {
  frontendId: string;
  type: string;
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
  unit: string;
  limitCount: number;
  period: string;
  dimension: string;
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
