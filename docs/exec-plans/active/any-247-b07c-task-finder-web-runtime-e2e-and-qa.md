# ANY-247: Task Finder web runtime and QA

## Status
- State: blocked
- Owner: agent
- Created: 2026-11-09
- Last updated: 2026-11-09
- Review date: 2026-11-16
- Next action: Rerun full-check on a host with passwordless sudo, then review the completed implementation.
- Blocker: full-check requires passwordless sudo for its existing activation-marker permission test.

## Goal
Deliver Task Finder through the shared web runtime with deterministic browser evidence.

## Scope
Shared smoke infrastructure (TD-014); product fields, parser, renderer, seven locales, registration,
unit and browser tests, runner command, optional CI workflow, documentation.
The original feature excluded execution-kernel, atom, Provider Gateway, mapping DSL and handoff changes.
The later authorized duplication follow-up also refactors shared workflow storage/recovery and
architecture analysis without changing their contracts.

## Implementation steps
- [x] Extract shared DB helpers, smoke configuration, runner preamble and CI workflow; verify four existing smokes.
- [x] Implement Task Finder using the shared runtime, canonical criterion ordering and independent score/verdict.
- [x] Add localization, directory card, copy/activation/error/quota tests and Task Finder browser smoke.
- [x] Run frontend/full checks and browser suites; record evidence and limitations.

## Decisions
The user authorized the mixed stack, number plus native meter, and optional ResultView.hideText.
Copy remains English per the renderer contract. On clipboard failure, reveal selectable text so the
existing fallback still works. Task Finder remains outside the committed release order; no handoff.
TD-014 extraction precedes the fifth smoke. Product-specific assertions stay in their suites.

## Validation
Use the repository-managed Python 3.12 environment. Run doctor, frontend-check, full-check, documentation and
architecture validation, then all five product smokes against dev-up.

## Progress log
- 2026-11-09: Confirmed Python 3.12 managed environment passes doctor; pnpm and Docker work with sandbox escalation.

## Risks
Shared smoke changes affect four existing suites. CI triggers require remote validation.
Translations require native-speaker review. Fake-provider checks do not assess live model quality.

- 2026-11-09: Extraction validated: ProposalAI 10/10, Client Update Writer 4/4, Brief Decoder 8/8, Acceptance Builder 11/11; smoke lint/typecheck and six focused runner tests pass. Existing runner permission test fails because passwordless sudo is unavailable.
- 2026-11-09: Task Finder's seven browser cases pass, including real API/worker/artifact correlation,
  independent score/verdict, once-per-result activation, copy, responsive layout/reset, validation,
  fixture-substituted weak result, terminal failure and quota exhaustion. Focused UI/copy tests:
  39 passed. Typecheck/lint, docs and architecture checks pass. Full repository/frontend gates running.
- 2026-11-09: Existing unrelated execution plans still contain a forbidden local skill-name literal;
  left untouched under the ticket-scoped documentation rule.
- 2026-11-09: Managed-environment doctor passes with Python 3.12.13, Node 24.22.1 and pnpm
  10.34.1. Product-suite tests pass (262); Task Finder API bundle tests pass (33), including the
  real weak-fixture workflow. Desktop and fresh mobile screenshots inspected. The existing CE-kit
  ESLint regression exceeds its 5-second timeout under parallel workers; limiting both workspace
  and Vitest worker concurrency makes it pass without changing test code or timeouts.

- 2026-11-09: Full-check baseline completed: 3,576 passed, 1 failed, 12 skipped, 655 deselected.
  Sole failure: `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`:
  sudo requires interactive authentication to run the marker read as nobody. The same failure was
  reproduced before the product implementation. No assertion, skip or privilege policy was changed.
  Full-check stops at that failure; frontend and product-suite stages are run separately.
- 2026-11-09: Frontend validation resumed from its failed stage: all 478 web tests pass after
  waiting for boot before the new description assertion. CE-kit 327, shared-ui 52 and Atom Lab
  browser 339 tests pass; generated OpenAPI types are current. Workspace lint and typecheck pass.
  Remaining frontend build and four final product browser regressions are running.
