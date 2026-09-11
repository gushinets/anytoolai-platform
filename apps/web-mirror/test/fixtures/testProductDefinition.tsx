import type { ChangeEvent } from "react";
import { ResultView } from "../../src/components/ResultView";
import type { ProductDefinition, ProductFieldsProps } from "../../src/products/runtime/productDefinition";

export type TestProductValues = { text: string };

export const TEST_PRODUCT_IDS = { productId: "test_product", scenarioId: "test_product.run_v1" } as const;

function TestProductFields({ values, errors, disabled, onChange }: ProductFieldsProps<TestProductValues>) {
  return (
    <>
      <label htmlFor="test-product-text">Text</label>
      <textarea
        id="test-product-text"
        value={values.text}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("text", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.text)}
      />
      {errors.text ? <p role="alert">{errors.text}</p> : null}
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
  title: "Test Product",
  emptyValues: { text: "" },
  validate: (values) => (values.text.trim().length === 0 ? { text: "Text is required." } : {}),
  toInput: (values) => ({ text: values.text }),
  extractResult: (output) => (typeof output.text === "string" ? output.text : null),
  copyNextActionId: "copy_result",
  Fields: TestProductFields,
  Result: ({ result, onCopied }) => <ResultView text={result} onCopied={onCopied} />,
  copy: {
    submit: "Run",
    running: "Running…",
    runFailed: "Something went wrong. Please try again.",
    quotaRemaining: (remaining, limit) => `${remaining} of ${limit} runs remaining.`,
  },
};
