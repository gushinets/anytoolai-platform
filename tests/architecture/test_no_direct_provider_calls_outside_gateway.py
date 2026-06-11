from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_direct_openai_imports_outside_provider_adapter() -> None:
    for path in ROOT.rglob("*.py"):
        if ".venv" in path.parts or "tests" in path.parts or "scripts" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "import openai" in text or "from openai" in text:
            assert "providers/adapters/openai.py" in str(path), f"direct provider import in {path}"
