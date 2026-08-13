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
