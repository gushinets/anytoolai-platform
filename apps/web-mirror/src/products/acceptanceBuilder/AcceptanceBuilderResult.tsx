"use client";

import { ResultView } from "../../components/ResultView";
import { useProductT } from "../../i18n";
import type { ProductResultProps } from "../runtime/productDefinition";
import styles from "./AcceptanceBuilderProduct.module.css";
import { composeCopyText, type AcceptanceBuilderResult } from "./parseAcceptanceBuilder";

/** Shows the copy-ready text itself (`renderer_contract.yaml` `copy_text`, fixed English, composed
 * from the structured fields only), so what the user reads is exactly what "Copy" puts on the
 * clipboard. Only the surrounding notes are localized. The model-written recap (`document`) is
 * display-only narrative: collapsed, and never copied. */
export function AcceptanceBuilderResultView({
  result,
  onCopy,
  secondaryAction,
}: ProductResultProps<AcceptanceBuilderResult>) {
  const t = useProductT();
  const { document } = result;
  return (
    <div className={styles.result}>
      {result.comparison ? <p className={styles.meta}>{t("result.verdictScope")}</p> : null}
      <details className={styles.section}>
        <summary>{t("result.recap")}</summary>
        <p>{document.summary}</p>
        {document.sections.map((section, index) => (
          <div key={index}>
            <div className={styles.label}>{section.title}</div>
            <div>{section.content}</div>
          </div>
        ))}
      </details>
      <ResultView text={composeCopyText(result)} onCopy={onCopy} secondaryAction={secondaryAction} embedded />
    </div>
  );
}
