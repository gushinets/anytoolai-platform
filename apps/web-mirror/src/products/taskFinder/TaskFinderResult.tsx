"use client";

import { ResultView } from "../../components/ResultView";
import { useProductT } from "../../i18n";
import type { ProductResultProps } from "../runtime/productDefinition";
import { composeCopyText, type TaskFinderResult } from "./parseTaskFinder";
import styles from "./TaskFinderProduct.module.css";

export function TaskFinderResultView({ result, onCopy, secondaryAction }: ProductResultProps<TaskFinderResult>) {
  const t = useProductT();
  return <div className={styles.result}>
    <section className={styles.section}>
      <h3>{t("result.fitScore")}</h3>
      <p className={styles.score}>{result.score} / 100</p>
      <meter min={0} max={100} value={result.score} aria-hidden="true" />
    </section>
    <section className={styles.section}>
      <h3>{t("result.verdict")}</h3>
      <p>{t(`verdicts.${result.verdict}`)}</p>
      <p className={styles.meta}>{t("result.verdictScope")}</p>
    </section>
    <section className={styles.section}>
      <h3>{t("result.criteriaComparison")}</h3>
      <ul className={styles.list}>{result.deltas.map((delta) => <li key={delta.criterionId}>
        <strong>{t(`criteria.${delta.criterionId}`)}: {t(`statuses.${delta.status}`)}.</strong> {delta.evidence}
      </li>)}</ul>
    </section>
    <section className={styles.section}>
      <h3>{t("result.criterionScores")}</h3>
      <ul className={styles.list}>{result.criterionScores.map((entry) => <li key={entry.criterionId}>
        <strong>{t(`criteria.${entry.criterionId}`)}: {entry.score}/100.</strong> {entry.rationale}
      </li>)}</ul>
    </section>
    {(["strengths", "gaps"] as const).map((field) => <section className={styles.section} key={field}>
      <h3>{t(`result.${field}`)}</h3>
      {result[field].length ? <ul className={styles.list}>{result[field].map((item, index) => <li key={index}>{item}</li>)}</ul>
        : <p>{t("result.notSpecified")}</p>}
    </section>)}
    <section className={styles.section}><h3>{t("result.rationale")}</h3><p>{result.rationale}</p></section>
    <section className={styles.section}><h3>{t("result.scoreRationale")}</h3><p>{result.scoreRationale}</p></section>
    <ResultView text={composeCopyText(result)} onCopy={onCopy} secondaryAction={secondaryAction} embedded hideText />
  </div>;
}