- 2026-11-09: Frontend stages completed successfully: frozen install, workspace lint/typecheck,
  CE-kit 327 tests, shared-ui 52 tests, Atom Lab 57 unit and 339 browser tests, web 478 tests,
  generated API-type drift check and workspace production builds. After the boot assertion fix,
  resumed with the web test command and remaining drift/build commands; the full frontend wrapper
  was not rerun through the already-passing 339 browser cases.

## Verification commands and environment

Use the managed Python 3.12 interpreter. The sandbox requires elevated access to the pnpm cache,
Docker and asynchronous API integration tests; no source or system privilege policy was changed.
For frontend resource limits use `VITEST_MAX_WORKERS=1 npm_config_workspace_concurrency=1`.
The checks executed were `doctor`, `full-check`, `frontend-check`, `validate-docs`,
`validate-architecture`, `generate-docs --check`, the five product smoke commands, and focused
runner, API-bundle and Freelancer Suite tests. The frontend continuation was:

```sh
VITEST_MAX_WORKERS=1 pnpm --filter @anytoolai/web-mirror test
pnpm -r --if-present generate-api-types:check
pnpm -r build
```

The development database's previous anonymous volume had incompatible credentials. Recreating
containers without deleting that volume gave the test stack a fresh database. The original data
volume was preserved. Sanitized failure context was collected for the sudo-dependent baseline test.

## Original delivery outcome

Implementation complete on feature/ANY-247. The infrastructure extraction is commit 2f017cd1;
the product implementation is a separate follow-up commit. No kernel, atom, provider gateway,
mapping DSL or handoff-runtime code changed. No GitHub writes were made.

All five product browser suites pass: Task Finder 7, ProposalAI 10, Client Update Writer 4,
Brief Decoder 8, Acceptance Builder 11. The four existing suites were rerun after the shared copy
component change, including both accepted and declined handoff journeys. Frontend validation
completed in stages as documented above; production builds pass. Documentation, architecture,
generated-artifact checks and diff whitespace checks pass.

The sole remaining validation blocker is the pre-existing sudo-dependent baseline test;
3,576 other baseline tests pass. Remote workflow dispatch and live-provider tests were not run.
Translations are structurally tested but still need native-speaker review. The optional future
Task Finder to ProposalAI handoff and broad visual polish remain out of scope.

## Sonar duplication follow-up — 2026-11-09

The user authorized removal of real smoke duplication and a proposal for translation dictionaries.
Sonar checks and exclusions must stay unchanged. The analyzed PR reports 484 duplicated new lines:
120 in Task Finder smoke and 364 in structurally parallel locale dictionaries.

Implementation plan:
1. Reuse smoke-support for layout/overflow checks in all five product suites; extract repeated run
   tracking, canonical-output substitution, failed-session substitution, execution correlation and
   copy activation where their contracts match. Preserve product-specific assertions and intercepts.
2. Run doctor, smoke-package lint/typecheck, documentation checks and all five browser suites.
3. Propose a maintainable dictionary representation separately; leave translations and Sonar settings
   unchanged in this follow-up. Do not claim the remote duplication gate passes without a new analysis.

### Dictionary proposal (not implemented)

The repeated keys describe the same message schema in seven languages; the translated values are
independent data. Removing those keys through positional arrays or a generic dictionary factory
would make translation maintenance harder without removing duplicate behavior.

Recommended follow-up: represent the 14 pure locale resources under
`apps/web-mirror/src/products/taskFinder/messages/` and `apps/web-mirror/src/app/homeMessages/`
as JSON, keeping each directory's TypeScript index and its existing
`Record<Locale, Shape<typeof en>>` contract. `resolveJsonModule` is already enabled. Preserve every
key and translated value, use ordinary static JSON imports, and keep the current consumer exports.
This separates resources from executable code and makes them usable by translation tooling without
introducing a loader, dependency or Sonar exclusion. Comments explaining a bundle belong in its
index; no translation text should be generated or silently replaced with English.

