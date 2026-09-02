from __future__ import annotations

import re
from pathlib import Path

import yaml

from static_string_resolution import (
    JS_TS_EXTS,
    iter_source_files,
    js_modules,
    js_string_literals,
    js_string_values,
    line_number_at,
    parse_python_files,
    python_modules,
    python_string_values,
)

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_FILES = {
    ROOT / "configs" / "kernel" / "provider_policies.yaml",
    ROOT / "configs" / "kernel" / "litellm_router.yaml",
}
SCAN_ROOTS = [
    ROOT / "apps",
    ROOT / "packages",
    ROOT / "extensions",
    ROOT / "configs",
    ROOT / "scripts",
]
SCAN_EXTS = JS_TS_EXTS | {".py", ".yaml", ".yml", ".json"}

# LiteLLM SDK/proxy model strings are "<provider>/<model>" (see configs/kernel/litellm_router.yaml
# litellm_params.model). They must appear only in provider policy/model registry files, never
# hardcoded in application source — regardless of what the surrounding variable/key is named
# (`DEFAULT_MODEL`, `DEFAULT_LLM`, `deployment`, `model_name`, ...). Detection doesn't key off the
# name at all: it requires the literal to be immediately preceded by a quote (`'`/`"`/`` ` `` —
# backtick included for JS/TS template literals, since SCAN_EXTS covers .js/.jsx/.ts/.tsx)/`=`/`:`/
# `,`/bracket/start-of-line, which a bare `<provider>/<name>` embedded in prose or a URL path never
# is (e.g. "github.com/openai/openai-python" — "openai" there is preceded by "/", not by any of
# those).
#
# ponytail: LITELLM_PROVIDERS is a static snapshot of litellm==1.89.3's provider_list (141 names,
# not imported at runtime here — importing `litellm` itself would violate this repo's own
# litellm-import boundary, see docs/architecture/llm-runtime.md). A provider litellm adds after
# this snapshot bypasses the guard until this list is refreshed; re-derive it with
# `python3 -c "import litellm; print(sorted({p.value for p in litellm.provider_list}))"` and paste
# the result back in when bumping the `litellm` pin materially.
LITELLM_PROVIDERS = [
    "a2a", "a2a_agent", "ai21", "ai21_chat", "aiml", "aiohttp_openai", "amazon_nova", "anthropic",
    "anthropic_text", "apertis", "assemblyai", "auto_router", "aws_polly", "azure", "azure_ai",
    "azure_text", "baseten", "bedrock", "bedrock_mantle", "black_forest_labs", "bytez", "cerebras",
    "charity_engine", "chatgpt", "chutes", "clarifai", "cloudflare", "codestral", "cohere",
    "cohere_chat", "cometapi", "compactifai", "cursor", "custom", "custom_openai", "dashscope",
    "databricks", "datarobot", "deepgram", "deepinfra", "deepseek", "docker_model_runner",
    "dotprompt", "elevenlabs", "empower", "fal_ai", "featherless_ai", "fireworks_ai", "friendliai",
    "galadriel", "gemini", "gigachat", "github", "github_copilot", "gradient_ai", "groq",
    "helicone", "heroku", "hosted_vllm", "huggingface", "humanloop", "hyperbolic", "inception",
    "infinity", "jina_ai", "lambda_ai", "langflow", "langfuse", "langgraph", "lemonade",
    "litellm_agent", "litellm_proxy", "llamafile", "lm_studio", "manus", "maritalk", "meta_llama",
    "milvus", "minimax", "mistral", "moonshot", "morph", "nano-gpt", "nebius", "neosantara",
    "nlp_cloud", "novita", "nscale", "nvidia_nim", "nvidia_riva", "oci", "ollama", "ollama_chat",
    "oobabooga", "openai", "openai_like", "openrouter", "ovhcloud", "perplexity", "petals",
    "pg_vector", "poe", "predibase", "publicai", "ragflow", "recraft", "reducto", "replicate",
    "runwayml", "s3_vectors", "sagemaker", "sagemaker_chat", "sagemaker_nova", "sambanova", "sap",
    "scaleway", "snowflake", "soniox", "stability", "synthetic", "tensormesh",
    "text-completion-codestral", "text-completion-inception", "text-completion-openai",
    "together_ai", "topaz", "triton", "v0", "vercel_ai_gateway", "vertex_ai", "vertex_ai_beta",
    "vllm", "volcengine", "voyage", "wandb", "watsonx", "watsonx_text", "xai", "xiaomi_mimo",
    "xinference", "zai",
]
LITELLM_MODEL_STRING_RE = re.compile(
    r"""(?:^|[\s"'`=:,\[{(])"""
    rf"""(?:{"|".join(sorted(LITELLM_PROVIDERS, key=len, reverse=True))})"""
    r"/[\w.\-]+",
    re.MULTILINE,  # `^` is each line's start: JS/TS text is now scanned whole, not per line
)
# A match still isn't necessarily a real hardcode: `"https://example.com?model=openai/gpt-4.1"` —
# a `?model=`/`&model=` query value inside a URL string — has `=` right before the provider name,
# same as a real assignment. `_is_url_query_value` filters those out, but narrowly: it requires an
# actual adjacent `?key=`/`&key=` token, not merely "some URL appears earlier in this string" (a
# real hardcode can share a quoted string with an unrelated URL, e.g. a serialized JSON blob).


