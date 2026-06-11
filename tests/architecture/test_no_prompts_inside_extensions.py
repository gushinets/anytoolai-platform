from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTENSIONS = ROOT / "extensions"


def test_no_prompts_inside_extensions() -> None:
    forbidden = ["system prompt", "prompt_ref", "provider_policy_ref"]
    for path in EXTENSIONS.rglob("*"):
        if path.is_file() and path.suffix in {".ts", ".tsx", ".md", ".json"}:
            if path.name in {"AGENTS.md", "README.md"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for token in forbidden:
                assert token not in text, f"{path} contains frontend-forbidden token {token}"
