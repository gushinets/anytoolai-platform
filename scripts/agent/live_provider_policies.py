"""Backend model selection shared by deployment generation and activation checks."""

LIVE_PROVIDER_POLICY_REF = "default_text_generation_v1"
# ANY-761: corrected Luna still changes language in AB comparison prose.
PRODUCT_LIVE_PROVIDER_POLICIES = {"acceptance_builder": "sol_text_generation_v1"}
