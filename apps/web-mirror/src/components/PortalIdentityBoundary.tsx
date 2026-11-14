"use client";

import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { Button, Card } from "@anytoolai/shared-ui";
import { LocaleProvider, useHostT } from "../i18n";
import { getPlatformApiClient } from "../lib/apiClient";
import { rememberPortalContinuation } from "../lib/portalAuthorization";
import { getPortalIdentity, requirePortalAuthorization, subscribePortalIdentity, synchronizePortalIdentity } from "../lib/portalSession";

export function PortalIdentityBoundary({ children, requirePaid = false }: { children: (client: PlatformApiClient) => ReactNode; requirePaid?: boolean }) {
  const identity = useSyncExternalStore(subscribePortalIdentity, getPortalIdentity, () => null);
  useEffect(() => {
    if (requirePaid && identity?.kind === "guest") requirePortalAuthorization();
  }, [requirePaid, identity]);
  useEffect(() => {
    const synchronize = () => { synchronizePortalIdentity(); };
    window.addEventListener("pageshow", synchronize);
    window.addEventListener("focus", synchronize);
    return () => { window.removeEventListener("pageshow", synchronize); window.removeEventListener("focus", synchronize); };
  }, []);
  useEffect(() => {
    if (identity?.kind !== "authorized") return;
    const timer = window.setTimeout(() => { synchronizePortalIdentity(); }, Math.max(0, Date.parse(identity.session.expiresAt) - Date.now()));
    return () => { clearTimeout(timer); };
  }, [identity]);
  if (!identity) return null;
  if (identity.kind === "required" || (requirePaid && identity.kind === "guest") || (identity.kind === "authorized" && Date.parse(identity.session.expiresAt) <= Date.now())) {
    return <LocaleProvider><PortalAuthorizationRequired /></LocaleProvider>;
  }
  return <div key={identity.generation}>
    {children(getPlatformApiClient())}
    {identity.kind === "authorized" ? <LocaleProvider><PortalLogout /></LocaleProvider> : null}
  </div>;
}

function PortalAuthorizationRequired() {
  const t = useHostT();
  const [failed, setFailed] = useState(false);
  return <main className="page-container"><Card>
    <h1>{t("portalSession.title")}</h1>
    <p role="status">{t("portalSession.required")}</p>
    <Button onClick={() => {
      try {
        const base = process.env.NEXT_PUBLIC_ANYTOOLAI_WEB_BASE_PATH ?? "";
        const target = window.location.pathname.slice(base.length) + window.location.search;
        rememberPortalContinuation(target);
        window.location.assign(`${base}/portal-session/launch`);
      } catch { setFailed(true); }
    }}>{t("portalSession.continue")}</Button>
    {failed ? <p role="alert">{t("portalSession.failed")}</p> : null}
  </Card></main>;
}

function PortalLogout() {
  const t = useHostT();
  return <div className="page-container"><Button variant="secondary" onClick={() => requirePortalAuthorization(true)}>{t("portalSession.signOut")}</Button></div>;
}
