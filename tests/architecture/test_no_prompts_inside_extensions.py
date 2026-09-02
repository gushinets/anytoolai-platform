import json
import re
from pathlib import Path

from static_string_resolution import (
    JS_TS_EXTS,
    iter_source_files,
    js_modules,
    js_string_expr_at,
    line_number_at,
)

ROOT = Path(__file__).resolve().parents[2]
EXTENSIONS = ROOT / "extensions"

FORBIDDEN_TOKENS = ["system prompt", "prompt_ref", "provider_policy_ref"]

# A real LLM message object's system role, regardless of quote style or exact key spacing:
# `{ role: "system", content: "..." }`, `{"role": "system", ...}` (JSON), `role: 'system'`. The
# forbidden literal tokens above catch a prompt referenced *by name* (`prompt_ref`) or labeled as
# such in prose (`system prompt`); this catches the actual message *shape* a real prompt payload
# takes, which contains neither of those tokens. Text-level, so it also covers `.md`/`.json` and
# a payload serialized inside a string.
_SYSTEM_ROLE_MESSAGE_RE = re.compile(r"""role["']?\s*:\s*["'`]system["'`]""", re.IGNORECASE)

# Request-shape keys that *carry* a prompt in every real provider/platform request format:
# `role` (a chat message — forbidden when it resolves to the system role) and the instruction
# fields (`instructions` — OpenAI Responses; `systemInstruction`/`system_instruction` — Gemini;
# `system` — Anthropic Messages; `systemPrompt`/`system_prompt` — common app-level names) —
# forbidden whenever their value is a statically-known string at all, since an extension has no
# business assembling *any* instruction text; it sends typed platform requests. Values are
# resolved through the shared static resolver, so `role: SYSTEM_ROLE` with
# `const SYSTEM_ROLE = "system"` (or imported from a sibling module), a concatenated or
# template-built instruction, etc. are all seen as the string they are.
ROLE_KEY = "role"
INSTRUCTION_KEYS = {
    "instructions",
    "systemInstruction",
    "system_instruction",
    "system",
    "systemPrompt",
    "system_prompt",
}
_JS_REQUEST_KEY_RE = re.compile(
    r"""(?<![\w$.?])["']?(role|instructions|systemInstruction|system_instruction|system|systemPrompt|system_prompt)["']?\s*:(?!:)"""
)


def _json_prompt_shape(value: object) -> str | None:
    """First prompt-bearing key in a parsed JSON document, walked structurally."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == ROLE_KEY and isinstance(item, str) and item.lower() == "system":
                return f"{key}: {item!r}"
            if key in INSTRUCTION_KEYS and isinstance(item, str) and item.strip():
                return f"{key}: {item!r}"
            found = _json_prompt_shape(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _json_prompt_shape(item)
            if found is not None:
                return found
    return None


def check_prompts_inside_extensions(extensions_root: Path) -> list[str]:
    offenders: list[str] = []
    files = [
        path
        for path in iter_source_files(extensions_root, JS_TS_EXTS | {".md", ".json"})
        if path.name not in {"AGENTS.md", "README.md"}
    ]
    js = js_modules([path for path in files if path.suffix in JS_TS_EXTS])
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        for token in FORBIDDEN_TOKENS:
            if token in lowered:
                offenders.append(f"{path.relative_to(extensions_root)} contains frontend-forbidden token {token!r}")
        match = _SYSTEM_ROLE_MESSAGE_RE.search(text)
        if match is not None:
            offenders.append(
                f"{path.relative_to(extensions_root)} contains a system-role message shape: {match.group(0)!r}"
            )
        if path.suffix == ".json":
            try:
                shape = _json_prompt_shape(json.loads(text))
            except ValueError:
                shape = None  # not strict JSON (e.g. a tsconfig with comments): text checks above still ran
            if shape is not None:
                offenders.append(f"{path.relative_to(extensions_root)} contains a prompt-bearing field: {shape}")
        elif path.suffix in JS_TS_EXTS:
            stripped = js.texts[path]
            for key_match in _JS_REQUEST_KEY_RE.finditer(stripped):
                key = key_match.group(1)
                value, _ = js_string_expr_at(js, path, key_match.end())
                if value is None:
                    continue
                if (key == ROLE_KEY and value.lower() == "system") or (key != ROLE_KEY and value.strip()):
                    offenders.append(
                        f"{path.relative_to(extensions_root)}:{line_number_at(stripped, key_match.start())} "
                        f"contains a prompt-bearing field: {key}: {value!r}"
                    )
                    break
    return offenders


def test_no_prompts_inside_extensions() -> None:
    offenders = check_prompts_inside_extensions(EXTENSIONS)
    assert offenders == [], "prompts found inside extensions: " + ", ".join(offenders)


def test_constant_indirected_system_role_is_detected(tmp_path: Path) -> None:
    (tmp_path / "roles.ts").write_text('export const SYSTEM_ROLE = "sys" + "tem";\n', encoding="utf-8")
    (tmp_path / "chat.ts").write_text(
        'import { SYSTEM_ROLE } from "./roles";\n'
        'const messages = [{ role: SYSTEM_ROLE, content: "Draft a proposal..." }];\n',
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "chat.ts:2" in offenders[0] and "role: 'system'" in offenders[0]


def test_instruction_fields_are_detected(tmp_path: Path) -> None:
    (tmp_path / "request.ts").write_text(
        'const TONE = "formal";\n'
        "const body = { model: pick(), instructions: `Write a ${TONE} proposal for the client.` };\n",
        encoding="utf-8",
    )
    (tmp_path / "gemini.js").write_text(
        'const req = { "systemInstruction": "You are a proposal writer" };\n', encoding="utf-8"
    )
    (tmp_path / "payload.json").write_text(
        '{"messages": [{"role": "user", "content": "hi"}], "system": "Be concise."}\n',
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 3, offenders


def test_typed_request_shapes_are_not_false_positives(tmp_path: Path) -> None:
    (tmp_path / "types.ts").write_text(
        "interface Message { role: string; content: string }\n"
        'const user = { role: "user", content: input };\n'
        "const passthrough = { instructions: response.instructions };\n"
        "const ok = cond ? system : fallback;\n",
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text('{"name": "ext", "version": "1.0"}\n', encoding="utf-8")
    assert check_prompts_inside_extensions(tmp_path) == []