# The `=` immediately preceding a `?key=`/`&key=` URL query value. Anchored (`$`) to the end of
# the string it's searched against, so it only matches when the query-key syntax sits directly
# against the candidate match's own prefix `=` — not merely "some `?...=` exists earlier".
_URL_QUERY_KEY_RE = re.compile(r"[?&][\w.\-]+=$")


def _is_url_query_value(value: str, spans: list[tuple[int, int]], position: int) -> bool:
    """True if `position` (the candidate match's prefix char) is genuinely a `?key=`/`&key=` URL
    query value: it must be `=`, sit inside one of `spans` (an enclosing string's content) and
    have a `://` before it within that span, AND have a `?`/`&`-prefixed key directly adjacent to
    it (`...?model=` / `...&provider=`).

    `position` is the match's *prefix* char, one position before a quoted span's own content
    start when the prefix char is the opening quote itself — spans are checked with
    `start - 1 <= position < end` for that reason, not `start <= position < end`.

    The `://`-in-span condition alone is too broad: a serialized-JSON string like
    `{"callback":"https://example.com","model":"openai/gpt-4.1"}` also contains `://` earlier in
    the same string, but the real `"model":"openai/..."` field there is a genuine hardcode, not
    part of the URL — its prefix char is `"`, not `=`, and there's no `?`/`&`-prefixed key right
    before it.
    """
    if value[position] != "=":
        return False
    for start, end in spans:
        if start - 1 <= position < end:
            prefix = value[start : position + 1]
            if "://" in prefix and _URL_QUERY_KEY_RE.search(prefix):
                return True
    return False


def _offending_match(value: str) -> str | None:
    """First real (non-URL-query) LiteLLM-format `provider/model` match in an already-isolated
    string value (a Python string-literal's decoded content, a YAML scalar's decoded content, a
    statically folded JS/TS string expression — values a real parser/resolver has already
    separated from comments/surrounding syntax), or `None`."""
    spans = [(0, len(value))]
    for match in LITELLM_MODEL_STRING_RE.finditer(value):
        if not _is_url_query_value(value, spans, match.start()):
            return match.group(0)
    return None


def _first_offender(values: list[tuple[int, str]]) -> tuple[int, str] | None:
    """(position, matched-text) of the lowest-positioned real hardcode among `(position, value)`
    pairs, or `None`."""
    best: tuple[int, str] | None = None
    for position, value in values:
        match = _offending_match(value)
        if match is not None and (best is None or position < best[0]):
            best = (position, match)
    return best


def _iter_yaml_scalars(node: yaml.Node):
    if isinstance(node, yaml.ScalarNode):
        yield node
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            yield from _iter_yaml_scalars(item)
    elif isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            yield from _iter_yaml_scalars(key_node)
            yield from _iter_yaml_scalars(value_node)


def _yaml_offender(root: Path, path: Path) -> tuple[int, str] | None:
    """(lineno, matched-text) of the first real hardcode in `path`'s scalar values, using a real
    YAML parser instead of hand-rolled `#`-is-a-comment tracking.

    `#` is not a comment marker inside a YAML block scalar (`|`/`>`) — it's literal content — and
    a hand-rolled line scanner has no way to know it's inside one without re-implementing YAML's
    block-scalar indentation rules. `yaml.compose_all` already does that correctly (per document);
    walking each document's node graph gives real scalar values (block/flow, quoted/unquoted —
    all resolved the same way) with real source positions, with no separate comment-stripping
    step needed. Uses `compose_all`, not `compose` (round 15: `compose` only accepts a single
    document and raises on a valid multi-document file — `compose_all` scans every document; line
    numbers stay absolute across `---` boundaries, not reset per document (verified)).

    A genuine parse failure is a loud test failure, not a silent skip of the whole file — matches
    this repo's own anti-silent-skip convention, and every real `.yaml`/`.yml` file in
    `SCAN_ROOTS` parses cleanly today (verified), so this can't newly break on anything that
    exists.
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        documents = list(yaml.compose_all(text))
    except yaml.YAMLError as exc:
        raise AssertionError(f"could not parse {path.relative_to(root)} as YAML: {exc}") from exc
    values = [
        (scalar.start_mark.line + 1, scalar.value)
        for document in documents
        if document is not None
        for scalar in _iter_yaml_scalars(document)
        if isinstance(scalar.value, str)
    ]
    return _first_offender(values)


def _json_offender(path: Path) -> tuple[int, str] | None:
    """`.json` has no comment syntax and only ever contains standard double-quoted strings, so a
    per-line regex over the raw text is exact here."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    for lineno, line in enumerate(text.splitlines(), start=1):
        spans = [(start + 1, end) for start, (end, _) in js_string_literals(line).items()]
        for match in LITELLM_MODEL_STRING_RE.finditer(line):
            if not _is_url_query_value(line, spans, match.start()):
                return lineno, match.group(0)
    return None


def _js_offender(js, path: Path) -> tuple[int, str] | None:
    """(lineno, matched-text) of the first real hardcode in a JS/TS file: a direct regex match on
    the comment-blanked text (every comment, in every file type, is already replaced with
    same-length whitespace by the real parser — see `static_string_resolution.js_modules`), or
    any *statically folded* string expression — a `+` concatenation across any number of
    lines/parens, a template literal interpolating a known constant (`` `${provider}/gpt-4.1` ``
    with `const provider = "openai"`), or a constant imported from a sibling module, all resolved
    through real lexical scope and write order by the shared static resolver."""
    text = js.texts[path]
    spans = [(start + 1, end) for start, (end, _) in js_string_literals(text).items()]
    direct = next(
        (
            (match.start(), match.group(0))
            for match in LITELLM_MODEL_STRING_RE.finditer(text)
            if not _is_url_query_value(text, spans, match.start())
        ),
        None,
    )
    folded = _first_offender(js_string_values(js, path))
    candidates = [found for found in (direct, folded) if found is not None]
    if not candidates:
        return None
    offset, match = min(candidates)
    return line_number_at(text, offset), match


