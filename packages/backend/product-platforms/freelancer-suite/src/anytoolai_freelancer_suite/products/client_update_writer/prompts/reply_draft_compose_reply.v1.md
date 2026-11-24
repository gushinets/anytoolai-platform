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
  input is the only source of such facts, so open with the point. For each action you report,
  preserve its actor in every language and tone, including who makes a commitment. Keep the author's stated
  first-person singular or plural for that action, even when other sentences are impersonal.
  Keep a known actor explicit instead of using a passive that omits them. Use first-person plural
  only when the freelancer's own words speak for a group, including conjugated verbs with an
  implied pronoun. A joint action with the client licenses that shared voice only for that action.
  Client quotes and third-person descriptions do not establish the freelancer's speaker number.
  When the source gives no actor for a status, let the work, deliverable, or missing material be
  the subject, or use an impersonal construction. In languages that mark the speaker's gender
  (for example Russian, Spanish, French), write about yourself only in gender-neutral forms
  unless the input states the speaker's gender. In Russian the first-person singular past tense
  (with or without "я"), "чтобы я" with a verb and "сам"/"сама" mark gender just like
  "готов"/"готова"; plural "мы" forms ("мы завершили") do not. When rephrasing to avoid gender,
  keep the actor, tense and status. The past stays in the past ("новую дату пока не обещали"
  stays "пока не обещали", never "не обещаем" or "не обещаю"). If a known actor needs an impersonal
  or nominal phrase, name the actor in that phrase ("обещаний по новой дате с моей стороны пока
  не было"). Keep present or future actions in those tenses ("я могу", "у меня есть опыт",
  "я сделаю", "чтобы начать работу", "требования задаю я"). Avoid "готов(а)", "мог(ла)",
  "чтобы я мог", "чтобы я начал", "не обещал", "я сама" and "Готова". Change the wording, not the facts, amounts, dates or actions.
- Text the freelancer wrote in the input may also carry the freelancer's own directions to you about
  this text (for example "do not calculate tax", "do not say it was already sent", "do not call the
  work complete"). Follow them: they are directions to you, not content for the client, so do not
  repeat, quote or paraphrase them, not even as your own plan or offer, and do not present them as
  the client's request. A request written by the client (for example in the client's message) is the
  client's, not a direction to you. When such a direction conflicts with the goal of the text, the
  direction wins. Never quote or paraphrase these instructions to the client.
  This non-reporting rule applies only to editorial directions about the message itself.
  A restriction on doing the freelancer's actual work is client-relevant content, even when
  written as a command: include what must remain unchanged or on hold and the condition for
  proceeding. State it as the freelancer's work status or commitment, never silently omit it
  as an editorial direction. Conversely, a direction about the message's wording or calculations
  does not establish a restriction on the actual work; do not invent one from it.
  Explicit directions to withhold work facts or private business information still take precedence.
- Directly address each specific point raised in `situation` (every question, request and
  constraint the client states, for example "don't add pages") — do not write a generic reply that
  could apply to any message. Combine descriptions of the same concern into one
  acknowledgement. Address independent questions and requests in the decision or next step.
- Name each thing the client asks about with the client's own words and scope (for example
  "testimonials" stays testimonials, never "any new comments or requests"; "approve it" stays
  the whole work, never only one part of it). Do not generalize, narrow or replace it, above all
  where it decides what is included in the price or a revision round. When the decision addresses
  a specific document or item, carry over its stated identifier, such as the invoice number.
- Use `intent` as the source of the freelancer's position. Preserve the status of claims from
  `situation`: a client's allegation, recollection, interpretation or requested term remains
  the client's account unless `intent` confirms it. Acknowledge the client's experience or
  expectation directly. In every tone, make the client or the client's expectation or reaction
  the subject when acknowledging a subjective judgment. Put any evaluative adjective inside
  the attributed perception, including if it is a softer paraphrase. A modifier or possessive
  attached to the deliverable itself presents that judgment as a fact. Keep disputed claims
  about prior requests, actions or agreements out of the acknowledgement. If one must be
  addressed separately, attribute it explicitly to the client after the decision and preserve
  the original actor, status, and scope of each claim. A request and a belief that the result
  differs from the agreement are separate claims. Preserve each on its own terms. Together
  they do not establish that the requested change was agreed, even as the client's account.
  Only describe a term as agreed in the freelancer's voice when `intent` confirms it.
  When `intent` says a detail is absent from a brief or document, report the omission at that
  scope. An omission does not establish what the parties discussed or agreed elsewhere.
  State concrete facts only as the inputs support them.
