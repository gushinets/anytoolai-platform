"""Manual evaluation of ProposalAI against the fixed order set (tests/fixtures/proposal_ai_eval).

Runs every order through a running platform-api + worker (one fresh guest per order, the guest
quota is lifetime), then applies the automatic checks from the QA protocol that need no LLM judge.
Facts about experience, tone distinguishability and "similar project in the first two sentences"
stay manual.

    .quick-check-venv/bin/python scripts/agent/proposal_ai_eval.py --api-url http://localhost:8000 [--tone warm] [--language ru]

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

from anytoolai_platform_actions.structured_llm.cross_validation.persuasive_text import numbers_absent_from_context

ORDERS_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "proposal_ai_eval" / "orders.json"
PLACEHOLDER = re.compile(r"\[[^\]\n]{1,80}\]|\{[^{}\n]{1,80}\}|\{\{|\}\}|\byour name\b|(?<!\w)<[^\W\d][\w ./:-]{0,39}>|<[^\W\d][\w ./:-]{0,39}>(?!\w)", re.IGNORECASE)
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


def _is_heading_like(line: str) -> bool:
    stripped = line.strip()
    return 0 < len(stripped) <= 60 and stripped[-1] not in ".!?:;,…" and len(stripped.split()) <= 8


def check_proposal(
    text: str, gaps: list, order: dict, profile: str, *, expect_language: str | None = None
) -> dict[str, bool | int]:
    """Hard checks (True means violated) plus the word count. `expect_language` overrides the
    order's own (an explicit `--language`); a language other than ru or en is not detectable here
    and skips the check."""
    lines = [line for line in text.splitlines() if line.strip()]
    language = "ru" if _cyrillic_share(text) > 0.5 else "en"
    expected = (expect_language or order["expect_language"]).split("-")[0]
    return {
        "wrong_language": expected in ("ru", "en") and language != expected,
        "placeholder": bool(PLACEHOLDER.search(text)),
        "meta_phrase": bool(META.search(text)),
        "invented_number": _has_invented_number(text, order["task_text"], profile),
        "list_or_heading": any(LIST_OR_HEADING_LINE.match(line) for line in lines)
        or (len(lines) > 1 and any(_is_heading_like(line) for line in lines)),
        "long_dash": bool(LONG_DASH.search(text)),
        "too_long": len(text.split()) > MAX_WORDS,
        "missing_gap": bool(order.get("expect_gap")) and not gaps,
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
    args = parser.parse_args()

    fixture = json.loads(ORDERS_PATH.read_text(encoding="utf-8"))
    profile = fixture["freelancer_positioning"]
    rows, raw, failed = [], {}, False
    for order in fixture["orders"]:
        try:
            output = run_order(args.api_url, order, profile, tone=args.tone, language=args.language, timeout=args.timeout)
        except (OSError, RuntimeError, TimeoutError, KeyError, ValueError) as exc:
            rows.append(f"| {order['id']} | run failed: {exc} |")
            failed = True
            continue
        raw[order["id"]] = output
        checks = check_proposal(
            output["text"], output.get("gaps", []), order, profile, expect_language=args.language
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