Retain the existing i18n tests for exact key sets, nonempty strings, ICU placeholder parity and
syntax, and untranslated whole-locale detection. Verify all locale values before/after migration,
then run web typecheck/lint, i18n and product tests, and a production build. Measure Sonar's result
after the next authorized push; changing the resource format is not evidence that duplication is
below the gate threshold.

Alternative: keep the current TypeScript dictionaries. This has zero migration cost and preserves
the present convention, but leaves the structural CPD findings. Either option is preferable to
reordering keys, splitting files, or adding exclusions solely to affect the metric. No dictionary
migration or analysis-setting change is part of the authorized code fix.

Follow-up verification: doctor passes; all E2E workspace packages pass typecheck and lint. All
five product smokes pass through their canonical runner commands: Task Finder 7, ProposalAI 10,
Client Update Writer 4, Brief Decoder 8, Acceptance Builder 11 (40 total), including accepted and
declined handoffs. Documentation validation, generated documentation drift and diff whitespace
checks pass. Generated-doc checking initially hit a LiteLLM import failure during its sandboxed
remote model-map fetch; the same command passed with network access. No dependency change was needed.
The refactor removes 225 net lines of test code. Full-check was not repeated for this test-only
extraction; its earlier sudo-dependent baseline failure remains documented above. No remote Sonar
analysis, commit, push or GitHub write was performed for this follow-up.

## Dictionary audit and proposed design — 2026-11-09

Status: proposal only, not approved for implementation. This supersedes the narrower 14-file
proposal above. The user requested a repository-wide dictionary audit and the smallest maintainable
solution; Sonar analysis and exclusions must remain unchanged.

### Evidence and ownership

The repository has nine web translation bundles, each with seven locale modules: 63 locale files
plus nine index modules. Locale-file contents total 2,682 lines including comments. The bundles are
host (33 message keys per locale), home (18), handoff (23), ProposalAI (29), Client Update Writer
(42 including imported tone labels), Brief Decoder (40), Acceptance Builder (26), Task Finder (35),
and shared tone labels (3). Extension `extensions/kernel-demo-ce/src/content/messages.ts` defines an IPC message contract, not
translations, and is outside the migration.

A read-only TypeScript AST inventory checked every locale, rejected duplicate object properties,
and confirmed identical key sets and nonempty values. The existing web i18n suite passes 32/32,
including placeholder parity, ICU syntax, plural behavior and locale fallback. The latest Sonar
analysis of 7ea42e4d reports zero new smoke duplication; all 364 remaining duplicated new lines are
translation structure. This is not evidence of repeated execution logic or untranslated locales.

Two concrete simplifications exist:
- `products/shared/toneMessages` has one real consumer, Client Update Writer's seven locale files.
  `TONE_MESSAGES` itself has no importer. ProposalAI deliberately uses different tone wording.
  Move those three values into Client Update Writer's own locale resources and remove the eight
  obsolete shared tone files. This preserves product ownership and removes indirection.
- Handoff's `capacityReserved` and host's `errors.quotaCapacityReserved` have identical translations
  in all seven languages and describe the same backend quota condition. Handoff already uses
  `useHostT`; render this condition from the host key and remove the seven handoff copies. Preserve
  the existing state transitions and the handoff-specific `actionFailed` message.

Other equal words occur in independent roles (mode/button/result heading, directory tag, field
label/validation name) or in different product domains. Do not join their keys merely because
English or all current translations happen to match. Some English-identical messages already have
different wording in other languages. Do not parameterize product action/error sentences or nouns:
that would introduce grammatical coupling. Runtime translation, fallback and locale storage already
have one implementation and do not need a replacement.

### Recommendation after the independent builder check

The smallest fix for actual duplication is to keep the current TypeScript representation and make
only the two ownership simplifications above. There is already one translation runtime; a generic
dictionary factory would add code without removing repeated behavior. Existing per-locale schemas
are useful data repetition. This recommendation supersedes the earlier unconditional JSON proposal.
It does not make the structural Sonar findings disappear, and that limitation must be explicit.

