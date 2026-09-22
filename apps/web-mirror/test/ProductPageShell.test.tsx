// The host-level locale behavior a user sees on `/products/{productId}`: one selector for every
// registered product, locale resolution/persistence, and -- the point of the ticket -- UI locale
// staying independent of scenario input (incl. the output-language field) and of form/run state.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LOCALES, type Locale } from "../src/i18n";
import { LOCALE_STORAGE_KEY, resetUnpersistedLocaleForTests } from "../src/i18n/localeStorage";
import { HOST_MESSAGES } from "../src/i18n/messages";
import { CLIENT_UPDATE_WRITER_MESSAGES } from "../src/products/clientUpdateWriter/messages";
import { ProductPageShell } from "../src/products/ProductPageShell";
import { PROPOSAL_AI_MESSAGES } from "../src/products/proposalAi/messages";
import { getRegisteredProduct, type RegisteredProduct } from "../src/products/registry";
import { ProductRunPage } from "../src/products/runtime/ProductRunPage";
import {
  errorResponse,
  type CapturedCall,
  guestIdentityResponse,
  makeClientCapturingRequests,
  quotaResponse,
  resultResponse,
  routesFor,
  runtimeConfigResponse,
  sessionResponse,
  startResponse,
  type RouteQueues,
} from "./fixtures/platformResponses";
import { TEST_PRODUCT_IDS, TEST_PRODUCT_MESSAGES_EN, testProductDefinition } from "./fixtures/testProductDefinition";
import { englishForAllLocales } from "./support/renderWithI18n";

const PROPOSAL_IDS = { productId: "proposal_ai", scenarioId: "proposal_ai.generate_v1" } as const;
const CUW_IDS = { productId: "client_update_writer", scenarioId: "client_update_writer.update_v1" } as const;

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.restoreAllMocks();
  document.documentElement.lang = "";
});

beforeEach(() => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(() => Promise.resolve()) },
  });
});

// Enough queued boot responses for a Client Update Writer test that mounts a fresh ProductRunPage
// per mode switch (a response body can only be read once, hence factories).
const MOUNTS = 4;
const times = <T,>(make: () => T): Array<() => T> => Array.from({ length: MOUNTS }, () => make);

// Client Update Writer runs one scenario per mode, so its runtime config must list all three.
const CUW_SCENARIO_IDS = [
  "client_update_writer.update_v1",
  "client_update_writer.reply_draft_v1",
  "client_update_writer.prepaid_request_v1",
];
function runtimeConfigFor(ids: typeof PROPOSAL_IDS | typeof CUW_IDS | typeof TEST_PRODUCT_IDS): Response {
  if (ids.productId !== CUW_IDS.productId) {
    return runtimeConfigResponse(ids);
  }
  const scenarios = CUW_SCENARIO_IDS.map((scenarioId) => ({
    scenario_id: scenarioId,
    version: 1,
    allowed_next_actions: ["copy_result"],
    input_renderer_hint: { renderer: "json_schema", schema_ref: `${ids.productId}.input_v1`, schema_version: 1 },
    output_renderer_hint: { renderer: "json_schema", schema_ref: `${ids.productId}.output_v1`, schema_version: 1 },
  }));
  return runtimeConfigResponse(ids, { scenario_ids: CUW_SCENARIO_IDS, scenarios });
}

function bootRoutes(ids: typeof PROPOSAL_IDS | typeof CUW_IDS | typeof TEST_PRODUCT_IDS): RouteQueues {
  const routes = routesFor(ids);
  return {
    [routes.RUNTIME_CONFIG]: times(() => runtimeConfigFor(ids)),
    [routes.GUEST_IDENTITY]: times(() => guestIdentityResponse()),
    [routes.QUOTA]: times(() => quotaResponse(ids)),
  };
}

function renderShell(product: RegisteredProduct, routes: RouteQueues) {
  const captured = makeClientCapturingRequests(routes);
  render(<ProductPageShell product={product} client={captured.client} />);
  return captured;
}

