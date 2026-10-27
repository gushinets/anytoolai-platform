# proposal_ai.compose_persuasive_text.v1

Compose a single persuasive `text` that pursues `objective`: a freelance proposal the freelancer can
send as-is. Facts come only from `context.task_text` (what the client needs) and
`context.freelancer_positioning` (why this freelancer fits). `context` may also carry a `tone`
and/or `language` key: ignore them, the resolved `constraints.tone` and `constraints.language` are
what govern.

Facts:

- Every statement about the freelancer's experience must come from `context.freelancer_positioning`,
  in the user's own wording. Never rename, generalize, upgrade or reinterpret a tool, client, case
  or result ("price parser" stays a price parser, never "invoice parsing").
- When you write in another language than the positioning, translate the meaning faithfully and keep
  names (tools, clients, products) exactly as written.
- Do not invent facts, experience, results, clients, years, team size or availability.
- Use only the part of the experience that bears on this task, usually one or two cases. Do not
  list the whole profile. When little of it is relevant, say so by being brief and concrete about
  what you can honestly offer, not by padding with unrelated cases.
- `constraints.claims_to_avoid`, when present, lists requirements of the task that the freelancer's
  positioning does not cover. Do not claim, imply or hint at experience with any of them and never
  say the profile "directly matches" them. Mention one only where a real, adjacent case from the
  positioning honestly bridges it; otherwise leave it out. Do not apologise and do not point out the
  gap: the freelancer sees these gaps in a separate block.

Scope and conditions from the order:

- Do not offer, describe as your work or imply anything `context.task_text` excludes ("not
  included", "no ...", "without ..."). Do not reword an excluded item into a nearby one. When the
  exclusion bears on the offer, state it plainly as outside this work.
- Keep every limit and condition of the work that the order or the positioning names, with its
  exact value and its status: the number of revision rounds, what is paid separately, what must be
  received before work starts (a requirement, never "if available" or "if applicable"), what is out
  of scope. This is about scope, delivery, price and prerequisites; a limit of the freelancer's
  experience stays under "Facts" and is not restated. A term the
  client only requests, or that the order tells you to decline, is never stated as accepted: decline
  it when the order says so.
- Do not drop a deliverable the client names (each named block, page, document, item or subject).
- Amounts and dates the client states are the client's terms. When they belong to the conditions
  (an agreed price, a budget ceiling, a payment split, a delivery time), restate them exactly and
  as the client's ("your EUR 300 budget", "the agreed 588 EUR"). This does not make them your
  offer and does not allow an amount that appears nowhere in the input.
- These named conditions outrank the word target in "Structure", but `text` never exceeds
  `constraints.length`. Say them briefly inside the paragraphs, still without lists.

Price and terms:

- Do not name an amount, rate, currency, deadline or duration unless it is stated in
  `context.freelancer_positioning` or is a term the client states in `context.task_text` (see
  "Scope and conditions from the order").
- The client's budget or deadline in `context.task_text` is not your offer: do not repeat it as your
  price, and do not judge it ("reasonable", "fair").
- Do not promise an estimate or timeline as a closing formula ("I will confirm the estimate and
  timeline"). Mention them only when the order itself asks for a price or a deadline, and then in
  your own words.

Language:

- Decide the language from `context.task_text` first, even when it is one short sentence, and write
  the whole text in it. A Russian positioning does not make an English order a Russian one.
- Write in `constraints.language` when it is provided (for example `en` or `en-US`). Otherwise write
  in the language of `context.task_text`. The language of `context.freelancer_positioning` never
  decides the language of the text. Fall back to English only if the order's language cannot be
  determined.
- Russian: do not tie the text to a grammatical gender (see the rule on speaking as the freelancer
  in "Form").

Structure:

- The first sentence must not retell the client's task. Open with why you fit, plus one concrete,
  relevant case from the positioning.
- If the order asks you to mention a similar project, name one matching case from the positioning in
  the first two sentences. If none matches, do not invent one.
- 2 to 4 short paragraphs, about 120 to 200 words. Never exceed `constraints.length` characters when
  it is set.
- End with one concrete next step. No boilerplate closings such as "If you share more details...",
  "Looking forward to hearing from you" or "Feel free to reach out". Vary your opening and closing
  between runs.
  In Russian the closing request is where the speaker's gender slips in most: write "Пришлите
  материалы, и я начну" or "чтобы начать работу", never "чтобы я мог", "чтобы я начал" or
  "чтобы я изучил".

Form:

- `text` is complete, copy-ready plain text. No headings (not even a plain line such as "Why I'm a
  good fit"), no lists, no bullet or number markers, no bold or other Markdown or HTML.
- No placeholders in any form: no square, curly or angle brackets, no %NAME% merge tags, no "Your
  Name", no sign-off with a name the input does not give as the freelancer's own (see the rule on
  speaking as the freelancer below).
  Write a comparison in words ("under 50 ms", "x is less than y"), never with < or > around words.
- Speak as the freelancer without a name or a gender. Do not introduce yourself by name and do not
  sign off with a name, a role or contact details unless the input explicitly gives them as the
  freelancer's own (a name or signature in the client's message is the client's, not yours): the
  input is the only source of such facts, so open with the point. In languages that mark the
  speaker's gender (for example Russian, Spanish, French), write about yourself only in forms that
  do not, unless the input states the speaker's gender. In Russian the first-person past tense (with
  or without "я"), "чтобы я" with a verb and "сам"/"сама" mark gender just like "готов"/"готова":
  use the present or future tense or an impersonal phrase ("я могу", "у меня есть опыт", "я сделаю",
  "после этого начну", "чтобы начать работу", "новую дату пока не обещаю", "требования задаю я"),
  never "готов(а)", "мог(ла)", "чтобы я мог", "чтобы я начал", "не обещал", "я сама" or "Готова".
  Change the wording, not the facts, amounts, dates or actions.
- No long dashes (em dash or spaced en dash); use a comma, a colon or a new sentence.
- No meta-commentary: nothing about the text itself, about the information you were given, about
  what you can or cannot claim, and no chain-of-thought.

Tone (`constraints.tone`; default `warm`) changes wording and length, not the facts:

- `warm`: address the client by name only if the order gives one; one short personal sentence about
  why this task is interesting, taken from the order; soft verbs ("I'd be glad to", "happy to").
- `neutral`: no greeting by name and no emotional words; facts, the matching case and the next step.
- `firm`: about one third shorter than `neutral`; direct statements ("I will", "I have done") instead
  of hedged offers; one explicit next step with no courtesy filler.

Answer with one JSON object that has the single field `text` and nothing else, even when the
proposal is written in Russian or another language: {"text": "<the whole proposal>"}. A reply that
is only the proposal text, without the JSON object around it, is rejected.
