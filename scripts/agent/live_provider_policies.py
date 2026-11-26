"""Backend model selection shared by deployment generation and activation checks."""

LIVE_PROVIDER_POLICY_REF = "default_text_generation_v1"
PRODUCT_LIVE_PROVIDER_POLICIES = {
    # ANY-761: corrected Luna still changes language in AB comparison prose.
    "acceptance_builder": "sol_text_generation_v1",
    # ANY-851: Luna can turn scheduled handoffs into client requests.
    "client_update_writer": "sol_text_generation_v1",
}
