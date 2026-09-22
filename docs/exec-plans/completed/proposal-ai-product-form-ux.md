# ProposalAI Product Form UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

## Status

- State: completed
- Owner: agent
- Created: 2026-09-22
- Last updated: 2026-09-22
- Review date: 2026-09-22
- Next action: product-owner review; optionally fix the two pre-existing Windows runner launchers separately
- Blocker: none

**Goal:** Turn ProposalAI's scaffold-like form into a focused, accessible proposal-writing flow
while preserving the existing Bundle 3 design system, replacing the Tone select with three visible
choices, and removing the technical Language input from the web UI.

**Architecture:** Keep transport, runtime state, schemas, and provider selection unchanged.
`ProductRunPage` gains only product-neutral page composition (description, quota badge, glass form
card, stable action/status area); ProposalAI continues to own its fields, copy, input mapping, and
product-specific CSS. The backend keeps optional `tone` and `language` contract support, but the web
product always sends a selected tone and omits language so the prompt uses the task language.

**Tech Stack:** Next.js 15, React 19, strict TypeScript, CSS Modules,
`@anytoolai/shared-ui`, Vitest + Testing Library, Playwright, YAML/Markdown product config, pytest.

**Spec:** Approved in-chat design from 2026-09-22, bounded by
`docs/product-specs/freelancer-suite-v0.md`, `docs/architecture/frontend-boundaries.md`, and the
Bundle 3 source of truth in `docs/exec-plans/active/any-503-adopt-bundle3-design-system.md`.

## Global Constraints

- Preserve Bundle 3 colors, gradients, Cabinet Grotesk/DM Sans typography, radii, and shared UI
  primitives; do not introduce a second design system or raw replacement palette.
- Reuse existing `Card`, `Button`, and `TextArea`; add no frontend dependency and no speculative
  shared RadioGroup abstraction for one product.
- Keep provider/model selection, workflow execution, quota, polling, result, and activation logic
  outside product UI code.
- Keep `language` optional in `generate_input.schema.json` and in workflow mapping for API/future
  callers; only the ProposalAI web form stops exposing and sending it.
- Default output language is the language of `task_text`; use English only when that language cannot
  be determined. Explicit `constraints.language` remains authoritative when another caller sends it.
- Present `warm`, `neutral`, and `firm` as an accessible native radio group with the user-facing
  labels `Warm & personable`, `Clear & professional`, and `Confident & direct`; default to `warm`.
- Use product-owned CSS Modules for ProposalAI-specific layout and the shared runtime CSS Module for
  generic page composition. Do not add ProposalAI rules to global `tokens.css`.
- Preserve entered values, idempotent retry behavior, quota semantics, safe errors, result copying,
  and analytics event boundaries.
- Do not include the existing local real-provider override in
  `products/proposal_ai/action_configs.yaml` in this UI change.

## File Map

- Modify `apps/web-mirror/src/products/runtime/productDefinition.ts`: add product-neutral description
  copy used by the shared header.
- Modify `apps/web-mirror/src/products/runtime/ProductRunPage.tsx`: semantic header, quota badge,
  form card, stable footer/status, owned validation, and first-invalid-field focus.
- Create `apps/web-mirror/src/products/runtime/ProductRunPage.module.css`: shared page/form geometry
  using existing Bundle 3 tokens.
- Modify `apps/web-mirror/src/products/proposalAi/ProposalAIProduct.tsx`: remove Language from web
  values, default Tone to warm, render grouped fields and native radios, and add product copy.
- Create `apps/web-mirror/src/products/proposalAi/ProposalAIProduct.module.css`: textarea sizing,
  field spacing, helper/error copy, and responsive segmented radios.
- Modify `apps/web-mirror/test/fixtures/testProductDefinition.tsx`: supply the new generic description.
- Modify `apps/web-mirror/test/ProductRunPage.test.tsx`: pin shared semantic and validation behavior.
- Modify `apps/web-mirror/test/ProposalAIProduct.test.tsx`: pin new fields, defaults, mapping, and
  accessibility.
- Modify
  `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/proposal_ai/prompts/compose_persuasive_text.v1.md`:
  use task language by default.
- Modify
  `packages/backend/product-platforms/freelancer-suite/tests/test_proposal_ai_product.py`: pin explicit
  language override and task-language fallback instructions.
- Modify `tests/e2e/proposal-ai-smoke/tests/proposal-ai-smoke.spec.ts`: assert the browser-visible tone
  contract without weakening the existing end-to-end journey.

