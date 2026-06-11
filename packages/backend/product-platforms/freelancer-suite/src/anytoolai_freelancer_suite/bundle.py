from anytoolai_platform_sdk import ProductBundle


class FreelancerSuiteBundle(ProductBundle):
    bundle_id = "freelancer_suite"

    def config_roots(self) -> list[str]:
        return [
            "products/proposal_ai",
            "products/acceptance_builder",
            "products/case_study",
            "products/scope_guard",
            "products/task_finder",
            "products/send_ready",
            "products/brief_decoder",
            "products/persuasion_lens",
        ]
