# Execution Plan: ANY-844 Data Processing Notice

## Status

- State: completed
- Owner: agent
- Created: 2026-11-12
- Last updated: 2026-11-12
- Review date: 2026-11-12
- Next action: Owner review; configure the approved public policy URL before deployment.
- Blocker: Approved production policy URL remains operator-owned; code is not blocked.

## Goal

Show a visible processing explanation and configured privacy-policy link before submit in every
shared product form, including ProposalAI, Brief Decoder and all Client Update Writer modes.

## Scope

Shared notice, seven host locales, HTTP(S) URL validation, build configuration, documentation,
component/product regression tests and responsive browser verification. No backend, database,
provider, retention, legal-acceptance or product-specific behavior changes.

## Baseline and data handling

- Checked branch `feature/ANY-844`, commit `b48eaaceaf36338683e529538982ccad78116183`, Linux,
  Node 24.22.1, managed Python 3.12.13.
- Code reproduction: the ready form renders fields followed directly by the submit footer, with
  no processing explanation or privacy-policy link. All five products use this shared form.
- Submitted input reaches Platform API, is stored in PostgreSQL as scenario `input_payload`,
  and is processed through Provider Gateway by an AI model provider. Results are also stored.
- Drafts remain tab-local; products opting into draft persistence use sessionStorage. Client
  events exclude user text. No retention/deletion period is implemented or promised.

## Implementation steps

- [x] Add optional build-time privacy URL helper accepting only absolute HTTP(S) URLs.
- [x] Add notice copy in all seven host locales and a shared, accessible component using existing tokens.
- [x] Render before submit in ProductRunPage; associate submit using aria-describedby.
- [x] Wire Docker/Compose build arguments and document required public-deployment configuration.
- [x] Test URL boundaries, translations, translation-safe markup, placement, run phases and product modes.
- [x] Run frontend, baseline and documentation checks; verify 360, 393 and 1280 px layouts in EN/RU.

## Verification

- Initial system-Python doctor failed: pytest and pydantic missing from Python 3.14.4.
  Use the repository-managed Python 3.12 environment for subsequent checks.
- Managed Python doctor passes using Python 3.12.13 and the already cached pinned pnpm 10.34.1.
- Web-host Vitest: 28 files, 698 tests pass, including 25 added cases. Workspace lint/typecheck pass.
- Documentation validation and generated-documentation drift checks pass.
- Chromium: 30 combinations pass on the real Next dev host with mocked API boot responses:
  ProposalAI, Brief Decoder and all three Client Update Writer modes, each in EN/RU at
  360×800, 393×852 and 1280×800, deviceScaleFactor 1. Checked notice before submit, wrapped text,
  no horizontal overflow, aria-describedby, Tab navigation, 2px visible focus ring and new-tab
  navigation. No page exceptions. Inspected RU mobile and desktop screenshots; spacing needs no
  adjustment. This is frontend evidence, not a live backend/provider or production-policy check.
- Full-check reached the complete backend baseline: 3,576 passed, 12 existing conditional skips,
  657 deselected; one failure in
  `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user` because
  `sudo -n -u nobody` requires interactive authentication here. This environment cannot satisfy
  that prerequisite. Full-check stops at this failure, so its later stages are not claimed green.
- Frontend-check lint/typecheck pass; its parallel test stage hit the existing CE-kit ESLint
  configuration test’s 5-second timeout. That unchanged test passes alone in 1.35 seconds.
  Serial workspace tests pass: CE-kit 336, shared UI 55, web host 698, Atom Lab 57 unit
  and 339 browser tests, plus stakeholder-demo tests. Generated API-contract drift check passes.
- Web production build passes on retry after Next’s automatic type installation completed.
  Initial build failed after that installation changed dependency resolution mid-build;
  the unchanged source passed on retry, consistent with a transient dependency-setup issue.
  Other workspace builds reached before that failure pass; workspace-wide typechecking passes. No new dependency is retained in manifests or the lockfile.
- Initial sandboxed broad runs were interrupted after local-server restrictions caused
  failures/stalls; the results above come from unrestricted local runs.
- Next dev attempted to auto-install Node type declarations; restored its unrelated manifest and
  lockfile edits. No dependency change is part of this task.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-12 | Use existing TypeScript frontend, confirmed by user | The requested behavior belongs to React; Python remains the check entrypoint. |
| 2026-11-12 | Keep current feature branch | Existing task branch is already checked out. |
| 2026-11-12 | Reuse design tokens and form spacing | Visible secondary copy, underlined link and accent focus ring fit the existing UI. |
| 2026-11-12 | Leave missing policy URL unset | No approved production URL is supplied; no placeholder is shipped. |

## Open questions and follow-up

- Operator must supply ANYTOOLAI_PRIVACY_POLICY_URL for public deployment and rebuild web-mirror.
  The notice remains visible when the link is absent or invalid.
- Native-speaker review of new translations remains a release consideration.
- Previously reported browser-translation crashes and Honor 50 run failures are separate issues;
  this task checks its own markup and does not claim to resolve those reports.
- Publishing to GitHub requires explicit user approval under the repository's personal rules.

## Completion

Implementation and scoped verification completed on 2026-11-12. The baseline sudo prerequisite
remains an environment limitation, not a passed check. The production URL and native-speaker
translation review remain operator/product-owner follow-up. No GitHub or Linear write occurred.

The repository-wide prohibited-phrase scan also found pre-existing matches in unrelated execution
plans; this ticket introduces none and leaves those plans unchanged.