Minimal implementation plan, if authorized:
1. Put the existing tone labels directly into Client Update Writer's seven typed locale objects;
   delete the now-unused seven tone locale modules and their unused index.
2. Use the existing host translator for handoff's quota-capacity error; delete that key from the
   seven handoff dictionaries. Preserve the closed error state and re-localization behavior.
3. Update current frontend recipes/comments referencing the removed tone source. Keep historical
   execution-plan records intact. Add a focused handoff capacity-error locale-switch test.
4. Check effective values before/after, then run web unit tests, typecheck/lint/build, documentation
   checks and the Client Update Writer, Brief Decoder and Acceptance Builder smokes (tone and both
   accepted/declined handoff journeys). Retain the existing JSON-free validation approach.
5. Report results; only commit/push when authorized. Expect the known structural CPD findings to
   remain unless a separate representation decision is made.

### Optional uniform data-format migration

Choose this only if separating translation resources from executable modules is itself desired,
not merely as proof that duplicated behavior was fixed. This is the smallest reasonable JSON
migration, not the smallest code change. It has no demonstrated runtime speed benefit.

Use plain UTF-8 JSON per bundle and locale, preserving the existing directory ownership, nesting,
ICU strings and consumer exports. After folding tone into its sole consumer, there will be eight
bundles and 56 JSON resources. Retain eight small TypeScript index modules with explicit static
imports and the existing closed `Record<Locale, Shape<typeof en>>` contracts. Keep `HostMessages`
compatible. No dynamic imports, factory, message-reference DSL, code generation, new dependency,
new localization framework or Sonar exclusion is needed. Existing `resolveJsonModule` supports
these imports. Preserve explanatory ownership/grammar comments in the relevant bundle index or
frontend architecture documentation rather than discarding their decisions.

The benefit is a consistent data format and simpler ownership, not a guarantee that Sonar becomes
green. Repeated message keys across locales are the necessary schema of translation data. JSON
does not remove this data repetition; it removes executable-module scaffolding. The analyzer's
actual result must be measured after an explicitly authorized push.

Alternatives considered:
- Keep TypeScript and apply only the two concrete simplifications: smallest diff, existing
  conventions and object-literal excess-key checks preserved; structural CPD findings remain.
- Put all locales into one JSON file per bundle: fewer files/imports, but mixes translator work
  across languages and changes the current per-locale editing convention without a runtime benefit.
- A generic factory, positional translation arrays or reordered/split source blocks: rejected;
  adds runtime/type machinery or hides structure merely to change duplication metrics.

### Optional JSON migration: validation contract and implementation plan

1. Capture the currently exported message trees before migration. Compare every locale's effective
   values after conversion, allowing only removal of the handoff capacity key and relocation of the
   shared tone source; visible text must remain byte-for-byte identical. Do not retain snapshots or
   a permanent migration script as a second source of truth.
2. Convert all eight retained bundles mechanically, fold tone into Client Update Writer and update
   static index imports. Preserve their public exports and all product/host namespace boundaries.
3. Route the handoff capacity error through its existing host translator. Add a focused check that
   this error re-localizes while visible. Update frontend translation/add-locale recipes and comments
   that refer to the removed shared tone bundle or `.ts` locale resources. Historical execution-plan
   records remain historical; do not rewrite them.
4. Extend the existing i18n tests rather than adding a separate validator/framework. Check the exact
   recursive key structure (including empty objects), string leaves, locale completeness, placeholders
   and ICU syntax. Add one small raw-JSON duplicate-key assertion using the already-installed
   TypeScript parser; JSON.parse and the TypeScript compiler both silently accept duplicate JSON keys.
   Include a negative case with a repeated nested key to prove that assertion fails. Keep this parser
   in test code only. The import type contract still rejects missing/wrongly typed values; tests own
   extra-key detection. A local compiler experiment confirmed valid JSON passes, a missing key fails,
   and extra/repeated keys do not fail typecheck. Do not claim excess-property compile checks survive
   JSON imports unchanged.