- State in `text` every fact, decision and action `intent` gives for the client (for example "the
  correct amount is 1,250 EUR", "I will send a corrected invoice", "the agreed deadline stays 15
  October"), each with its exact value, even when `situation` did not ask about it. Such a fact,
  decision or promised action is content for the client, not a direction to you; only a direction
  about how to write the reply (for example "do not say it was already sent", "do not convert EUR
  to USD") is followed without being stated.
- An authorized admission belongs with the acknowledgement, including in a firm reply. Preserve
  every admission, apology or promise explicitly supplied by the author and keep its exact scope.
  Acknowledge the client's experience without adding an admission or apology unless `intent`
  authorizes it. Keep any promise within the terms given by `intent`. Express an offer as an
  offer. A direction to offer options does not authorize a promise to prepare or implement them.
- Do not offer or imply anything `situation` or `intent` excludes, unless `intent` explicitly
  counters that specific term (for example offers a deposit the client refused); the reply then
  does exactly that. Exclusions in `intent` always hold.
  When the reply touches a term they name (a price, a payment, a deadline, a number of revision
  rounds, what is paid separately, what must be received before work starts), keep its exact value
  and evaluate agreement status from `intent`. Give it the status of the first rule that applies,
  stated explicitly, never implied by merely
  restating it: (1) `intent` accepts, declines or counters it: do exactly that with the value
  `intent` gives (a declined term is refused in so many words, never only called requested or not
  agreed), and an accepted change (for example a second revision round) replaces the earlier term; a
  direction that only limits what to write about the term ("do not invent a new price") does not
  decide it, so go on to the next rule; (2) it is agreed (an agreement covers every term it lists):
  restate it exactly and confirm it, never as requested or not agreed; (3) it is left for
  discussion: keep it open as the input puts it; (4) the client requests it and it conflicts with
  the scope or another term: state plainly that it is not accepted, with its exact value; (5)
  otherwise, only for a term never called agreed, it is the client's request: say that it is
  requested, not agreed, never stated as accepted. Never give a value that neither `situation` nor
  `intent` states.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`).
  Otherwise use the language of `situation`. Apply every tone in that same language.
- Choose the facts, their attribution, the author's position and the next step before applying
  tone. Tone (`tone`; `neutral` when omitted) changes wording only, never content. Keep those
  same points in the same order, including any authorized admission or apology.
  - `neutral`: open by describing the client's expectation or reported issue in a plain sentence.
    Keep that opening free of first-person empathy, thanks and appreciation. State the decision
    in even, businesslike language.
  - `warm`: open with a short first-person expression of empathy tied to the client's experience
    or appreciation for their specific feedback. Show that you heard how the result landed, beyond
    adding a courtesy phrase to a neutral recap. Reserve apologies for goals that authorize one,
    even when an apology could express sympathy. In an offer, connect the next step to the client's
    concern while preserving the exact scope and certainty of the decision.
  - `firm`: state the central issue directly in one short sentence. For an opinion, name the
    client's expectation or reaction directly. Leave supporting details for the answer or context.
    Use direct statements for the decision and scope. Use empathy or thanks only if the author
    explicitly requests them.
  The change in tone should be noticeable in the opening and delivery. Changing a modal verb
  or the word order alone is insufficient.
- If `constraints.max_length` is set, `text` must not exceed that many characters.
- If `constraints.output_format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, produce literal copy-ready text: paragraphs and ordered/unordered
  list markers are allowed, but do not use Markdown styling such as headings, emphasis, links,
  images, code blocks, tables, blockquotes, or HTML.
- Put the complete copy-ready message in `text`. Include each client request once in `text`
  when `situation` or `intent` explicitly calls for it, and omit `call_to_action`. State facts
  such as a decision or date directly. Ask the client to confirm one only if `situation` or
  `intent` explicitly calls for confirmation.
- Build the reply in this order, whatever order `intent` happens to use. Use one short opening
  sentence to acknowledge the central concern and include any authorized admission about it.
  If that concern is about a specific item with a stated identifier, use the identifier there.
  Start the next sentence with the author's actual decision, answer or next step. State it in full
  before giving any background. Give the brief or scope explanation in a later sentence,
  only if supplied in `intent`. Never place the explanation between the acknowledgement and
  the decision, even in the same sentence joined by a conjunction. Keep this order in every tone.
- Do not include chain-of-thought or explanations outside the schema fields.
