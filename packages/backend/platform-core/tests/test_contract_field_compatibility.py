from __future__ import annotations

from dataclasses import is_dataclass
from enum import StrEnum
from typing import Any

import pytest
from anytoolai_platform_core.actions.models import (
    ActionConfiguration as CoreActionConfiguration,
)
from anytoolai_platform_core.actions.models import (
    ActionDefinition as CoreActionDefinition,
)
from anytoolai_platform_core.actions.models import (
    ActionExecutor as CoreActionExecutor,
)
from anytoolai_platform_core.events.envelope import EventEnvelope as CoreEventEnvelope
from anytoolai_platform_core.handoffs.models import (
    HandoffDefinition as CoreHandoffDefinition,
)
from anytoolai_platform_core.handoffs.models import (
    HandoffStatus as CoreHandoffStatus,
)
from anytoolai_platform_core.products.models import (
    FrontendDefinition as CoreFrontendDefinition,
)
from anytoolai_platform_core.products.models import (
    FrontendType as CoreFrontendType,
)
from anytoolai_platform_core.products.models import (
    ProductDefinition as CoreProductDefinition,
)
from anytoolai_platform_core.prompts.models import PromptRef as CorePromptRef
from anytoolai_platform_core.providers.models import (
    ProviderPolicy as CoreProviderPolicy,
)
from anytoolai_platform_core.providers.models import (
    ProviderRetryHardLimits as CoreProviderRetryHardLimits,
)
from anytoolai_platform_core.providers.models import (
    ProviderRetryPolicy as CoreProviderRetryPolicy,
)
from anytoolai_platform_core.providers.models import (
    ProviderTransportRetryPolicy as CoreProviderTransportRetryPolicy,
)
from anytoolai_platform_core.providers.models import (
    ProviderValidationRetryPolicy as CoreProviderValidationRetryPolicy,
)
from anytoolai_platform_core.providers.models import (
    StructuredOutputMode as CoreStructuredOutputMode,
)
from anytoolai_platform_core.providers.models import (
    TransportRetryOwner as CoreTransportRetryOwner,
)
from anytoolai_platform_core.providers.models import (
    ValidationRetryOwner as CoreValidationRetryOwner,
)
from anytoolai_platform_core.quotas.models import (
    QuotaPeriod as CoreQuotaPeriod,
)
from anytoolai_platform_core.quotas.models import (
    QuotaPolicy as CoreQuotaPolicy,
)
from anytoolai_platform_core.quotas.models import (
    QuotaUnit as CoreQuotaUnit,
)
from anytoolai_platform_core.scenarios.models import (
    ScenarioDefinition as CoreScenarioDefinition,
)
from anytoolai_platform_core.scenarios.models import (
    ScenarioSessionStatus as CoreScenarioSessionStatus,
)
from anytoolai_platform_core.workflows.models import (
    JobStatus as CoreJobStatus,
)
from anytoolai_platform_core.workflows.models import (
    WorkflowDefinition as CoreWorkflowDefinition,
)
from anytoolai_platform_core.workflows.models import (
    WorkflowStepDefinition as CoreWorkflowStepDefinition,
)
from anytoolai_platform_sdk.contracts import (
    ActionConfiguration,
    ActionDefinition,
    ActionExecutor,
    EventEnvelope,
    FrontendDefinition,
    FrontendType,
    HandoffDefinition,
    HandoffStatus,
    JobStatus,
    ProductDefinition,
    PromptRef,
    ProviderPolicy,
    ProviderRetryHardLimits,
    ProviderRetryPolicy,
    ProviderTransportRetryPolicy,
    ProviderValidationRetryPolicy,
    QuotaPeriod,
    QuotaPolicy,
    QuotaUnit,
    ScenarioDefinition,
    ScenarioSessionStatus,
    StructuredOutputMode,
    TransportRetryOwner,
    ValidationRetryOwner,
    WorkflowDefinition,
    WorkflowStepDefinition,
)


def sdk_model_fields(model: type[Any]) -> set[str]:
    return set(model.model_fields)


def core_dataclass_fields(model: type[Any]) -> set[str]:
    assert is_dataclass(model)
    return set(model.__dataclass_fields__)


@pytest.mark.parametrize(
    ("sdk_model", "core_model"),
    [
        (ActionConfiguration, CoreActionConfiguration),
        (ActionDefinition, CoreActionDefinition),
        (EventEnvelope, CoreEventEnvelope),
        (FrontendDefinition, CoreFrontendDefinition),
        (HandoffDefinition, CoreHandoffDefinition),
        (ProductDefinition, CoreProductDefinition),
        (PromptRef, CorePromptRef),
        (ProviderPolicy, CoreProviderPolicy),
        (ProviderRetryHardLimits, CoreProviderRetryHardLimits),
        (ProviderRetryPolicy, CoreProviderRetryPolicy),
        (ProviderTransportRetryPolicy, CoreProviderTransportRetryPolicy),
        (ProviderValidationRetryPolicy, CoreProviderValidationRetryPolicy),
        (QuotaPolicy, CoreQuotaPolicy),
        (ScenarioDefinition, CoreScenarioDefinition),
        (WorkflowDefinition, CoreWorkflowDefinition),
        (WorkflowStepDefinition, CoreWorkflowStepDefinition),
    ],
)
def test_core_models_mirror_sdk_contract_field_names(
    sdk_model: type[Any], core_model: type[Any]
) -> None:
    assert core_dataclass_fields(core_model) == sdk_model_fields(sdk_model)


def enum_values(enum_type: type[StrEnum]) -> set[str]:
    return {member.value for member in enum_type}


@pytest.mark.parametrize(
    ("sdk_enum", "core_enum"),
    [
        (ActionExecutor, CoreActionExecutor),
        (FrontendType, CoreFrontendType),
        (HandoffStatus, CoreHandoffStatus),
        (JobStatus, CoreJobStatus),
        (QuotaPeriod, CoreQuotaPeriod),
        (QuotaUnit, CoreQuotaUnit),
        (ScenarioSessionStatus, CoreScenarioSessionStatus),
        (StructuredOutputMode, CoreStructuredOutputMode),
        (TransportRetryOwner, CoreTransportRetryOwner),
        (ValidationRetryOwner, CoreValidationRetryOwner),
    ],
)
def test_core_enums_mirror_sdk_contract_values(
    sdk_enum: type[StrEnum], core_enum: type[StrEnum]
) -> None:
    assert enum_values(core_enum) == enum_values(sdk_enum)
