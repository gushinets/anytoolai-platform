from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_CORE = ROOT / "packages" / "backend" / "platform-core"
SKIP_PATH_PARTS = {".venv", ".quick-check-tmp", ".quick-check-venv", ".uv-cache", "node_modules"}
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


def test_no_freelancer_terms_in_platform_core() -> None:
    for path in PLATFORM_CORE.rglob("*"):
        if any(part in SKIP_PATH_PARTS for part in path.parts):
            continue
        if path.is_file() and path.suffix in {".py", ".md", ".yaml"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in FORBIDDEN:
                assert token not in text, f"{path} contains forbidden product term {token}"
