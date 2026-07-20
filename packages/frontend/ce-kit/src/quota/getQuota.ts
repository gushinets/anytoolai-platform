export type QuotaRequest = {
  productId: string;
  guestId: string;
};

/**
 * A16-deferred placeholder.
 *
 * A13 quota is backend-complete, but the shared CE-kit HTTP quota client belongs to A16's
 * PlatformApiClient work. Frontends must treat backend quota state as authoritative and must not
 * enforce quota from this placeholder.
 */
export async function getQuota(_request: QuotaRequest): Promise<never> {
  throw new Error("CE-kit getQuota() is deferred to A16 PlatformApiClient integration.");
}
