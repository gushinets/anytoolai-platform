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
SCAN_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".yaml", ".yml"}

# LiteLLM SDK/proxy model strings are "<provider>/<model>" (see configs/kernel/litellm_router.yaml
# litellm_params.model). They must appear only in provider policy/model registry files, never
# hardcoded in application source. Anchored to a `model`-named key (any case/spelling —
# `DEFAULT_MODEL`, `self.default_model: str`, `"model":`, `model:`) immediately followed by
# `:`/`=`/`==`, so a URL or comment mentioning e.g. "github.com/openai/openai-python" does not
# false-positive.
LITELLM_MODEL_STRING_RE = re.compile(
    r"""(?i)["']?[\w.]*model[\w]*["']?\s*(?::\s*[\w\[\], ]+)?[:=]+\s*["']?"""
    r"(?:openai|anthropic|azure|vertex_ai|bedrock|gemini|cohere|mistral|together_ai|groq)"
    r"/[\w.\-]+"
)


def _scan_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        for path in root.rglob("*"):
            if any(part in SKIP_PATH_PARTS for part in path.parts):
                continue
            if path.is_file() and path.suffix in SCAN_EXTS and path not in ALLOWED_FILES:
                files.append(path)
    return files


def test_litellm_model_strings_only_in_provider_config() -> None:
    offenders: list[str] = []
    for path in _scan_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = LITELLM_MODEL_STRING_RE.search(text)
        if match:
            offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)!r}")

    assert offenders == [], "LiteLLM-format model strings found outside provider config: " + ", ".join(
        offenders
    )
