"use client";

import { Card } from "@anytoolai/shared-ui";
import { ResultView } from "../../components/ResultView";
import { useProductT } from "../../i18n";
import type { ProductResultProps } from "../runtime/productDefinition";
import styles from "./BriefDecoderProduct.module.css";
import { BRIEF_FIELDS, composeCopyText, type BriefDecoderResult } from "./parseBriefDecoder";

/** The four contract parts in `renderer_contract.yaml` order. Severity and priority are text
 * labels, never colour alone; `brief.confidence` is deliberately not shown. */
export function BriefDecoderResultView({ result, onCopy }: ProductResultProps<BriefDecoderResult>) {
  const t = useProductT();
  const { brief, issues, questions, document } = result;
  return (
    <div className={styles.result}>
      <Card>
        <section className={styles.section} aria-labelledby="brief-decoder-brief-heading">
          <h2 id="brief-decoder-brief-heading">{t("result.brief")}</h2>
          <dl>
            {BRIEF_FIELDS.map((field) => {
              const value = brief.values[field];
              return (
                <div key={field}>
                  <dt className={styles.label}>{t(`briefFields.${field}`)}</dt>
                  <dd>
                    {value === undefined ? (
                      <span className={styles.meta}>{t("result.notProvided")}</span>
                    ) : Array.isArray(value) ? (
                      <ul className={styles.list}>
                        {value.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    ) : (
                      value
                    )}
                  </dd>
                </div>
              );
            })}
          </dl>
        </section>
      </Card>

      <Card>
        <section className={styles.section} aria-labelledby="brief-decoder-issues-heading">
          <h2 id="brief-decoder-issues-heading">{t("result.issues")}</h2>
          {issues.length === 0 ? (
            <p>{t("result.noIssues")}</p>
          ) : (
            <ul className={styles.list}>
              {issues.map((issue, index) => (
                <li key={index}>
                  <span className={styles.label}>
                    {t(`categories.${issue.category}`)} · {t(`severity.${issue.severity}`)}
                  </span>
                  <div>{issue.description}</div>
                  {issue.evidence ? (
                    <div className={styles.meta}>
                      {t("result.evidence", { text: issue.evidence })}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      </Card>

      <Card>
        <section className={styles.section} aria-labelledby="brief-decoder-questions-heading">
          <h2 id="brief-decoder-questions-heading">{t("result.questions", { count: questions.length })}</h2>
          {questions.length === 0 ? (
            <p>{t("result.noQuestions")}</p>
          ) : (
            <ol className={styles.list}>
              {questions.map((question, index) => (
                <li key={index}>
                  <div className={styles.label}>{question.question}</div>
                  <div className={styles.meta}>
                    {t("result.rationale", { text: question.rationale })} · {t(`categories.${question.category}`)} ·{" "}
                    {t(`priority.${question.priority}`)}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </Card>

      <section className={styles.section} aria-labelledby="brief-decoder-document-heading">
        <h2 id="brief-decoder-document-heading">{t("result.document")}</h2>
        <ResultView text={composeCopyText(document)} onCopy={onCopy} />
      </section>
    </div>
  );
}
