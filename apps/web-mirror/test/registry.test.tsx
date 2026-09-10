import { describe, expect, it } from "vitest";
import { getProductDefinition } from "../src/products/registry";

describe("getProductDefinition", () => {
  it("returns the enabled ProposalAI definition", () => {
    const definition = getProductDefinition("proposal_ai");
    expect(definition?.productId).toBe("proposal_ai");
  });

  it("returns null for an unknown product id", () => {
    expect(getProductDefinition("does_not_exist")).toBeNull();
  });
});
