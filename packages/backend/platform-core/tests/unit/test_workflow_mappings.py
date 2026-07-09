from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
PLATFORM_CORE_SRC = REPO_ROOT / "packages" / "backend" / "platform-core" / "src"

if str(PLATFORM_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(PLATFORM_CORE_SRC))

from anytoolai_platform_core.workflows.errors import WorkflowStepContractValidationError
from anytoolai_platform_core.workflows.mappings import validate_step_contract


def test_validate_step_contract_raises_dedicated_validation_error() -> None:
    with pytest.raises(WorkflowStepContractValidationError) as exc_info:
        validate_step_contract(
            step_id="extract",
            prior_step_ids=(),
            input_mapping={},
            output_mapping={},
            when=None,
            retry_count=-1,
        )

    assert "retry_count" in str(exc_info.value)
