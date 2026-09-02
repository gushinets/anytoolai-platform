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
    the comment-stripped text (which also covers `//` prose retained in JSX-capable files, where
    comment stripping is deliberately disabled), or any *statically folded* string expression —
    a `+` concatenation across any number of lines/parens, a template literal interpolating a
    known constant (`` `${provider}/gpt-4.1` `` with `const provider = "openai"`), or a constant
    imported from a sibling module — resolved by the shared static resolver."""
    text = js.texts[path]
    spans = [(start + 1, end) for start, (end, _) in js.literals[path].items()]
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
