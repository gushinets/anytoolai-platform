# kernel_demo.score_multidimensional_axes.v1

Score `text` independently against each caller-supplied `axes` item (each has `id` and
`description`, and may have a `weight` — ignore `weight` when scoring; it is not part of this
contract). Return:

- `scores`: exactly one entry per `axes` item, each with:
  - `axis_id`: the matching axis's `id`, unchanged.
  - `score`: 1-10, how well `text` satisfies that axis's `description`, on a fixed scale where
    1 is the weakest and 10 is the strongest.
  - `commentary`: a concise justification tied to `text` and the axis `description`. State the
    conclusion and the evidence directly — do not narrate step-by-step reasoning, alternatives
    considered, or any other chain-of-thought.
- `dominant_axes`: every axis id from `scores` whose `score` equals the maximum reported score,
  listed in the order the axes were given in the input — include every axis tied for that
  maximum, not just one.
- `weakest_axes`: every axis id from `scores` whose `score` equals the minimum reported score,
  listed in the order the axes were given in the input — include every axis tied for that
  minimum, not just one.

Do not invent axes beyond the ones given, and do not include chain-of-thought or explanations
outside the schema fields.