def check_litellm_model_strings(root: Path, scan_roots: list[Path], allowed_files: set[Path]) -> list[str]:
    """Offender descriptions for every LiteLLM-format model string hardcoded under `scan_roots`
    (outside `allowed_files`), each rooted under `root` for import resolution and reporting."""
    files = [
        path
        for scan_root in scan_roots
        for path in iter_source_files(scan_root, SCAN_EXTS, {"tests"})
        if path not in allowed_files
    ]
    # Python goes through the real AST plus the shared static resolver (round 15 found `tokenize`
    # misses Python 3.12+ f-strings; `ast` node shapes are stable and comments don't exist in the
    # AST at all). A `"openai/" + "gpt-4.1"` concatenation, an f-string interpolating a known
    # constant (`PROVIDER = "openai"; MODEL = f"{PROVIDER}/gpt-4.1"`), or a constant imported from
    # another module all fold to the string they build; a genuinely dynamic value never does.
    py = python_modules(root, parse_python_files(path for path in files if path.suffix == ".py"))
    js = js_modules([path for path in files if path.suffix in JS_TS_EXTS])

    offenders: list[str] = []
    for path in files:
        if path.suffix == ".py":
            found = _first_offender(python_string_values(py, path)) if path in py.trees else None
        elif path.suffix in (".yaml", ".yml"):
            found = _yaml_offender(root, path)
        elif path.suffix == ".json":
            found = _json_offender(path)
        else:
            found = _js_offender(js, path)
        if found is not None:
            lineno, offender = found
            offenders.append(f"{path.relative_to(root)}:{lineno}: {offender!r}")
    return offenders


def test_litellm_model_strings_only_in_provider_config() -> None:
    offenders = check_litellm_model_strings(ROOT, SCAN_ROOTS, ALLOWED_FILES)
    assert offenders == [], "LiteLLM-format model strings found outside provider config: " + ", ".join(
        offenders
    )


