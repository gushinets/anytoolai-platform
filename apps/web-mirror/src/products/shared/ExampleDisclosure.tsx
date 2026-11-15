"use client";

import { useHostT } from "../../i18n";
import styles from "./ExampleDisclosure.module.css";

export type ExampleItem = { label: string; value: string };

// Static content keeps opening the example independent of form values and draft storage.
export function ExampleDisclosure({ intro, items, output }: { intro: string; items: readonly ExampleItem[]; output: string }) {
  const th = useHostT();
  return (
    <details className={styles.details} data-testid="first-run-example">
      <summary className={styles.summary}>{th("example.toggle")}</summary>
      <div className={styles.body}>
        <p className={styles.intro}>{intro}</p>
        <h3 className={styles.heading}>{th("example.inputs")}</h3>
        <dl className={styles.items}>
          {items.map((item) => (
            <div key={item.label} className={styles.item}>
              <dt className={styles.label}>{item.label}</dt>
              <dd className={styles.value}>{item.value}</dd>
            </div>
          ))}
        </dl>
        <h3 className={styles.heading}>{th("example.output")}</h3>
        <p className={styles.output}>{output}</p>
        <p className={styles.note}>{th("example.note")}</p>
      </div>
    </details>
  );
}
