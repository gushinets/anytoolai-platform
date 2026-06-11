from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_CORE = ROOT / "packages" / "backend" / "platform-core"


def test_platform_core_has_no_product_imports() -> None:
    forbidden = ["product-platforms", "anytoolai_freelancer", "FreelancerSuiteBundle"]
    for path in PLATFORM_CORE.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} contains forbidden token {token}"
