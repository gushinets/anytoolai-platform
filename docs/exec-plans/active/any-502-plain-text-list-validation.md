# Execution Plan: ANY-502 plain_text Cross-Validation Rejects Valid CommonMark List Output

## Status

- State: active
- Owner: agent
- Created: 2026-09-17
- Last updated: 2026-09-17
- Review date: 2026-09-18 (code review rounds 1-3)
- Next action: await round-4 review; move to `completed/` once merged.
- Blocker: none

## Goal

`PersuasiveTextCrossValidator` (A06 `compose_persuasive_text`) and `ComposeReplyCrossValidator`
(A07 `compose_reply`) rejected any recognized CommonMark markup for `plain_text`/omitted format,
including ordered/unordered lists — even though the frontend renders `text` as literal
`pre-wrap`, so a CommonMark list would have displayed fine. A live model (`gpt-5.4-nano`) naturally
reaches for numbered lists on multi-item asks and was rejected twice, burning quota with a generic
error each time (found during ANY-501). Team lead decision: relax the `plain_text` contract to mean
"copy-ready text", allowing list markers while still rejecting bold/headers/links/code/tables/
blockquotes/HTML.

## Scope

### In scope

- New `_has_disallowed_plain_text_markup()` helper in `_markup.py`, extending the existing
  plain-text token allowlist with the six list-container token types
  (`ordered_list_open/close`, `bullet_list_open/close`, `list_item_open/close`). The existing
  `_has_markup`/`_has_markdown`/`_has_html_construct`/`_has_html_tag` are untouched.
- Switch the `text` plain-text check in `persuasive_text.py` (A06) and `compose_reply.py` (A07,
  `text` field only) to the new helper.
- `compose_reply.py`'s `call_to_action` check keeps calling `_has_markup` unchanged — it stays
  under the stricter no-markup contract.
- Update the 3 prompts using the "must contain no markup" wording (re-grepped repo-wide; confirmed
  exhaustive, no Client Update Writer or other product overrides this prompt today):
  `configs/kernel/products/kernel_demo/prompts/compose_persuasive_text.v1.md`,
  `configs/kernel/products/kernel_demo/prompts/compose_reply.v1.md`,
  `packages/backend/product-platforms/freelancer-suite/.../proposal_ai/prompts/compose_persuasive_text.v1.md`.
- Regression tests in `test_cross_validation.py` for both validators: list-acceptance cases
  (`1.`/`1)`/`-`/`*`/`+`, multi-paragraph), a blockquote reject case (no prior pin existed), a
  list-item-with-nested-markup reject case, and (A07 only) a `call_to_action`-with-list-syntax
  reject case proving the `text`/`call_to_action` asymmetry is real, not incidental.
- (Round 1 fixes) `_has_disallowed_plain_text_markup()` also rejects: an empty list item (`-`,
  `1)` with no real content) and a GFM task-list checkbox (`- [ ] todo`, not tokenized as such by
  this parser but not a plain list marker either). `_has_markdown`/`_has_disallowed_plain_text_markup`
  now share one `_tokenize_markdown()` parse pipeline instead of two independent copies.
- (Round 2 fix) The checkbox regex now also matches a *bare* checkbox with no task text after it
  (`- [ ]`, `- [x]`) — round 1's regex required trailing whitespace, so a checkbox with nothing
  after it fell through as accepted. A dead `next_token is None` branch (unreachable —
  markdown-it-py guarantees balanced open/close tokens) was removed.
