import type { ChangeEvent } from "react";
import { FieldErrorMessage } from "../../src/components/FieldErrorMessage";
import { ResultView } from "../../src/components/ResultView";
import { useProductT } from "../../src/i18n";
import type { ProductDefinition, ProductFieldsProps } from "../../src/products/runtime/productDefinition";

/** The test-only product's English messages (product-owned in a real product). */
export const TEST_PRODUCT_MESSAGES_EN = {
  title: "Test Product",
  quotaRemaining: "{remaining} of {limit} runs remaining.",
  fields: { text: "Text" },
  run: { submit: "Run", running: "Running…", runFailed: "Something went wrong. Please try again." },
};

export type TestProductValues = { text: string };

export const TEST_PRODUCT_IDS = { productId: "test_product", scenarioId: "test_product.run_v1" } as const;

function TestProductFields({ values, errors, disabled, onChange }: ProductFieldsProps<TestProductValues>) {
  const t = useProductT();
  return (
    <>
      <label htmlFor="test-product-text">{t("fields.text")}</label>
      <textarea
        id="test-product-text"
        value={values.text}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("text", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.text)}
        aria-describedby={errors.text ? "test-product-text-help test-product-text-error" : "test-product-text-help"}
      />
      <p id="test-product-text-help">Enter the text to process.</p>
      {errors.text ? (
        <p id="test-product-text-error" role="alert">
          {errors.text}
        </p>
      ) : null}
    </>
  );
}

/**
 * The minimal test-only product definition ANY-453's acceptance criteria call for: the shared
 * runtime suite runs against this, so it proves the runtime with no real product's meaning in
 * the loop. Deliberately not registered in `src/products/registry.ts` (registry.test.tsx proves
 * that) -- it must never become a production product.
 */
export const testProductDefinition: ProductDefinition<TestProductValues, string> = {
  productId: TEST_PRODUCT_IDS.productId,
  scenarioId: TEST_PRODUCT_IDS.scenarioId,
  messageScope: "run",
  emptyValues: { text: "" },
  validate: (values) => (values.text.trim().length === 0 ? { text: { code: "required" } } : {}),
  toInput: (values) => ({ text: values.text }),
  extractResult: (output) => (typeof output.text === "string" ? output.text : null),
  Fields: TestProductFields,
  Result: ({ result, onCopy }) => <ResultView text={result} onCopy={onCopy} />,
  copy: {
    description: "Describe the test run.",
    submit: "Run",
    startAnother: "Start another run",
    running: "Running…",
    runFailed: "Something went wrong. Please try again.",
    quotaRemaining: (remaining, limit) => `${remaining} of ${limit} runs remaining.`,
  },
};
