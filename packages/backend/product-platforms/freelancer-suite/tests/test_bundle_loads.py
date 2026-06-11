from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle


def test_freelancer_bundle_exposes_all_validation_products() -> None:
    assert FreelancerSuiteBundle().config_roots() == [
        "products/proposal_ai",
        "products/acceptance_builder",
        "products/case_study",
        "products/scope_guard",
        "products/task_finder",
        "products/send_ready",
        "products/brief_decoder",
        "products/persuasion_lens",
    ]
