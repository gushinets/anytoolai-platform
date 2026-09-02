import json
import re
from pathlib import Path

from static_string_resolution import (
    JS_TS_EXTS,
    iter_source_files,
    js_modules,
    js_string_expr_at,
    line_number_at,
    resolve_js_identifier,
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
# `static_string_resolution.js_modules` blanks every comment (regardless of file type) to
# same-length whitespace before this file ever sees the text, so a real comment sitting inside
# object-literal syntax (`role /* note */: value`) is already invisible to these regexes — plain
# `\s*` is all that's needed here; no JSX-specific comment handling required.
_PROMPT_KEY_ALTERNATION = r"role|instructions|systemInstruction|system_instruction|system|systemPrompt|system_prompt"
_JS_REQUEST_KEY_RE = re.compile(
    rf"""(?<![\w$.?])["']?({_PROMPT_KEY_ALTERNATION})["']?\s*:(?!:)"""
)
# ES2015 shorthand property (`{ role, content }`, `{ instructions }`) builds the exact same
# request object as `{ role: role, ... }` but has no `:` at all — invisible to
# `_JS_REQUEST_KEY_RE` above, which requires one. Matches a tracked key immediately preceded by
# `{`/`,` and immediately followed by `,`/`}` (only whitespace allowed on either side, so a
# colon-form property's *value* position, e.g. `x: role`, never matches — the char right before
# "role" there is `:`, not `{`/`,`). Reported key is resolved through the shared JS resolver at
# its own position (key and value share one name in shorthand form, so there is no separate value
# expression to resolve, but the *name* can still be shadowed/reassigned like any other binding —
# real lexical scope and write order, resolved by a real parser, not approximated here at all).
#
# ponytail: a regex, not a real parser, so it can also match a same-named element inside a plain
# array literal (`[x, role]`) if `role` happens to be a locally-declared constant too — a false
# positive (one extra line to look at), not a false negative, which is the direction this file's
# own conservative design already favors throughout.
_JS_SHORTHAND_KEY_RE = re.compile(
    rf"""[{{,]\s*({_PROMPT_KEY_ALTERNATION})\s*(?=[,}}])"""
)


def _offending_value(key: str, values: frozenset[str]) -> str | None:
    """The first forbidden value in `values` (a resolved `role`/instruction field's every
    statically-known possible value — round 38: a value reachable only through a conditional
    write is still a real, reachable value, so a use is offending if *any* of them is, not only
    if the whole expression resolves to a single, unconditional one), sorted for a deterministic
    report, or `None` if none of them are forbidden."""
    return next(
        (
            value
            for value in sorted(values)
            if (key == ROLE_KEY and value.lower() == "system") or (key != ROLE_KEY and value.strip())
        ),
        None,
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
            found: tuple[int, str, str] | None = None
            for key_match in _JS_REQUEST_KEY_RE.finditer(stripped):
                key = key_match.group(1)
                values = js_string_expr_at(js, path, key_match.end())
                offending = _offending_value(key, values)
                if offending is not None:
                    found = (key_match.start(), key, offending)
                    break
            if found is None:
                for shorthand_match in _JS_SHORTHAND_KEY_RE.finditer(stripped):
                    key = shorthand_match.group(1)
                    values = resolve_js_identifier(js, path, key, shorthand_match.start(1))
                    offending = _offending_value(key, values)
                    if offending is not None:
                        found = (shorthand_match.start(1), key, offending)
                        break
            if found is not None:
                position, key, value = found
                offenders.append(
                    f"{path.relative_to(extensions_root)}:{line_number_at(stripped, position)} "
                    f"contains a prompt-bearing field: {key}: {value!r}"
                )
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


def test_shorthand_role_and_instructions_are_detected(tmp_path: Path) -> None:
    (tmp_path / "chat.ts").write_text(
        'const role = "system";\n'
        'const content = "Draft a proposal from this brief";\n'
        "const messages = [{ role, content }];\n",
        encoding="utf-8",
    )
    (tmp_path / "request.ts").write_text(
        'const instructions = "Write a concise proposal.";\n'
        "const body = { instructions };\n",
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 2, offenders
    assert any("chat.ts:3" in o and "role: 'system'" in o for o in offenders)
    assert any("request.ts:2" in o and "instructions:" in o for o in offenders)


def test_nested_scope_role_does_not_shadow_outer_binding(tmp_path: Path) -> None:
    (tmp_path / "chat.ts").write_text(
        'const role = "system";\n\n'
        "function helper() {\n"
        '  const role = "user";\n'
        "  return role;\n"
        "}\n\n"
        "const messages = [{ role }];\n",
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "role: 'system'" in offenders[0]


def test_role_mutation_inside_uncalled_arrow_does_not_override_outer_value(tmp_path: Path) -> None:
    # `switchToUser` is only *defined* here, never called — `{ role }` is still deterministically
    # a system-role message at runtime. A write reachable only by crossing into a nested
    # function/arrow can never be assumed to have run just because its source position precedes
    # the use site (round 44).
    (tmp_path / "chat.ts").write_text(
        'let role = "system";\n\n'
        'const switchToUser = () => role = "user";\n\n'
        "const messages = [{ role }];\n",
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "role: 'system'" in offenders[0]


def test_deterministic_reassignment_resolves_to_its_final_value(tmp_path: Path) -> None:
    # `role` is deterministically "system" at the use site (round 37): a static reassignment
    # must resolve to the value actually in effect, not to "unresolved" just because a write
    # happened after the declaration.
    (tmp_path / "chat.ts").write_text(
        'let role = "user";\nrole = "system";\n\nconst messages = [{ role }];\n',
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "role: 'system'" in offenders[0]


def test_default_role_and_instructions_parameters_are_detected(tmp_path: Path) -> None:
    (tmp_path / "chat.ts").write_text(
        "function buildMessage(role = \"system\") {\n  return { role };\n}\n", encoding="utf-8"
    )
    (tmp_path / "req.ts").write_text(
        'function buildRequest(instructions = "Write a concise proposal.") {\n'
        "  return { instructions };\n"
        "}\n",
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 2, offenders
    assert any("chat.ts:2" in o and "role: 'system'" in o for o in offenders)
    assert any("req.ts:2" in o and "instructions:" in o for o in offenders)


def test_default_role_parameter_in_concise_arrow_body_is_detected(tmp_path: Path) -> None:
    # No `{ ... }` block at all — a concise (expression) arrow body, exactly as ordinary a form
    # of a parameter default as the braced ones already covered (round 40).
    (tmp_path / "chat.ts").write_text(
        'const buildMessage = (role = "system") => ({ role });\n', encoding="utf-8"
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "role: 'system'" in offenders[0]


def test_concise_arrow_role_parameter_does_not_leak_past_array_comma(tmp_path: Path) -> None:
    # The comma ends the arrow's own body — the next array element must still resolve `role`
    # through the outer "system" binding, not the arrow's own leaked "user" parameter (round 41).
    (tmp_path / "chat.ts").write_text(
        'const role = "system";\n\n'
        "const values = [\n"
        '  (role = "user") => role,\n'
        "  { role },\n"
        "];\n",
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "role: 'system'" in offenders[0]


def test_concise_arrow_role_parameter_does_not_leak_past_object_property_comma(tmp_path: Path) -> None:
    # Single line deliberately: the multi-line form could otherwise close the scope via
    # ASI/newline instead of via the object-literal comma this actually tests for (round 42).
    (tmp_path / "chat.ts").write_text(
        'const role = "system";\n'
        'const config = { normalize: (role = "user") => role, message: { role } };\n',
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "role: 'system'" in offenders[0]


def test_non_default_role_parameter_is_not_a_false_positive(tmp_path: Path) -> None:
    (tmp_path / "chat.ts").write_text(
        "function buildMessage(role) {\n  return { role };\n}\n"
        "function pick(role = getRole()) {\n  return { role };\n}\n",
        encoding="utf-8",
    )
    assert check_prompts_inside_extensions(tmp_path) == []


def test_conditionally_reachable_forbidden_role_is_detected(tmp_path: Path) -> None:
    # `role` is "system" whenever `useUserRole` is false — a real, reachable runtime value, not
    # merely the value the resolver happens to see last in the source (round 38).
    (tmp_path / "chat.ts").write_text(
        'let role = "system";\n\n'
        "if (useUserRole) {\n"
        '  role = "user";\n'
        "}\n\n"
        "const messages = [{ role }];\n",
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "role: 'system'" in offenders[0]


def test_conditionally_reachable_safe_role_does_not_mask_deterministic_one(tmp_path: Path) -> None:
    # The mirror image: a conditional branch introduces a *safe* alternative, but the
    # unconditional value is still "system" and must still be caught.
    (tmp_path / "chat.ts").write_text(
        'let role = "user";\n\n'
        "if (useSystemRole) {\n"
        '  role = "system";\n'
        "}\n\n"
        "const messages = [{ role }];\n",
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "role: 'system'" in offenders[0]


def test_braceless_conditional_write_does_not_mask_forbidden_role(tmp_path: Path) -> None:
    # `if (cond) role = "user";` has no `{}` at all, but is exactly as conditional as the braced
    # form — `"system"` remains reachable whenever `useUserRole` is false (round 39).
    (tmp_path / "chat.ts").write_text(
        'let role = "system";\n\n'
        "if (useUserRole)\n"
        '  role = "user";\n\n'
        "const messages = [{ role }];\n",
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "role: 'system'" in offenders[0]


def test_braceless_else_if_chain_still_resolves_correctly(tmp_path: Path) -> None:
    # Both the `if` and `else if` bodies are braceless — chained single-statement control flow.
    (tmp_path / "chat.ts").write_text(
        'let role = "user";\n\n'
        "if (a)\n"
        '  role = "safe";\n'
        "else if (b)\n"
        '  role = "system";\n\n'
        "const messages = [{ role }];\n",
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "role: 'system'" in offenders[0]


def test_comment_between_role_and_colon_is_detected_in_tsx(tmp_path: Path) -> None:
    (tmp_path / "chat.tsx").write_text(
        'const SYSTEM_ROLE = "system";\n\n'
        "const messages = [\n"
        "  {\n"
        "    role /* request role */: SYSTEM_ROLE,\n"
        '    content: "Draft a proposal",\n'
        "  },\n"
        "];\n",
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "role: 'system'" in offenders[0]


def test_comment_before_shorthand_role_is_detected_in_tsx(tmp_path: Path) -> None:
    (tmp_path / "chat.tsx").write_text(
        'const role = "system";\n\n'
        "const messages = [\n"
        "  {\n"
        "    /* request role */\n"
        "    role,\n"
        '    content: "Draft a proposal",\n'
        "  },\n"
        "];\n",
        encoding="utf-8",
    )
    offenders = check_prompts_inside_extensions(tmp_path)
    assert len(offenders) == 1 and "role: 'system'" in offenders[0]


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
