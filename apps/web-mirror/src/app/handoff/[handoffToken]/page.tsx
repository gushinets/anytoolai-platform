"use client";

import { use } from "react";
import { getPlatformApiClient } from "../../../lib/apiClient";
import { HandoffConsent } from "../../../components/HandoffConsent";
import { HANDOFF_MESSAGES } from "../../../components/handoffMessages";
import { LocaleProvider } from "../../../i18n";

type HandoffPageProps = {
  params: Promise<{ handoffToken: string }>;
};

export default function HandoffPage({ params }: HandoffPageProps) {
  const { handoffToken } = use(params);
  // The page-load-wide client (see `getPlatformApiClient`), so a re-render that isn't a real
  // navigation never hands HandoffConsent a new instance and re-triggers its fetch effect.
  const client = getPlatformApiClient();
  // Keyed on handoffToken so a token change always mounts a fresh HandoffConsent instance --
  // otherwise an in-flight accept/decline started under the old token could resolve after the
  // token changes and overwrite state with a stale result.
  return (
    <LocaleProvider productMessages={HANDOFF_MESSAGES}>
      <HandoffConsent key={handoffToken} client={client} handoffToken={handoffToken} />
    </LocaleProvider>
  );
}