## Review Focus

- A first submit with both required fields empty focuses `Describe the task`, shows both text errors,
  and makes no start request.
- The default untouched style sends `tone: "warm"`; changing the visible choice sends the matching
  backend enum without a parallel string mapping.
- No Language control or locale-code validation remains in the web form, and the browser request
  omits `language` entirely.
- Long task/positioning text remains usable at narrow widths without horizontal overflow or a
  user-resizable textarea breaking the card layout.
- Loading, running, retryable-error, terminal-error, quota-exhausted, and result states keep the
  existing behavior and do not create nested glass cards or move the primary action unexpectedly.

---

### Task 1: Change the product contract and prompt defaults

**Files:**

- Modify: `apps/web-mirror/src/products/proposalAi/ProposalAIProduct.tsx`
- Test: `apps/web-mirror/test/ProposalAIProduct.test.tsx`
- Modify:
  `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/proposal_ai/prompts/compose_persuasive_text.v1.md`
- Test: `packages/backend/product-platforms/freelancer-suite/tests/test_proposal_ai_product.py`

**Interfaces:**

- Consumes: existing `Tone = "neutral" | "warm" | "firm"`, optional backend
  `constraints.tone`/`constraints.language`, and required `task_text`/`freelancer_positioning`.
- Produces: `ProposalAIValues = { taskText: string; freelancerPositioning: string; tone: Tone }`,
  default `{ tone: "warm" }`, and a start payload that always includes `tone` and never includes
  `language` from this web surface.

- [x] **Step 1: Replace the old field-contract tests with failing behavior tests**

  Update `ProposalAIProduct.test.tsx` so it asserts:

  ```tsx
  const styleGroup = screen.getByRole("radiogroup", { name: "Proposal style" });
  expect(styleGroup).toBeTruthy();
  expect(screen.getByRole("radio", { name: "Warm & personable" })).toBeChecked();
  expect(screen.queryByLabelText(/Language/)).toBeNull();
  ```

  Keep required-field validation coverage, delete the obsolete `Language must look like...`
  assertion, and make the request-mapping test submit once untouched and once after selecting
  `Confident & direct`. Assert `tone` is respectively `warm` and `firm`, and both bodies lack
  `input.language`.

- [x] **Step 2: Add a failing prompt-policy test**

  Add a small `_load_prompt()` helper beside the existing YAML/JSON helpers in
  `test_proposal_ai_product.py`, then add:

  ```python
  def test_prompt_uses_task_language_by_default_and_preserves_explicit_override() -> None:
      prompt = _load_prompt("prompts/compose_persuasive_text.v1.md")
      assert "constraints.language" in prompt
      assert "language of `context.task_text`" in prompt
      assert "cannot be determined" in prompt
      assert "English" in prompt
  ```

- [x] **Step 3: Run the focused tests and verify they fail for the old UI/prompt**

  Run:

  ```powershell
  pnpm --filter @anytoolai/web-mirror test -- ProposalAIProduct.test.tsx
  python scripts/agent/runner.py validate-configs
  ```

  Expected: the frontend test fails because Tone is a select and Language is visible; the new
  prompt-policy assertion fails because the prompt currently defaults directly to English.

- [x] **Step 4: Implement the minimal contract change**

  In `ProposalAIProduct.tsx`:

  - remove `Input`, `LANGUAGE_PATTERN`, `language` from `ProposalAIValues`, its validation branch,
    `emptyValues`, and `toInput`;
  - make `tone` a non-empty `Tone` and initialize it to `"warm"`;
  - replace `<Select>` with a `<fieldset>`/`<legend>` and three native radio inputs;
  - use one checked-state source: `checked={values.tone === option.value}`;
  - call `onChange("tone", option.value)` from each radio; do not create a separate label-to-enum map.

  Use this single product-owned option list:

  ```tsx
  const TONE_OPTIONS = [
    { value: "warm", label: "Warm & personable" },
    { value: "neutral", label: "Clear & professional" },
    { value: "firm", label: "Confident & direct" },
  ] as const;
  ```

  In the prompt, replace the direct-English fallback with an explicit precedence rule:

  ```markdown
  - Write in `constraints.language` when it is provided. Otherwise write in the language of
    `context.task_text`; fall back to English only when that language cannot be determined.
  ```

  Do not change `generate_input.schema.json`, `workflows.yaml`, or the generic A06 contract.