def test_python_fstring_of_known_constant_is_detected(tmp_path: Path) -> None:
    (tmp_path / "providers.py").write_text('PROVIDER = "openai"\n', encoding="utf-8")
    (tmp_path / "config.py").write_text(
        'from providers import PROVIDER\nMODEL = f"{PROVIDER}/gpt-4.1"\n', encoding="utf-8"
    )
    (tmp_path / "dynamic.py").write_text(
        'def model(name: str) -> str:\n    return f"openai/{name}"\n', encoding="utf-8"
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.py:2: 'openai/gpt-4.1'"], offenders


def test_js_template_literal_of_known_constant_is_detected(tmp_path: Path) -> None:
    (tmp_path / "providers.ts").write_text('export const provider = "open" + "ai";\n', encoding="utf-8")
    (tmp_path / "config.ts").write_text(
        'import { provider } from "./providers";\n'
        "const model = `${provider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    (tmp_path / "dynamic.ts").write_text(
        "export const model = (name: string) => `openai/${name}`;\n", encoding="utf-8"
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.ts:2: 'openai/gpt-4.1'"], offenders


def test_deterministic_reassignment_resolves_to_its_final_value(tmp_path: Path) -> None:
    # `provider` is deterministically "openai" at the use site (round 37): a static reassignment
    # must resolve to the value actually in effect, not to "unresolved" just because a write
    # happened after the declaration.
    (tmp_path / "config.ts").write_text(
        'let provider = "cohere";\n'
        'provider = "openai";\n\n'
        "const model = `${provider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.ts:4: 'openai/gpt-4.1'"], offenders


def test_default_js_provider_parameter_is_detected(tmp_path: Path) -> None:
    (tmp_path / "model.ts").write_text(
        "function chooseModel(provider = \"openai\") {\n  return `${provider}/gpt-4.1`;\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "dynamic.ts").write_text(
        "function chooseOther(provider) {\n  return `${provider}/gpt-4.1`;\n}\n", encoding="utf-8"
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:2: 'openai/gpt-4.1'"], offenders


def test_default_provider_in_concise_arrow_body_is_detected(tmp_path: Path) -> None:
    # No `{ ... }` block at all — a concise (expression) arrow body, exactly as ordinary a form
    # of a function/arrow parameter default as the braced ones already covered (round 40). Uses
    # plain concatenation, not a template literal, so it can't accidentally resolve via a
    # coincidental `{` inside a `${...}` hole.
    (tmp_path / "model.ts").write_text(
        'const chooseModel = (provider = "openai") => provider + "/gpt-4.1";\n', encoding="utf-8"
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:1: 'openai/gpt-4.1'"], offenders


def test_conditionally_reachable_provider_is_detected(tmp_path: Path) -> None:
    # `openai/gpt-4.1` remains a real, reachable value whenever `useFallback` is false — the
    # resolver must not discard it just because a later, conditional write also exists (round 38).
    (tmp_path / "config.ts").write_text(
        'let provider = "openai";\n\n'
        "if (useFallback) {\n"
        '  provider = "internal";\n'
        "}\n\n"
        "const model = `${provider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.ts:7: 'openai/gpt-4.1'"], offenders


def test_braceless_conditional_write_does_not_mask_provider(tmp_path: Path) -> None:
    # `if (cond) provider = "";` has no `{}` at all, but is exactly as conditional as the braced
    # form — `openai/gpt-4.1` remains reachable whenever `useFallback` is false (round 39).
    (tmp_path / "config.ts").write_text(
        'let provider = "openai";\n\n'
        "if (useFallback)\n"
        '  provider = "";\n\n'
        'const model = provider + "/gpt-4.1";\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.ts:6: 'openai/gpt-4.1'"], offenders


def test_braceless_while_loop_write_does_not_mask_provider(tmp_path: Path) -> None:
    (tmp_path / "config.ts").write_text(
        'let provider = "openai";\n\n'
        "while (useFallback)\n"
        '  provider = "internal";\n\n'
        'const model = provider + "/gpt-4.1";\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.ts:6: 'openai/gpt-4.1'"], offenders


def test_concise_arrow_parameter_does_not_leak_past_asi_newline(tmp_path: Path) -> None:
    # Semicolon-free TS: the arrow's own concise body ends at the newline, not at the file's
    # next `;` — the outer `provider` must still be "openai" for the later template (round 41).
    (tmp_path / "config.ts").write_text(
        'const provider = "openai"\n\n'
        'const normalize = (provider = "internal") => provider\n\n'
        "const model = `${provider}/gpt-4.1`\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.ts:5: 'openai/gpt-4.1'"], offenders


def test_concise_arrow_parameter_does_not_leak_past_array_comma(tmp_path: Path) -> None:
    # The comma ends the arrow's own body — the next array element must still resolve `provider`
    # through the outer binding, not the arrow's own leaked parameter (round 41).
    (tmp_path / "config.ts").write_text(
        'const provider = "openai";\n\n'
        "const values = [\n"
        '  (provider = "internal") => provider,\n'
        "  `${provider}/gpt-4.1`,\n"
        "];\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.ts:5: 'openai/gpt-4.1'"], offenders


def test_concise_arrow_parameter_does_not_leak_past_object_property_comma(tmp_path: Path) -> None:
    # The comma after the `normalize` property ends the arrow's own body — the sibling `model`
    # property must still resolve `provider` through the outer binding, not the arrow's own
    # leaked parameter. Single line deliberately: the multi-line form could otherwise close the
    # scope via ASI/newline instead of via the object-literal comma this actually tests for
    # (round 42).
    (tmp_path / "config.ts").write_text(
        'const provider = "openai";\n'
        'const config = { normalize: (provider = "internal") => provider, model: `${provider}/gpt-4.1` };\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.ts:2: 'openai/gpt-4.1'"], offenders


def test_nested_scope_js_provider_does_not_shadow_outer_binding(tmp_path: Path) -> None:
    (tmp_path / "config.ts").write_text(
        'const provider = "openai";\n\n'
        "function helper() {\n"
        '  const provider = "cohere";\n'
        "  return provider;\n"
        "}\n\n"
        "const model = `${provider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.ts:8: 'openai/gpt-4.1'"], offenders


def test_provider_mutation_inside_uncalled_arrow_does_not_override_outer_value(tmp_path: Path) -> None:
    # `setFallback` is only *defined* here, never called — at module evaluation `provider` is
    # still deterministically "openai", so the real model is `openai/gpt-4.1`. A write reachable
    # only by crossing into a nested function/arrow can never be assumed to have run just because
    # its source position precedes the use site (round 44).
    (tmp_path / "model.ts").write_text(
        'let provider = "openai";\n\n'
        'const setFallback = () => provider = "internal";\n\n'
        "const model = `${provider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:5: 'openai/gpt-4.1'"], offenders


def test_provider_survives_as_const_assertion(tmp_path: Path) -> None:
    # `as const` is a compile-time-only TypeScript annotation — the runtime value is exactly the
    # inner literal, "openai" (round 46).
    (tmp_path / "model.ts").write_text(
        'const provider = "openai" as const;\nconst model = `${provider}/gpt-4.1`;\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:2: 'openai/gpt-4.1'"], offenders


def test_var_declared_inside_if_block_is_visible_at_function_scope(tmp_path: Path) -> None:
    # `var` is function-scoped, not block-scoped — it escapes the `if` block the same way real JS
    # hoisting does, unlike `let`/`const` (round 46). The write itself still correctly stays
    # conditional (added to the reachable set, not replacing anything), since the `if` might not
    # run — there's nothing else in scope for the deterministic branch to replace here anyway.
    (tmp_path / "model.ts").write_text(
        "function buildModel(enabled) {\n"
        "  if (enabled) {\n"
        '    var provider = "openai";\n'
        "  }\n"
        '  return `${provider}/gpt-4.1`;\n'
        "}\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:5: 'openai/gpt-4.1'"], offenders


def test_for_header_declaration_is_visible_inside_the_loop_body(tmp_path: Path) -> None:
    (tmp_path / "model.ts").write_text(
        'for (let provider = "openai", i = 0; i < 1; i++) {\n'
        "  const model = `${provider}/gpt-4.1`;\n"
        "}\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:2: 'openai/gpt-4.1'"], offenders


def test_multi_hop_import_chain_resolves_regardless_of_file_traversal_order(tmp_path: Path) -> None:
    # Filenames deliberately put the consumer (a-config.ts) before the intermediate (m-alias.ts)
    # and the source (z-provider.ts) in sorted/traversal order — resolution must not depend on
    # every file's own imports already being installed by the time a dependent file is processed
    # (round 46: eager, single-pass resolution made this order-dependent).
    (tmp_path / "z-provider.ts").write_text('export const provider = "openai";\n', encoding="utf-8")
    (tmp_path / "m-alias.ts").write_text(
        'import { provider } from "./z-provider";\nexport const MODEL_PROVIDER = provider;\n',
        encoding="utf-8",
    )
    (tmp_path / "a-config.ts").write_text(
        'import { MODEL_PROVIDER } from "./m-alias";\nconst model = `${MODEL_PROVIDER}/gpt-4.1`;\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["a-config.ts:2: 'openai/gpt-4.1'"], offenders


def test_uninitialized_declaration_with_later_assignment_is_detected(tmp_path: Path) -> None:
    # `let provider;` alone used to register no binding at all, so the later plain assignment had
    # no declaration to attach its write to and was silently dropped (round 47).
    (tmp_path / "model.ts").write_text(
        'let provider;\nprovider = "openai";\n\nconst model = `${provider}/gpt-4.1`;\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:4: 'openai/gpt-4.1'"], offenders


def test_conditional_var_redeclaration_preserves_earlier_reachable_value(tmp_path: Path) -> None:
    # A `var` redeclared inside a conditional branch is one runtime binding, not two — when the
    # branch doesn't run, the earlier value ("openai") is still reachable. The resolver used to
    # give each redeclaration its own separate declaration object, so the later one (wrongly
    # treated as unconditionally deterministic merely for introducing "a" binding) hid the earlier
    # one entirely — the gate reported only "internal/gpt-4.1" and missed "openai/gpt-4.1" being
    # reachable at all (round 47). The gate reports the lowest-positioned reachable value per
    # file, and both candidate values share one position (the template), so the earlier-written
    # ("openai") one — now visible again — is what's reported.
    (tmp_path / "model.ts").write_text(
        "function pick(useFallback) {\n"
        '  var provider = "openai";\n\n'
        "  if (useFallback) {\n"
        '    var provider = "internal";\n'
        "  }\n\n"
        "  return `${provider}/gpt-4.1`;\n"
        "}\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:8: 'openai/gpt-4.1'"], offenders


def test_bare_local_reexport_resolves_without_self_cycle(tmp_path: Path) -> None:
    # A bare `export { name };` (no `from`) re-exporting this same file's own ordinary (no
    # `export` keyword) local declaration used to be recorded as a self-pointing re-export, so
    # `resolveExport` walked straight back into its own cycle guard and gave up (round 47).
    (tmp_path / "z-provider.ts").write_text(
        'const provider = "openai";\nexport { provider };\n', encoding="utf-8"
    )
    (tmp_path / "a-config.ts").write_text(
        'import { provider } from "./z-provider";\nconst model = `${provider}/gpt-4.1`;\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["a-config.ts:2: 'openai/gpt-4.1'"], offenders


def test_star_reexport_resolves_through_the_module_graph(tmp_path: Path) -> None:
    # `export * from "./x"` was never even read into the export map, so an import going through
    # one couldn't resolve under any file order (round 47).
    (tmp_path / "z-provider.ts").write_text('export const provider = "openai";\n', encoding="utf-8")
    (tmp_path / "index.ts").write_text('export * from "./z-provider";\n', encoding="utf-8")
    (tmp_path / "a-config.ts").write_text(
        'import { provider } from "./index";\nconst model = `${provider}/gpt-4.1`;\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["a-config.ts:2: 'openai/gpt-4.1'"], offenders


def test_barrel_reexport_resolves_the_real_source_declaration(tmp_path: Path) -> None:
    (tmp_path / "z-provider.ts").write_text('export const provider = "openai";\n', encoding="utf-8")
    (tmp_path / "barrel.ts").write_text(
        'export { provider as MODEL_PROVIDER } from "./z-provider";\n', encoding="utf-8"
    )
    (tmp_path / "a-config.ts").write_text(
        'import { MODEL_PROVIDER } from "./barrel";\nconst model = `${MODEL_PROVIDER}/gpt-4.1`;\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["a-config.ts:2: 'openai/gpt-4.1'"], offenders


def test_default_exported_provider_is_detected(tmp_path: Path) -> None:
    # A default import/export used no module-graph edge at all — `resolveImports` only ever read
    # `importClause.namedBindings`, and `export default ...;` is an `ExportAssignment`, a
    # different AST node the export side never looked at either (round 50).
    (tmp_path / "provider.ts").write_text('const provider = "openai";\nexport default provider;\n', encoding="utf-8")
    (tmp_path / "config.ts").write_text(
        'import provider from "./provider";\nconst model = `${provider}/gpt-4.1`;\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.ts:2: 'openai/gpt-4.1'"], offenders


def test_default_export_via_named_reexport_is_detected(tmp_path: Path) -> None:
    # `export { default as provider } from "./x"` re-exports the *default* export under a chosen
    # name — resolves through the same reserved `"default"` export-map key an ordinary default
    # import/export uses (round 50).
    (tmp_path / "provider.ts").write_text('export default "openai";\n', encoding="utf-8")
    (tmp_path / "barrel.ts").write_text(
        'export { default as provider } from "./provider";\n', encoding="utf-8"
    )
    (tmp_path / "config.ts").write_text(
        'import { provider } from "./barrel";\nconst model = `${provider}/gpt-4.1`;\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.ts:2: 'openai/gpt-4.1'"], offenders


def test_later_parameter_default_resolves_an_earlier_one(tmp_path: Path) -> None:
    # A braced function's parameters were registered inside the function's own *body* scope, which
    # a later parameter's default value expression never actually enters syntactically — so it
    # couldn't see an earlier parameter's binding at all (round 50).
    (tmp_path / "model.ts").write_text(
        "function chooseModel(\n"
        '  provider = "openai",\n'
        "  model = `${provider}/gpt-4.1`,\n"
        ") {\n"
        "  return model;\n"
        "}\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:3: 'openai/gpt-4.1'"], offenders


def test_body_local_declaration_does_not_shadow_a_parameter_defaults_outer_reference(tmp_path: Path) -> None:
    # A parameter default evaluates in a distinct "parameter environment" that sits *outside* the
    # function body's own lexical environment — a same-named body-local declaration does not
    # shadow it, even though it's declared in the same function (round 50 routed parameter
    # defaults into the body's own scope, so the body-local `provider = "internal"` incorrectly
    # won lexical lookup over the real outer `"openai"` binding the default actually sees at
    # runtime; round 51 fixes it).
    (tmp_path / "model.ts").write_text(
        'const provider = "openai";\n\n'
        "function chooseModel(\n"
        "  model = `${provider}/gpt-4.1`,\n"
        ") {\n"
        '  const provider = "internal";\n'
        "  return model;\n"
        "}\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:4: 'openai/gpt-4.1'"], offenders


def test_unconditional_parameter_reassignment_inside_body_still_resolves_to_its_final_value(
    tmp_path: Path,
) -> None:
    # A parameter's own scope moved to the function node itself (round 51, to keep a body-local
    # declaration from shadowing a default's outer reference — see the test above), which put the
    # function's own top-level body `Block` *between* an ordinary body-level write and that scope.
    # Without an explicit exemption for a function's own body, that would misread every plain,
    # unconditional reassignment of a parameter from directly inside the body as merely
    # conditional, losing precision `isDeterministicWrite` already had for this exact shape before
    # round 51 (self-caught while fixing the shadowing bug above, not part of the review).
    (tmp_path / "model.ts").write_text(
        "function pick(provider = \"safe\") {\n"
        '  provider = "openai";\n'
        "  return `${provider}/gpt-4.1`;\n"
        "}\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:3: 'openai/gpt-4.1'"], offenders


def test_body_var_redeclaring_a_parameter_starts_from_the_parameters_value(tmp_path: Path) -> None:
    # Real JS (`FunctionDeclarationInstantiation`) copies a parameter's own current value into a
    # same-named body `var` binding at function entry, even with parameter-default expressions
    # present — before any of the `var`'s own body-level writes run. Splitting the parameter scope
    # from the body scope (round 51) made a same-named body `var` an entirely independent,
    # initially-empty binding instead, hiding the parameter's real value from a reference that
    # comes before the `var`'s own declaration/write (round 52).
    (tmp_path / "model.ts").write_text(
        'function chooseModel(provider = "openai") {\n'
        "  const model = `${provider}/gpt-4.1`;\n"
        "  var provider;\n\n"
        "  return model;\n"
        "}\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:2: 'openai/gpt-4.1'"], offenders


def test_body_var_redeclaring_a_parameter_with_its_own_initializer_still_starts_from_the_parameter(
    tmp_path: Path,
) -> None:
    # Same as above, but the body `var` has its own initializer too — that initializer's write
    # still only takes effect once the `var provider = "internal";` statement itself executes;
    # a reference earlier in the body sees the parameter's value, not the later initializer's.
    (tmp_path / "model.ts").write_text(
        'function chooseModel(provider = "openai") {\n'
        "  const model = `${provider}/gpt-4.1`;\n"
        '  var provider = "internal";\n\n'
        "  return model;\n"
        "}\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:2: 'openai/gpt-4.1'"], offenders


def test_assignment_before_a_local_var_declaration_resolves_to_the_hoisted_binding(tmp_path: Path) -> None:
    # A `var`'s binding is hoisted to function entry regardless of where its declaration
    # textually sits — an assignment appearing before the `var` statement still targets that same
    # hoisted binding, not some unrelated outer scope's same-named binding (round 53: a single
    # source-order traversal made binding *existence* depend on how far traversal had gotten, so
    # this assignment found no binding registered yet and was silently dropped).
    (tmp_path / "model.ts").write_text(
        "function chooseModel() {\n"
        '  provider = "openai";\n'
        "  var provider;\n\n"
        "  return `${provider}/gpt-4.1`;\n"
        "}\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:5: 'openai/gpt-4.1'"], offenders


def test_parameter_reassigned_before_a_same_named_var_still_resolves_the_parameters_original_value(
    tmp_path: Path,
) -> None:
    # The hoisted `var provider;` binding already exists at function entry — a reassignment that
    # textually precedes its declaration statement still targets *that* hoisted binding, not the
    # parameter's own. An earlier reference (the `model` template) therefore still sees the
    # parameter's own function-entry value, unaffected by a reassignment that happens later at
    # runtime (round 53: this reassignment was, at the time of traversal, wrongly attached to the
    # *parameter's* own binding instead — because the `var`'s binding didn't exist yet — which then
    # leaked into the round-52 function-entry seed via `copyDeclValue`, since that seed replays the
    # parameter's own timeline in full).
    (tmp_path / "model.ts").write_text(
        'function chooseModel(provider = "openai") {\n'
        "  const model = `${provider}/gpt-4.1`;\n\n"
        '  provider = "internal";\n'
        "  var provider;\n\n"
        "  return model;\n"
        "}\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:2: 'openai/gpt-4.1'"], offenders


def test_short_circuit_and_reassignment_does_not_replace_the_deterministic_value(tmp_path: Path) -> None:
    # The RHS of `&&` only evaluates when the LHS is truthy — `useFallback && (provider =
    # "internal")` never runs the assignment at all when `useFallback` is falsy, exactly like an
    # `if` body that might not run. `isDeterministicWrite` didn't recognize this AST position as
    # conditional at all, so the write replaced the reachable set instead of joining it, hiding the
    # still-reachable "openai" value entirely (round 54).
    (tmp_path / "model.ts").write_text(
        'let provider = "openai";\n\n'
        'useFallback && (provider = "internal");\n\n'
        "const model = `${provider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:5: 'openai/gpt-4.1'"], offenders


def test_ternary_branch_reassignment_does_not_replace_the_deterministic_value(tmp_path: Path) -> None:
    # Only one branch of a ternary ever runs — a reassignment in `whenTrue`/`whenFalse` is exactly
    # as conditional as an `if`/`else` arm (round 54).
    (tmp_path / "model.ts").write_text(
        'let provider = "openai";\n\n'
        "useFallback\n"
        '  ? (provider = "internal")\n'
        "  : null;\n\n"
        "const model = `${provider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:7: 'openai/gpt-4.1'"], offenders


def test_self_referential_reassignment_resolves_using_the_pre_write_value(tmp_path: Path) -> None:
    # Real JS evaluates an assignment's RHS fully, using the *pre-write* state, before ever
    # committing the new value. `provider = provider + "ai"`'s own `provider` reference inside the
    # RHS is textually *after* `provider =`, so resolving it at its own natural position always
    # included this same not-yet-applied write, hit the fold cycle guard, and lost the value
    # entirely rather than resolving to "open" + "ai" (round 56).
    (tmp_path / "model.ts").write_text(
        'let provider = "open";\n'
        'provider = provider + "ai";\n\n'
        "const model = `${provider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:4: 'openai/gpt-4.1'"], offenders


def test_compound_plus_equals_concatenates_the_pre_write_value(tmp_path: Path) -> None:
    # `provider += "ai"` was never even recorded as a write at all — the collector only matched
    # a plain `=` assignment (round 56).
    (tmp_path / "model.ts").write_text(
        'let provider = "open";\n'
        'provider += "ai";\n\n'
        "const model = `${provider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:4: 'openai/gpt-4.1'"], offenders


def test_logical_or_equals_from_a_falsy_value_is_detected(tmp_path: Path) -> None:
    # `provider ||= "openai"` only assigns when `provider` is currently falsy — never recorded as
    # a write at all before this round, so the gate saw only the empty initializer (round 56).
    (tmp_path / "model.ts").write_text(
        'let provider = "";\n'
        'provider ||= "openai";\n\n'
        "const model = `${provider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:4: 'openai/gpt-4.1'"], offenders


def test_nested_assignment_inside_compound_logical_assignment_rhs_is_conditional(tmp_path: Path) -> None:
    # `enabled &&= (provider = "internal")` never runs the nested assignment at all when `enabled`
    # is falsy — the exact same short-circuit round 54 already modeled for the plain `&&`
    # operator, just on its compound-assignment form (`&&=`), which used a different operator
    # token round 54 didn't check for (round 56, self-caught while extending that fix — not part
    # of any review).
    (tmp_path / "model.ts").write_text(
        'let provider = "openai";\n\n'
        'enabled &&= (provider = "internal");\n\n'
        "const model = `${provider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:5: 'openai/gpt-4.1'"], offenders


def test_non_default_parameter_deterministically_assigned_is_detected(tmp_path: Path) -> None:
    # A parameter with no default value was never registered as a binding at all — an assignment
    # to it had nowhere to attach, so it was silently dropped and the parameter's later use stayed
    # unresolved even though it's deterministically "openai" at runtime (round 57).
    (tmp_path / "model.ts").write_text(
        "function chooseModel(provider) {\n"
        '  provider = "openai";\n\n'
        "  return `${provider}/gpt-4.1`;\n"
        "}\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:4: 'openai/gpt-4.1'"], offenders


def test_non_default_parameter_shadows_a_same_named_outer_provider(tmp_path: Path) -> None:
    # A non-default parameter still lexically shadows a same-named outer binding for the whole
    # function — unregistered, it let a reference inside the function fall through to the outer
    # constant instead, a false positive claiming a specific value the parameter's real (dynamic,
    # caller-provided) runtime value never actually has (round 57).
    (tmp_path / "model.ts").write_text(
        'const provider = "openai";\n\n'
        "function chooseModel(provider) {\n"
        "  return `${provider}/gpt-4.1`;\n"
        "}\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == [], offenders


def test_namespace_import_property_access_is_detected(tmp_path: Path) -> None:
    # `import * as providers from "./providers"` never registered a binding for `providers` at
    # all, and `providers.primaryProvider` (a `PropertyAccessExpression`) was never resolved by
    # `foldExprInner` either — the resolver had no way to fold either half of this ordinary
    # cross-module property access (round 58).
    (tmp_path / "providers.ts").write_text('export const primaryProvider = "openai";\n', encoding="utf-8")
    (tmp_path / "config.ts").write_text(
        'import * as providers from "./providers";\n\n'
        "const model = `${providers.primaryProvider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["config.ts:3: 'openai/gpt-4.1'"], offenders


def test_local_object_literal_property_access_is_detected(tmp_path: Path) -> None:
    # `config.primaryProvider`, where `config` is a fully static local object literal, is ordinary
    # TypeScript — the resolver had no model for object/member lookup at all (round 58).
    (tmp_path / "model.ts").write_text(
        "const config = {\n"
        '  primaryProvider: "openai",\n'
        "};\n\n"
        "const model = `${config.primaryProvider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:5: 'openai/gpt-4.1'"], offenders


def test_element_access_with_a_static_string_key_is_detected(tmp_path: Path) -> None:
    # `config["primaryProvider"]` is the same static property lookup as `config.primaryProvider`,
    # just via bracket notation with a literal key (round 58).
    (tmp_path / "model.ts").write_text(
        'const config = { primaryProvider: "openai" };\n\n'
        'const model = `${config["primaryProvider"]}/gpt-4.1`;\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:3: 'openai/gpt-4.1'"], offenders


def test_element_access_with_a_dynamic_key_is_not_a_false_positive(tmp_path: Path) -> None:
    # `config[key]` has no statically-known property name to look up — must stay unresolved rather
    # than guessing (round 58).
    (tmp_path / "model.ts").write_text(
        'const config = { primaryProvider: "openai" };\n\n'
        "function pick(key) {\n"
        "  return `${config[key]}/gpt-4.1`;\n"
        "}\n",
        encoding="utf-8",
    )
    assert check_litellm_model_strings(tmp_path, [tmp_path], set()) == []


def test_reassigned_object_property_access_is_not_a_false_positive(tmp_path: Path) -> None:
    # A `let` reassigned to a second object literal has no single, unambiguous shape — resolving
    # its property to either literal's value would be a guess, not a static fact (round 58).
    (tmp_path / "model.ts").write_text(
        'let config = { primaryProvider: "openai" };\n'
        'config = { primaryProvider: "internal" };\n\n'
        "const model = `${config.primaryProvider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    assert check_litellm_model_strings(tmp_path, [tmp_path], set()) == []


def test_object_property_mutation_after_construction_is_detected(tmp_path: Path) -> None:
    # `config.primaryProvider = "openai";` — an ordinary, deterministic mutation after the object
    # is constructed — was invisible entirely: the resolver only ever looked at the object
    # literal's own initializer, so it kept treating the property as permanently equal to that
    # initializer even after a later mutation overwrote it (round 59).
    (tmp_path / "model.ts").write_text(
        "const config = {\n"
        '  primaryProvider: "internal",\n'
        "};\n\n"
        'config.primaryProvider = "openai";\n\n'
        "const model = `${config.primaryProvider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:7: 'openai/gpt-4.1'"], offenders


def test_static_element_assignment_mutation_is_detected(tmp_path: Path) -> None:
    # `config["primaryProvider"] = "openai";` is the same static property mutation as
    # `config.primaryProvider = "openai";`, just via bracket notation (round 59).
    (tmp_path / "model.ts").write_text(
        "const config = {\n"
        '  primaryProvider: "internal",\n'
        "};\n\n"
        'config["primaryProvider"] = "openai";\n\n'
        "const model = `${config.primaryProvider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:7: 'openai/gpt-4.1'"], offenders


def test_conditional_object_property_mutation_preserves_the_earlier_reachable_value(
    tmp_path: Path,
) -> None:
    # A mutation inside an `if` might not run — the property's original value stays reachable too,
    # exactly like an ordinary conditional variable reassignment already does (round 59). Uses
    # "custom" (a real `LITELLM_PROVIDERS` entry, unlike "internal") for the pre-mutation value, so
    # the gate's own provider-name-aware regex can actually match it as a candidate hardcode; the
    # gate itself only ever reports the lowest-positioned match per file, so only one of the two
    # reachable values shows up here even though the resolver tracks both (same as round 52's
    # equivalent `var`-redeclaration test).
    (tmp_path / "model.ts").write_text(
        'const config = { primaryProvider: "custom" };\n\n'
        "if (useFallback) {\n"
        '  config.primaryProvider = "openai";\n'
        "}\n\n"
        "const model = `${config.primaryProvider}/gpt-4.1`;\n",
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:7: 'custom/gpt-4.1'"], offenders


def test_object_property_mutation_after_the_use_site_does_not_apply_retroactively(
    tmp_path: Path,
) -> None:
    # A reference before a later mutation sees only the value in effect at that point — real JS
    # temporal order, not "any write anywhere in the file" (round 59). Uses "custom" (a real
    # `LITELLM_PROVIDERS` entry) so the gate's own regex can match the pre-mutation value.
    (tmp_path / "model.ts").write_text(
        'const config = { primaryProvider: "custom" };\n\n'
        "const model = `${config.primaryProvider}/gpt-4.1`;\n\n"
        'config.primaryProvider = "openai";\n',
        encoding="utf-8",
    )
    offenders = check_litellm_model_strings(tmp_path, [tmp_path], set())
    assert offenders == ["model.ts:3: 'custom/gpt-4.1'"], offenders
