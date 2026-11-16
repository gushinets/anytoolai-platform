"use client";

import { useHostT } from "../i18n";
import { privacyPolicyUrl } from "../lib/legalUrls";
import styles from "./DataProcessingNotice.module.css";

export const DATA_NOTICE_ID = "product-data-notice";

export function DataProcessingNotice() {
  const th = useHostT();
  const url = privacyPolicyUrl();
  return (
    <p id={DATA_NOTICE_ID} className={styles.notice} data-testid="data-processing-notice">
      <strong className={styles.label}>{th("dataNotice.label")}</strong>{" "}
      <span>{th("dataNotice.text")}</span>
      {url ? (
        <span className={styles.linkWrap}>
          <a className={styles.link} href={url} target="_blank" rel="noopener noreferrer">
            <span>{th("dataNotice.policyLink")}</span>
            <span className={styles.srOnly}>{th("dataNotice.opensInNewTab")}</span>
          </a>
        </span>
      ) : null}
    </p>
  );
}
