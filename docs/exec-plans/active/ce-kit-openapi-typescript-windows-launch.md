# CE-kit OpenAPI TypeScript Windows Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Status

- State: active
- Owner: agent
- Created: 2026-08-13
- Last updated: 2026-08-13
- Review date: 2026-08-13
- Next action: add a failing Windows-portable invocation regression for the OpenAPI TypeScript CLI.
- Blocker: none

**Goal:** Make CE-kit's generated API-type check invoke `openapi-typescript` portably on Windows and
Linux without depending on a platform-specific pnpm `.bin` shim.

**Architecture:** Resolve the installed package's JavaScript CLI entrypoint and launch it with the
current Node executable. Keep schema/output/check behavior unchanged and cover the invocation shape
with a focused Vitest regression before rerunning the real frontend gate.

**Tech stack:** Node.js, pnpm 10.34.1, Vitest, `openapi-typescript` 7.13.0.

## Global Constraints

- Do not change generated API types unless the canonical schema actually differs.
- Do not enable `shell: true` or interpolate command strings.
- Preserve `pnpm --filter @anytoolai/ce-kit generate-api-types[:check]` public commands.
- Use `process.execPath` plus the package CLI JavaScript file on every platform.

---

### Task 1: Replace platform-specific shim execution

**Files:**

- Create: `packages/frontend/ce-kit/scripts/openapiTypescriptInvocation.mjs`
- Modify: `packages/frontend/ce-kit/scripts/generate-api-types.mjs`
- Create: `packages/frontend/ce-kit/test/scripts/openapiTypescriptInvocation.test.ts`

**Interfaces:**

- Produces: `openapiTypescriptInvocation(schemaPath, outputPath)` returning
  `{ executable: string, args: string[] }`.
- Consumes: `process.execPath` and
  `packages/frontend/ce-kit/node_modules/openapi-typescript/bin/cli.js`.

- [ ] **Step 1: Add the failing portable-invocation test**

  Add a Vitest test which imports `openapiTypescriptInvocation`, passes `schema.json` and
  `platformApi.ts`, and asserts:

  ```typescript
  expect(invocation.executable).toBe(process.execPath);
  expect(invocation.args[0].replaceAll("\\", "/")).toMatch(
    /node_modules\/openapi-typescript\/bin\/cli\.js$/,
  );
  expect(invocation.args.slice(1)).toEqual(["schema.json", "-o", "platformApi.ts"]);
  ```

- [ ] **Step 2: Run the test and confirm the helper is absent**

  Run:

  ```text
  pnpm --filter @anytoolai/ce-kit test -- openapiTypescriptInvocation
  ```

  Expected: FAIL because the invocation helper does not exist.

- [ ] **Step 3: Implement the direct Node CLI invocation**

  Create the helper with `fileURLToPath(import.meta.url)`/`dirname()`/`join()` and return
  `process.execPath` plus the installed `bin/cli.js` path and CLI arguments. Update
  `generate-api-types.mjs` to pass that executable and argument list to `execFileSync()` instead of
  `node_modules/.bin/openapi-typescript`.

- [ ] **Step 4: Run the focused test and the original failing command**

  Run:

  ```text
  pnpm --filter @anytoolai/ce-kit test -- openapiTypescriptInvocation
  pnpm -r --if-present generate-api-types:check
  ```

  Expected: both commands pass on Windows; the generated API types remain unchanged.

- [ ] **Step 5: Run cross-platform repository gates**

  Run on Windows and Ubuntu:

  ```text
  python scripts/agent/runner.py frontend-check
  python scripts/agent/runner.py full-check
  git diff --check
  ```

  Expected: every command exits zero on both operating systems.

## Validation

- [ ] focused red/green invocation regression
- [ ] Windows `pnpm -r --if-present generate-api-types:check`
- [ ] Windows `python scripts/agent/runner.py full-check`
- [ ] Ubuntu `python scripts/agent/runner.py full-check`
- [ ] `git diff --check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-13 | Launch the package's JavaScript CLI with `process.execPath`. | The extensionless pnpm shim exists but `execFileSync()` reports `ENOENT` on Windows; direct Node execution is shell-free and platform-neutral. |
| 2026-08-13 | Track this separately from locked Python generated-doc parity. | Python OpenAPI rendering and Node API-type CLI launch are independent failure boundaries with different owners and regressions. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-13 | Reproduced `spawnSync ...node_modules/.bin/openapi-typescript ENOENT` under Windows Node 24.18.0 after a clean frozen pnpm install; Ubuntu-only frontend CI does not exercise the failing path. | Add the portable invocation regression, then replace shim execution. |

## Open questions

- Decide separately whether repository tooling should pin a supported Node major and add a Windows
  frontend CI job; neither is required for the direct CLI-launch fix.

## Follow-up debt

- Node major-version policy and Windows frontend CI coverage remain explicit follow-up decisions.
