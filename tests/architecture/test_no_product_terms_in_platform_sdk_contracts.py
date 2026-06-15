from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_SDK_CONTRACTS = (
    ROOT / "packages" / "backend" / "platform-sdk" / "src" / "anytoolai_platform_sdk" / "contracts"
)
FORBIDDEN = [
    "FreelancerProfile",
    "ExternalTask",
    "Proposal",
    "Brief",
    "ScopeCreep",
    "AcceptanceDocument",
    "CaseStudy",
    "RhetoricalAnalysis",
    "Upwork",
    "Gmail",
    "client message",
    "proposal angle",
    "send-ready verdict",
    "generate_proposal",
    "acceptance_document",
    "proposal_ai",
]


def test_no_product_terms_in_platform_sdk_contracts() -> None:
    for path in PLATFORM_SDK_CONTRACTS.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in FORBIDDEN:
            assert token not in text, f"{path} contains forbidden product term {token}"
