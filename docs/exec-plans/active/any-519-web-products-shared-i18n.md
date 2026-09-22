# Execution Plan: ANY-519 Web Products Shared i18n Foundation And Per-Product Localization

## Status

- State: active
- Owner: agent
- Created: 2026-09-22
- Last updated: 2026-09-22
- Review date: 2026-09-29
- Next action: native-speaker review of the six non-English locales; rebase on `main` after PR #127 merges.
- Blocker: none. Stacked on `feature/ANY-414` (PR #127, still open); rebase once it merges.

## Goal

One host-level locale mechanism in `apps/web-mirror` for every registered web product: a language
switcher on `/products/{productId}`, seven UI locales (`en fr it de es ru pt`), product-owned
translations, and UI locale kept fully independent from generated-content language.

## Scope

### In scope

- `apps/web-mirror/src/i18n/`: locale set, resolution, persistence, provider, switcher, host messages.
- `apps/web-mirror/src/products/*/messages/`: product-owned messages, registered via `registry.ts`.
- Shared runtime migration (`ProductRunPage`, `ResultView`, `ErrorState`, `tone.tsx`) and both
  products.
- Structured validation errors replacing English prose in `fieldValidation.ts`.
- `ProductDefinition` loses `title`/`copy`; presentation comes from the i18n layer.
- Tests, one E2E smoke scenario, and the frontend architecture doc.

### Out of scope

Platform Core, Provider Gateway, workflow runtime, product/scenario IDs, prompt translation,
deriving output language from UI locale, locale-prefixed routes, `pt-BR`/`pt-PT`, remote
translation management, handoff/paywall/onboarding/artifact/home pages, server-side
`Accept-Language` resolution.

## Design decisions

1. **Library: `use-intl`** (framework-agnostic core of next-intl). ICU interpolation and plurals
   (Russian few/many via `Intl.PluralRules`), namespaces, runtime switching by provider props; no
   Next plugin, routing or middleware. Spike: `pnpm install --frozen-lockfile` passes, no build
   scripts added. Only `src/i18n/**` imports it (source-scan test); the rest of the app uses the
   app-owned `useHostT`/`useProductT`/`useLocale` boundary.
2. **Two namespaces in one message tree**: `host` (generic runtime/result/error/validation/tone
   vocabulary/switcher) and `product` (the current product's own messages, supplied by its
   registry entry). The shared runtime reads `product` only through keys the product's definition
   names (`title`, `quotaRemaining`, `<messageScope>.submit|running|runFailed`).
3. **Fallback = deep merge with `en`** at provider level (use-intl has no locale fallback).
   Non-English message files are typed `Shape<typeof en>`, so a missing/extra key is a compile
   error; a vitest parity test also compares flattened keys and ICU placeholder names.
4. **Locale resolution**: persisted explicit choice -> `navigator.languages` (base subtag) -> `en`.
   Only an explicit choice is persisted (`anytoolai.ui_locale`). Resolved client-side in a layout
   effect (server/first render are `en`); read synchronously from localStorage, unlike the async
   ce-kit adapter, so there is no flash of the wrong language.
5. **The provider never remounts the tree** (no `key={locale}`), so form values, `phase`,
   `pendingStart` and the selected CUW mode survive a switch.
6. **Retryable-error state stores a closed reason, not English prose**, so a visible error
   re-localizes on switch.
7. **Wire values never translated**: tone `<option value>` stays `neutral|warm|firm`; only labels
   come from `host.tone.*`. UI locale is never read by any `toInput`.
8. **Registry owns product messages**: `RegisteredProduct.messages: Record<Locale, ...>`;
   `ProductPageShell` wraps every product in the provider and switcher, so a new product needs no
   selector/persistence code.
9. **English strings stay byte-identical** to the pre-i18n UI except the `max_length` message,
   which now pluralizes ("1 character"); this keeps existing English assertions and E2E valid.
10. **Translations are machine-drafted**; native-speaker review is required before release.

## Verification

All run and passing:

```
python scripts/agent/runner.py frontend-check      # typecheck, lint, unit tests, build
python scripts/agent/runner.py full-check           # + backend baseline + product suites
python scripts/agent/runner.py validate-architecture
python scripts/agent/runner.py validate-docs
python scripts/agent/runner.py generate-docs --check
pnpm --filter @anytoolai/web-mirror test            # 209 tests, incl. i18n.test.ts, ProductPageShell.test.tsx
python scripts/agent/runner.py dev-up
python scripts/agent/runner.py proposal-ai-smoke          # 8/8, incl. the new language-switch scenario
python scripts/agent/runner.py client-update-writer-smoke # 3/3, English default unaffected
python scripts/agent/runner.py dev-down
```

## Risks / open items

- Stacked on PR #127; conflicts likely in `fieldValidation.ts`, `tone.tsx`,
  `ClientUpdateWriterProduct.tsx`, `ProductRunPage.tsx` if review changes land there.
- Translation quality needs human review; automated checks cover keys and placeholders only.
- All locales are bundled statically; move to per-locale dynamic `import()` if message volume grows.
- `CopyButton` in `shared-ui` has hardcoded English but is unused by `web-mirror`; adopting it
  requires passing labels.