- [x] **Step 5: Run focused checks and verify the new contract passes**

  Run:

  ```powershell
  pnpm --filter @anytoolai/web-mirror test -- ProposalAIProduct.test.tsx
  python scripts/agent/runner.py validate-configs
  python scripts/agent/runner.py quick-check
  ```

  Expected: all commands exit `0`; the quick check includes the freelancer-suite prompt/config
  tests and catches forbidden provider or schema drift.

- [x] **Step 6: Commit the product contract separately**

  ```powershell
  git add apps/web-mirror/src/products/proposalAi/ProposalAIProduct.tsx apps/web-mirror/test/ProposalAIProduct.test.tsx packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/proposal_ai/prompts/compose_persuasive_text.v1.md packages/backend/product-platforms/freelancer-suite/tests/test_proposal_ai_product.py
  git commit -m "feat: simplify ProposalAI output controls"
  ```

  Exclude the pre-existing local `action_configs.yaml` modification from the commit.

### Task 2: Build the shared product-page composition

**Files:**

- Modify: `apps/web-mirror/src/products/runtime/productDefinition.ts`
- Modify: `apps/web-mirror/src/products/runtime/ProductRunPage.tsx`
- Create: `apps/web-mirror/src/products/runtime/ProductRunPage.module.css`
- Modify: `apps/web-mirror/test/fixtures/testProductDefinition.tsx`
- Test: `apps/web-mirror/test/ProductRunPage.test.tsx`

**Interfaces:**

- Consumes: existing `ProductDefinition`, `Card`, `Button`, phase state, quota state, and product-owned
  `Fields`/`Result` components.
- Produces: required `copy.description: string`; a centered content column; header description and
  quota badge; a `Card` around form states only; `noValidate`; and focus on the first invalid field.

- [x] **Step 1: Write failing shared-runtime tests**

  Extend `testProductDefinition.copy` with `description: "Describe the test run."` and assert in
  `ProductRunPage.test.tsx` that:

  ```tsx
  expect(await screen.findByText("Describe the test run.")).toBeTruthy();
  expect(screen.getByText("3 of 3 runs remaining.")).toHaveAttribute("aria-live", "polite");
  expect(screen.getByRole("form")).toHaveAttribute("novalidate");
  ```

  Give the test form `aria-describedby` ids for help/error text. In the invalid-submit test, assert
  the first invalid field owns focus after the render settles and no start request was made.

- [x] **Step 2: Run the focused runtime test and verify it fails**

  Run:

  ```powershell
  pnpm --filter @anytoolai/web-mirror test -- ProductRunPage.test.tsx
  ```

  Expected: FAIL because `description`, named form semantics, and invalid-field focus do not exist.

- [x] **Step 3: Add product-neutral composition without changing runtime state**

  In `productDefinition.ts`, add `description: string` under `copy`. In `ProductRunPage.tsx`:

  - import `Card` and `ProductRunPage.module.css`;
  - group the heading, description, and conditional quota badge in a semantic header;
  - constrain the working column to `min(100%, 820px)` inside the existing `.page-container`;
  - render `<form aria-label={`${definition.title} form`} noValidate ...>` inside `Card` only for
    form phases; do not wrap `Result`, `ErrorState`, or quota-exhausted content in another card;
  - place the submit button and a fixed-min-height status region in a footer so running text does
    not move the action area;
  - after validation produces errors, schedule focus of the first `[aria-invalid="true"]` control
    inside the form; do not query outside this form.

  Keep all existing phase branches and handlers intact. The CSS Module should use only existing
  token custom properties for color, border, radius, and typography, with explicit layout values:

  ```css
  .content { width: min(100%, 820px); margin: 0 auto; }
  .header { margin-bottom: 24px; }
  .description { color: var(--color-text-secondary); max-width: 62ch; }
  .quota { display: inline-flex; border: 1px solid var(--color-border); border-radius: var(--radius-pill); }
  .form { display: grid; gap: 24px; }
  .footer { min-height: 44px; padding-top: 20px; border-top: 1px solid var(--color-border); }
  ```

  Add responsive rules only where behavior changes: at `max-width: 520px`, stack footer content
  and retain the existing full-width submit behavior. Do not add animation or a second gradient.

- [x] **Step 4: Run runtime tests, typecheck, and lint**

  Run:

  ```powershell
  pnpm --filter @anytoolai/web-mirror test -- ProductRunPage.test.tsx
  pnpm --filter @anytoolai/web-mirror typecheck
  pnpm --filter @anytoolai/web-mirror lint
  ```

  Expected: all commands exit `0`; the existing phase/retry/quota tests remain green.

