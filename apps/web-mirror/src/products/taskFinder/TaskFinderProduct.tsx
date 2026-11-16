"use client";

import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { useProductT } from "../../i18n";
import { ProductRunPage } from "../runtime/ProductRunPage";
import { collectFieldErrors, requiredBackendTrimmedFieldError, trimBackendWhitespace } from "../runtime/fieldValidation";
import type { ProductDefinition, ProductFieldsProps, ProductRunEvent } from "../runtime/productDefinition";
import { TextAreaField } from "../shared/TextAreaField";
import { TaskFinderResultView } from "./TaskFinderResult";
import { parseTaskFinder, type TaskFinderResult } from "./parseTaskFinder";

const TEXT_MAX_LENGTH = 4000;
type Values = { taskText: string; positioning: string };

function Fields({ values, errors, disabled, onChange }: ProductFieldsProps<Values>) {
  const t = useProductT();
  return (
    <>
      <TextAreaField
        id="task-finder-task-text"
        label={t("fields.taskText")}
        placeholder={t("fields.taskTextPlaceholder")}
        help={t("fields.taskTextHelp")}
        value={values.taskText}
        error={errors.taskText}
        disabled={disabled}
        onChange={(value) => onChange("taskText", value)}
      />
      <TextAreaField
        id="task-finder-positioning"
        label={t("fields.positioning")}
        placeholder={t("fields.positioningPlaceholder")}
        help={t("fields.positioningHelp")}
        value={values.positioning}
        error={errors.positioning}
        disabled={disabled}
        onChange={(value) => onChange("positioning", value)}
      />
    </>
  );
}

export const taskFinderDefinition: ProductDefinition<Values, TaskFinderResult> = {
  productId: "task_finder",
  scenarioId: "task_finder.fit_v1",
  outputSchema: { schemaRef: "task_finder.fit_output_v1", schemaVersion: 1 },
  messageScope: "fit",
  hasDescription: true,
  emptyValues: { taskText: "", positioning: "" },
  validate: (values) => collectFieldErrors<Values>([
    ["taskText", requiredBackendTrimmedFieldError(values.taskText, TEXT_MAX_LENGTH)],
    ["positioning", requiredBackendTrimmedFieldError(values.positioning, TEXT_MAX_LENGTH)],
  ]),
  toInput: (values) => ({
    task_text: trimBackendWhitespace(values.taskText),
    freelancer_positioning: trimBackendWhitespace(values.positioning),
  }),
  extractResult: parseTaskFinder,
  Fields,
  Result: TaskFinderResultView,
};

export function TaskFinderProduct(props: { client: PlatformApiClient; onEvent?: (event: ProductRunEvent) => void; visitId?: string }) {
  return <ProductRunPage definition={taskFinderDefinition} {...props} />;
}
