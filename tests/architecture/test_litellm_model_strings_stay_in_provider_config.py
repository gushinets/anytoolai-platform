from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

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
    string value (a Python string-literal's decoded content, or a YAML scalar's decoded content —
    values a real parser has already separated from comments/surrounding syntax), or `None`."""
    spans = [(0, len(value))]
    for match in LITELLM_MODEL_STRING_RE.finditer(value):
        if not _is_url_query_value(value, spans, match.start()):
            return match.group(0)
    return None


def _python_offender(path: Path) -> tuple[int, str] | None:
    """(lineno, matched-text) of the first real hardcode in `path`'s string literals, using the
    real Python AST instead of hand-rolled quote/comment tracking.

    Nine review rounds (7, 9, 11, 12, 13) found real bugs in a hand-rolled Python string/comment
    tracker; round 14 replaced it with `tokenize`, which round 15 then found only inspects
    `tokenize.STRING` — Python 3.12+ tokenizes an f-string as `FSTRING_START`/`MIDDLE`/`END`
    instead, so a plain `model = f"openai/gpt-4.1"` hardcode was invisible (a regression versus
    the original regex scanner). `ast.walk` sidesteps this rather than teaching the scanner about
    another token shape: `JoinedStr`/`FormattedValue`/`Constant` node shapes are stable since
    Python 3.6, unaffected by tokenizer-level changes, give already-decoded string values with no
    `ast.literal_eval` failure modes, and comments don't exist in the AST at all (excluded from
    consideration by construction, the same guarantee `tokenize.COMMENT`-skipping gave before —
    with no separate comment-stripping step needed either way).

    An f-string with real interpolation (`f"openai/{name}"`) is a genuinely dynamic value, not a
    hardcode — a `JoinedStr` is only checked when *every* part is a literal `Constant` (no
    `FormattedValue` at all); one with any interpolation is skipped, matching the original
    (correct) intent to never evaluate expressions.
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None

    # A JoinedStr's own Constant parts must not also be checked independently as top-level
    # strings (`ast.walk` visits them too) — that would double-process a plain f-string and could
    # match an incomplete fragment of a genuinely dynamic one on its own.
    fstring_part_ids = {
        id(part)
        for node in ast.walk(tree)
        if isinstance(node, ast.JoinedStr)
        for part in node.values
    }

    best: tuple[int, str] | None = None
    for node in ast.walk(tree):
        value: str | None = None
        lineno = getattr(node, "lineno", None)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in fstring_part_ids
        ):
            value = node.value
        elif isinstance(node, ast.JoinedStr) and all(
            isinstance(part, ast.Constant) and isinstance(part.value, str)
            for part in node.values
        ):
            value = "".join(part.value for part in node.values)
        if value is None or lineno is None:
            continue
        match = _offending_match(value)
        if match is not None and (best is None or lineno < best[0]):
            best = (lineno, match)
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


def _yaml_offender(path: Path) -> tuple[int, str] | None:
    """(lineno, matched-text) of the first real hardcode in `path`'s scalar values, using a real
    YAML parser instead of hand-rolled `#`-is-a-comment tracking.

    `#` is not a comment marker inside a YAML block scalar (`|`/`>`) — it's literal content — and
    a hand-rolled line scanner has no way to know it's inside one without re-implementing YAML's
    block-scalar indentation rules. `yaml.compose_all` already does that correctly (per document);
    walking each document's node graph gives real scalar values (block/flow, quoted/unquoted —
    all resolved the same way) with real source positions, with no separate comment-stripping
    step needed. Uses `compose_all`, not `compose` (round 15: `compose` only accepts a single
    document and raises on a valid multi-document file, e.g. `foo: bar\\n---\\nmodel:
    openai/gpt-4.1` — `compose_all` scans every document; line numbers stay absolute across `---`
    boundaries, not reset per document (verified)).

    A genuine parse failure is a loud test failure, not a silent skip of the whole file — matches
    this repo's own anti-silent-skip convention, and every real `.yaml`/`.yml` file in
    `SCAN_ROOTS` parses cleanly today (verified), so this can't newly break on anything that
    exists.
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        documents = list(yaml.compose_all(text))
    except yaml.YAMLError as exc:
        raise AssertionError(f"could not parse {path.relative_to(ROOT)} as YAML: {exc}") from exc

    best: tuple[int, str] | None = None
    for document in documents:
        if document is None:
            continue
        for scalar in _iter_yaml_scalars(document):
            if not isinstance(scalar.value, str):
                continue
            match = _offending_match(scalar.value)
            if match is not None:
                lineno = scalar.start_mark.line + 1
                if best is None or lineno < best[0]:
                    best = (lineno, match)
    return best


# Only `.json`/`.js`/`.jsx`/`.ts`/`.tsx` still go through this line-based scanner. `.json` has no
# comment syntax at all (the marker set below is empty for it, so `_strip_comments` is a no-op)
# and only ever contains standard double-quoted strings — none of the ambiguity that motivated
# moving Python/YAML to real parsers exists in JSON's grammar. `.js`/`.ts` are handled the same
# way `.py` used to be (regex + hand-rolled quote/comment tracking).
#
# ponytail: no JS/TS tokenizer is available here without adding a new dependency, so this path
# keeps the same class of bug the Python/YAML paths were just moved off of (a comment or a
# multi-line construct this tracker doesn't model could still misread). Upgrade path: parse with
# a real JS/TS tokenizer if a bug is ever found here, the same way Python/YAML were fixed.
_QUOTE_CHARS = ("'", '"', "`")  # backtick included: JS/TS template literals
_COMMENT_MARKERS_BY_SUFFIX: dict[str, tuple[str, ...]] = {
    ".json": (),  # JSON has no comment syntax at all
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


def _strip_comments(text: str, markers: tuple[str, ...]) -> list[str]:
    """Comment-stripped lines of `text` (only using `markers`), with quote state carried across
    line boundaries rather than reset at each newline — a JS/TS template literal containing `//`
    (e.g. a URL) must not have that `//` misread as a comment start on a later physical line."""
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


def _line_offender(stripped_line: str) -> str | None:
    spans = _quoted_string_spans(stripped_line)
    for match in LITELLM_MODEL_STRING_RE.finditer(stripped_line):
        if not _is_url_query_value(stripped_line, spans, match.start()):
            return match.group(0)
    return None


def _regex_offender(path: Path) -> tuple[int, str] | None:
    markers = _COMMENT_MARKERS_BY_SUFFIX[path.suffix]
    text = path.read_text(encoding="utf-8", errors="ignore")
    for lineno, stripped_line in enumerate(_strip_comments(text, markers), start=1):
        offender = _line_offender(stripped_line)
        if offender is not None:
            return lineno, offender
    return None


def test_litellm_model_strings_only_in_provider_config() -> None:
    offenders: list[str] = []
    for path in _scan_files():
        if path.suffix == ".py":
            found = _python_offender(path)
        elif path.suffix in (".yaml", ".yml"):
            found = _yaml_offender(path)
        else:
            found = _regex_offender(path)
        if found is not None:
            lineno, offender = found
            offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {offender!r}")

    assert offenders == [], "LiteLLM-format model strings found outside provider config: " + ", ".join(
        offenders
    )
