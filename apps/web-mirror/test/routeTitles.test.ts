// Every route has a title of its own, so browser tabs and page-title navigation tell pages apart.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { metadata as handoffMetadata } from "../src/app/handoff/[handoffToken]/layout";
import { metadata as notFoundMetadata } from "../src/app/not-found";
import { metadata as onboardingMetadata } from "../src/app/onboarding/[productId]/page";
import { metadata as paywallMetadata } from "../src/app/paywall/[productId]/page";
import { generateMetadata as productMetadata } from "../src/app/products/[productId]/layout";
import { metadata as resultMetadata } from "../src/app/r/[artifactId]/page";

describe("route titles", () => {
  it("adds each route's own segment to the site name", () => {
    // layout.tsx wires next/font, which cannot load under vitest, so its title is read as text.
    expect(readFileSync("src/app/layout.tsx", "utf-8")).toContain(
      'title: { default: "AnytoolAI", template: "%s · AnytoolAI" }',
    );
    expect([handoffMetadata, notFoundMetadata, onboardingMetadata, paywallMetadata, resultMetadata].map((m) => m.title)).toEqual([
      "Review handoff",
      "Page not found",
      "Onboarding",
      "Paywall",
      "Result",
    ]);
  });

  it("titles a product page with the product's name and gives an unknown product the 404 title", async () => {
    expect(await productMetadata({ params: Promise.resolve({ productId: "proposal_ai" }) })).toEqual({ title: "ProposalAI" });
    expect(await productMetadata({ params: Promise.resolve({ productId: "client_update_writer" }) })).toEqual({
      title: "Client Update Writer",
    });
    expect(await productMetadata({ params: Promise.resolve({ productId: "nope" }) })).toEqual({ title: "Page not found" });
  });
});