- [x] **Step 5: Commit the shared composition separately**

  ```powershell
  git add apps/web-mirror/src/products/runtime/productDefinition.ts apps/web-mirror/src/products/runtime/ProductRunPage.tsx apps/web-mirror/src/products/runtime/ProductRunPage.module.css apps/web-mirror/test/fixtures/testProductDefinition.tsx apps/web-mirror/test/ProductRunPage.test.tsx
  git commit -m "feat: compose focused web product forms"
  ```

### Task 3: Finish ProposalAI field layout and accessible copy

**Files:**

- Modify: `apps/web-mirror/src/products/proposalAi/ProposalAIProduct.tsx`
- Create: `apps/web-mirror/src/products/proposalAi/ProposalAIProduct.module.css`
- Test: `apps/web-mirror/test/ProposalAIProduct.test.tsx`

**Interfaces:**

- Consumes: Task 1's non-empty `Tone` and Task 2's form card/header composition.
- Produces: grouped required fields with stable help/error ids, larger non-resizable textareas,
  responsive radio segments, ProposalAI description copy, and no new shared primitive.

- [x] **Step 1: Add failing copy and accessibility assertions**

  Assert that the page contains the agreed one-line description, both textarea examples, and the
  `Proposal style` group. Assert each textarea's `aria-describedby` references an existing help
  element and, after invalid submit, its error element as well. Keep the radio test keyboard-native
  by changing it with `fireEvent.click`, not by calling product state directly.

- [x] **Step 2: Run the focused test and verify the new assertions fail**

  Run:

  ```powershell
  pnpm --filter @anytoolai/web-mirror test -- ProposalAIProduct.test.tsx
  ```

  Expected: FAIL because helper copy, ids, and product-specific layout are not implemented yet.

- [x] **Step 3: Implement the product-owned field presentation**

  Set `copy.description` to:

  ```text
  Turn a client brief and your relevant strengths into a proposal ready to send.
  ```

  Group each field in a product-owned wrapper and use concise supporting copy:

  - Task placeholder: `Paste the client's task, brief, or job post.`
  - Task help: `Include the goal, deliverables, constraints, and timeline when available.`
  - Positioning placeholder: `Describe the experience and strengths that make you a good fit.`
  - Positioning help: `Use only claims you can stand behind—the proposal will not invent experience.`

  Give the task textarea at least `144px` and positioning at least `120px`, set `resize: none`, and
  use `width: 100%`. Style the tone controls as one three-column segmented group with native radios
  visually hidden but focusable; use `:focus-within`, `:has(input:checked)`, existing surface/border/
  accent tokens, and a `44px` minimum option height. At a narrow breakpoint, stack the three labels.

  Errors remain text with `role="alert"`, `aria-invalid="true"`, and deterministic ids. Build each
  `aria-describedby` value from the always-present help id plus the error id only when present.

- [x] **Step 4: Run product tests and the complete web-mirror suite**

  Run:

  ```powershell
  pnpm --filter @anytoolai/web-mirror test -- ProposalAIProduct.test.tsx
  pnpm --filter @anytoolai/web-mirror test
  pnpm --filter @anytoolai/web-mirror typecheck
  pnpm --filter @anytoolai/web-mirror lint
  ```

  Expected: all commands exit `0`.

- [x] **Step 5: Commit the ProposalAI presentation separately**

  ```powershell
  git add apps/web-mirror/src/products/proposalAi/ProposalAIProduct.tsx apps/web-mirror/src/products/proposalAi/ProposalAIProduct.module.css apps/web-mirror/test/ProposalAIProduct.test.tsx
  git commit -m "feat: refine ProposalAI form presentation"
  ```

### Task 4: Update browser evidence and verify the complete change

**Files:**

- Modify: `tests/e2e/proposal-ai-smoke/tests/proposal-ai-smoke.spec.ts`
- Update: `docs/exec-plans/active/proposal-ai-product-form-ux.md` status/evidence only

**Interfaces:**

- Consumes: the completed ProposalAI page and existing real form → start → poll → result → copy
  smoke path.
- Produces: browser evidence for visible product controls plus final repository verification.

- [x] **Step 1: Update the existing happy-path browser assertion**

  After navigation, assert the description is visible, the `Proposal style` radiogroup exists,
  `Warm & personable` is checked, and no Language textbox or combobox is present. Keep the existing
  helper functions and backend-recorded copy assertion; do not add a new E2E file or snapshot tool.