function registered(productId: string): RegisteredProduct {
  const product = getRegisteredProduct(productId);
  if (!product) {
    throw new Error(`${productId} is not registered`);
  }
  return product;
}

function startInput(calls: CapturedCall[]): Record<string, unknown> {
  const start = calls.find((call) => call.key === routesFor(PROPOSAL_IDS).START);
  return (JSON.parse(start?.init.body as string) as { input: Record<string, unknown> }).input;
}

const selector = () => document.getElementById("ui-language") as HTMLSelectElement;
const switchTo = (locale: Locale) => fireEvent.change(selector(), { target: { value: locale } });
const valueOf = (element: HTMLElement) => (element as HTMLInputElement | HTMLTextAreaElement).value;

function mockBrowserLanguages(languages: string[]) {
  vi.spyOn(window.navigator, "languages", "get").mockReturnValue(languages);
}

describe("ProductPageShell locale rendering", () => {
  it.each(LOCALES)("renders ProposalAI's UI in %s", async (locale) => {
    const messages = PROPOSAL_AI_MESSAGES[locale];
    renderShell(registered("proposal_ai"), bootRoutes(PROPOSAL_IDS));
    await screen.findByRole("button", { name: PROPOSAL_AI_MESSAGES.en.generate.submit });

    switchTo(locale);

    expect(await screen.findByRole("button", { name: messages.generate.submit })).toBeTruthy();
    expect(screen.getByLabelText(messages.fields.taskText)).toBeTruthy();
    expect(screen.getByLabelText(messages.fields.freelancerPositioning)).toBeTruthy();
    expect(screen.getByLabelText(messages.fields.tone)).toBeTruthy();
    expect(screen.getByLabelText(messages.fields.language)).toBeTruthy();
    expect(screen.getByRole("heading", { name: messages.title })).toBeTruthy();
    expect(document.documentElement.lang).toBe(locale);
    expect(selector().value).toBe(locale);
  });

  it.each(LOCALES)("renders Client Update Writer's UI in %s, for every mode", async (locale) => {
    const messages = CLIENT_UPDATE_WRITER_MESSAGES[locale];
    renderShell(registered("client_update_writer"), bootRoutes(CUW_IDS));
    await screen.findByRole("button", { name: CLIENT_UPDATE_WRITER_MESSAGES.en.update.submit });

    switchTo(locale);

    expect(await screen.findByRole("button", { name: messages.update.submit })).toBeTruthy();
    expect(screen.getByText(messages.modes.legend)).toBeTruthy();
    expect(screen.getByLabelText(messages.fields.progressNotes)).toBeTruthy();
    expect(screen.getByLabelText(messages.fields.tone)).toBeTruthy();

    fireEvent.click(screen.getByLabelText(messages.modes.reply_draft));
    expect(await screen.findByRole("button", { name: messages.reply_draft.submit })).toBeTruthy();
    expect(screen.getByLabelText(messages.fields.clientMessage)).toBeTruthy();
    expect(screen.getByLabelText(messages.fields.replyGoal)).toBeTruthy();

    fireEvent.click(screen.getByLabelText(messages.modes.prepaid_request));
    expect(await screen.findByRole("button", { name: messages.prepaid_request.submit })).toBeTruthy();
    expect(screen.getByLabelText(messages.fields.billingNotes)).toBeTruthy();
    expect(screen.getByLabelText(messages.fields.billingAmount)).toBeTruthy();
    expect(screen.getByLabelText(messages.fields.billingDueDate)).toBeTruthy();
  });

  it("lists every supported locale under its own name in one selector", async () => {
    renderShell(registered("proposal_ai"), bootRoutes(PROPOSAL_IDS));
    expect([...selector().options].map((option) => option.textContent)).toEqual([
      "English",
      "Français",
      "Italiano",
      "Deutsch",
      "Español",
      "Русский",
      "Português",
    ]);
  });
});

