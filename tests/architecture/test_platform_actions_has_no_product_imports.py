from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ACTIONS = ROOT / "packages" / "backend" / "platform-actions"


def test_platform_actions_has_no_product_imports() -> None:
    for path in PLATFORM_ACTIONS.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "product-platforms" not in text
        assert "anytoolai_freelancer" not in text
