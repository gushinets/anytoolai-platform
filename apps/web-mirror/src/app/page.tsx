"use client";

import Link from "next/link";
import { Card } from "@anytoolai/shared-ui";
import { LanguageSwitcher, LocaleProvider, useLocale, useProductT } from "../i18n";
import { listRegisteredProducts } from "../products/registry";
import { HOME_MESSAGES } from "./homeMessages";
import styles from "./page.module.css";

// Which registered products have directory copy in `homeMessages` (`cards.<productId>`), and which
// of them list mode chips (`cards.<productId>.tags.<key>`). A product missing here is listed by
// name only.
const CARD_TAGS: Record<string, readonly string[]> = {
  proposal_ai: [],
  client_update_writer: ["update", "replyDraft", "prepaidRequest"],
  brief_decoder: [],
};

export default function HomePage() {
  return (
    <LocaleProvider productMessages={HOME_MESSAGES}>
      <HomeContent />
    </LocaleProvider>
  );
}

function HomeContent() {
  const t = useProductT();
  const { locale } = useLocale();
  const products = listRegisteredProducts().filter((product) => product.enabled);
  return (
    <main className={`page-container ${styles.page}`}>
      <header className={styles.top}>
        <div className={styles.hero}>
          <h1 className={styles.title}>{t("title")}</h1>
          <p className={styles.lead}>{t("lead")}</p>
        </div>
        <LanguageSwitcher />
      </header>
      <ul className={styles.grid}>
        {products.map((product) => {
          const tags = CARD_TAGS[product.productId];
          return (
            <li key={product.productId} className={styles.item}>
              <Card className={styles.card}>
                <h2 className={styles.name}>
                  <Link className={styles.link} href={`/products/${product.productId}`}>
                    {product.messages[locale].title}
                  </Link>
                </h2>
                {tags ? <p className={styles.blurb}>{t(`cards.${product.productId}.blurb`)}</p> : null}
                {tags?.length ? (
                  <ul className={styles.tags}>
                    {tags.map((tag) => (
                      <li key={tag} className={styles.tag}>
                        {t(`cards.${product.productId}.tags.${tag}`)}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {tags ? (
                  <p className={styles.sample}>{t(`cards.${product.productId}.sample`)}</p>
                ) : null}
                {/* Hidden from assistive tech only because the heading link already says it. */}
                <span className={styles.cta} aria-hidden="true">
                  {t("open")}
                </span>
              </Card>
            </li>
          );
        })}
      </ul>
    </main>
  );
}
