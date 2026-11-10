"use client";

import { ResultView } from "../../components/ResultView";
import { useProductT } from "../../i18n";
import type { ProductResultProps } from "../runtime/productDefinition";
import { composeDocument } from "./presentation";
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
  const document = composeDocument(result);
  return (
    <div className={styles.result}>
      {result.comparison ? <p className={styles.meta}>{t("result.verdictScope")}</p> : null}
      <details className={styles.section}>
        <summary>{t("result.recap")}</summary>
        <p className={styles.content}>{document.summary}</p>
        {document.sections.map((section, index) => (
          <div key={index}>
            <div className={styles.label}>{section.title}</div>
            <div className={styles.content}>{section.content}</div>
          </div>
        ))}
      </details>
      <ResultView text={composeCopyText(result)} onCopy={onCopy} secondaryAction={secondaryAction} embedded />
    </div>
  );
}