describe("ProductPageShell locale resolution and persistence", () => {
  it("follows an explicit switch made in another same-origin tab", async () => {
    renderShell(registered("proposal_ai"), bootRoutes(PROPOSAL_IDS));
    await screen.findByRole("button", { name: PROPOSAL_AI_MESSAGES.en.generate.submit });

    // The real browser never dispatches `storage` in the tab that wrote the key -- this simulates
    // the event as another tab's write would arrive here, without going through this tab's own
    // localStorage.setItem (there is nothing else to assert on the writing tab's side).
    window.dispatchEvent(new StorageEvent("storage", { key: LOCALE_STORAGE_KEY, newValue: "de" }));

    expect(await screen.findByRole("button", { name: PROPOSAL_AI_MESSAGES.de.generate.submit })).toBeTruthy();
  });

  it("re-resolves down to the browser language when another tab clears the stored choice", async () => {
    mockBrowserLanguages(["it-IT"]);
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "ru");
    renderShell(registered("proposal_ai"), bootRoutes(PROPOSAL_IDS));
    await screen.findByRole("button", { name: PROPOSAL_AI_MESSAGES.ru.generate.submit });

    window.dispatchEvent(new StorageEvent("storage", { key: LOCALE_STORAGE_KEY, newValue: null }));

    expect(await screen.findByRole("button", { name: PROPOSAL_AI_MESSAGES.it.generate.submit })).toBeTruthy();
  });

  it("persists an explicit choice and applies it on the next visit", async () => {
    renderShell(registered("proposal_ai"), bootRoutes(PROPOSAL_IDS));
    switchTo("ru");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("ru");
    cleanup();

    renderShell(registered("proposal_ai"), bootRoutes(PROPOSAL_IDS));
    expect(await screen.findByRole("button", { name: PROPOSAL_AI_MESSAGES.ru.generate.submit })).toBeTruthy();
    expect(document.documentElement.lang).toBe("ru");
  });

  it("uses the browser locale (regional variant -> base locale) when there is no explicit choice, without persisting it", async () => {
    mockBrowserLanguages(["pt-BR", "en-US"]);
    renderShell(registered("proposal_ai"), bootRoutes(PROPOSAL_IDS));

    expect(await screen.findByRole("button", { name: PROPOSAL_AI_MESSAGES.pt.generate.submit })).toBeTruthy();
    expect(document.documentElement.lang).toBe("pt");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBeNull();
  });

  it("falls back to English for an unsupported browser locale", async () => {
    mockBrowserLanguages(["ja-JP"]);
    renderShell(registered("proposal_ai"), bootRoutes(PROPOSAL_IDS));

    expect(await screen.findByRole("button", { name: PROPOSAL_AI_MESSAGES.en.generate.submit })).toBeTruthy();
    expect(document.documentElement.lang).toBe("en");
  });

  it("prefers the explicit choice over the browser locale", async () => {
    mockBrowserLanguages(["de-DE"]);
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "it");
    renderShell(registered("proposal_ai"), bootRoutes(PROPOSAL_IDS));

    expect(await screen.findByRole("button", { name: PROPOSAL_AI_MESSAGES.it.generate.submit })).toBeTruthy();
  });

  it("still switches, and survives a remount within the same page load, when localStorage throws", async () => {
    // getItem is left real (not mocked) on purpose: the classic Safari-private-mode shape this
    // guards is setItem throwing while getItem keeps succeeding (just never seeing the write).
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    renderShell(registered("proposal_ai"), bootRoutes(PROPOSAL_IDS));
    switchTo("fr");
    expect(await screen.findByRole("button", { name: PROPOSAL_AI_MESSAGES.fr.generate.submit })).toBeTruthy();
    cleanup();

    // A remount (e.g. navigating to another product and back) re-resolves from storage; the failed
    // write must not silently revert to English here.
    renderShell(registered("proposal_ai"), bootRoutes(PROPOSAL_IDS));
    expect(await screen.findByRole("button", { name: PROPOSAL_AI_MESSAGES.fr.generate.submit })).toBeTruthy();

    resetUnpersistedLocaleForTests();
  });
});

