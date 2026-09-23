from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.providers.models import ProviderResponse, ResolvedProviderRequest


class RecordingProviderAdapter(FakeProviderAdapter):
    """Test-only FakeProviderAdapter double that records every resolved provider request and can
    optionally redirect chosen action_config_ids to a fixture-key variant (e.g. ".weak_input")
    instead of their default action_config_id-keyed fixture.

    Recording every request (not just counting them) is what lets a test assert a step's actual
    resolved input payload/prompt_ref -- proving a mapped prior-step output really flowed into
    the right place, not just that a provider_calls row exists (provider_calls_table has no
    request-payload column). Use `input_payload()` to parse the payload back out of the rendered
    prompt.

    Code review finding (ANY-232 round #2): generalizes and replaces three independent,
    behaviorally-overlapping FakeProviderAdapter subclasses that had each accumulated separately
    per product test file -- test_composite_workflow_matrix.py's pure recorder, no variants;
    test_client_update_writer_bundle.py's `_WeakInputProviderAdapter`, unconditionally forcing
    every call to `<action_config_id>.weak_input` (equivalent to passing every step's
    action_config_id mapped to ".weak_input" here); test_proposal_ai_bundle.py's
    `_FixedFixtureProviderAdapter`, forcing one literal fixture_key for its single-step workflow
    (equivalent to a one-entry variants map here). Consolidated the same way `app`/`_request`
    were moved into apps/platform-api/tests/conftest.py once duplication crossed this package's
    own "extract on second use" threshold. Only test_brief_decoder_bundle.py has been migrated to
    this shared adapter so far; migrating the three pre-existing call sites is separate follow-up
    debt, not part of the change that added this module."""

    def __init__(self, fixture_root: Path, *, variants: Mapping[str, str] | None = None) -> None:
        super().__init__(fixture_root)
        self.variants = dict(variants or {})
        self.calls: list[ResolvedProviderRequest] = []

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        self.calls.append(request)
        suffix = self.variants.get(request.action_config_id)
        if suffix is not None:
            request = replace(request, fixture_key=f"{request.action_config_id}{suffix}")
        return await super().complete(request)

    def input_payload(self, index: int) -> dict[str, Any]:
        """The input payload StructuredLlmActionExecutor._render_prompt rendered into call
        `index`'s prompt (`<template>\n\nInput payload:\n<json.dumps(input_payload)>`)."""
        prompt = self.calls[index].prompt
        _, _, payload_json = prompt.partition("\n\nInput payload:\n")
        assert payload_json, f"call {index} rendered no input payload: {prompt!r}"
        return json.loads(payload_json)
