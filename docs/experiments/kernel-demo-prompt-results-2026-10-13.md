# Kernel Demo: selected prompt results

The working templates in `configs/kernel/products/kernel_demo/prompts/` now contain the selected
Atom Lab variants: **A07 D1, A09 C, and B1 for the other atoms**. A06 is unchanged. B1 means the
frozen B variant from the first prompt-improvement experiment. These are experimental variant
names, not new runtime prompt references: existing `.v1` references, schemas, and action configs
remain in place. Models, SDK dependencies, routing, other product prompts, and deployment are
outside this change.

## Selection

| Atom | Variant | Decision |
|---|---|---|
| A01 | B1 | Resolve dates only from supplied evidence; preserve missing fields, zero and false. |
| A02 | B1 | Retain the tested locale rules; no additional semantic rewrite. |
| A03 | B1 | Retain the tested prompt; separate task correctness from unanchored score magnitude. |
| A04 | B1 | Retain the tested locale rules; no additional semantic rewrite. |
| A05 | B1 | Retain the tested locale rules; historical delivery/launch ambiguity remains. |
| A06 | B1 = original A | Unchanged control. |
| A07 | D1 | Determine completed prerequisites from the situation; request only missing ones. |
| A08 | B1 | Preserve roles, timing and commitment strength across rewrites. |
| A09 | C | Omit unsupported optional fields; retain a separately supported secondary angle. |
| A10 | B1 | Keep supplied facts separate from inferred causes, blockers and proposals. |
| A11 | B1 | Preserve locale and distinguish broad capability from a confirmed operation; C remains unselected. |

Generated human-facing fields use the requested locale or the main input language. Schema keys,
enums, supplied options, identifiers, names and permitted source quotations retain their original
form. This locale rule was not added to the unchanged A06 control.

## Evidence used for selection

The paid experiments used GPT-6 Luna and GPT-6.1 Sol with reasoning medium and RU/ES/EN inputs.
Semantic ratings are **agent_review**, without human calibration or a native Spanish reviewer.
Contract validation and semantic interpretation are reported separately.

- **A01 B1:** 18/18 follow-up cases passed, covering explicit years, document-year context and
  missing years. Price=0 and approved=false were preserved; positive dates were not rejected.
- **A09 C:** 12/12 primary cases and 4/4 additional trials passed. Unsupported `secondary_angle`
  was omitted; all six supported-secondary primary cases retained it. No validation retry was
  needed. Fresh B1 had one structured-output failure with a last debug output containing an
  empty secondary string. Debug output is not an accepted response.
- **A11:** B1 and C both passed the fresh language/grounding checks. C superiority was not
  demonstrated, so B1 remains selected. The historical CSV support/export fixture is ambiguous;
  foreign source quotation emission was not directly exercised.
- **A08/A10:** retain the preceding B1 changes; the final targeted run did not retest them or
  A02/A04/A05/A06. No new whole-package paid E2E result is claimed.

### A07 B1 versus D1

The comparison reused six exact inputs: `missing_access` and `fulfilled`, each in RU/ES/EN,
with warm tone, plain_text and max_length=320. Two models, one reasoning setting and two prompts
produced 24 primary runs. Six additional runs were three B1/D1 pairs for Luna/RU/missing_access.
Within each pair only the prompt changed; primary order was balanced, six pairs per first variant.

| Check | B1 | D1 |
|---|---:|---:|
| Primary accepted outputs | 12/12 | 12/12 |
| Primary fully usable outputs | 9/12 | 12/12 |
| Missing-access fully usable outputs | 5/6 | 6/6 |
| Fulfilled fully usable outputs | 4/6 | 6/6 |
| Additional fully usable outputs | 2/3 | 3/3 |
| Scope reconfirmation defects: primary / additional | 1 / 1 | 0 / 0 |

B1/Luna/EN made the start depend on confirmation of already agreed scope. One B1/Luna/RU repeat
explicitly requested that confirmation again. D1 requested only missing access and kept the start
conditional on its receipt. All six D1 positive cases confirmed the Thursday start on both models
and all three languages. Both prompts preserved the prerequisite logic in all positive cases;
two B1/Luna positive responses were separately partial for unsolicited future-update commitments.

No D1 language, fact, length, format, prerequisite or positive-case regression was observed.
Luna primary usability was 3/6 to 6/6; Sol was 6/6 for both prompts. Successful repeats did not
replace primary ratings. All 30 runs used one physical attempt each, with no retries. Their known
ledger cost estimate was $0.0259506, not an invoice. This comparison supports selecting the exact
tested D1; it does not establish a general failure rate or statistical superiority.

### A03 measurement

One rubric was applied offline to all 24 historical A/B1 outputs. Task, structure, commentary
facts and language passed. Exact numeric score magnitude remains uncertain because the contract
does not define intermediate numeric anchors. This uncertainty is not a factual error or a task
failure and must be shown separately rather than resolved by requiring higher scores.

The revised historical medium comparison, with score magnitude reported separately, was
Luna 52/66 to 60/66 and Sol 60/66 to 63/66. These are the preceding whole-corpus A/B1 comparisons,
not the new A07 subset; revising A03 ratings corrected measurement rather than model output.

## Provenance and limits

Local source runs: `20261013-kernel-prompt-improvement-01`, `20261013-kernel-prompt-followup-01`
and `20261013-a07-selection-01`. Selected working files were copied exactly and checked against
the stored submitted-prompt SHA256 values. Raw inputs, replies, ledgers and intermediate prompts
remain local and are not part of this change. The source conversation is
[Kernel Demo experiments](codex://threads/01a1353d-1fd6-7551-b4cd-44ee4110dbd2).

The corpus is small, targeted and reused, not a randomized holdout. A07 D1 was tested on two input
families; its behavior with missing scope or other situations was not freshly established.
These findings do not establish production-product prompt quality. New API/worker processes load
the updated Kernel Demo files; this repository change does not deploy or restart running services.

## Adoption checks

Validated in an isolated checkout based on main `0c81cc65`, without the local SDK/Gateway changes
or experiment archive. ConfigLoader content hashes match all eleven selected snapshots; A06 is
unchanged. Doctor, config/architecture/docs validation and generated-doc drift checks passed.
The canonical quick-check passed: 2185 tests passed, 7 skipped and 485 deselected by `not slow`.
It includes loader and Kernel Demo smoke-harness tests; a new live-provider or whole-stack Compose
run was not performed for this adoption. No additional paid requests were made.