5. Run web lint/typecheck, all web unit tests (including localization and handoff), production build,
   documentation checks and all five product smokes because every product's resources change.
   Verify no old locale/tone imports remain, then review the resulting diff. Do not change runtime
   versions or lockfiles. Do not modify CI/quality gates to accommodate the conversion.
6. Report results and any remaining warnings. Commit/push and any further GitHub write require the
   user's authorization. Recheck Sonar after an authorized push; no green-gate promise beforehand.

Potential implementation risks: dropped comments, accidental translation edits, a missed direct
locale import, loss of extra-key validation, or a hardcoded error string that fails to re-localize.
The plan above explicitly covers each. Native-speaker translation review and live-provider quality
are outside this structural audit. A new abstraction to prevent all repeated words is not a goal.


Audit completion: web i18n tests pass 32/32; the AST audit covered all 63 locale modules. A fresh
builder review found no important unresolved implementation questions and confirmed the ownership
simplifications, but correctly distinguished the minimal TypeScript fix from a larger JSON format
migration. No product source, tests, configuration, dependencies or Sonar settings changed during
this audit. Only this execution plan and the local task plan were updated.

## Authorized TypeScript dictionary simplification — 2026-11-09

The user approved only the two minimal ownership simplifications and their verification. Keep all
locale resources in TypeScript; do not implement the optional JSON design or modify Sonar settings.
Doctor passes. Follow the minimal implementation plan above, preserving all effective translations
and checking capacity-error re-localization before retry. The earlier audit-only status records the
previous turn; implementation is now authorized.

Implementation complete: Client Update Writer owns its three tone labels in each typed locale;
the eight shared tone files are removed. Handoff renders occupied-capacity errors from the existing
host translator, with its seven duplicate entries removed. Current recipes and ownership comments
are updated; no locale format, Sonar rule, exclusion, dependency or runtime version changed.

Verification: all effective translations match their pre-change values; the removed handoff values
match the host key in all seven locales. All 478 web unit tests pass, including the extended retry
case that switches the visible capacity error through every locale and retains the same handoff and
guest for retry. Web typecheck and lint pass. Three canonical product smokes pass: Client Update
Writer 4, Brief Decoder 8, Acceptance Builder 11 (23 total), including accepted and declined handoffs.
Each smoke's production build passes. Doctor, architecture/documentation validation, generated-doc
checks and diff whitespace checks pass. Initial standalone typecheck overlapped the first smoke's
recreation of `.next` and reported missing generated files; rerunning after all builds passed without
source/config changes. No additional unit-test rerun was needed.

Full-check was not repeated for these frontend-only changes; the earlier sudo-dependent baseline
failure remains documented. No commit, push or GitHub write was performed in this implementation
turn. Structural dictionary CPD findings remain expected; no new Sonar analysis was requested.

## Whole-project duplication inspection — 2026-11-09

The user requested analysis across the monorepo as one project. This is a read-only code review;
no additional implementation was authorized. The previous two dictionary cleanups did not solve
the remaining structural CPD findings.

Latest PR analysis: revision 27a6615a, 2026-11-09 14:46 UTC. New duplicated lines are 371 / 1,444
(25.7%): Task Finder locale modules 336, home locale modules 28, and the newly inlined Client Update
Writer tone entries 7. Queried duplicate-block details for all 21 affected files: three block groups,
each matching the seven locale versions within its bundle. Smoke files have no new duplication.
Sonar already compares the entire repository under a single project key; merging source folders
or presenting the products as one project does not change these matches.

Separately inspected all 967 file measures in the latest main analysis (72ff15bc, 2026-11-08 16:28
UTC). This is baseline evidence, not the PR's new-code metric. Nonzero duplicated-line counts:
- tests: 4,604 lines in 46 files;
- translations: 2,071 lines in 49 files;
- generated OpenAPI TypeScript: 2,004 lines in one file;
- other source: 408 lines in nine files;
- migrations: 346 lines in six files.
These are analyzer counts, not a claim that every block is an actionable defect. Main and PR
analyses are different revisions and must not be added together.

