import { within } from "@testing-library/react";
import { expect } from "vitest";

export function expectDataProcessingNotice(form: HTMLElement, policyUrl: string) {
  expect(within(form).getByText("Data processing.")).toBeTruthy();
  expect(within(form).getByRole("link", { name: /Privacy policy/ }).getAttribute("href")).toBe(policyUrl);
}
