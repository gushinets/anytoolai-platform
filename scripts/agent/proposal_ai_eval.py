"""Manual evaluation of ProposalAI against the fixed order set (tests/fixtures/proposal_ai_eval).

Runs every order through a running platform-api + worker (one fresh guest per order, the guest
quota is lifetime), then applies the automatic checks from the QA protocol that need no LLM judge.
Facts about experience, tone distinguishability and "similar project in the first two sentences"
stay manual.

    .quick-check-venv/bin/python scripts/agent/proposal_ai_eval.py --api-url http://localhost:8000 [--tone warm] [--language ru]
    .quick-check-venv/bin/python scripts/agent/proposal_ai_eval.py --api-url http://localhost:8000 --orders tests/fixtures/proposal_ai_eval/terms.json

An order may carry its own `freelancer_positioning`, `tone` and `language` (they win over the file's
and the flags'), `terms`: the expected status of each client term (see `term_status_errors`), and
`must` / `must_not`: regular expressions (case-insensitive) the proposal has to contain or must not
contain. terms.json is the regression set for the status of client terms
(ANY-631): run it after any change to how ProposalAI states prices, deadlines and limits.

(the quick-check environment, because the number check is imported from the A06 validator)

Exit code 1 when any order has a hard violation. The report is Markdown on stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

import re2

from anytoolai_platform_actions.structured_llm.cross_validation.persuasive_text import numbers_absent_from_context

ORDERS_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "proposal_ai_eval" / "orders.json"
# RE2, like the A06 validator that runs the same placeholder patterns (`\pL` is any letter there).
_RE2_IGNORE_CASE = re2.Options()
_RE2_IGNORE_CASE.case_sensitive = False
PLACEHOLDER = re2.compile(
    r"\[[^\]\n]{1,80}\]|\{[^{}\n]{1,80}\}|\{\{|\}\}|\byour name\b|<[^\s\d<>=][^<>\n]{0,79}>|%\pL[\pL\pN_.]{0,39}%",
    _RE2_IGNORE_CASE,
)
META = re.compile(
    r"based on the information i(?:.m| am| have| was| can)|truthfully|as an ai (?:language )?model"
    r"|as an ai,? i (?:can|cannot|can.?t|am|do|don.?t)\b|my listed experience|haven.t specified"
    r"|в описании моего опыта|не буду заявлять",
    re.IGNORECASE,
)
LONG_DASH = re.compile(r"—| – ")
LIST_OR_HEADING_LINE = re.compile(r"^\s*(#{1,6}\s|[-*+•]\s|\d+[.)]\s)")
MAX_WORDS = 250


def _has_invented_number(text: str, *sources: str) -> bool:
    # The validator's own reading of numbers; each source is a separate string so the end of one field
    # and the start of the next are never one number.
    return bool(numbers_absent_from_context(text, list(sources)))


def _cyrillic_share(value: str) -> float:
    letters = [char for char in value if char.isalpha()]
    return sum("Ѐ" <= char <= "ӿ" for char in letters) / len(letters) if letters else 0.0


# Function words that are frequent in one language and rare in the others. ANY-631 saw whole English
# orders answered in Spanish, Dutch and German; a Cyrillic share alone calls all of those "en".
_FUNCTION_WORDS = {
    "en": {"the", "and", "to", "of", "your", "you", "for", "is", "are", "with", "not", "i", "my", "this", "will"},
    "es": {"el", "la", "los", "las", "que", "de", "para", "con", "una", "por", "del", "su", "tu", "y", "no", "es"},
    "de": {"der", "die", "das", "und", "ich", "ist", "nicht", "mit", "für", "ein", "eine", "zu", "sie", "den", "auf"},
    "nl": {"de", "het", "een", "en", "ik", "is", "niet", "met", "voor", "van", "uw", "op", "te", "dat", "zijn"},
    "fr": {"le", "la", "les", "et", "je", "est", "pas", "avec", "pour", "un", "une", "des", "du", "vous", "votre"},
    "it": {"il", "la", "e", "di", "che", "per", "con", "non", "un", "una", "sono", "del", "della", "gli", "suo"},
    "pt": {"o", "a", "os", "as", "e", "de", "que", "para", "com", "não", "um", "uma", "do", "da", "seu"},
}


def detect_language(text: str) -> str | None:
    """`ru` for a mainly Cyrillic text, otherwise the language whose function words lead clearly;
    None when no language leads clearly (the caller reports it as unverified, never as correct)."""
    if _cyrillic_share(text) > 0.5:
        return "ru"
    words = re.findall(r"[^\W\d_]+", text.lower())
    if len(words) < 20:
        return None
    hits = sorted(((sum(word in vocab for word in words), lang) for lang, vocab in _FUNCTION_WORDS.items()), reverse=True)
    (best, lang), (second, _) = hits[0], hits[1]
    return lang if best >= 0.12 * len(words) and best >= 1.5 * second else None


# Status of a client term (ANY-631 "Terms"). In each sentence that names the term's value, the
# status marker nearest to the value decides: an acceptance, a refusal (an acceptance word with a
# negation right before it, or decline/reject/does not cover), the client's proposal (proposed, a
# ceiling) or a term left open ("will be agreed after the call"). Nearest, because a governing verb
# covers a list ("I cannot accept EUR 300, unlimited revisions or ...") while an unrelated "agreed"
# elsewhere in the sentence ("rounds agreed in advance") must not decide this term.
_NEGATION = (
    r"(?:\bnot\b|n['’]t\b|\bnever\b|\bcannot\b|\bno\b|\btampoco\b|\bni\b|\bне\b|\bни\b"
    r"|\bdeclin\w*|\brefus\w*|\brechaz\w*|\bотказ\w*|\bотклоня\w*)"
)
_POSITIVE = re.compile(
    r"\baccept\w*|\bagree to\b|\bagreed\b|\bconfirm\w*|\bapprove\w*|\bguarantee(?:s|d to)?\b(?! (?:a |the )?top)"
    r"|\bincluded\b|\bI(?:.ll| will)? include\b|\btake on\b"
    r"|\bacept\w*|\bconfirm\w*|\bacordad\w*|\bincluid\w*|\bgarantiz(?:o|ar|aré|amos)\b"
    r"|\bпринима\w*|\bпринят\w*|\bподтвержд\w*|\bсогласован\w*+(?! \w+ нет)|\bвключ[её]н\w*|\bгарантир\w*",
    re.IGNORECASE,
)
_REFUSAL = re.compile(
    r"\bdeclin\w*|\breject\w*|does not cover|doesn.t cover|\bno cubre\b|не покрыва\w*|\brather than\b|\brechaz\w*"
    r"|\bотклоня\w*|\bотказ\w*|\bunrealistic\b|not realistic|unworkable|no es realista|\bнереал\w*"
    r"|does not fit|doesn.t fit|\bno encaja\b|\bне подходит\b|\bсогласован\w* \w+ нет\b",
    re.IGNORECASE,
)
_PROPOSAL = re.compile(r"\bpropos\w*|\bpropuest\w*|\bпредлож\w*|\bпредел\w*|\bпотол\w*", re.IGNORECASE)
_OPEN = re.compile(
    r"(?:will|can|could|would|must|is to|are to|to) be agreed|remains? to be agreed|agreed (?:afterwards?|later)"
    r"|remains? open|stays? open|open for discussion"
    r"|not (?:yet )?fixed|not tied to a fixed|not a fixed|requested (?:target|timing)|preferred timing"
    r"|after (?:the|a|our) [\w-]+ (?:call|inspection|review)|after (?:inspect|review)\w*|until (?:the )?theme is inspected"
    r"|\bне зафиксирован\w*|\bпосле оценки|\bдо оценки|\bбудет согласован\w*|\bpor acordar|\bse acordar\w*",
    re.IGNORECASE,
)
_OFFER = re.compile(r"\boffer\w*|\bpropose\b|\bquote\b|\bofrezco\b|\bpropongo\b|\bпредлага\w*", re.IGNORECASE)


def _markers(sentence: str) -> list[tuple[int, int, str]]:
    """(start, end, kind) of every status marker; kind is positive, refusal, proposal, open or offer."""
    found = [(m.start(), m.end(), "open") for m in _OPEN.finditer(sentence)]

    def inside_open(m: re.Match) -> bool:
        return any(s <= m.start() < e for s, e, _ in found)

    for m in _POSITIVE.finditer(sentence):
        if inside_open(m):
            continue
        negated = re.search(_NEGATION + r"[^.;:!?]{0,25}$", sentence[: m.start()], re.IGNORECASE)
        found.append((m.start(), m.end(), "refusal" if negated else "positive"))
    found += [(m.start(), m.end(), "refusal") for m in _REFUSAL.finditer(sentence)]
    found += [(m.start(), m.end(), "proposal") for m in _PROPOSAL.finditer(sentence) if not inside_open(m)]
    for m in _OFFER.finditer(sentence):
        negated = re.search(_NEGATION + r"[^.;:!?]{0,15}$", sentence[: m.start()], re.IGNORECASE)
        found.append((m.start(), m.end(), "refusal" if negated else "offer"))
    return found


def _nearest_kinds(text: str, value: str) -> list[str | None]:
    """For every mention of the value: the kind of the nearest marker in its sentence (None: no marker)."""
    kinds = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        marks = _markers(sentence)
        for v in re.finditer(value, sentence, re.IGNORECASE):
            def distance(mark: tuple[int, int, str]) -> int:
                return max(0, mark[0] - v.end(), v.start() - mark[1])
            kinds.append(min(marks, key=distance)[2] if marks else None)
    return kinds


def term_status_errors(text: str, terms: list[dict]) -> list[str]:
    """Each expected term status that the text does not show. `value` is a regular expression for
    the term's value; `status` is `not_accepted` (declined, or the client's proposal and not agreed),
    `agreed` (restated at least once without a refusal; one confirmation often covers several terms
    and the value may recur inside a refusal of something else), `accepted`
    (an acceptance next to it: a change the freelancer accepts), `offered` (the freelancer's own
    value, offered) or `open` (left for discussion; the value may be absent)."""
    errors = []
    for term in terms:
        kinds, status = _nearest_kinds(text, term["value"]), term["status"]
        if status == "open":
            ok = "positive" not in kinds
        elif not kinds:
            ok = False
        elif status == "not_accepted":
            ok = "positive" not in kinds and any(kind in ("refusal", "proposal", "open") for kind in kinds)
        elif status == "agreed":
            ok = any(kind in ("positive", None) for kind in kinds)
        elif status == "accepted":
            ok = "positive" in kinds and "refusal" not in kinds
        elif status == "offered":
            ok = "offer" in kinds
        else:
            raise ValueError(f"unknown term status {status!r}")
        if not ok:
            errors.append(f"{term['value']} should be {status}, nearest markers {kinds}")
    return errors


def _is_heading_like(line: str) -> bool:
    stripped = line.strip()
    return 0 < len(stripped) <= 60 and stripped[-1] not in ".!?:;,…" and len(stripped.split()) <= 8


def check_proposal(
    text: str, gaps: list, order: dict, profile: str, *, expect_language: str | None = None
) -> dict[str, bool | int]:
    """Hard checks (True means violated) plus the word count. `expect_language` overrides the
    order's own (an explicit `--language`). A language the detector cannot tell apart is reported as
    `language_unverified` for a manual read, never as correct."""
    lines = [line for line in text.splitlines() if line.strip()]
    language = detect_language(text)
    expected = (expect_language or order["expect_language"]).split("-")[0]
    return {
        "wrong_language": language is not None and language != expected,
        "language_unverified": language is None,
        "term_status": bool(term_status_errors(text, order.get("terms", []))),
        "placeholder": bool(PLACEHOLDER.search(text)),
        "meta_phrase": bool(META.search(text)),
        "invented_number": _has_invented_number(text, order["task_text"], profile),
        "list_or_heading": any(LIST_OR_HEADING_LINE.match(line) for line in lines)
        or (len(lines) > 1 and any(_is_heading_like(line) for line in lines)),
        "long_dash": bool(LONG_DASH.search(text)),
        "too_long": len(text.split()) > MAX_WORDS,
        "missing_gap": bool(order.get("expect_gap")) and not gaps,
        "missing_required": any(not re.search(p, text, re.IGNORECASE) for p in order.get("must", [])),
        "forbidden_present": any(re.search(p, text, re.IGNORECASE) for p in order.get("must_not", [])),
        "words": len(text.split()),
    }


def _request(url: str, *, payload: dict | None = None, method: str = "GET") -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Accept": "application/json", **({"Content-Type": "application/json"} if data else {})}
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=30) as response:
        return json.loads(response.read())


def run_order(api_url: str, order: dict, profile: str, *, tone: str, language: str | None, timeout: float) -> dict:
    guest_id = _request(f"{api_url}/v1/identity/guest", method="POST")["guest_id"]
    scenario_input = {"task_text": order["task_text"], "freelancer_positioning": profile, "tone": tone}
    if language:
        scenario_input["language"] = language
    start = _request(
        f"{api_url}/v1/products/proposal_ai/scenarios/proposal_ai.generate_v1/start",
        payload={"frontend_id": "web_mirror", "guest_id": guest_id, "input": scenario_input},
        method="POST",
    )
    session_url = f"{api_url}/v1/scenario-sessions/{start['scenario_session_id']}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        session = _request(session_url)
        if session["status"] == "completed":
            return _request(f"{api_url}/v1/results/{session['result_artifact_id']}")["output"]
        if session["status"] == "failed":
            raise RuntimeError(f"session failed: {session}")
        time.sleep(1.0)
    raise TimeoutError(f"timed out waiting for {session_url}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--tone", default="warm", choices=["neutral", "warm", "firm"])
    parser.add_argument("--language", help="explicit proposal language, default: the task's language")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--save-json", type=Path, help="also write the raw outputs here")
    parser.add_argument("--orders", type=Path, default=ORDERS_PATH, help="order set, default: orders.json")
    args = parser.parse_args()

    fixture = json.loads(args.orders.read_text(encoding="utf-8"))
    rows, raw, failed = [], {}, False
    for order in fixture["orders"]:
        profile = order.get("freelancer_positioning", fixture.get("freelancer_positioning"))
        language = order.get("language", args.language)
        try:
            output = run_order(
                args.api_url, order, profile, tone=order.get("tone", args.tone), language=language, timeout=args.timeout
            )
        except (OSError, RuntimeError, TimeoutError, KeyError, ValueError) as exc:
            rows.append(f"| {order['id']} | run failed: {exc} |")
            failed = True
            continue
        raw[order["id"]] = output
        checks = check_proposal(
            output["text"], output.get("gaps", []), order, profile, expect_language=language
        )
        violations = [name for name, value in checks.items() if value is True]
        failed = failed or bool(violations)
        rows.append(
            f"| {order['id']} | {checks['words']} words, {len(output.get('gaps', []))} gaps | "
            + (", ".join(violations) or "ok")
            + " |"
        )
    if args.save_json:
        args.save_json.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    opening = [" ".join(out["text"].split()[:5]).lower() for out in raw.values()]
    print("| order | size | violations |\n|---|---|---|")
    print("\n".join(rows))
    print(f"\nRepeated openings (first five words): {len(opening) - len(set(opening))}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
