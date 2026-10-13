# kernel_demo.synthesize_angle.v1

Synthesize a strategic recommendation from `signals` (each with `id`, `label`, `value`, and
optional `evidence`) toward the given `objective`. Return:

- `angle`: the primary recommendation. If `options` is non-empty, `angle` must be exactly one of
  the given `options`; if `options` is empty or omitted, phrase a concise recommendation yourself.
- `rationale`: a concise explanation tied to the supplied `signals`. State the conclusion and the
  supporting signals directly — do not narrate step-by-step reasoning, alternatives considered, or
  any other chain-of-thought.
- `secondary_angle` (optional): a second-choice recommendation, subject to the same `options`
  constraint as `angle` when `options` is non-empty.

Do not invent signals, goals, or constraints beyond what `signals` and `objective` provide.

Language for user-facing fields:

- Use an explicit input language constraint when present; otherwise use the language of the
  main input text. Apply it to every generated human-facing string, including explanations,
  rationales, commentary, titles, summaries, labels, extracted descriptive strings and array items.
- Keep schema keys, required enums, supplied option/taxonomy values, IDs, proper names, technical
  identifiers and permitted source quotations unchanged. They are not language violations.

Ground both recommendations:

- Include secondary_angle only if supplied signals independently support that recommendation;
  membership in options alone is insufficient. Omit it when that support is absent.
- An observed numeric zero is a measured value, not a missing measurement. A false value is a
  known negative, and null/unknown remains unknown. Do not convert unknown risk into a known risk
  level or infer performance benefits from the absence of evidence.
- Preserve the kind and content of the evidence in each signal's value; its label alone cannot
  turn one kind of observation into another. Separate recommendations from observed facts.

Optional-field serialization:

- If no independently supported secondary recommendation exists, omit the secondary_angle key
  entirely from the JSON object. An empty string, whitespace, null or another placeholder is not
  omission and is not a valid value for this field.
- If the objective requests both a primary and a secondary recommendation and separate supplied
  signals support each, include secondary_angle as a nonempty, distinct recommendation satisfying
  the same allowed-options rule. Do not solve optional-field validation by always omitting it.
