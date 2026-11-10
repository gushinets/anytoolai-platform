"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Card } from "@anytoolai/shared-ui";
import { LocaleProvider, useHostT } from "../i18n";
import { beginPortalAuthorization, completePortalAuthorization, readPortalContinuation } from "../lib/portalAuthorization";
import { synchronizePortalIdentity } from "../lib/portalSession";

export function PortalSessionFlow({ callback = false }: { callback?: boolean }) {
  return <LocaleProvider><Flow callback={callback} /></LocaleProvider>;
}

function Flow({ callback }: { callback: boolean }) {
  const t = useHostT();
  const [failed, setFailed] = useState(false);
  const operation = useRef<Promise<string> | null>(null);
  useEffect(() => {
    const synchronize = () => { synchronizePortalIdentity(); };
    window.addEventListener("pageshow", synchronize);
    window.addEventListener("focus", synchronize);
    return () => { window.removeEventListener("pageshow", synchronize); window.removeEventListener("focus", synchronize); };
  }, []);
  useEffect(() => {
    let active = true;
    if (!operation.current) {
      if (callback) {
        const fragment = window.location.hash;
        // Remove credentials before storage, networking, or any async boundary.
        window.history.replaceState(null, "", window.location.pathname);
        operation.current = completePortalAuthorization(fragment);
      } else {
        const params = new URLSearchParams(window.location.search);
        const target = params.getAll("return_to").length === 1 ? params.get("return_to") : readPortalContinuation();
        operation.current = target ? beginPortalAuthorization(target) : Promise.reject(new Error("portal_target_invalid"));
      }
    }
    void operation.current.then((url) => {
      if (active) window.location.replace(callback ? `${process.env.NEXT_PUBLIC_ANYTOOLAI_WEB_BASE_PATH ?? ""}${url}` : url);
    }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [callback]);
  return <main className="page-container"><Card>
    <h1>{t("portalSession.title")}</h1>
    <p role={failed ? "alert" : "status"}>{t(failed ? "portalSession.failed" : "portalSession.loading")}</p>
    {failed ? <Button onClick={() => {
      let target: string | null = null;
      try { target = readPortalContinuation(); } catch { /* Unreadable storage cannot supply a continuation. */ }
      if (target) window.location.replace(`${process.env.NEXT_PUBLIC_ANYTOOLAI_WEB_BASE_PATH ?? ""}/portal-session/launch`);
      else window.location.reload();
    }}>{t("portalSession.retry")}</Button> : null}
  </Card></main>;
}
