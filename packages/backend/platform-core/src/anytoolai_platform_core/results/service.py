from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from anytoolai_platform_core.artifacts.canonical import (
    CanonicalArtifactError,
    resolve_canonical_workflow_result,
)
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.workflows.repository import JobRepository

# Defense-in-depth backstop: unlike handoffs (which only ever expose an explicit per-field
# allowlist mapping), this endpoint returns the full normalized output object, and shipped
# workflow output schemas may still declare `additionalProperties: true`. Reject output
# containing a key name that matches an internal/unsafe marker at any nesting depth.
#
# This is a dedicated, results-specific list -- deliberately NOT
# `common.logging.SENSITIVE_KEY_PARTS`. That list is tuned for log redaction, where a false
# positive just replaces a value with `[REDACTED]`; here a false positive makes an entire valid,
# already-succeeded result silently disappear as a 404.
#
# Matching is against the *whole* normalized key, not a substring: an earlier revision matched
# markers as substrings, which both under- and over-blocked. Substring matching let bare internal
# names (`prompt`, `provider`, `model`, `provider_call_id`, `gateway_model` -- the actual field
# names used for provider/prompt lineage in `providers/models.py` and
# `context/execution_context.py`) through, because those bare words were deliberately left off the
# marker list to avoid rejecting legitimate compound fields like `car_model`/`insurance_provider`.
# But the same substring check then rejected *other* legitimate compound fields that happen to
# contain a marker, e.g. `vehicle_model_id`, `car_model_version`, `insurance_provider_name`, or
# `business_trace_id`. Exact whole-key matching (after normalization) avoids both problems: it
# blocks the real bare internal names outright, and it no longer collides with domain fields that
# merely contain a marker as a substring.
_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        # Bare internal identifier/lineage field names used elsewhere in the platform (see
        # `providers/models.py`, `context/execution_context.py`,
        # `common.logging.IDENTIFIER_FIELDS`). Safe to block exactly now that matching is
        # whole-key, not substring.
        "prompt",
        "prompt_ref",
        "provider",
        "model",
        # `model_ref` is one of `config.loader.FORBIDDEN_RAW_LLM_FIELDS` (config-authoring-time
        # guard against raw LLM params leaking into config), included here too so the same field
        # name can't reach a public response either. The rest of that list (`temperature`,
        # `top_p`, `seed`, `stop`, `stream`, `tools`, ...) is deliberately NOT mirrored here: those
        # are generic English words with real domain-field collision risk (a weather workflow's
        # `temperature`, a bus-route workflow's `stop`), the same reason bare `email`/`token` were
        # excluded earlier -- `model_ref`/`prompt_ref`/`provider_policy_ref` are specific enough
        # to not have that problem.
        "model_ref",
        "provider_policy_ref",
        "provider_call_id",
        "gateway_backend",
        "gateway_model",
        "pydantic_run_id",
        "litellm_response_id",
        # Compound/lineage-shaped names not found verbatim elsewhere in the platform today, but
        # plausible leak shapes for provider/prompt/model/debug lineage.
        "system_prompt",
        "raw_prompt",
        "prompt_template",
        "raw_provider",
        "provider_output",
        "provider_model",
        "provider_name",
        "provider_policy",
        "model_name",
        "model_id",
        "model_version",
        "litellm",
        "litellm_debug_info",
        "trace_id",
        "parent_trace_id",
    }
)

_SEPARATORS = re.compile(r"[-_]")


def _canonical_key(key: Any) -> str:
    """Collapse `-`/`_` and case so every spelling of a marker compares equal.

    Two earlier revisions tried to re-insert word boundaries into arbitrary camelCase/acronym
    spellings before matching (`providerModel` -> `provider_model`), adding one regex rule per
    reported bypass (lower/digit -> upper, then acronym-run -> capitalized-word). That approach
    is inherently incomplete: fully-uppercase spellings (`GATEWAYMODEL`, `TRACEID`) have no
    lowercase letter to anchor a boundary on, and multi-acronym PascalCase (`LiteLlmDebugInfo`)
    splits into more words than the marker has (`lite_llm_debug_info` vs `litellm_debug_info`).
    Word-boundary detection is ambiguous in general (is `TRACEID` `trace_id` or `traceid`?) and
    doesn't need solving here: matching is against a small, fixed, known marker list, not
    free-form text, so stripping separators from *both* the key and the marker and comparing the
    result for equality sidesteps the boundary question entirely. This still can't reopen the
    earlier substring false-positive problem (`vehicle_model_id`, `business_trace_id`, ...)
    because it stays a whole-string equality check, just on a separator-free canonical form.
    """
    return _SEPARATORS.sub("", str(key)).casefold()


_FORBIDDEN_OUTPUT_KEYS_CANONICAL = frozenset(
    _canonical_key(marker) for marker in _FORBIDDEN_OUTPUT_KEYS
)


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if _canonical_key(key) in _FORBIDDEN_OUTPUT_KEYS_CANONICAL:
                return True
            if _contains_forbidden_key(nested):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


class ResultArtifactNotFoundError(PlatformError):
    def __init__(self) -> None:
        super().__init__("result_artifact_not_found", "Result artifact not found.")


class ResultArtifactUnavailableError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "result_artifact_unavailable", "Result artifact is not available."
        )


@dataclass(frozen=True)
class ResultArtifactView:
    artifact_id: str
    scenario_session_id: str
    job_id: str
    workflow_id: str
    workflow_version: int
    schema_ref: str
    schema_version: int
    created_at: datetime
    output: dict[str, Any]


class ResultService:
    def __init__(
        self,
        *,
        config_registry: ConfigRegistry,
        artifact_repository: ArtifactRepository,
        job_repository: JobRepository,
    ) -> None:
        self._registry = config_registry
        self._artifacts = artifact_repository
        self._jobs = job_repository

    def get_result(
        self,
        artifact_id: str,
        *,
        tenant_id: str,
        region: str,
    ) -> ResultArtifactView:
        artifact = self._artifacts.get_in_scope(
            artifact_id,
            tenant_id=tenant_id,
            region=region,
        )
        if artifact is None:
            raise ResultArtifactNotFoundError()
        job = None if artifact.job_id is None else self._jobs.get(artifact.job_id)
        try:
            canonical = resolve_canonical_workflow_result(
                artifact=artifact,
                job=job,
                config_registry=self._registry,
            )
        except CanonicalArtifactError as exc:
            raise ResultArtifactUnavailableError() from exc
        if _contains_forbidden_key(canonical.normalized_output):
            raise ResultArtifactUnavailableError()
        return ResultArtifactView(
            artifact_id=canonical.artifact.id,
            scenario_session_id=canonical.artifact.scenario_session_id,
            job_id=canonical.job.id,
            workflow_id=canonical.workflow.workflow_id,
            workflow_version=canonical.job.workflow_version,
            schema_ref=canonical.schema.schema_ref,
            schema_version=canonical.schema.version,
            created_at=canonical.artifact.created_at,
            output=canonical.normalized_output,
        )