Confirmed current-source cross-module reuse candidates:
1. `_EXTRACT_FIELDS` has exactly equal parsed values in six modules: platform-worker's
   `test_worker_boot.py` and `test_worker_claim_postgresql.py`; platform-api's
   `test_composite_workflow_matrix.py` and `test_scenario_runtime_api.py`; platform-core's
   `test_action_runner.py` and `test_workflow_runner.py`. A shared test fixture belongs in test
   support, preserving independent mutable inputs for each test rather than sharing mutable state.
2. Brief Decoder and Acceptance Builder parsers repeat `isRecord`, `isStringArray` and `isOneOf`.
   Task Finder repeats the first two under `record` and `strings`. Shared structural guards can
   serve these real callers; product-specific closed enums, ordering and copy contracts must stay
   product-owned. `ce-kit/src/api/parsing.ts` has a different `isRecord` contract (allows arrays),
   so importing it as a supposedly equivalent helper would weaken product validation.

Generated OpenAPI code must remain generated; historical migrations must remain reproducible and
must not import evolving runtime table definitions merely to remove duplicated column declarations.
Neither is permission to add Sonar exclusions. Fixing the confirmed source/test candidates will not
eliminate the 371 translation lines in the PR metric. Any further dictionary model change needs a
separate concrete design consistent with the user's requirement to retain TypeScript. No new
source/config edits, test runs, commit, push or GitHub writes were made during this inspection.

## Approved resource direction and whole-project remediation design — 2026-11-09

The user requested remediation of Sonar findings first and the other confirmed duplicates too,
across the monorepo. They explicitly approved JSON for translated text with TypeScript contracts,
superseding the earlier TS-only constraint. Analysis rules, gates and exclusions remain unchanged.
The detailed optional JSON migration contract above now supplies the resource migration design.

Execution order and boundaries:
1. Convert all 56 remaining locale resources to JSON, preserving every effective value and the eight
   existing named TypeScript bundle exports. Preserve comments explaining translation semantics in
   bundle indexes/current documentation. Keep static imports and existing locale/provider APIs.
   Strengthen current i18n tests with exact recursive structure and raw duplicate-key checks using
   the already-installed TypeScript parser; no runtime parser/framework/dependency is added.
2. Extract identical structural guards used by the three web product parsers into a product-shared
   utility. Preserve rejection of arrays as records. Keep enum membership policy, criterion order,
   schema-specific validation and rendering/copy semantics local. Do not silently substitute the
   less strict ce-kit record guard.
3. Replace the six identical `_EXTRACT_FIELDS` lists in API, worker and core tests with one shared
   test-support function returning fresh mutable data. Do not share mutable state between tests.
4. Consolidate job repository transitions through one private implementation parameterized by
   required source status and target status, preserving atomic UPDATE predicates, validation,
   idempotent replay, not-found errors and status-conflict failures. Preserve public methods.
5. In workflow recovery, share the repeated decision to release an existing terminal reserved job
   while preserving row locks, transaction ownership and distinct failure/cancellation recovery. The
   Sonar main-line offsets point at recovery code, not error-message redaction; do not refactor an
   unrelated sanitizer. For the JS scope resolver, share only the chronological/filtering
   mechanics of write replay; keep possible-value and definite-presence reductions separate. Both
   consumers are real and covered by the architecture validation tests; no general callback framework.
6. Review remaining Sonar categories against current source before changing them. Tests can reuse
   setup/fixtures and parameterize genuinely identical cases, never delete independent assertions
   merely to reduce the counter. Generated TypeScript is changed only through its source generator
   or canonical OpenAPI definitions when the representation can safely improve. Historical migration
   table declarations and independent SDK/runtime representations are not blindly merged: immutable
   migration history, schema compatibility, dataclass/Pydantic behavior and package boundaries take
   precedence over eliminating every textual match. Record any justified remaining match explicitly.

