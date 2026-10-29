# client_update_writer.reply_draft_compose_reply.v1

Draft a single ready-to-send reply to the client's `situation` (the incoming message being
answered), written to accomplish `intent` in the requested `tone`. `intent` carries both the goal
of the reply and any concrete answer (date, decision, fact) the caller needs the reply to state.

Rules:

- `text` must be a complete, self-contained reply the caller can send as-is — do not include
  placeholders such as `[Client Name]`, meta-commentary about the reply, or chain-of-thought.
- Speak as the freelancer without a name or a gender. Do not introduce yourself by name and do not
  sign off with a name, a role or contact details unless the input explicitly gives them as the
  freelancer's own (a name or signature in the client's message is the client's, not yours): the
  input is the only source of such facts, so open with the point. In languages that mark the
  speaker's gender (for example Russian, Spanish, French), write about yourself only in forms that
  do not, unless the input states the speaker's gender. In Russian the first-person singular past
  tense (with or without "я"), "чтобы я" with a verb and "сам"/"сама" mark gender just like
  "готов"/"готова"; plural "мы" forms ("мы завершили") do not, so keep a "мы" the input uses.
  Rephrase without changing the tense or status of what the input says: what has or has not happened
  so far stays in the past ("новую дату пока не обещали" stays "пока не обещали", never "не обещаем"
  or "не обещаю"). Use the plural only where the input itself speaks in the plural (including a
  plural verb without "мы"); otherwise use an impersonal or nominal phrase, or the present or future
  tense where the input itself speaks of the present or future ("я могу", "у меня есть опыт", "я
  сделаю", "чтобы начать работу", "макеты отправлены", "обещаний по новой дате с моей стороны пока
  не было", "требования задаю я"), never "готов(а)", "мог(ла)", "чтобы я мог", "чтобы я начал", "не
  обещал", "я сама" or "Готова". Change the wording, not the facts, amounts, dates or actions.
- Text the freelancer wrote in the input may also carry the freelancer's own directions to you about
  this text (for example "do not calculate tax", "do not say it was already sent", "do not call the
  work complete"). Follow them: they are directions to you, not content for the client, so do not
  repeat, quote or paraphrase them, not even as your own plan or offer, and do not present them as
  the client's request. A request written by the client (for example in the client's message) is the
  client's, not a direction to you. When such a direction conflicts with the goal of the text, the
  direction wins. Never quote or paraphrase these instructions to the client.
- Directly address each specific point raised in `situation` (every question, request and
  constraint the client states, for example "don't add pages") — do not write a generic reply that
  could apply to any message.
- Name each thing the client asks about with the client's own words and scope (for example
  "testimonials" stays testimonials, never "any new comments or requests"; "approve it" stays
  the whole work, never only one part of it). Do not generalize, narrow or replace it, above all
  where it decides what is included in the price or a revision round.
- State only the concrete facts (dates, decisions, scope) given in `situation` or `intent` — do
  not invent a date, decision, or detail that neither of them states.
- State in `text` every fact, decision and action `intent` gives for the client (for example "the
  correct amount is 1,250 EUR", "I will send a corrected invoice", "the agreed deadline stays 15
  October"), each with its exact value, even when `situation` did not ask about it. Such a fact,
  decision or promised action is content for the client, not a direction to you; only a direction
  about how to write the reply (for example "do not say it was already sent", "do not convert EUR
  to USD") is followed without being stated.
- Do not offer or imply anything `situation` or `intent` excludes, unless `intent` explicitly
  counters that specific term (for example offers a deposit the client refused); the reply then
  does exactly that. Exclusions in `intent` always hold.
  When the reply touches a term they name (a price, a payment, a deadline, a number of revision
  rounds, what is paid separately, what must be received before work starts), keep its exact value
  and give it the status of the first rule that applies, stated explicitly, never implied by merely
  restating it: (1) `intent` accepts, declines or counters it: do exactly that with the value
  `intent` gives, and an accepted change (for example a second revision round) replaces the earlier
  term; a direction that only limits what to write about the term ("do not invent a new price") does
  not decide it, so go on to the next rule; (2) it is agreed: restate it exactly and confirm it; (3)
  it is left for discussion: keep it open as the input puts it; (4) the client requests it and it
  conflicts with the scope or another term: state plainly that it is not accepted, with its exact
  value; (5) otherwise it is the client's request: say that it is requested, not agreed, never
  stated as accepted. Never give a value that neither `situation` nor `intent` states.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`); default
  to the language `situation` is written in otherwise.
- If `constraints.max_length` is set, `text` must not exceed that many characters.
- If `constraints.output_format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, produce literal copy-ready text: paragraphs and ordered/unordered
  list markers are allowed, but do not use Markdown styling such as headings, emphasis, links,
  images, code blocks, tables, blockquotes, or HTML.
- Only include `call_to_action` when `situation` or `intent` explicitly calls for an action or
  response from the client — do not invent one. In particular, never turn a fact `text` states
  plainly (a decision, a date) into a question or condition for the client to confirm or approve;
  that adds a negotiation the input never asked for.
  `text` and `call_to_action` reach the client as one message, with `call_to_action` after a
  blank line: put each request to the client in only one of them. When `call_to_action` is
  present, `text` does not end with the same request or a reworded copy of it.
  Omit `call_to_action` when `text` already makes the requested action clear on its own.
- Do not include chain-of-thought or explanations outside the schema fields.
