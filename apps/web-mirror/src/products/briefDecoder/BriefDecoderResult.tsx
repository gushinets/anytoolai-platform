"use client";

import { ResultView } from "../../components/ResultView";
import { useProductT } from "../../i18n";
import type { ProductResultProps } from "../runtime/productDefinition";
import styles from "./BriefDecoderProduct.module.css";
import { BRIEF_FIELDS, composeCopyText, composeQuestionsCopyText, type BriefDecoderResult } from "./parseBriefDecoder";

/** The four contract parts in `renderer_contract.yaml` order, embedded in the workspace's result
 * card (whose `h2` they sit under, hence `h3`) and separated by rules, not nested cards. Severity
 * and priority are text labels, never colour alone; `brief.confidence` is deliberately not shown.
 * Copy uses structured fields only; the model-written document is display only (ANY-616). */
export function BriefDecoderResultView({ result, onCopy, secondaryAction }: ProductResultProps<BriefDecoderResult>) {
  const t = useProductT();
  const { brief, issues, questions, document } = result;
  const questionsText = composeQuestionsCopyText(questions);
  return (
    <div className={styles.result}>
      <section className={styles.section} aria-labelledby="brief-decoder-brief-heading">
        <h3 id="brief-decoder-brief-heading">{t("result.brief")}</h3>
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

      <section className={styles.section} aria-labelledby="brief-decoder-issues-heading">
        <h3 id="brief-decoder-issues-heading">{t("result.issues")}</h3>
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

      <section className={styles.section} aria-labelledby="brief-decoder-questions-heading">
        <h3 id="brief-decoder-questions-heading">{t("result.questions", { count: questions.length })}</h3>
        {questionsText ? (
          <ResultView
            text={questionsText}
            onCopy={onCopy}
            copyLabels={{ idle: t("copy.questions"), copied: t("copy.questionsCopied") }}
            embedded
            hideText
          />
        ) : null}
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

      <section className={styles.section} aria-labelledby="brief-decoder-document-heading">
        <h3 id="brief-decoder-document-heading">{t("result.document")}</h3>
        {document.sections.map((section, index) => (
          <div key={index}>
            <div className={styles.label}>{section.title}</div>
            <div className={styles.content}>{section.content}</div>
          </div>
        ))}
        <p className={styles.content}>{document.summary}</p>
      </section>
      <p className={styles.meta}>{t("copy.hint")}</p>
      <ResultView text={composeCopyText(result, t)} onCopy={onCopy} secondaryAction={secondaryAction} embedded hideText />
    </div>
  );
}
