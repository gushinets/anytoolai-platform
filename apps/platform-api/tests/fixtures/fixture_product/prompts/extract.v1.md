# fixture_product.extract.v1

Deterministic test-only fixture prompt. Never rendered against a real provider -- see
test_bundle_composition.py, which proves this fixture bundle loads through the real application
composition path (build_runtime) but is excluded from production loaded_bundles/registry.