- (Round 3 reversal) Nested lists (`- Parent\n  - Child`) are now **accepted**, not rejected.
  Rounds 1-2 had added a nesting-depth gate (first via a manual counter, then via
  `token.level != 0`) on the reading that the Linear decision's examples were all flat. Round 3
  review disputed this as narrower than the actual decision text ("ordered/unordered list
  markers", no stated depth limit) and the product owner confirmed: allow nesting. The gate is
  removed; disallowed markup nested inside a sub-list item (e.g. `- Parent\n  - **Child**`)
  still rejects via that markup's own token type, independent of nesting depth.

### Out of scope

- Quota-consumption timing (`quota.consumed` fires at `scenario.started`, before provider call).
- User-facing validation-error specificity/messaging.
- Any change to `_has_markup`/`_has_markdown`/`_has_html_construct`/`_has_html_tag` semantics.
- Any other atom (A01-A05 don't touch `_markup.py`).
- Live-provider replay of the original reproduction — requires a real `OPENAI_API_KEY`, not
  available in this sandbox (same blocker ANY-501 documented); left as an operator follow-up.

## Relevant docs

- `docs/exec-plans/completed/any-501-proposalai-live-provider-validation.md`'s "Follow-up debt"
  section (original reproduction evidence).

## Contracts touched

- Prompt wording only (no schema/wire-contract change). `structured_output_validation_failed`
  stays the one machine error code; reason strings (`text_contains_markup_for_plain_text_format`,
  `call_to_action_contains_markup_for_plain_text_format`) are unchanged strings, only their trigger
  condition narrows for `text`.

## Implementation steps

- [x] `_markup.py`: added `_PLAIN_TEXT_WITH_LISTS_TOKEN_TYPES` and
      `_has_disallowed_plain_text_markup()`.
- [x] `persuasive_text.py`: `text` check switched to the new helper; import updated.
- [x] `compose_reply.py`: `text` check switched to the new helper; `call_to_action` check left
      calling `_has_markup` unchanged; import updated.
- [x] 3 prompts updated to the team lead's suggested wording (adapted per field name).
- [x] Regression tests added to both `TestPersuasiveTextCrossValidator` and
      `TestComposeReplyCrossValidator` (`test_accepts`/`test_rejects`).

## Validation

- [x] `uv run pytest packages/backend/platform-actions/tests/test_cross_validation.py -k "PersuasiveText or ComposeReply"` — 120 passed (104 before round 1, 112 before round 2, 118 before round 3).
- [x] `uv run pytest packages/backend/platform-actions/tests/test_cross_validation.py` — full file green (239 passed).
- [x] `python scripts/agent/runner.py validate-configs` — passed.
- [x] `python scripts/agent/runner.py quick-check` — 1368 passed (1352 before round 1, 1360 before round 2, 1366 before round 3).
- [ ] `python scripts/agent/runner.py full-check` — not run this session (quick-check already
      covers the affected backend suite and config/architecture/docs validation; full-check adds
      frontend checks and product-suite tests untouched by this change).
- [ ] Live replay of the original multi-item reproduction — blocked, no `OPENAI_API_KEY` in this
      sandbox; follow-up for an operator with live credentials.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-17 | New `_has_disallowed_plain_text_markup()` function instead of modifying `_has_markdown`/`_PLAIN_TEXT_TOKEN_TYPES` in place. | Ticket explicitly requires not changing the existing generic helper's semantics — it's still used by the `html`/`markdown` format branches and `call_to_action`. |
| 2026-09-17 | Only A06/A07 `text` switched; A07 `call_to_action` left on `_has_markup`. | Team lead's explicit instruction: a short call-to-action has no reason to carry list formatting, and the ticket's own regression list implies this asymmetry (list syntax must still reject somewhere to prove the two checks diverge). |
| 2026-09-17 | Reason strings (`text_contains_markup_for_plain_text_format` etc.) left unchanged. | Ticket defers user-facing error specificity to a separate follow-up; only the trigger condition narrows, not the machine reason string. |
| 2026-09-17 | Round-1 review findings #1-3 (empty list items, GFM task-list checkboxes, nested lists all wrongly accepted) fixed by walking the token stream once with list-depth tracking, an empty-item check, and a regex match on each item's leading inline content, rather than a bare token-type allowlist. | Live repro against the real parser confirmed all three: a plain type-allowlist can't see "list item has zero content" or "list nesting depth", and this parser doesn't tokenize GFM checkboxes as a distinct construct at all (no task-lists plugin loaded), so `[ ]`/`[x]` needs its own regex check. |
| 2026-09-17 | Findings #4 (text/call_to_action asymmetry) and #6 (link-reference-definitions gap) left as-is; #5 (asymmetric combining-mark escape) left as-is. | #4 is the deliberate, tested design (documented in prompt/tests/exec-plan already). #6 is a pre-existing gap in `_has_markdown` itself (inherited, not introduced by this diff) — fixing it would change the untouched generic helper's semantics, out of this ticket's scope. #5 is reviewer-confirmed but synthetic/unlikely in real text (a combining mark immediately after `*` with no base character before it) and also pre-existing in shared escaping logic. |
| 2026-09-17 | Findings #7 (short-circuit) and #8 (duplicated parse pipeline) fixed together via a shared `_tokenize_markdown()` helper; the HTML check now runs first in `_has_disallowed_plain_text_markup` too. | Both were cheap, safe simplifications with no behavior change for existing cases — reduces the risk a future edit touches one function's parse pipeline and not the other's. |
| 2026-09-17 | Finding #9 (missing asymmetry comment) fixed with an inline comment at the `call_to_action` check site. Finding #10 (prompt sentence duplicated across 3 files) left as-is. Finding #11 (duplicated test cases) fixed via shared `_PLAIN_TEXT_LIST_ACCEPT_CASES`/`_PLAIN_TEXT_LIST_REJECT_CASES` module-level constants reused by both test classes. | #10 has no existing shared-prompt-fragment mechanism in this repo; introducing one for 3 nearly-identical sentences would be a speculative abstraction (YAGNI) — left as documented, minor duplication. #11 was a same-file, mechanical dedup with no design cost. |
| 2026-09-17 | Round-2 review: fixed a real gap the round-1 checkbox regex left — a *bare* checkbox with no task text (`- [ ]`, `- [x]`) was still accepted, because `^\[[ xX]\]\s` required trailing whitespace. Regex widened to `^\[[ xX]\](?:\s|$)`. | Live repro confirmed `- [ ]`/`- [x]`/`"1. [ ]\n2. real item"` all returned `False` (accepted) before the fix, `True` after — root cause was the regex only covering "checkbox followed by more text," not "checkbox is the entire item." |
| 2026-09-17 | Round-2 review: simplified nesting detection to check the parser's own `token.level` (0 for a genuinely top-level list container) instead of a hand-maintained `list_depth` counter; removed the `next_token is None` defensive branch after `list_item_open`. | Live repro confirmed `token.level` already encodes nesting depth (nested `bullet_list_open` is `level=2`, not `0`), making the manual counter redundant. The `None` branch is unreachable — markdown-it-py's token stream always pairs every `_open` with a `_close}`, so `list_item_open` can never be the last token; a task-list-plugin dependency to replace the whole regex approach was considered and declined as unnecessary weight for this one narrow false-negative (YAGNI). |
| 2026-09-17 | Round-2 review's prompt-wording note (#3) required no change. | The 3 prompts already phrase the disallowed-markdown list with "such as" (non-exhaustive framing) from round 1, which already covers constructs not explicitly named (horizontal rules, strikethrough, autolinks, hard line breaks) that the validator still rejects. |
| 2026-09-18 | Round-3 review: reversed the round-1/round-2 nested-list rejection — nested ordered/unordered lists are now accepted, matching the Linear decision's literal wording (no stated depth limit) rather than the narrower "flat lists only" reading rounds 1-2 had assumed from its examples. | Genuine product/scope ambiguity, not a clear-cut implementation bug — flagged to the product owner rather than resolved unilaterally a third time; owner confirmed nesting should be allowed. Disallowed markup nested inside a sub-list item still rejects independently (via that markup's own token type), so the "list structure allowed, markup inside items still isn't" invariant is unchanged. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-17 | Implemented allowlist extension, switched A06/A07 `text` call sites, updated 3 prompts, added regression tests for both validators. `quick-check` and targeted pytest green. | Await code review. |
| 2026-09-17 | Code review round 1 found 3 critical regressions (empty list items, GFM checkboxes, nested lists all wrongly accepted) plus several lower-severity dedup/comment findings. Fixed the 3 critical ones with an explicit token-stream walk (list-depth tracking, empty-item check, checkbox regex); fixed the cheap dedup/comment findings (short-circuit ordering, duplicated parse pipeline, missing asymmetry comment, duplicated test cases); left the text/call_to_action asymmetry, the pre-existing combining-mark escape asymmetry, the pre-existing link-reference-definition gap, and the duplicated prompt sentence as documented, reasoned skips (see Decision log below). Re-verified: `TestPersuasiveTextCrossValidator`/`TestComposeReplyCrossValidator` (112 passed), full `test_cross_validation.py` (231 passed), full `quick-check` (1360 passed). | Await round-2 review; run `full-check` before merge. |
| 2026-09-17 | Code review round 2 found a real gap the round-1 checkbox fix left behind (a bare checkbox with no task text still passed) plus two code-quality simplifications (use `token.level` instead of a manual depth counter; drop a genuinely unreachable defensive branch) and confirmed the prompt-wording note needed no further change. Fixed the checkbox regex and both simplifications; added 3 new bare-checkbox reject cases to the shared test constant. Re-verified: `TestPersuasiveTextCrossValidator`/`TestComposeReplyCrossValidator` (118 passed), full `test_cross_validation.py` (237 passed), full `quick-check` (1366 passed). | Await round-3 review; run `full-check` before merge. |
| 2026-09-18 | Code review round 3 (inline PR comment) disputed the round-1/round-2 nested-list rejection as narrower than the actual Linear decision text. Flagged to the product owner as a genuine scope question rather than resolved unilaterally; owner chose to allow nesting. Removed the `token.level != 0` gate; moved the nested-list case from reject to accept and added a nested-item-with-disallowed-markup reject case. Re-verified: `TestPersuasiveTextCrossValidator`/`TestComposeReplyCrossValidator` (120 passed), full `test_cross_validation.py` (239 passed), full `quick-check` (1368 passed). | Await round-4 review; run `full-check` before merge; still need to reply to the GitHub inline review comment (not done — separate ask). |

## Open questions

- None.

## Follow-up debt

- Live-provider replay of the original multi-item scenario against a real provider — needs an
  operator with `OPENAI_API_KEY` (same constraint ANY-501 hit).
- Quota-consumption timing and user-facing validation-error specificity remain open, tracked
  separately per the ticket's own scope note (not filed as new tickets by this session).
