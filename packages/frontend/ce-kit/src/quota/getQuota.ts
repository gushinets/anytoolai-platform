import { requestAndParse } from "../api/client";
import type { PlatformApiClient, PlatformApiResult } from "../api/client";
import { parseQuotaState } from "./parseQuotaState";
import type { QuotaRequest, QuotaState } from "./types";

export async function getQuota(
  client: PlatformApiClient,
  request: QuotaRequest,
): Promise<PlatformApiResult<QuotaState>> {
  const query = new URLSearchParams({ guest_id: request.guestId });
  if (request.scenarioId !== undefined) {
    query.set("scenario_id", request.scenarioId);
  }

  return requestAndParse(
    client,
    {
      method: "GET",
      path: `/v1/products/${encodeURIComponent(request.productId)}/quota?${query.toString()}`,
    },
    parseQuotaState,
    "Quota response was invalid.",
  );
}
