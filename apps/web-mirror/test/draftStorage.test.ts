import { afterEach, describe, expect, it, vi } from "vitest";
import { clearProductDraft, productDraftKey, readProductDraft, saveDraftRun, saveDraftValues, readProductDraftScenario, saveProductDraftScenario } from "../src/products/runtime/draftStorage";

const key = productDraftKey("proposal_ai", "generate");
const run = { scenarioSessionId: "session_1", input: { text: "accepted input" } };

afterEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
});

describe("tab draft storage", () => {
  it("keeps the selected scenario separate for each product", () => {
    expect(readProductDraftScenario("client_update_writer")).toBeUndefined();
    saveProductDraftScenario("client_update_writer", "client_update_writer.reply_draft_v1");
    saveProductDraftScenario("proposal_ai", "proposal_ai.generate_v1");
    expect(readProductDraftScenario("client_update_writer")).toBe("client_update_writer.reply_draft_v1");
    expect(readProductDraftScenario("proposal_ai")).toBe("proposal_ai.generate_v1");
  });

  it("scopes keys by product and mode", () => {
    expect(key).toBe("anytoolai.product_draft.proposal_ai.generate");
    expect(productDraftKey("proposal_ai", "other")).not.toBe(key);
    expect(productDraftKey("other", "generate")).not.toBe(key);
  });

  it("round trips values and run independently, and clears both", () => {
    expect(readProductDraft(key)).toBeUndefined();
    saveDraftValues(key, { text: "draft" });
    saveDraftRun(key, run);
    expect(readProductDraft(key)).toEqual({ values: { text: "draft" }, run });
    saveDraftValues(key, { text: "edited" });
    expect(readProductDraft(key)).toEqual({ values: { text: "edited" }, run });
    saveDraftRun(key, null);
    expect(readProductDraft(key)).toEqual({ values: { text: "edited" } });
    clearProductDraft(key);
    expect(readProductDraft(key)).toBeUndefined();
    saveDraftRun(key, run);
    saveDraftRun(key, null);
    expect(window.sessionStorage.getItem(key)).toBeNull();
  });

  it.each(["{", "null", "5", '[]', '{"v":2}', '{"values":{}}'])("ignores invalid envelope %s", (raw) => {
    window.sessionStorage.setItem(key, raw);
    expect(readProductDraft(key)).toBeUndefined();
  });

  it.each([null, {}, { scenarioSessionId: "" }, { scenarioSessionId: 5 }])("ignores invalid run %j and retains values", (invalid) => {
    window.sessionStorage.setItem(key, JSON.stringify({ v: 1, values: "draft", run: invalid }));
    expect(readProductDraft(key)).toEqual({ values: "draft" });
  });

  it.each(["getItem", "setItem", "removeItem"] as const)("survives throwing %s", (method) => {
    vi.spyOn(Storage.prototype, method).mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
    expect(() => {
      readProductDraft(key);
      saveDraftValues(key, { text: "draft" });
      saveDraftRun(key, run);
      clearProductDraft(key);
      readProductDraftScenario("client_update_writer");
      saveProductDraftScenario("client_update_writer", "client_update_writer.reply_draft_v1");
    }).not.toThrow();
  });

  it("survives a throwing storage getter and unserializable values", () => {
    const circular: Record<string, unknown> = {};
    circular.self = circular;
    expect(() => saveDraftValues(key, circular)).not.toThrow();
    vi.spyOn(window, "sessionStorage", "get").mockImplementation(() => { throw new Error("blocked"); });
    expect(readProductDraft(key)).toBeUndefined();
    expect(() => {
      saveDraftValues(key, {});
      saveDraftRun(key, run);
      clearProductDraft(key);
      readProductDraftScenario("client_update_writer");
      saveProductDraftScenario("client_update_writer", "client_update_writer.reply_draft_v1");
    }).not.toThrow();
  });
});
