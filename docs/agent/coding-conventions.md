# Coding Conventions For Agents

Operational do/don't for AnytoolAI production code. Philosophy lives in
[`docs/core-beliefs.md`](../core-beliefs.md). Architecture lives in `docs/architecture/` and ADRs.
This file is how to write the next diff.

## Applicability

These rules apply to **new files and changed lines**. Neighboring legacy that already violates them
is not a license to add another violation.

Do **not**:

- rewrite unrelated files to match this document;
- start a mass lint cleanup, enum migration, or loader rewrite because a rule exists here;
- add a root `rules.md` or copy this text into scoped `AGENTS.md` files.

Mass cleanup needs its own execution plan and ticket. Feature PRs own tests and docs for the
behavior they introduce.

## Shared

### Closed sets

A closed set of values is a type, not an open `str` / `string`: `StrEnum`, `Literal`, a
discriminated union, or `as const`.

Statuses, kinds, modes, error codes, quota units/periods/dimensions, frontend types, and other
protocol values must not travel as unconstrained strings.

Reuse the existing type along the **allowed dependency direction**. Do not invent a parallel list.

Current backend split, which is an allowed checked mirror rather than a bug:

- HTTP/runtime owner is the **Core** domain enum.
- `platform-sdk` keeps a public mirror for product bundles.
- `packages/backend/platform-core/tests/test_contract_field_compatibility.py` must keep enum
  **values** in sync.
- `platform-core` must not import `platform-sdk` to "deduplicate" these types.

New duplication outside this Core/SDK pair needs an architectural decision and a drift-check.

### Boundaries

Parse and validate once at the trust boundary (HTTP, YAML, provider output, browser message,
storage). After that boundary, code uses a typed model.

Do **not** keep probing `dict[str, Any]`, `unknown`, or string keys in business logic after the
parser has accepted the payload.

### One concept, one source of truth

Do not copy an enum, status list, schema shape, or tool configuration unless the architecture
already requires a mirror **and** a test checks it.

### Magic values

`0`, `1`, and local arithmetic are fine. Timeouts, limits, HTTP statuses, sizes, retries, and
business thresholds need a named constant or a config field.

### Fail-fast

- Invalid input or state: reject or raise. Do not continue with a partial result.
- Catch only expected exceptions; log with context; re-raise anything else.
- Do not invent a default to hide missing required data.
- `a or b or c` is forbidden when it substitutes missing **business** data with a different
  meaning (`status or "completed"`, `name or "Anonymous"`).
- `a or b or c` is allowed only for an **explicit, documented configuration precedence** (for
  example env, then file, then a declared default). Silent loader fallback and hidden merge stay
  forbidden; see [`docs/architecture/config-model.md`](../architecture/config-model.md).

### Abstraction

Do not add an abstraction, dependency, or configuration point until a second real consumer exists.
Prefer boring, explicit, searchable code.

### Comments

A comment states an invariant or a non-obvious reason. It does not restate the next line of code.

### Tests

A non-trivial branch, boundary parser, money/security path, or bugfix gets a focused runnable test
in the same PR.

A parser that accepts a closed set must have a **negative** test: an unknown member is rejected.

Do not use placeholders, silent skips, or expected failures as proof that unfinished behavior works.

### Ratchet

New and changed code must not make the current lint or typecheck baseline worse. Turning on a new
gate, wiping hundreds of existing violations, or enabling mypy are separate plans.

## Backend

### Models at trust boundaries

HTTP requests/responses, YAML configs, provider payloads, and persisted JSON go through Pydantic
models. Boundary models use `extra="forbid"`. Use `strict=True` only where coercion would hide an
error; do not apply it indiscriminately to YAML or HTTP models.

Follow existing `ContractModel` / `StrEnum` patterns. Do not introduce a parallel DTO base class.

Closed HTTP fields use the Core `StrEnum`, not `str`, so OpenAPI emits an `enum` rather than an
open string. Do not widen that field back to `str` in the API layer.

### PydanticAI

Structured LLM actions must use a **typed output binding**. `output_type=str` is not an acceptable
structured-output contract.