Validation: compare before/after messages, all web tests, typecheck/lint/build, generated docs/types
checks, all five product smokes after resource migration, focused Python/JS regression tests for
changed helpers, and PostgreSQL-backed transition tests with an explicitly provisioned test DB.
Use the canonical repository runners where applicable. Do not accept skipped DB tests as evidence.
Run broader gates after focused checks; document existing environment failures honestly.
No claim of a green Sonar gate until a new remote analysis. Commit/push/GitHub writes still require
explicit authorization. The broad baseline inventory is a prioritization source, not proof that all
9,433 baseline duplicated lines are defects or safe to mechanically refactor.


## Implemented JSON resources and shared logic — 2026-11-09

- Migrated all 56 dictionaries (eight bundles, seven locales) to JSON. An exact before/after
  comparison verified every effective key and string. Named TypeScript exports, locale records,
  required-key/value typing, fallback, ICU validation and product ownership remain intact.
  Added strict JSON, repeated/escaped key and exact recursive structure checks; documented the
  JSON/TypeScript contract and retained translation guidance in bundle indexes.
- Shared structural guards now serve Brief Decoder, Acceptance Builder and Task Finder without
  weakening array rejection, product enums or result ordering. All 481 web tests, ESLint and
  TypeScript checks passed.
- Replaced six copied A01 field definitions with a fresh-data helper. Also updated the seventh
  consumer in worker lease recovery, which previously imported another test module's constant.
  The isolation regression passed. Initial runs caught a missing import and the seventh consumer;
  both are fixed and their affected suites were rerun.
- Consolidated job transitions and failure normalization while preserving public methods,
  source-state UPDATE predicates, idempotent replay and conflict errors. Added regression coverage
  for created/running source states and replay; all nine JobRepository cases passed on PostgreSQL.
- Shared the terminal reserved-job recovery decision. Both failure and cancellation recovery are
  exercised against a competing successful commit, preserving consumed quota. The API/finalization
  and new transition regression run passed 73 tests; the expanded competing-transaction cases
  passed separately. The other changed backend suites passed 158 tests in the initial combined run.
  Worker lease recovery passed all five tests, including an actual SIGTERM subprocess.
- Shared write-replay iteration in the JS analyzer while retaining its distinct value/presence
  reductions. Architecture regression matrix: 242 passed; import-validator/helper checks: 27 passed.
- All five browser suites passed after migration: ProposalAI 10, Client Update Writer 4,
  Brief Decoder 8, Acceptance Builder 11 and Task Finder 7. Each ran against a production web build
  and the local API/worker/PostgreSQL stack. Generated documentation and OpenAPI types are current;
  config, architecture and documentation validators passed. No Sonar settings or exclusions changed.

Environment: LiteLLM's remote model-cost fetch intermittently timed out during import, including
in a worker subprocess. The verification commands use its supported
`LITELLM_LOCAL_MODEL_COST_MAP=True` option to load the installed table. This is a command-local
setting, not a source/dependency/config change or skipped check. The canonical baseline rerun
completed: 3,576 passed, 12 skipped, 657 deselected, one warning and one failure. The sole failure
is the unchanged activation-marker permission test: `sudo: interactive authentication is required`.
No baseline assertion, skip or host privilege policy was changed. The broader full-check wrapper
therefore remains blocked by its baseline stage; affected frontend and PostgreSQL checks passed
separately as recorded above. The development containers were stopped with volumes preserved.
Existing Ruff findings remain outside this refactor; comparison against HEAD found no added
findings after wrapping the modified long input lines.

Remaining intentional matches: generated OpenAPI declarations remain generator-owned; historical
migration declarations remain immutable; provider request and SDK/runtime event representations
retain their different contracts and package boundaries. Independent test assertions are retained.
These categories are not exclusions, and this work does not claim that every baseline textual match
has disappeared. A new remote Sonar analysis is still required to establish the PR metric and gate.
No commit, push or GitHub write was performed for this follow-up.
