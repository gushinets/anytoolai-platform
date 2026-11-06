# client_update_writer.prepaid_request_compose_persuasive_text.v1

Write the final, ready-to-send message that accomplishes `objective`, built only from facts stated
in `context`: `context.notes` (what the payment covers), `context.amount` and — when given —
`context.due_date`. Do not invent facts that are not there. Depending on the notes the message is a
prepayment request, a request to confirm the payment terms, a hold-off acknowledgment or a settled
acknowledgment. Decide which first, in three steps.

Step 1. Attribute every fact to this payment or not.

Only facts about *this* payment (the one `context.amount` is for) can agree with, contradict or
settle its terms. A project total, a separate later instalment or balance (one the notes present as its own
payment) and its due date, a currency named only for other amounts, penalties, or any other payment
are facts about something else: they
are never a conflict with `context.amount` / `context.due_date` and never a reason to confirm terms
(for example `amount: USD 500`, `due_date: 15 October` against "deposit USD 500 due 15 October,
remaining USD 1,500 due 30 November" is consistent). A project total is no exception when this payment is computed from it (for example "deposit is 50%
of the final fee"): if the notes say that total is not agreed or leave two current candidates, this amount is
open; a total the notes call rejected or superseded is history, and the current one is the base. What is left of *this* amount after a partial
receipt is part of this payment, not another one: its stated due date is a due date for this
payment (`due_date: 15 October` against "remaining USD 750 due 30 October" is a different due date). When it is unclear whether a fact concerns
this payment, treat the condition it touches as open (Step 2): a question costs less than an
unfounded payment demand.

Step 2. Decide which conditions of this payment are open (not needed when rule A below applies).

`context.notes` take precedence over `context.amount` and `context.due_date`. An essential
condition of this payment (its amount, currency, deposit terms, due date, payment method or
schedule) is open when any of these holds:

- the notes say it is not agreed, disputed, awaiting confirmation or contradicted, or that no
  payment demand may be sent until it is confirmed;
- the notes state a different current amount, currency or due date for this payment than
  `context.amount` / `context.due_date` (`amount: USD 500` against "the agreed currency is EUR") (an earlier proposal the notes call rejected, superseded or replaced is history,
  not a conflict), or an amount that the notes' own terms determine (for example "50% of an agreed
  total of USD 2,000" is USD 1,000, against `amount: USD 1,200`), even without calling it a mismatch and even if the notes call that value agreed (for example `amount: USD 1,200` against
  "deposit is 50%, USD 1,000"; `due_date: 7 October` against "payment due after delivery on
  20 October");
- `context.amount` is computed from a base (a total, a rate) that the notes say is not agreed or leave
  as two current candidates, even if the rate itself is agreed (50% of USD 2,000 or of USD 2,400);
  a rejected or superseded base next to one agreed current base opens nothing;
- `context.amount`, or a given `context.due_date`, is a placeholder such as "TBD" or "to be
  agreed", or does not name one value (alternatives such as "USD 500 or EUR 460", or a range)
  (an absent `due_date` is not a placeholder);
- `context.amount` names no currency (a bare number, or one with other words such as
  "500 (deposit)") and the notes do not tie a currency to this payment (a currency named only for
  other amounts, or several currencies with none named for this payment, does not count);
- part of this amount was received (and not reversed) and the notes do not state the remaining figure, or the
  received part, the stated remainder and `context.amount` do not add up (for example
  "500", "200 received", "remaining 400").

Never open by themselves: a missing `due_date`, payment details still to come (for example in a
separate invoice), a balance due after delivery, or a request in the notes to go gently. Notes that
merely describe the payment consistently with the fields, without saying anything about agreement,
open nothing.

Step 3. Pick the kind of message: the first matching rule wins.

Only rule D may ask for payment. Rules A–C never ask the client to pay or remit, never turn
`context.amount` or `context.due_date` into an amount or date to pay ("once you confirm, please pay
X by Y" is a payment ask too), and never ask the client to report a payment.

- A. Nothing is owed on this payment as things stand now, and nothing about it is disputed or
  unclear: the notes say it is received in full (receipts that add up to `context.amount`, or a
  stated zero balance, count as in full) or that the request is cancelled → settled acknowledgment:
  a short thank-you for the payment, or a note that the request is withdrawn, without restating
  `context.amount` as owed. An obsolete placeholder in `context.amount` or `context.due_date` does
  not block this: it compares with nothing. A settled amount that differs from a concrete
  `context.amount` (USD 1,000 settled against `amount: USD 1,200`) is a conflict and goes to rule B.
  A reversal, refund or chargeback matters only through what it leaves: final with nothing owed
  keeps A; final with an agreed amount still owed is an ordinary unpaid payment (rules B–D as
  usual, so D when nothing is open); pending or contested, a live dispute about the received
  amount, or an unclear status is an open condition (rule B).
- B. Any condition is open → terms confirmation. Ask the client to confirm only the open
  conditions, named as stated or discussed, never as agreed; anything the notes call agreed and
  that conflicts with nothing stays stated as agreed. A value the notes call agreed that differs
  from `context.amount` / `context.due_date` is still an open point: ask the client to confirm it
  without presenting either value as settled or repeating the notes' agreement claim.
  For each open condition, include every concrete current candidate value from the fields and
  notes, with its currency or timing relation (for example after delivery). Ask which applies;
  do not replace known conflicting amounts or dates with a generic request to confirm terms.
  This does not override an explicit instruction to withhold private information.
  Asking for the information the terms need (for example which currency applies,
  or the amount still due) is fine. Never print a placeholder as a value: ask the client to confirm
  that amount or due date instead.
  Directions about when to ask for payment select this message kind; they are not a plan to
  announce to the client. In a terms confirmation, do not announce, promise or describe a later
  payment request (including "before sending a payment request" or "after you confirm, I will
  request payment"). Ask for confirmation directly. Preserve actual invoice, delivery and payment
  terms stated separately from such editorial directions.
- C. The notes say not to ask for payment yet (for example "do not request payment yet, we are
  waiting for the client's review"), whether or not they call the terms agreed → hold-off
  acknowledgment: a short note that you will wait.
- D. Otherwise → payment request for the amount still due: the remaining figure the notes state if
  part was already received, else `context.amount`. Follow a "go gently" note in the wording.
  Explicitly and politely ask the client to pay that amount. Describing the payment terms or
  asking only to be notified after payment does not replace the request to pay.

Rules:

- `text` must be a complete, self-contained message the caller can send as-is — do not include
  placeholders such as `[Client Name]`, meta-commentary about the message, or chain-of-thought.
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
  This non-reporting rule applies only to editorial directions about the message itself.
  A restriction on doing the freelancer's actual work is client-relevant content, even when
  written as a command: include what must remain unchanged or on hold and the condition for
  proceeding. State it as the freelancer's work status or commitment, never silently omit it
  as an editorial direction. Conversely, a direction about the message's wording or calculations
  does not establish a restriction on the actual work; do not invent one from it.
  Explicit directions to withhold work facts or private business information still take precedence.
- In a payment request, ground the request in what `context.notes` states (what the payment
  covers). Do not invent a reason the payment is urgent, gating, or blocking (for example that other work will stall
  without it) beyond what `notes` itself says.
- In a payment request (rule D) state the amount still due exactly as given: the stated remaining
  figure after a partial receipt, else `context.amount`, never request both as still owed. Always state the
  currency with the number, never a bare figure, without changing the number. The currency is the
  one `context.amount` names, else the one the notes tie to this payment; this holds for a bare
  remainder too (`amount: USD 1,000` with "750 remains" is "USD 750"; `amount: 500` with "the
  currency is USD" is "USD 500"; `amount: 500`, "the currency is USD", "300 remains" is "USD 300").
  A different currency in the notes is an open point, not a choice. A terms confirmation shows an
  amount or due date only as the stated value of an open point; rules A and C never present an
  amount or due date as owed or upcoming.
- In a payment request, preserve the complete explicitly stated payment arrangement: the deposit
  percentage and agreed total, when the remaining balance is payable (including its delivery
  condition), and whether payment details will come in a separate invoice. These are payment
  terms, not optional background. Request only the amount due now; mentioning the agreed later
  balance does not make it due now. Do not calculate an unstated balance or invent any terms.
  When stating a deposit percentage, explicitly attach it to the agreed total, not to the
  deposit amount. Name the deposit amount separately as that share of the total; the wording
  must not suggest applying the percentage to the deposit amount again, in any language.
  Preserve future invoice timing without claiming it has already been sent. Shorten phrasing
  before dropping these terms when a length limit applies; explicit withholding directions still win.
- In a payment request, when `context.due_date` is a real, non-placeholder due date or deadline (a
  calendar date or a relative term such as "Net 30 after invoice" or "within 14 days of delivery")
  and the notes give no other due date for the amount still due, state its date exactly (urgency words in it follow the urgency rule below) — do not tighten
  it to an earlier date (for example writing "before Friday" when the due date is "Friday"; use
  "by Friday" or "due Friday"). Preserve the temporal relation in every language, not just the
  date: a bare due date means "no later than", allowing earlier payment, not "on that day".
  For Friday, use "by Friday", "не позднее пятницы" or "a más tardar el viernes", not an instruction
  to pay "on Friday", "в пятницу" or "el viernes". Keep explicitly stated on/before/after conditions
  as given, with notes taking precedence. Unless the notes say the payment is not urgent or not
  to be rushed, ASAP with a due-by date means as soon as possible and no later than that date,
  never waiting until that day.
  A placeholder (`TBD`, "to be agreed") is never stated as a value:
  ask the client to confirm that amount or due date instead.
- If `context` has no `due_date`, do not state or imply any date, deadline or time frame (for
  example "by end of week" or "within 3 days") unless `context.notes` itself states one.
- Urgency in a payment request comes only from `context.notes` or the free text of
  `context.due_date` that themselves express urgency of this payment (for example "the payment is
  urgent", "needed ASAP", "оплата срочная", or `due_date: "Friday — ASAP"`; the date is stated
  as given and its urgency kept, unless the notes say the payment is not urgent or not to be
  rushed: then the notes win and only the date is stated, without its urgency words). A plain date in
  `context.due_date`, a placeholder `due_date`, `constraints.tone: firm`, or incidental time
  words in the notes ("we agreed the deposit today") are not urgency, and neither is "not urgent,
  no rush". State the date of a given `due_date` exactly as given and add no urgency words of your own. With
  urgency in the input, convey it as stated, without strengthening it or turning it into a date
  that is not there, and do not soften it into an open-ended timeframe (for example "when you get
  a chance"). Without it, make a neutral request: no "promptly", "as soon as possible", "right
  away", "immediately", "now", "urgently", "quickly", "soon" or "shortly", or their equivalents in
  the reply language (examples, the rule is by meaning). Firmness belongs in the wording, not in a
  deadline.
- Other billing-note details that matter to the request (for example what is and is not agreed)
  are kept as stated, but briefly: when `constraints.length` is set, shortening the notes takes
  precedence over keeping every detail; in a terms confirmation, drop other detail before the open
  points. `text` (including the closing line) never exceeds `constraints.length` when set.
  Only if an explicitly supplied `constraints.length` is too short
  to name every open value, name none of them: ask the client to confirm only the conditions that
  are actually open (or "the unresolved payment terms" if even those labels do not fit), without
  stating or endorsing any value and without raising anything the notes call agreed.
  Without an explicit length limit, keep every concrete current candidate value of each open
  condition; brevity alone never permits omitting them.
- End the message matching its kind. Payment request (rule D): ask the client to let the caller
  know once the payment has been sent, in addition to the explicit request to pay;
  do not phrase it as the client confirming *receipt* of
  something (the client is sending the payment). Terms confirmation (rule B): end with a short
  request to reply with the confirmation. Rules A–C never ask the client to report a payment.
- Do not state a payment method, link, reference, or account details (for example a bank name,
  PayPal address, invoice number, or "the account on file") unless `context.notes` states it —
  `context.amount` and `context.due_date` never contain any, so any other such detail would be
  invented. Naming an open payment condition (for example "the payment method") is fine.
- Match `constraints.tone` (`neutral`, `warm`, or `firm`) when provided.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`); default
  to the language of `context.notes` otherwise.
- If `constraints.length` is set, `text` must not exceed that many characters.
- If `constraints.format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, produce literal copy-ready text: paragraphs and ordered/unordered list
  markers are allowed, but do not use Markdown styling such as headings, emphasis, links, images,
  code blocks, tables, blockquotes, or HTML.
- Do not include chain-of-thought or explanations outside the schema fields.
