import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Card } from "../src/Card";

afterEach(() => {
  cleanup();
});

describe("Card", () => {
  it("renders its children inside a glass surface container", () => {
    render(<Card>Result text</Card>);
    expect(screen.getByText("Result text")).toBeTruthy();
  });
});
