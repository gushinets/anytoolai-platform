// Drift guard between the web copy text and `renderer_contract.yaml` (the backend product's pinned
// copy contract): the machine-readable fields are compared field by field, and the wording that only
// exists in the contract's prose is checked as required phrases. A contract edit that the web copy
// does not follow fails here instead of shipping stale text to clients.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  ALL_STATED,
  DELTA_CRITERIA,
  DELTA_LABELS,
  GAP_NAMES,
  LIST_FIELDS,
  LIST_TITLES,
  NOT_SPECIFIED,
  VERDICT_WORDS,
  VERDICTS,
} from "../src/products/acceptanceBuilder/parseAcceptanceBuilder";

const CONTRACT = readFileSync(
  resolve(
    dirname(fileURLToPath(import.meta.url)),
    "../../../packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/acceptance_builder/renderer_contract.yaml",
  ),
  "utf8",
);

type Block = { id: string; title?: string; whenAbsent?: string; whenEmpty?: string; scenarios?: string };

/** The `copy_text.blocks` entries, read with one regex per scalar field (no YAML dependency). */
function copyBlocks(): Block[] {
  const section = CONTRACT.slice(CONTRACT.indexOf("copy_text:"));
  return section
    .split(/\n {6}- block_id: /)
    .slice(1)
    .map((entry) => {
      const field = (name: string) => new RegExp(`^ {8}${name}: (.+)$`, "m").exec(entry)?.[1]?.trim();
      return {
        id: entry.split("\n")[0]!.trim(),
        title: field("title"),
        whenAbsent: field("when_absent"),
        whenEmpty: field("when_empty"),
        scenarios: field("scenarios"),
      };
    });
}

const prose = CONTRACT.replace(/\s+/g, " ");

describe("renderer_contract.yaml copy contract vs the web copy text", () => {
  const blocks = copyBlocks();

  it("has the blocks in the order the renderer composes them, with the same titles", () => {
    expect(blocks.map((b) => b.id)).toEqual(["verdict", "acceptance_criteria", "assumptions", "deliverables", "open_gaps"]);
    expect(blocks[0]!.title).toBe("Verdict");
    for (const field of LIST_FIELDS) {
      expect(blocks.find((b) => b.id === field)?.title).toBe(LIST_TITLES[field]);
    }
    expect(blocks.at(-1)!.title).toBe("Open gaps");
  });

  it("applies the verdict block to check_v1 only (the renderer composes it only when a comparison exists)", () => {
    expect(blocks[0]!.scenarios).toBe("[acceptance_builder.check_v1]");
    for (const block of blocks.slice(1)) {
      expect(block.scenarios).toBeUndefined();
    }
  });

  it("uses the contract's fallbacks for an absent list and an empty gap list", () => {
    for (const field of LIST_FIELDS) {
      expect(blocks.find((b) => b.id === field)?.whenAbsent).toBe(NOT_SPECIFIED);
    }
    expect(blocks.find((b) => b.id === "open_gaps")?.whenEmpty).toBe(ALL_STATED);
  });

  it("keeps copy_result as the next action the shared runtime records", () => {
    expect(/^ {2}next_action: (.+)$/m.exec(CONTRACT)?.[1]).toBe("copy_result");
  });

  it("names the verdict words, delta labels and gap wording the contract prose requires", () => {
    expect(prose).toContain([...VERDICTS].map((v) => VERDICT_WORDS[v]).join(" | "));
    expect(prose).toContain(`labels ${DELTA_CRITERIA.map((c) => DELTA_LABELS[c]).join(", ")}`);
    expect(prose).toContain(
      `as "${LIST_FIELDS.map((f) => GAP_NAMES[f]).slice(0, 2).map((n) => n).join('", "')}" or "${GAP_NAMES.deliverables}"`,
    );
    expect(prose).toContain('"- <name>: the client should confirm it."');
    expect(prose).toContain('"<Label>: <status>. <evidence>"');
    expect(prose).toContain('"Verdict: " followed by the verdict in words');
  });
});
