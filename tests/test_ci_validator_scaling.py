"""Relative growth regressions, with no machine-specific absolute time limit."""

from statistics import median
from time import perf_counter

import pytest

from tests.test_validate_architecture_imports import load_validator
from tests.test_validate_pr_metadata import load_validator_module, pr_body

MAX_EIGHTFOLD_GROWTH_RATIO = 32


@pytest.mark.parametrize("kind", ["fence", "imports"])
def test_adversarial_text_growth_is_not_quadratic(tmp_path, kind):
    metadata = load_validator_module()
    architecture = load_validator()
    path = tmp_path / "module.ts"
    timings = []
    for size in (1000, 8000):
        body = pr_body() + "`" * size + "\r"
        path.write_text("import " * size, encoding="utf-8")
        samples = []
        for _ in range(5):
            start = perf_counter()
            if kind == "fence":
                metadata.validate_pr_metadata("ANY-338 - Something", body)
            else:
                assert architecture.imported_js_ts_modules(path) == set()
            samples.append(perf_counter() - start)
        timings.append(median(samples))
    # An eightfold input increase gives ~64x for the old algorithms. Allow ample
    # noise and fixed overhead over the expected <=8x linear growth.
    assert timings[1] / timings[0] < MAX_EIGHTFOLD_GROWTH_RATIO, timings
