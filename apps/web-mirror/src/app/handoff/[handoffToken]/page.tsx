"use client";

import { use, useMemo } from "react";
import { PlatformApiClient } from "@anytoolai/ce-kit";
import { HandoffConsent } from "../../../components/HandoffConsent";

type HandoffPageProps = {
  params: Promise<{ handoffToken: string }>;
};

export default function HandoffPage({ params }: HandoffPageProps) {
  const { handoffToken } = use(params);
  // Memoized so a re-render of HandoffPage that isn't a real navigation (e.g. a parent state
  // change) doesn't hand HandoffConsent a new client instance and re-trigger its fetch effect.
  const client = useMemo(
    () =>
      new PlatformApiClient({
        baseUrl: typeof window !== "undefined" ? window.location.origin : "http://localhost",
      }),
    [],
  );
  // Keyed on handoffToken so a token change always mounts a fresh HandoffConsent instance --
  // otherwise an in-flight accept/decline started under the old token could resolve after the
  // token changes and overwrite state with a stale result.
  return <HandoffConsent key={handoffToken} client={client} handoffToken={handoffToken} />;
}
