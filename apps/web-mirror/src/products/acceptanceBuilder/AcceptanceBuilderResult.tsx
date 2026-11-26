"use client";

import { ResultView } from "../../components/ResultView";
import { useProductT } from "../../i18n";
import type { ProductResultProps } from "../runtime/productDefinition";
import styles from "./AcceptanceBuilderProduct.module.css";
import { composeCopyText, type AcceptanceBuilderResult } from "./parseAcceptanceBuilder";

/** Recap and Copy are projections of the same structured authority and analysis language.
 * Independent model-written documents are never displayed or copied. */
export function AcceptanceBuilderResultView({
  result,
  onCopy,
  secondaryAction,
}: ProductResultProps<AcceptanceBuilderResult>) {
  const t = useProductT();
  const { check, sections, summary } = result.document;
  return (
    <div className={styles.result}>
      {check ? (
        <>
          <p className={styles.label} lang={result.analysisLanguage}>{summary}</p>
          {check.findings.length > 0 ? (
            <ul className={styles.findings} lang={result.analysisLanguage}>
              {check.findings.map((line) => <li key={line}>{line}</li>)}
            </ul>
          ) : null}
          <p className={styles.meta}>{t("result.verdictScope")}</p>
        </>
      ) : null}
      <details className={styles.section}>
        <summary>{t("result.recap")}</summary>
        {check ? (
          <div className={styles.section} lang={result.analysisLanguage}>
            {check.evidence.map((line) => <p key={line} className={styles.content}>{line}</p>)}
            {check.rationale ? <p className={styles.content}>{check.rationale}</p> : null}
          </div>
        ) : <p className={styles.content}>{summary}</p>}
        {sections.map((section, index) => (
          <div key={index}>
            <div className={styles.label}>{section.title}</div>
            <div className={styles.content}>{section.content}</div>
          </div>
        ))}
      </details>
      <ResultView text={composeCopyText(result)} onCopy={onCopy} secondaryAction={secondaryAction} embedded hideText={Boolean(check)} />
    </div>
  );
}