- [x] **Step 2: Run frontend and config gates**

  Run:

  ```powershell
  python scripts/agent/runner.py validate-configs
  python scripts/agent/runner.py frontend-check
  ```

  Expected: both commands exit `0`.

- [x] **Step 3: Run the ProposalAI browser smoke in a clean provider-test composition**

  Use the repository's normal ProposalAI smoke setup, not the developer's local real-provider
  override:

  ```powershell
  python scripts/agent/runner.py dev-up
  python scripts/agent/runner.py proposal-ai-smoke
  ```

  Expected: all ProposalAI Playwright tests pass, including validation, happy path, retry,
  safe-error, quota, and copy activation. If execution stays in the current dirty workspace, first
  preserve the user's `action_configs.yaml` override and run this step from an isolated worktree;
  do not overwrite or commit that local override.

- [x] **Step 4: Inspect the live page visually and by keyboard**

  In a real browser, verify at approximately `1280x800`, `768x800`, and `390x844`:

  - the content column never exceeds `820px` and has no horizontal overflow;
  - task and positioning fields are comfortably usable and cannot be manually resized;
  - radio labels remain readable, checked state is not color-only, and arrow-key navigation follows
    native radio behavior;
  - Tab focus is visible on every control and invalid submit focuses the task field;
  - button/status geometry remains stable while submitting and running;
  - result/error states are not wrapped in duplicate glass cards;
  - reduced-motion mode introduces no hidden content or required animation.

- [x] **Step 5: Run the final repository gate and diff hygiene**

  Run:

  ```powershell
  python scripts/agent/runner.py full-check
  git diff --check
  git status --short
  ```

  Expected: `full-check` and `git diff --check` exit `0`; status contains only this plan's intended
  implementation files plus explicitly preserved pre-existing user changes.

- [x] **Step 6: Record evidence and complete the plan**

  Update this plan's Status with exact command results, browser viewport coverage, and remaining
  risks. Move it to `docs/exec-plans/completed/` only after all applicable checks pass.

- [x] **Step 7: Commit browser evidence and plan closeout**

  ```powershell
  git add tests/e2e/proposal-ai-smoke/tests/proposal-ai-smoke.spec.ts docs/exec-plans/active/proposal-ai-product-form-ux.md
  git commit -m "test: verify ProposalAI form experience"
  ```

  If the plan has already moved to `completed/`, stage that destination path instead of the active
  path. Never stage the unrelated local provider override or other pre-existing untracked files.

## Completion Evidence

- `validate-configs`: passed.
- Focused web-mirror verification: 78/78 tests passed; typecheck, lint, and production build passed.
- Freelancer ProposalAI backend tests: 15/15 passed before the final repository run.
- Strict premium design audit: 0 findings.
- Isolated fake-provider browser smoke: all 7 Playwright scenarios passed. The Windows runner then
  returned `1` only while cleaning up the already-successful run because `os.getpgid` is not
  available on Windows; the exact orphaned port-3100 process and temporary Compose project were
  stopped separately.
- Clean-worktree `full-check`: 1861 backend tests passed (3 skipped, 479 deselected); repository
  lint, typecheck, 315 ce-kit tests, 48 shared-ui tests, 78 web-mirror tests, and 13 atom-lab browser
  tests passed. The wrapper then returned `1` at the pre-existing Windows/Node 24
  `openapi-typescript` extensionless-shim launch. Running the same generator through `pnpm exec`
  and diffing its output against the committed generated client passed with exit `0`.
- Live browser: desktop, 768px, and 390px layouts inspected; 390px had no horizontal overflow and
  stacked Tone choices; checked state included a non-color check mark; ArrowRight moved native
  radio selection; invalid submit focused `proposal-ai-task-text` with a visible outline.
- `git diff --check`: passed. The user's real-provider `action_configs.yaml`, `.cursor/`, and the
  unrelated `atoms-proof-required-ci-gate.md` remain outside these commits.

## Explicitly Deferred

- A visible output-language override, locale picker, or automatic language detector in frontend
  code. Add one only when observed users need output in a language different from the task.
- A shared RadioGroup component. Extract one only after a second real product needs the same
  interaction and styling contract.
- Custom select/listbox infrastructure, illustrations, animation, another gradient, or new design
  tokens. None is necessary for the approved ProposalAI flow.
- Changes to provider/model selection, quotas, workflow mapping, result contracts, or activation.
