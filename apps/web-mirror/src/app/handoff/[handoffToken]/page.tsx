"use client";

import { use } from "react";
import { PortalIdentityBoundary } from "../../../components/PortalIdentityBoundary";
import { HandoffConsent } from "../../../components/HandoffConsent";
import { HANDOFF_MESSAGES } from "../../../components/handoffMessages";
import { LocaleProvider } from "../../../i18n";
import { canAttachTarget } from "../../../products/attachTargets";

type HandoffPageProps = {
  params: Promise<{ handoffToken: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default function HandoffPage({ params, searchParams }: HandoffPageProps) {
  const { handoffToken } = use(params);
  const query = use(searchParams);
  // The page-load-wide client (see `getPlatformApiClient`), so a re-render that isn't a real
  // navigation never hands HandoffConsent a new instance and re-triggers its fetch effect.
  // Keyed on handoffToken so a token change always mounts a fresh HandoffConsent instance --
  // otherwise an in-flight accept/decline started under the old token could resolve after the
  // token changes and overwrite state with a stale result.
  return (
    <PortalIdentityBoundary requirePaid={query.paid === "1"}>{(client) => <LocaleProvider productMessages={HANDOFF_MESSAGES}>
      <HandoffConsent
        key={handoffToken}
        client={client}
        handoffToken={handoffToken}
        canOpenTarget={canAttachTarget}
      />
    </LocaleProvider>}</PortalIdentityBoundary>
  );
}