The concrete PydanticAI API belongs in [`docs/architecture/llm-runtime.md`](../architecture/llm-runtime.md)
and [ADR 0007](../adr/0007-llm-runtime-pydanticai-litellm-sdk.md). Do not encode a library helper
name in this file.

AnytoolAI still owns **final** validation before persistence. Typed PydanticAI output and platform
final validation solve different problems; do not delete the platform step because the agent bound
a type.

### `Any`

`Any` is allowed only on the trust-boundary parameter or payload. Narrow it to a concrete type in
the same module before other code consumes it.

### Comparisons and error codes

Compare statuses and error codes through the domain enum or a named constant, not by repeating
`"completed"` or `"quota_exhausted"` in production logic. Prefer `http.HTTPStatus` over raw `200`
or `429`.

Tests that assert the wire value may use the literal once.

### Config loading

Pydantic models check shape. The config loader loads files and checks cross-references. Do not add
new hand-rolled `.get(...)` / `isinstance(...)` shape checks. Rewriting the existing loader is a
separate plan.

## Frontend

### Strict TypeScript

Frontend packages keep `strict: true`.

### Parse at the boundary

Network, storage, and message handlers take `unknown`, validate it, and return a concrete type.

After the parser:

- do not use `as SomeType` to bypass checking;
- do not probe arbitrary JSON in components.

API transport, parsing, and camelCase mapping stay in CE-kit. UI components do not parse backend
payloads.

Do not add a parser or handwritten DTO until a real consumer exists.

### Generated unions

A backend closed set must appear in OpenAPI and in the generated CE-kit union.

Do **not** weaken a generated union back to `string` in a handwritten DTO, public CE-kit type, or
`AssertExactSchemaShape` expectation. Those handwritten shapes are part of the contract: they
narrow together with the generated file.

Alias the generated field. Do not hand-maintain a second copy of the member list.

```ts
export type ExampleStatus = components["schemas"]["ExampleResponse"]["status"];
```

### Membership guards

One semantic enum has one runtime map and guard, checked with `satisfies Record<Union, true>`.
Unknown values must not be accepted as "a string". The parser returns `null` and the client maps
that to `invalid_response`.

Use `Object.hasOwn`. Do not use `value in map` (inherited keys such as `"toString"` would pass).

```ts
const EXAMPLE_STATUS_BY_VALUE = {
  started: true,
  completed: true,
} as const satisfies Record<ExampleStatus, true>;

export function isExampleStatus(value: unknown): value is ExampleStatus {
  return typeof value === "string" && Object.hasOwn(EXAMPLE_STATUS_BY_VALUE, value);
}

const STOP_STATUSES: ReadonlySet<ExampleStatus> = new Set(["completed"]);
```

`ReadonlySet<ExampleStatus>` is fine. `ReadonlySet<string>` is not.

A subset such as `STOP_STATUSES` is not a second source of truth. The exhaustive map is.

When two CE-kit features share one semantic enum, they import one alias/guard. They do not each
copy the map.

### Exhaustiveness

For discriminated unions and UI state machines, handle every variant. Use a `never` helper so a new
union member fails typecheck:

```ts
function assertNever(value: never): never {
  throw new Error(`unexpected value: ${String(value)}`);
}
```

### Timeouts and polling

Timeouts and polling intervals are named constants. Override them only when the caller has a real
reason.

### Lint vs typecheck

`tsc --noEmit` is typecheck. Do not add a new `lint` script that only aliases `tsc --noEmit`.

Do not add a runtime schema library for a single parser. Add one when repeated guards are clearly
cheaper as shared schemas.

## Related docs

- [`docs/core-beliefs.md`](../core-beliefs.md) — typed contracts at boundaries; agent legibility.
- [`docs/architecture/structured-output.md`](../architecture/structured-output.md) — no loose JSON probing.
- [`docs/architecture/llm-runtime.md`](../architecture/llm-runtime.md) — PydanticAI vs LiteLLM vs platform.
- [`docs/architecture/frontend-boundaries.md`](../architecture/frontend-boundaries.md) — CE-kit ownership.
- [`docs/architecture/package-layering.md`](../architecture/package-layering.md) — allowed imports.
- [`docs/agent/review-checklist.md`](review-checklist.md) — review gate for these rules.