describe("UI locale is independent of scenario input and state", () => {
  function happyRoutes(ids: typeof PROPOSAL_IDS | typeof CUW_IDS): RouteQueues {
    const routes = routesFor(ids);
    return {
      ...bootRoutes(ids),
      [routes.START]: [startResponse()],
      [routes.SESSION]: [sessionResponse()],
      [routes.RESULT]: [resultResponse(ids, { output: { text: "Generated." } })],
    };
  }

  it("keeps entered values, and never touches the output-language field, when the UI locale changes (and back)", async () => {
    const { calls } = renderShell(registered("proposal_ai"), happyRoutes(PROPOSAL_IDS));
    const en = PROPOSAL_AI_MESSAGES.en.fields;
    const ru = PROPOSAL_AI_MESSAGES.ru.fields;
    await screen.findByLabelText(en.taskText);
    fireEvent.change(screen.getByLabelText(en.taskText), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText(en.freelancerPositioning), { target: { value: "Frontend freelancer." } });
    fireEvent.change(screen.getByLabelText(en.language), { target: { value: "fr" } });

    switchTo("ru");

    expect(valueOf(screen.getByLabelText(ru.taskText))).toBe("Build a landing page.");
    expect(valueOf(screen.getByLabelText(ru.freelancerPositioning))).toBe("Frontend freelancer.");
    expect(valueOf(screen.getByLabelText(ru.language))).toBe("fr");

    // ... and the reverse: changing the output language does not change the UI locale.
    fireEvent.change(screen.getByLabelText(ru.language), { target: { value: "de-DE" } });
    expect(selector().value).toBe("ru");
    expect(document.documentElement.lang).toBe("ru");

    switchTo("en");
    fireEvent.click(screen.getByRole("button", { name: PROPOSAL_AI_MESSAGES.en.generate.submit }));
    await waitFor(() => expect(screen.getByText("Generated.")).toBeTruthy());
    expect(startInput(calls)).toEqual({
      task_text: "Build a landing page.",
      freelancer_positioning: "Frontend freelancer.",
      language: "de-DE",
    });
  });

  it("sends the untranslated wire value for a tone chosen while the labels are translated", async () => {
    const { calls } = renderShell(registered("proposal_ai"), happyRoutes(PROPOSAL_IDS));
    await screen.findByLabelText(PROPOSAL_AI_MESSAGES.en.fields.taskText);
    switchTo("ru");
    const tone = screen.getByLabelText(PROPOSAL_AI_MESSAGES.ru.fields.tone) as HTMLSelectElement;

    expect([...tone.options].map((option) => option.value)).toEqual(["", "neutral", "warm", "firm"]);
    expect([...tone.options].map((option) => option.textContent)).toEqual([
      PROPOSAL_AI_MESSAGES.ru.fields.tonePlaceholder,
      HOST_MESSAGES.ru.tone.neutral,
      HOST_MESSAGES.ru.tone.warm,
      HOST_MESSAGES.ru.tone.firm,
    ]);

    fireEvent.change(screen.getByLabelText(PROPOSAL_AI_MESSAGES.ru.fields.taskText), { target: { value: "Task" } });
    fireEvent.change(screen.getByLabelText(PROPOSAL_AI_MESSAGES.ru.fields.freelancerPositioning), {
      target: { value: "Me" },
    });
    fireEvent.change(tone, { target: { value: "warm" } });
    fireEvent.click(screen.getByRole("button", { name: PROPOSAL_AI_MESSAGES.ru.generate.submit }));

    await waitFor(() => expect(screen.getByText("Generated.")).toBeTruthy());
    expect(startInput(calls).tone).toBe("warm");
  });

  it("keeps Client Update Writer's selected mode, its values and the mode wire values across a switch", async () => {
    renderShell(registered("client_update_writer"), bootRoutes(CUW_IDS));
    const en = CLIENT_UPDATE_WRITER_MESSAGES.en;
    await screen.findByLabelText(en.fields.progressNotes);
    fireEvent.click(screen.getByLabelText(en.modes.reply_draft));
    fireEvent.change(await screen.findByLabelText(en.fields.clientMessage), { target: { value: "Where is my invoice?" } });

    switchTo("fr");

    const fr = CLIENT_UPDATE_WRITER_MESSAGES.fr;
    const radios = screen.getAllByRole("radio") as HTMLInputElement[];
    expect(radios.map((radio) => radio.value)).toEqual(["update", "reply_draft", "prepaid_request"]);
    expect(radios.find((radio) => radio.checked)?.value).toBe("reply_draft");
    expect(screen.getByLabelText(fr.modes.reply_draft)).toBe(radios[1]);
    expect(valueOf(screen.getByLabelText(fr.fields.clientMessage))).toBe("Where is my invoice?");
    expect(screen.getByRole("button", { name: fr.reply_draft.submit })).toBeTruthy();
  });

  it("re-localizes validation errors and a retryable run error that are already on screen", async () => {
    const routes = routesFor(PROPOSAL_IDS);
    renderShell(registered("proposal_ai"), {
      ...bootRoutes(PROPOSAL_IDS),
      [routes.START]: [errorResponse(500, "internal_error")],
    });
    const en = PROPOSAL_AI_MESSAGES.en;
    await screen.findByLabelText(en.fields.taskText);

    fireEvent.click(screen.getByRole("button", { name: en.generate.submit }));
    expect(await screen.findAllByText("Task description is required.")).toBeTruthy();

    switchTo("ru");
    const required = HOST_MESSAGES.ru.validation.required;
    expect(screen.getByText(required.replace("{field}", PROPOSAL_AI_MESSAGES.ru.fieldNames.taskText))).toBeTruthy();

    fireEvent.change(screen.getByLabelText(PROPOSAL_AI_MESSAGES.ru.fields.taskText), { target: { value: "Task" } });
    fireEvent.change(screen.getByLabelText(PROPOSAL_AI_MESSAGES.ru.fields.freelancerPositioning), {
      target: { value: "Me" },
    });
    fireEvent.click(screen.getByRole("button", { name: PROPOSAL_AI_MESSAGES.ru.generate.submit }));
    const startFailed = (locale: Locale) =>
      HOST_MESSAGES[locale].errors.startFailed.replace("{product}", PROPOSAL_AI_MESSAGES[locale].title);
    expect(await screen.findByText(startFailed("ru"))).toBeTruthy();
    expect(screen.getByRole("button", { name: HOST_MESSAGES.ru.retry })).toBeTruthy();

    switchTo("de");
    expect(screen.getByText(startFailed("de"))).toBeTruthy();
    expect(screen.queryByText(startFailed("ru"))).toBeNull();
    expect(valueOf(screen.getByLabelText(PROPOSAL_AI_MESSAGES.de.fields.taskText))).toBe("Task");
  });
});

describe("a newly registered product gets the language selector without implementing it", () => {
  const fakeProduct: RegisteredProduct = {
    productId: TEST_PRODUCT_IDS.productId,
    enabled: true,
    messages: englishForAllLocales(TEST_PRODUCT_MESSAGES_EN),
    Component: ({ client, onEvent, visitId }) => (
      <ProductRunPage definition={testProductDefinition} client={client} onEvent={onEvent} visitId={visitId} />
    ),
  };

  it("renders the shared selector, switches the shared runtime's language and persists the choice", async () => {
    renderShell(fakeProduct, bootRoutes(TEST_PRODUCT_IDS));
    await screen.findByRole("button", { name: TEST_PRODUCT_MESSAGES_EN.run.submit });
    expect(selector().options).toHaveLength(LOCALES.length);

    fireEvent.click(screen.getByRole("button", { name: TEST_PRODUCT_MESSAGES_EN.run.submit }));
    expect(await screen.findByText("Text is required.")).toBeTruthy();

    switchTo("it");
    expect(screen.getByText(HOST_MESSAGES.it.validation.required.replace("{field}", "Text"))).toBeTruthy();
    expect(document.documentElement.lang).toBe("it");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("it");
  });
});
