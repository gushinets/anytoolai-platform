from __future__ import annotations

from pathlib import Path

from anytoolai_platform_sdk import ProductBundle


class FreelancerSuiteBundle(ProductBundle):
    """MVP-B Freelancer Suite. ProposalAI (ANY-227, B02a) and Client Update Writer (ANY-413) are
    the implemented product roots so far, in release order. See this package's README for the
    5-product release order (ANY-452); a product only appears in config_roots() once its own
    bundle-and-workflow issue lands a real product directory here."""

    bundle_id = "freelancer_suite"

    def config_roots(self) -> list[Path]:
        return [
            self._package_dir() / "products" / "proposal_ai",
            self._package_dir() / "products" / "client_update_writer",
        ]
