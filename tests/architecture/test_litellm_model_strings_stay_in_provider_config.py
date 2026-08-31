from __future__ import annotations

import re
from pathlib import Path

# Reuse the canonical skip-dir set instead of hand-maintaining a copy that can drift (this file's
# own copy already diverged from this neighbor's twice across two code-review rounds).
from test_no_direct_provider_calls_outside_gateway import SKIP_PATH_PARTS as _NEIGHBOR_SKIP_PATH_PARTS

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_FILES = {
    ROOT / "configs" / "kernel" / "provider_policies.yaml",
    ROOT / "configs" / "kernel" / "litellm_router.yaml",
}
SCAN_ROOTS = [ROOT / "apps", ROOT / "packages", ROOT / "extensions", ROOT / "configs"]
# Extra entry beyond the neighbor: skip test fixtures, since they legitimately assert against
# real litellm-format config values (e.g. test_litellm_adapter.py), unlike the neighbor which
# filters "tests" per-function instead of via this set.
SKIP_PATH_PARTS = _NEIGHBOR_SKIP_PATH_PARTS | {"tests"}
SCAN_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".yaml", ".yml", ".json"}

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
    r"/[\w.\-]+"
)
# A match still isn't necessarily a real hardcode: `"https://example.com?model=openai/gpt-4.1"` —
# a `?model=`/`&model=` query value inside a URL string — has `=` right before the provider name,
# same as a real assignment. `_is_url_query_value` filters those out, but narrowly: it requires an
# actual adjacent `?key=`/`&key=` token, not merely "some URL appears earlier in this string" (a
# real hardcode can share a quoted string with an unrelated URL, e.g. a serialized JSON blob).


def _scan_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        for path in root.rglob("*"):
            if any(part in SKIP_PATH_PARTS for part in path.parts):
                continue
            if path.is_file() and path.suffix in SCAN_EXTS and path not in ALLOWED_FILES:
                files.append(path)
    return files


_QUOTE_CHARS = ("'", '"', "`")  # backtick included: JS/TS template literals (SCAN_EXTS has .ts/.js)
# `//` is a JS/TS comment marker, never a YAML/JSON one — YAML/JSON allow a bare (unquoted) URL as
# a scalar value, so treating `//` as a comment start there truncates a real line before the
# `model` field that follows the URL, e.g. `settings: {callback: https://x, model: openai/y}`.
_COMMENT_MARKERS_BY_SUFFIX: dict[str, tuple[str, ...]] = {
    ".py": ("#",),
    ".yaml": ("#",),
    ".yml": ("#",),
    ".json": (),  # JSON has no comment syntax at all
    # `#` is NOT a JS/TS comment marker — it's valid syntax there (private class fields:
    # `class C { #cache = 1; }`); treating it as one truncated a line before a real model literal
    # that followed. Only `//` is a genuine JS/TS single-line comment marker here.
    ".ts": ("//",),
    ".tsx": ("//",),
    ".js": ("//",),
    ".jsx": ("//",),
}


def _quoted_string_spans(line: str) -> list[tuple[int, int]]:
    """(start, end) of each quoted string's content (excluding the quote chars) on `line`."""
    spans: list[tuple[int, int]] = []
    quote_char: str | None = None
    content_start = 0
    i = 0
    length = len(line)
    while i < length:
        char = line[i]
        if quote_char:
            if char == "\\":
                i += 2
                continue
            if char == quote_char:
                spans.append((content_start, i))
                quote_char = None
            i += 1
            continue
        if char in _QUOTE_CHARS:
            quote_char = char
            content_start = i + 1
        i += 1
    return spans


# The `=` immediately preceding a `?key=`/`&key=` URL query value. Anchored (`$`) to the end of
# the string it's searched against, so it only matches when the query-key syntax sits directly
# against the candidate match's own prefix `=` — not merely "some `?...=` exists earlier".
_URL_QUERY_KEY_RE = re.compile(r"[?&][\w.\-]+=$")


def _is_url_query_value(line: str, spans: list[tuple[int, int]], position: int) -> bool:
    """True if `position` (the candidate match's prefix char) is genuinely a `?key=`/`&key=` URL
    query value: it must be `=`, sit inside a quoted string containing `://` before it, AND have
    a `?`/`&`-prefixed key directly adjacent to it (`...?model=` / `...&provider=`).

    The first two conditions alone are too broad: a serialized-JSON string like
    `'{"callback":"https://example.com","model":"openai/gpt-4.1"}'` also contains `://` earlier in
    the same (outer, single-quoted) string, but the real `"model":"openai/..."` field there is a
    genuine hardcode, not part of the URL — its prefix char is `"`, not `=`, and there's no
    `?`/`&`-prefixed key right before it.
    """
    if position < 0 or position >= len(line) or line[position] != "=":
        return False
    for start, end in spans:
        if start <= position < end:
            prefix = line[start : position + 1]
            return "://" in prefix and bool(_URL_QUERY_KEY_RE.search(prefix))
    return False


def _strip_comments(text: str, markers: tuple[str, ...]) -> list[str]:
    """Comment-stripped lines of `text` (only using `markers` — see `_COMMENT_MARKERS_BY_SUFFIX`),
    with quote state carried across line boundaries rather than reset at each newline.

    A naive per-line scan truncates at the first marker occurrence anywhere on that line,
    including inside a string spanning multiple lines — e.g. a Python triple-quoted string whose
    body contains a bare `#` (or a JS/TS template literal containing `//`): resetting
    `in_string = None` at the start of the *next* physical line misreads that marker as a real
    comment and truncates a real hardcode that follows the string's close later on the same
    (closing) line. Backticks are tracked as a quote delimiter too, alongside `'`/`"`.
    """
    if not markers:
        return text.splitlines()

    lines: list[str] = []
    current: list[str] = []
    in_string: str | None = None
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char == "\n":
            lines.append("".join(current))
            current = []
            i += 1
            continue
        if in_string:
            if char == "\\" and i + 1 < length and text[i + 1] != "\n":
                current.append(char)
                current.append(text[i + 1])
                i += 2
                continue
            current.append(char)
            if char == in_string:
                in_string = None
            i += 1
            continue
        if char in _QUOTE_CHARS:
            in_string = char
            current.append(char)
            i += 1
            continue
        if any(text.startswith(marker, i) for marker in markers):
            newline_pos = text.find("\n", i)
            i = length if newline_pos == -1 else newline_pos
            continue
        current.append(char)
        i += 1
    lines.append("".join(current))
    return lines


def _first_real_offender(stripped_line: str) -> str | None:
    spans = _quoted_string_spans(stripped_line)
    for match in LITELLM_MODEL_STRING_RE.finditer(stripped_line):
        if not _is_url_query_value(stripped_line, spans, match.start()):
            return match.group(0)
    return None


def test_litellm_model_strings_only_in_provider_config() -> None:
    offenders: list[str] = []
    for path in _scan_files():
        markers = _COMMENT_MARKERS_BY_SUFFIX[path.suffix]
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, stripped_line in enumerate(_strip_comments(text, markers), start=1):
            offender = _first_real_offender(stripped_line)
            if offender is not None:
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {offender!r}")
                break

    assert offenders == [], "LiteLLM-format model strings found outside provider config: " + ", ".join(
        offenders
    )
