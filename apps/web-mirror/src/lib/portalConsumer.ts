/** The host owns the deployment audience; CE-kit receives it explicitly. */
export const DEFAULT_PORTAL_CONSUMER_ID = "platform-kernel";

export function portalConsumerId(): string {
  return process.env.NEXT_PUBLIC_PORTAL_CONSUMER_ID ?? DEFAULT_PORTAL_CONSUMER_ID;
}
