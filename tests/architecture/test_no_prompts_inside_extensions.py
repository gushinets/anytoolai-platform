import re
from pathlib import Path

# Reuse the canonical vendor/build skip-dir set instead of hand-maintaining a copy — this file
# previously had none at all, so a `node_modules` checked out under an extension (real today
# under `extensions/kernel-demo-ce/`) was scanned along with real source.
from test_no_direct_provider_calls_outside_gateway import SKIP_PATH_PARTS

ROOT = Path(__file__).resolve().parents[2]
EXTENSIONS = ROOT / "extensions"

# A real LLM message object's system role, regardless of quote style or exact key spacing:
# `{ role: "system", content: "..." }`, `{"role": "system", ...}` (JSON), `role: 'system'`. The
# forbidden literal tokens above catch a prompt referenced *by name* (`prompt_ref`) or labeled as
# such in prose (`system prompt`); this catches the actual message *shape* a real prompt payload
# takes, which contains neither of those tokens.
_SYSTEM_ROLE_MESSAGE_RE = re.compile(r"""role["']?\s*:\s*["'`]system["'`]""", re.IGNORECASE)


def test_no_prompts_inside_extensions() -> None:
    forbidden = ["system prompt", "prompt_ref", "provider_policy_ref"]
    for path in EXTENSIONS.rglob("*"):
        if any(part in SKIP_PATH_PARTS for part in path.parts):
            continue
        if path.is_file() and path.suffix in {".ts", ".tsx", ".md", ".json"}:
            if path.name in {"AGENTS.md", "README.md"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            lowered = text.lower()
            for token in forbidden:
                assert token not in lowered, f"{path} contains frontend-forbidden token {token}"
            match = _SYSTEM_ROLE_MESSAGE_RE.search(text)
            assert match is None, f"{path} contains a system-role message shape: {match.group(0)!r}"
