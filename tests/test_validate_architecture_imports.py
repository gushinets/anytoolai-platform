from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def load_validator():
    path = Path(__file__).resolve().parents[1] / "scripts/agent/validate_architecture.py"
    spec = importlib.util.spec_from_file_location("architecture_validator", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def validator():
    return load_validator()


@pytest.mark.parametrize(
    "source,expected",
    [
        ('import "openai";', {"openai"}),
        ("import Client from 'openai/client';", {"openai/client"}),
        ('import Default, {\n type X, Y as Z\n} from "@google/genai";', {"@google/genai"}),
        ('import type { X } from "cohere";', {"cohere"}),
        ('import * as SDK from "anthropic";', {"anthropic"}),
        ('export { X as Y } from "mistralai";', {"mistralai"}),
        ('export type { X } from "cohere";', {"cohere"}),
        ('export * from "litellm";', {"litellm"}),
        ('export * as SDK from "openai";', {"openai"}),
        ('const x = require(\n "openai"\n);', {"openai"}),
        ('const x = import(\n "openai"\n);', {"openai"}),
        ('import {\n genai as ai\n} from "google";', {"google", "google.genai"}),
        ('import type { genai } from "google";', {"google", "google.genai"}),
        ('import { other } from "google";', {"google"}),
        ('export { genai } from "google";', {"google"}),
        ('import ""; require(name); import(name);', set()),
        ('// import X from "openai"', {"openai"}),
        ('const text = `import X from "openai"`;', {"openai"}),
        ('import import import\nconst broken = "x"; import "openai";', {"openai"}),
        (
            'import "cohere"; export * from "openai"; require("anthropic")',
            {"cohere", "openai", "anthropic"},
        ),
        ('import  from "openai";', {"openai"}),
        ('import from "openai";', set()),
        ('import { "genai" as ai } from "google";', {"google.genai"}),
    ],
)
def test_supported_textual_import_forms(validator, tmp_path, source, expected):
    path = tmp_path / "module.ts"
    path.write_text(source, encoding="utf-8")
    assert validator.imported_modules(path) == expected


@pytest.mark.parametrize("container", ["// {}", "const text = `{}`;"])
def test_long_malformed_prefix_keeps_next_import(validator, tmp_path, container):
    path = tmp_path / "module.ts"
    path.write_text(
        container.format("import " * 8000) + '\nimport "openai/client";\n', encoding="utf-8"
    )
    assert validator.imported_js_ts_modules(path) == {"openai/client"}


def test_provider_and_product_boundary_diagnostics(validator, tmp_path, monkeypatch):
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "SKIP_PATH_PARTS", set())
    root = tmp_path / "packages/backend/product-platforms/test-product"
    root.mkdir(parents=True)
    path = root / "module.ts"
    path.write_text(
        'import "openai/client"; export * from "anytoolai_platform_core/internal";',
        encoding="utf-8",
    )
    assert any(
        "ATAI006" in error and "openai" in error
        for error in validator.check_llm_provider_boundary([root])
    )
    assert any(
        "ATAI007" in error and "anytoolai_platform_core" in error
        for error in validator.check_product_platforms_boundary(root)
    )
