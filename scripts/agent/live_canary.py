#!/usr/bin/env python3
"""ANY-221: runs the same 11 standalone kernel_demo atom scenarios and 3 composite kernel_demo
workflows atoms_proof.py proves deterministically, but through their `_live_` siblings --
action_configs wired to `default_text_generation_v1` (a real LiteLLM/OpenAI call via
ProviderGateway), not the fake provider. Same ledger/schema validation, same privacy-safe evidence
shape, plus an estimated-cost cap this run-scoped script owns (ProviderGateway itself stays frozen
-- see ANY-221's execution constraints).

Reuses atoms_proof.py's HTTP/DB/evidence machinery wholesale (_run_case_with_ledger_check,
_build_engine, _fail, write_evidence_report) instead of duplicating it -- this script only adds
the live scenario-id substitution and the cost-abort loop.

Invoked by scripts/agent/runner.py's live-canary command, which fails fast if OPENAI_API_KEY is
unset before this script (or Docker) ever starts. Costs real money when it runs -- never part of
quick-check/full-check/postgresql-check.
"""

from __future__ import annotations

import math
import os
import sys
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.test_atoms_proof import load_atoms_proof_module  # noqa: E402

# Loaded via the same load_cached_module()-backed helper tests/test_atoms_proof.py itself uses
# (cache key "atoms_proof_module"), not a bare `import atoms_proof` -- a bare import registers a
# SEPARATE copy of the module under sys.modules["atoms_proof"], re-parsing/re-executing
# atoms_proof.py's own YAML/config loading and engine-wiring a second time whenever this script
# and the test suite's own atoms_proof tests load in the same process (e.g. a single quick-check
# pytest invocation covering both tests/test_atoms_proof.py and tests/test_live_canary.py) --
# pure duplicate work in a gate that's supposed to stay fast. Mirrors atoms_proof.py's own
# `smoke = load_smoke_module()` for exactly the same reason (see its docstring there).
atoms_proof = load_atoms_proof_module()
EvidenceCase = atoms_proof.EvidenceCase  # always defined, unlike `smoke` (see below)

# atoms_proof.smoke is only bound when atoms_proof's own module-load try/except block succeeds
# (mirrors atoms_proof.py's own guarded ATOM_SMOKE_CASES/COMPOSITE_SMOKE_CASES pattern) -- looked
# up lazily via atoms_proof.smoke.* inside run()/main() below, both gated on
# atoms_proof._MODULE_LOAD_ERROR being None, instead of imported here at parse time where a failed
# atoms_proof load would raise a raw ImportError before main() ever gets to print a clean code.

DEFAULT_MAX_TOTAL_COST_USD = 0.50

# Code-review finding: _classify_ledger's PROOF003 check used to require exactly one
# provider_calls row per action_run, but configs/kernel/provider_policies.yaml's
# default_text_generation_v1 -- the policy every live_ action_config uses -- permits up to 4
# physical provider calls per action (retry_policy.hard_limits.max_physical_provider_calls_per_
# action: 4, from 2 transport attempts x 2 validation attempts), so a live case that legitimately
# retried once was failing as a PROOF003 correctness bug. Not read dynamically from that YAML
# (this script deliberately keeps no ConfigLoader dependency for a pure ledger-correctness check)
# -- if the policy's own cap ever changes, this constant needs updating to match.
_LIVE_PROVIDER_MAX_CALLS_PER_ACTION = 4

LIVE_CANARY_TOKEN_ENV_VAR = "ANYTOOLAI_LIVE_CANARY_TOKEN"
ATOM_LAB_ACCESS_CODE_ENV_VAR = "ANYTOOLAI_ATOM_LAB_ACCESS_CODE"
ATOM_LAB_MODEL_ID_ENV_VAR = "ANYTOOLAI_ATOM_LAB_MODEL_ID"
LIVE_CANARY_SURFACE_ENV_VAR = "ANYTOOLAI_LIVE_CANARY_SURFACE"
PRODUCTION_SURFACE = "production"
ATOM_LAB_SURFACE = "atom-lab"


@dataclass(frozen=True)
class AtomLabCase:
    atom_id: str
    input_payload: dict[str, Any]
    label: str | None = None
    kind: str = "atom"


# Deliberately distinct from the deterministic smoke literals. These values exercise the full
# laboratory passthrough while remaining valid against the repo-owned A01-A11 input contracts.
ATOM_LAB_CASES: tuple[AtomLabCase, ...] = (
    AtomLabCase("A01", {
        "source_text": "Acceptance A01: delivery is 17 October and costs 91500 EUR.",
        "fields": [
            {
                "name": "delivery_date", "type": "date", "description": "Delivery date",
                "required": True,
            },
            {"name": "price_eur", "type": "number", "description": "Price", "required": False},
        ],
        "strict": False,
    }),
    AtomLabCase("A02", {
        "text_a": "Acceptance A02: audited prototype in nine days.",
        "text_b": "The brief requires the prototype within twelve days.",
        "rubric": [{"id": "deadline", "description": "Meets the deadline", "weight": 3}],
    }),
    AtomLabCase("A03", {
        "text": "Acceptance A03: every milestone names an owner and verification step.",
        "axes": [
            {"id": "ownership", "description": "Explicit owners", "weight": 2},
            {"id": "verification", "description": "Acceptance checks", "weight": 4},
        ],
    }),
    AtomLabCase("A04", {
        "source_text": "Acceptance A04: approver and rollback plan are missing.",
        "context": "Release readiness review",
        "taxonomy": ["approval", "rollback"],
    }),
    AtomLabCase("A05", {
        "issues": [{
            "category": "ownership", "description": "No approver is named.",
            "severity": "medium", "evidence": "The approval field is blank.",
        }],
        "context": "Acceptance A05 launch decision", "target_audience": "Release manager",
        "max_questions": 2,
    }),
    AtomLabCase("A06", {
        "context": {"product": "Acceptance A06", "saved_hours_per_week": 11},
        "objective": "Secure approval for a measurement pilot", "audience": "Operations lead",
        "angle": "Measure saved time before rollout",
        "constraints": {"tone": "firm", "length": 640, "language": "en-GB", "format": "plain_text"},
    }),
    AtomLabCase("A07", {
        "situation": "Acceptance A07: customer asks whether the audit can start Tuesday.",
        "intent": "Confirm availability and request repository access", "tone": "neutral",
        "constraints": {"language": "en", "max_length": 420, "output_format": "markdown"},
    }),
    AtomLabCase("A08", {
        "source_text": "Acceptance A08: We can probably deliver something soon.",
        "gap": "Replace ambiguity with a measurable delivery commitment", "style": "bold",
    }),
    AtomLabCase("A09", {
        "signals": [
            {"id": "evidence", "label": "Acceptance evidence", "value": "three verified pilots"},
            {"id": "risk", "label": "Delivery risk", "value": 0},
        ],
        "objective": "Select the strongest acceptance argument", "options": ["speed", "proof"],
    }),
    AtomLabCase("A10", {
        "template_ref": "acceptance_summary_v1",
        "data": {"project": "Acceptance A10", "approved": False, "variance": 0, "notes": None},
    }),
    AtomLabCase("A11", {
        "subject_text": "Acceptance A11 pilot delivered in nine days.",
        "reference_text": "The brief requires delivery within twelve days.",
        "categories": ["match", "gap"],
        "criteria": [{"id": "deadline", "description": "Delivery deadline"}],
    }),
)


def _select_atom_lab_model(
    catalog: dict[str, Any], *, requested_model_id: str | None
) -> tuple[str, tuple[str, ...]]:
    compatible = [
        item for item in catalog.get("items", [])
        if isinstance(item, dict) and item.get("compatibility") == "compatible"
    ]
    requested_raw = (
        requested_model_id.removeprefix("openai/") if requested_model_id is not None else None
    )
    selected = next(
        (
            item for item in compatible
            if isinstance(item.get("model_id"), str)
            and item["model_id"].removeprefix("openai/") == requested_raw
        ),
        None,
    ) if requested_model_id else next(
        (
            item for item in compatible
            if item.get("reasoning_supported") is True
            and isinstance(item.get("allowed_reasoning_efforts"), list)
            and item["allowed_reasoning_efforts"]
        ),
        compatible[0] if compatible else None,
    )
    if selected is None:
        raise ValueError("requested Atom Lab model is absent or not compatible")
    model_id = selected.get("model_id")
    if not isinstance(model_id, str) or not model_id:
        raise ValueError("compatible Atom Lab model has no model_id")
    model_id = model_id if model_id.startswith("openai/") else f"openai/{model_id}"
    efforts = selected.get("allowed_reasoning_efforts")
    if selected.get("reasoning_supported") is not True or efforts is None:
        return model_id, ()
    if not isinstance(efforts, list) or any(not isinstance(effort, str) for effort in efforts):
        raise ValueError("Atom Lab model has malformed reasoning capabilities")
    return model_id, tuple(efforts)


def _run_atom_lab_case(
    api_url: str,
    engine: Any,
    *,
    case: AtomLabCase,
    prompt: str,
    model_id: str,
    reasoning_effort: str | None,
    access_code: str,
    timeout: float,
) -> EvidenceCase:
    label = case.label or case.atom_id
    scenario_id = f"atom-lab.{label}"
    payload = {
        "atom_id": case.atom_id,
        "input": case.input_payload,
        "prompt": prompt,
        "model_id": model_id,
        "reasoning_effort": reasoning_effort,
        "preset_ref": None,
    }
    idempotency_key = f"any-467-{case.atom_id}-{uuid.uuid4().hex}"
    headers = {
        "X-Atom-Lab-Access-Code": access_code,
        "Idempotency-Key": idempotency_key,
    }
    run_id = session_id = job_id = None

    def failure(code: str, *, ambiguous_cost: bool = False) -> EvidenceCase:
        known_steps = (
            atoms_proof._known_steps_for_session(engine, session_id)
            if session_id is not None
            else ()
        )
        return replace(
            atoms_proof._fail(
                label=label, scenario_id=scenario_id, kind=case.kind,
                session_id=session_id, job_id=job_id, error_code=code,
                error_message=f"{code}: Atom Lab acceptance case {case.atom_id} failed",
                steps=known_steps or (),
                cost_unknown=(
                    ambiguous_cost or (session_id is not None and known_steps is None)
                ),
            ),
            run_id=run_id,
            requested_model_id=model_id,
            reasoning_effort=reasoning_effort,
            input_valid=session_id is not None,
            result_valid=False,
        )

    for admission_attempt in range(2):
        try:
            accepted = atoms_proof.smoke._http_json_request(
                f"{api_url}/v1/atom-lab/runs", method="POST", payload=payload,
                extra_headers=headers,
            )
            accepted_ids = (
                accepted["run_id"], accepted["scenario_session_id"], accepted["job_id"]
            )
            if any(
                not isinstance(accepted_id, str) or not accepted_id.strip()
                for accepted_id in accepted_ids
            ):
                raise ValueError("Atom Lab admission returned a blank runtime ID")
            run_id, session_id, job_id = accepted_ids
            break
        except (OSError, KeyError, ValueError, TypeError, AttributeError):
            if admission_attempt == 1:
                # Either POST may have committed before its response was lost. The identical
                # idempotency key makes one recovery replay safe; if both responses are
                # ambiguous, stop the entire costed matrix instead of assuming $0 spend.
                return failure("LIVE020", ambiguous_cost=True)

    deadline = time.monotonic() + timeout
    detail: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        try:
            detail = atoms_proof.smoke._http_json_request(
                f"{api_url}/v1/atom-lab/runs/{run_id}",
                extra_headers={"X-Atom-Lab-Access-Code": access_code},
            )
        except (OSError, KeyError, ValueError, TypeError, AttributeError):
            return failure("LIVE021", ambiguous_cost=True)
        status = detail.get("status")
        if status == "succeeded":
            break
        if status in {"failed", "expired", "cancelled"}:
            return failure("LIVE022")
        time.sleep(0.25)
    else:
        return failure("LIVE023", ambiguous_cost=True)

    assert detail is not None
    snapshot = detail.get("snapshot")
    runtime_ids = detail.get("runtime_ids")
    diagnostics = detail.get("diagnostics")
    prompt_snapshot = snapshot.get("prompt") if isinstance(snapshot, dict) else None
    provider_snapshot = snapshot.get("provider") if isinstance(snapshot, dict) else None
    if (
        detail.get("run_id") != run_id
        or not isinstance(snapshot, dict)
        or snapshot.get("atom_id") != case.atom_id
        or snapshot.get("input") != case.input_payload
        or not isinstance(prompt_snapshot, dict)
        or prompt_snapshot.get("content") != prompt
        or not isinstance(provider_snapshot, dict)
        or provider_snapshot.get("model_id") != model_id
        or provider_snapshot.get("reasoning_effort") != reasoning_effort
        or snapshot.get("preset") != {"id": None, "version": None}
    ):
        return failure("LIVE024")
    if not isinstance(runtime_ids, dict) or (
        runtime_ids.get("scenario_session_id") != session_id
        or runtime_ids.get("job_id") != job_id
        or not isinstance(runtime_ids.get("action_run_id"), str)
        or not runtime_ids["action_run_id"].strip()
        or not isinstance(runtime_ids.get("artifact_id"), str)
        or not runtime_ids["artifact_id"].strip()
    ):
        return failure("LIVE025")
    if not isinstance(diagnostics, dict) or (
        diagnostics.get("requested_model_id") != model_id
        or diagnostics.get("requested_reasoning_effort") != reasoning_effort
        or not isinstance(diagnostics.get("response_model_id"), str)
        or not diagnostics["response_model_id"].strip()
    ):
        return failure("LIVE026")
    result = detail.get("result")
    if not isinstance(result, (dict, list)):
        return failure("LIVE027")
    finished_at = detail.get("finished_at")
    if not isinstance(finished_at, str) or not finished_at.strip():
        return failure("LIVE030")
    try:
        replay = atoms_proof.smoke._http_json_request(
            f"{api_url}/v1/atom-lab/runs", method="POST", payload=payload,
            extra_headers=headers,
        )
    except (OSError, KeyError, ValueError, TypeError, AttributeError):
        return failure("LIVE028", ambiguous_cost=True)
    if (
        replay.get("run_id") != run_id
        or replay.get("scenario_session_id") != session_id
        or replay.get("job_id") != job_id
    ):
        return failure("LIVE028", ambiguous_cost=True)

    ledger = atoms_proof._check_ledger(
        engine, label=label, scenario_id=scenario_id, kind=case.kind,
        scenario_session_id=session_id,
        max_provider_calls_per_action=_LIVE_PROVIDER_MAX_CALLS_PER_ACTION,
    )
    return replace(
        ledger,
        run_id=run_id,
        action_run_id=runtime_ids["action_run_id"],
        artifact_id=runtime_ids["artifact_id"],
        requested_model_id=model_id,
        response_model_id=diagnostics.get("response_model_id"),
        reasoning_effort=reasoning_effort,
        input_valid=True,
        result_valid=True,
        finished_at=finished_at,
    )


def run_atom_lab(
    api_url: str,
    database_url: str,
    timeout: float,
    *,
    max_total_cost_usd: float,
    access_code: str,
    requested_model_id: str | None,
    decode_database_name: bool = False,
) -> tuple[list[EvidenceCase], int]:
    """Run ANY-467 on the protected Lab surface while reusing atoms-proof ledger checks."""
    headers = {"X-Atom-Lab-Access-Code": access_code}
    try:
        catalog = atoms_proof.smoke._http_json_request(
            f"{api_url}/v1/atom-lab/atoms", extra_headers=headers
        )
        models = atoms_proof.smoke._http_json_request(
            f"{api_url}/v1/atom-lab/models", extra_headers=headers
        )
        model_id, efforts = _select_atom_lab_model(
            models, requested_model_id=requested_model_id
        )
        prompt_by_atom = {
            item["atom_id"]: item["prompt"]
            for item in catalog["items"]
            if isinstance(item, dict)
            and isinstance(item.get("atom_id"), str)
            and isinstance(item.get("prompt"), str)
            and item["prompt"].strip()
        }
        if set(prompt_by_atom) != {case.atom_id for case in ATOM_LAB_CASES}:
            raise ValueError("Atom Lab catalog does not contain exactly A01-A11 prompts")
        if not efforts:
            raise ValueError("selected Atom Lab model has no confirmed reasoning effort")
        engine = atoms_proof._build_engine(
            database_url, decode_database_name=decode_database_name
        )
    except (OSError, KeyError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
        print(f"LIVE029: Atom Lab acceptance setup failed: {type(exc).__name__}", file=sys.stderr)
        return [], 1

    queue = list(ATOM_LAB_CASES)
    base = ATOM_LAB_CASES[0]
    queue.extend(
        AtomLabCase(
            atom_id=base.atom_id,
            input_payload=base.input_payload,
            label=f"{base.atom_id}-reasoning-{effort}",
            kind="reasoning",
        )
        for effort in efforts
    )
    cases: list[EvidenceCase] = []
    aborted = False
    try:
        for index, case in enumerate(queue):
            effort = None if index < len(ATOM_LAB_CASES) else efforts[index - len(ATOM_LAB_CASES)]
            result = _run_atom_lab_case(
                api_url,
                engine,
                case=case,
                prompt=prompt_by_atom[case.atom_id],
                model_id=model_id,
                reasoning_effort=effort,
                access_code=access_code,
                timeout=timeout,
            )
            cases.append(result)
            if result.status == "pass":
                print(f"PASS {result.label}: {result.scenario_id} (session {result.session_id})")
            else:
                print(
                    f"FAIL {result.label}: {result.scenario_id} -> {result.error_code}",
                    file=sys.stderr,
                )
            if result.cost_unknown or _cumulative_estimated_cost(cases) > max_total_cost_usd:
                aborted = True
                code = "LIVE012" if result.cost_unknown else "LIVE001"
                for skipped in queue[index + 1:]:
                    skipped_label = skipped.label or skipped.atom_id
                    cases.append(atoms_proof._fail(
                        label=skipped_label,
                        scenario_id=f"atom-lab.{skipped_label}",
                        kind=skipped.kind,
                        session_id=None,
                        job_id=None,
                        error_code=code,
                        error_message=f"{code}: skipped after cost-safety abort",
                    ))
                break
    finally:
        engine.dispose()

    atom_passed = sum(
        1 for case in cases if case.kind == "atom" and case.status == "pass"
    )
    reasoning_passed = sum(
        1 for case in cases if case.kind == "reasoning" and case.status == "pass"
    )
    print(f"{atom_passed}/{len(ATOM_LAB_CASES)} Atom Lab live atoms passed")
    print(f"{reasoning_passed}/{len(efforts)} Atom Lab reasoning combinations passed")
    exit_code = 0 if (
        atom_passed == len(ATOM_LAB_CASES)
        and reasoning_passed == len(efforts)
        and not aborted
    ) else 1
    return cases, exit_code


def _positive_finite_cost(raw: str) -> float:
    """Code-review finding: a bare float() accepts "nan"/"inf"/"-inf"/"0"/negative strings as
    "valid" for --max-total-cost-usd/ANYTOOLAI_LIVE_CANARY_MAX_COST_USD. nan is the catastrophic
    case -- `total_cost > max_total_cost_usd` (run()'s cost-cap check) is always False when
    max_total_cost_usd is nan, so LIVE001 can never fire and the canary runs every case with no
    cost cap at all, silently defeating the whole point of this cap. Used both as argparse's
    type= for --max-total-cost-usd (argparse turns a raised ValueError into a clean, controlled
    CLI error before any case runs) and directly for the ANYTOOLAI_LIVE_CANARY_MAX_COST_USD env
    var (main() already wraps that call in its own try/except ValueError -> LIVE006)."""
    value = float(raw)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"must be a positive, finite number, got {raw!r}")
    return value

# action_type -> live scenario_id, mirroring the fake-sibling scenario ids one-for-one (see
# configs/kernel/products/kernel_demo/scenarios.yaml). Explicit rather than a string-transform
# helper: the extract atom's fake scenario_id (kernel_demo.single_action_smoke_v1) is missing its
# whole atom-name segment, so no mechanical suffix rule covers all 11 uniformly.
LIVE_ATOM_SCENARIO_IDS: dict[str, str] = {
    "text.extract_structured_fields": "kernel_demo.single_action_live_smoke_v1",
    "text.detect_issues_by_taxonomy": "kernel_demo.single_action_detect_issues_live_smoke_v1",
    "document.generate_from_template": "kernel_demo.single_action_generate_report_live_smoke_v1",
    "text.compose_reply": "kernel_demo.single_action_compose_reply_live_smoke_v1",
    "text.generate_clarifying_questions": (
        "kernel_demo.single_action_generate_clarifying_questions_live_smoke_v1"
    ),
    "text.synthesize_angle": "kernel_demo.single_action_synthesize_angle_live_smoke_v1",
    "text.compose_persuasive_text": (
        "kernel_demo.single_action_compose_persuasive_text_live_smoke_v1"
    ),
    "text.generate_gap_rewrites": "kernel_demo.single_action_generate_gap_rewrites_live_smoke_v1",
    "text.compare_and_classify": "kernel_demo.single_action_compare_and_classify_live_smoke_v1",
    "text.score_match_by_rubric": "kernel_demo.single_action_score_match_by_rubric_live_smoke_v1",
    "text.score_multidimensional_axes": (
        "kernel_demo.single_action_score_multidimensional_axes_live_smoke_v1"
    ),
}

# Guarded like atoms_proof.py's own module-load try/except: a future 12th atom added to
# kernel_demo_smoke.py's ATOM_SMOKE_CASES without a matching LIVE_ATOM_SCENARIO_IDS entry in the
# same PR must fail as a clean LIVE007, not a raw KeyError out of this module-level comprehension.
_MODULE_LOAD_ERROR: str | None = None
try:
    LIVE_ATOM_CASES: tuple[tuple[str, str, dict], ...] = tuple(
        (action_type, LIVE_ATOM_SCENARIO_IDS[action_type], start_input)
        for action_type, _fake_scenario_id, start_input in atoms_proof.ATOM_SMOKE_CASES
    )
except KeyError as exc:
    _MODULE_LOAD_ERROR = (
        f"LIVE007: action_type {exc} from kernel_demo_smoke.py's ATOM_SMOKE_CASES has no matching "
        "entry in LIVE_ATOM_SCENARIO_IDS"
    )
    LIVE_ATOM_CASES = ()

# fake workflow_id/scenario_id -> live equivalent, inline. A mechanical transform is safe here:
# all 3 fake composite workflow_ids uniformly end in "_v1" and their scenario_ids uniformly end in
# "_smoke_v1" (verified against configs/kernel/products/kernel_demo/workflows.yaml and
# scenarios.yaml), unlike the atom-level extract case above which lacks a uniform suffix pattern.
LIVE_COMPOSITE_CASES: tuple[tuple[str, str, dict], ...] = tuple(
    (
        f"{workflow_id.removesuffix('_v1')}_live_v1",
        f"{fake_scenario_id.removesuffix('_smoke_v1')}_live_smoke_v1",
        start_input,
    )
    for workflow_id, fake_scenario_id, start_input in atoms_proof.COMPOSITE_SMOKE_CASES
)


def _schema_ref_overrides(
    fake_cases: tuple[tuple[str, str, dict], ...], live_cases: tuple[tuple[str, str, dict], ...]
) -> dict[str, str]:
    """live_scenario_id -> its fake sibling's expected_output_schema_ref, for
    LIVE_EXPECTED_SCHEMA_REF_BY_SCENARIO below. fake_cases/live_cases are same-length,
    same-order-zippable by construction (LIVE_ATOM_CASES/LIVE_COMPOSITE_CASES are each built by a
    single comprehension over ATOM_SMOKE_CASES/COMPOSITE_SMOKE_CASES)."""
    fake_schema_ref_by_scenario = atoms_proof.smoke._EXPECTED_SCHEMA_REF_BY_SCENARIO
    return {
        live_scenario_id: fake_schema_ref_by_scenario[fake_scenario_id]
        for (_fake_label, fake_scenario_id, _fake_input), (_live_label, live_scenario_id, _live_input)
        in zip(fake_cases, live_cases, strict=True)
        if fake_scenario_id in fake_schema_ref_by_scenario
    }


# Extends smoke._run_one_case()'s SMOKE009 schema_ref cross-check to the 14 live scenario_ids --
# without this, that check silently no-ops for every live case (kernel_demo_smoke.py's own
# _EXPECTED_SCHEMA_REF_BY_SCENARIO only ever knows about fake-provider scenario_ids), exactly the
# class of "wired to the wrong workflow/action" bug SMOKE009 exists to catch. Built as its own
# local dict (see _run_case_with_ledger_check's expected_schema_ref_by_scenario parameter), not by
# mutating the shared kernel_demo_smoke.py module-level dict, since that module is the same cached
# instance atoms_proof.py's own fake-provider runs and kernel_demo_smoke.py's own tests share
# in-process during a single quick-check/pytest run.
# Gated on atoms_proof._MODULE_LOAD_ERROR too, not just this module's own _MODULE_LOAD_ERROR:
# _schema_ref_overrides() reaches into atoms_proof.smoke, which is never bound as an attribute at
# all when atoms_proof's own guarded import block fails (its `smoke = load_smoke_module()` never
# runs) -- calling it unconditionally would raise a raw AttributeError at this module's own import
# time instead of leaving the mapping empty for main() to report the already-recorded load error
# cleanly.
LIVE_EXPECTED_SCHEMA_REF_BY_SCENARIO: dict[str, str] = {}
if atoms_proof._MODULE_LOAD_ERROR is None and _MODULE_LOAD_ERROR is None:
    LIVE_EXPECTED_SCHEMA_REF_BY_SCENARIO.update(
        _schema_ref_overrides(atoms_proof.ATOM_SMOKE_CASES, LIVE_ATOM_CASES)
    )
    LIVE_EXPECTED_SCHEMA_REF_BY_SCENARIO.update(
        _schema_ref_overrides(atoms_proof.COMPOSITE_SMOKE_CASES, LIVE_COMPOSITE_CASES)
    )


def _live_composite_workflow_entries() -> list[dict]:
    """Live-canary-named wrapper around kernel_demo_smoke.py's shared
    _composite_workflow_entries_by_suffix(live=True) -- the inverse of that module's own
    _composite_workflow_entries() (live=False), which permanently excludes them (see that
    function's docstring). code review #4 (2026-08-24) finding #2: this used to be its own
    near-verbatim copy of the open+parse+filter logic; only the suffix-check direction actually
    differs between the fake and live variants, so that's the only thing this wrapper supplies."""
    return atoms_proof.smoke._composite_workflow_entries_by_suffix(live=True)


# Same atoms_proof._MODULE_LOAD_ERROR guard as LIVE_EXPECTED_SCHEMA_REF_BY_SCENARIO above and for
# the same reason: atoms_proof.smoke isn't bound at all when atoms_proof's own guarded import
# fails, and these are otherwise never consulted in that case anyway -- main() already returns
# before its coverage_error check (the only place either is read) once it sees
# atoms_proof._MODULE_LOAD_ERROR is not None.
_LIVE_ATOM_COVERAGE_LABELS = None
_LIVE_COMPOSITE_COVERAGE_LABELS = None
if atoms_proof._MODULE_LOAD_ERROR is None:
    _LIVE_ATOM_COVERAGE_LABELS = atoms_proof.smoke.CoverageLabels(
        error_code="LIVE008", tuple_name="LIVE_ATOM_CASES", kind="live action types"
    )
    _LIVE_COMPOSITE_COVERAGE_LABELS = atoms_proof.smoke.CoverageLabels(
        error_code="LIVE010", tuple_name="LIVE_COMPOSITE_CASES", kind="live composite workflows"
    )


def _live_composite_coverage_error(cases: tuple[tuple[str, str, dict], ...]) -> str | None:
    """Live-canary counterpart of kernel_demo_smoke.py's _composite_coverage_error(), scoped to
    the 3 "_live_v1" composite workflows instead of the 3 fake ones. A thin wrapper around that
    same function (parameterized by entries_provider/labels precisely for this kind of reuse)
    instead of a second ~35-line copy of its duplicate/shape/coverage/binding checks -- keeps a
    future fix to any of those checks from needing to be applied twice."""
    return atoms_proof.smoke._composite_coverage_error(
        cases,
        entries_provider=_live_composite_workflow_entries,
        labels=_LIVE_COMPOSITE_COVERAGE_LABELS,
    )


def _safe_step_cost(estimated_cost: float | None) -> float:
    """None (a step whose provider_calls row predates cost tracking, or a still-fake case)
    contributes 0, not a TypeError -- matches how the rest of this ledger is nullable-by-default.

    A non-finite (NaN/inf) or negative value -- a corrupt ledger row, never a value this script
    itself writes -- returns math.inf instead of its face value: NaN would make every later
    `total_cost > max_total_cost_usd` comparison silently False (the same catastrophic failure
    mode `_positive_finite_cost()`'s own docstring documents for the cap value itself), and a
    negative value would quietly reduce the running total instead of adding to it. math.inf
    propagates through sum() (inf + anything finite is inf) straight into run()'s existing
    cap-trip branch to fail closed -- code review finding."""
    if estimated_cost is None:
        return 0.0
    if not math.isfinite(estimated_cost) or estimated_cost < 0:
        return math.inf
    return estimated_cost


def _cumulative_estimated_cost(cases: list[EvidenceCase]) -> float:
    """Sums estimated_cost across every step of every case so far -- see _safe_step_cost() for
    the None/NaN/negative handling. Plain sum(), not a hand-rolled accumulator loop: CPython's
    sum() uses compensated (Neumaier) summation for floats, which is measurably more accurate
    than naive left-to-right accumulation for a long run of small per-step costs."""
    return sum(
        _safe_step_cost(step.estimated_cost) for case in cases for step in case.steps
    )


def run(
    api_url: str,
    database_url: str,
    timeout: float,
    *,
    max_total_cost_usd: float,
    decode_database_name: bool = False,
    live_canary_token: str | None = None,
) -> tuple[list[EvidenceCase], int]:
    """Runs LIVE_ATOM_CASES then LIVE_COMPOSITE_CASES against a live api_url/database_url, as one
    combined, kind-tagged queue -- atoms first, then composites -- so a single cumulative
    estimated_cost cap and a single chained case_timeout apply across both without duplicating the
    per-case loop for each group. Once the cap trips (LIVE001), every remaining case is marked
    failed instead of silently dropped, regardless of whether it's still in the atom queue or
    hasn't reached the composite queue yet -- so composite_total in the evidence report always
    reflects all 3 composites, even if none of them actually ran. The tripping case itself keeps
    its own real pass/fail status (its ledger/schema correctness is a separate question from the
    cost cap), but the run-level `cost_safety_aborted` flag still forces a non-zero exit_code even
    when the cap trips on the very last queued case -- `remaining` is empty then, so no case would
    otherwise get marked failed and the run would silently report success (`code-review` (me #9)
    finding). decode_database_name is
    forwarded to atoms_proof._build_engine() verbatim -- see its own docstring. live_canary_token
    is forwarded to atoms_proof._run_case_with_ledger_check()/smoke._run_one_case() verbatim as
    the X-Live-Canary-Token header -- the 14 live scenario_ids are config-flagged internal_only,
    so the backend rejects a start request for them without a token matching its own
    ANYTOOLAI_LIVE_CANARY_TOKEN (code review finding: the normal public start-session API used to
    reach these scenarios with no gate at all, bypassing this script's own cost cap/API-key
    fail-fast entirely)."""
    for cases_spec, tuple_name, error_code in (
        (LIVE_ATOM_CASES, "LIVE_ATOM_CASES", "LIVE002"),
        (LIVE_COMPOSITE_CASES, "LIVE_COMPOSITE_CASES", "LIVE003"),
    ):
        empty_error = atoms_proof.smoke._empty_cases_error(
            cases_spec, error_code=error_code, tuple_name=tuple_name, purpose="prove"
        )
        if empty_error is not None:
            print(empty_error, file=sys.stderr)
            return [], 1

    # Code-review finding: _build_engine() can raise RuntimeError for any engine-configuration
    # problem (malformed DSN, unsupported driver, decode-with-nothing-to-decode -- see its own
    # docstring). Left uncaught, this used to propagate as a raw traceback instead of a LIVE0xx
    # code, and skipped write_evidence_report() entirely (main() only calls it after run()
    # returns), leaving the operator with no evidence artifact to diagnose from -- mirrors
    # atoms_proof.py's own run(), which already wraps this the same way (PROOF022).
    try:
        engine = atoms_proof._build_engine(database_url, decode_database_name=decode_database_name)
    except RuntimeError as exc:
        print(f"LIVE009: engine configuration error: {exc}", file=sys.stderr)
        return [], 1

    cases: list[EvidenceCase] = []
    case_timeout = timeout
    # `code-review` (me #9) finding: exit_code below is derived purely from per-case pass/fail
    # counts. Both abort branches below mark every case still in `remaining` as failed -- but if
    # the tripping case is the *last* one in the queue, `remaining` is already empty, so nothing
    # gets marked failed and a cost-cap violation on the final case silently reports exit 0. This
    # flag makes the abort itself part of exit_code, independent of whether any case happened to
    # need marking.
    cost_safety_aborted = False
    try:
        remaining: list[tuple[str, str, str, dict]] = [
            ("atom", label, scenario_id, scenario_input)
            for label, scenario_id, scenario_input in LIVE_ATOM_CASES
        ] + [
            ("composite", label, scenario_id, scenario_input)
            for label, scenario_id, scenario_input in LIVE_COMPOSITE_CASES
        ]
        while remaining:
            kind, label, scenario_id, scenario_input = remaining.pop(0)
            case = atoms_proof._run_case_with_ledger_check(
                api_url, engine, kind=kind, label=label, scenario_id=scenario_id,
                scenario_input=scenario_input, timeout=case_timeout,
                expected_schema_ref_by_scenario=LIVE_EXPECTED_SCHEMA_REF_BY_SCENARIO,
                live_canary_token=live_canary_token,
                max_provider_calls_per_action=_LIVE_PROVIDER_MAX_CALLS_PER_ACTION,
            )
            cases.append(case)
            if case.status == "pass":
                print(f"PASS {label}: {scenario_id} (session {case.session_id})")
            else:
                print(f"FAIL {label}: {scenario_id} -> {case.error_message}", file=sys.stderr)
            case_timeout = atoms_proof.smoke._next_case_timeout(
                case_timeout, timeout,
                timed_out=case.error_code == atoms_proof.smoke._TIMEOUT_ERROR_CODE,
            )

            # `code-review` finding: a case whose real cost couldn't be recovered after
            # a ledger/DB error (case.cost_unknown) used to fall through as $0 to the cumulative
            # cost-cap check below, fail-open -- a lost DB connection let every remaining case
            # keep spending with no cap in effect. Fail closed instead: abort immediately, since
            # a real, billed provider call may already have happened for this case.
            # LIVE012, not LIVE011: `code-review` (me #6) finding -- runner.py already uses
            # LIVE011 for a completely different condition (ANYTOOLAI_LIVE_CANARY_TOKEN unset),
            # and that error-code namespace is shared across logs/evidence/automation.
            if case.cost_unknown:
                cost_safety_aborted = True
                print(
                    f"LIVE012: cost for case {label} ({scenario_id}) could not be recovered "
                    f"after a ledger/database error -- aborting remaining {len(remaining)} "
                    "case(s) fail-closed since actual spend is unknown",
                    file=sys.stderr,
                )
                for skipped_kind, skipped_label, skipped_scenario_id, _ in remaining:
                    cases.append(
                        atoms_proof._fail(
                            label=skipped_label, scenario_id=skipped_scenario_id,
                            kind=skipped_kind,
                            session_id=None, job_id=None,
                            error_code="LIVE012",
                            error_message=(
                                f"LIVE012: skipped -- case {label} left the cumulative cost "
                                "cap in an unknown state after a ledger/database error"
                            ),
                        )
                    )
                break

            total_cost = _cumulative_estimated_cost(cases)
            if total_cost > max_total_cost_usd:
                cost_safety_aborted = True
                print(
                    f"LIVE001: cumulative estimated_cost {total_cost:.4f} exceeded cap "
                    f"{max_total_cost_usd:.4f} after case {label} -- aborting remaining "
                    f"{len(remaining)} case(s)",
                    file=sys.stderr,
                )
                for skipped_kind, skipped_label, skipped_scenario_id, _ in remaining:
                    cases.append(
                        atoms_proof._fail(
                            label=skipped_label, scenario_id=skipped_scenario_id,
                            kind=skipped_kind,
                            session_id=None, job_id=None,
                            error_code="LIVE001",
                            error_message=(
                                f"LIVE001: skipped -- cumulative estimated_cost cap "
                                f"{max_total_cost_usd:.4f} was already exceeded"
                            ),
                        )
                    )
                break

        atom_total = len(LIVE_ATOM_CASES)
        atom_passed = sum(1 for case in cases if case.kind == "atom" and case.status == "pass")
        composite_total = len(LIVE_COMPOSITE_CASES)
        composite_passed = sum(
            1 for case in cases if case.kind == "composite" and case.status == "pass"
        )
        print(f"{atom_passed}/{atom_total} kernel_demo live atoms passed")
        print(f"{composite_passed}/{composite_total} kernel_demo live composites passed")
        if cost_safety_aborted:
            print(
                "LIVE001/LIVE012: cost-safety abort tripped during this run -- forcing a "
                "non-zero exit code even though every attempted case's own ledger/schema "
                "correctness passed",
                file=sys.stderr,
            )
        exit_code = (
            0
            if atom_passed == atom_total
            and composite_passed == composite_total
            and not cost_safety_aborted
            else 1
        )
        return cases, exit_code
    finally:
        engine.dispose()


def main() -> int:
    if atoms_proof._MODULE_LOAD_ERROR is not None:
        print(atoms_proof._MODULE_LOAD_ERROR, file=sys.stderr)
        return 1
    if _MODULE_LOAD_ERROR is not None:
        print(_MODULE_LOAD_ERROR, file=sys.stderr)
        return 1

    try:
        default_timeout = atoms_proof._default_timeout()
    except ValueError as exc:
        print(f"LIVE005: ANYTOOLAI_SMOKE_TIMEOUT must be a number: {exc}", file=sys.stderr)
        return 2

    try:
        raw_max_cost = os.environ.get("ANYTOOLAI_LIVE_CANARY_MAX_COST_USD")
        default_max_cost = (
            DEFAULT_MAX_TOTAL_COST_USD if raw_max_cost is None else _positive_finite_cost(raw_max_cost)
        )
    except ValueError as exc:
        print(
            f"LIVE006: ANYTOOLAI_LIVE_CANARY_MAX_COST_USD must be a number: {exc}",
            file=sys.stderr,
        )
        return 2

    # Shared with atoms_proof.py's own main() -- see its own docstring for why this isn't
    # declared separately here (it drifted out of sync once already when it was).
    parser = atoms_proof._build_arg_parser(__doc__, default_timeout=default_timeout)
    parser.add_argument(
        "--max-total-cost-usd",
        type=_positive_finite_cost,
        default=default_max_cost,
        help="Abort remaining cases once cumulative estimated_cost exceeds this (default: "
        "%(default)s, also settable via ANYTOOLAI_LIVE_CANARY_MAX_COST_USD)",
    )
    args = parser.parse_args()

    database_url = os.environ.get(args.database_url_env)
    if not database_url:
        print(
            f"LIVE004: environment variable {args.database_url_env!r} (--database-url-env) "
            "is not set or empty",
            file=sys.stderr,
        )
        return 2

    surface = os.environ.get(LIVE_CANARY_SURFACE_ENV_VAR, PRODUCTION_SURFACE).strip()
    if surface not in {PRODUCTION_SURFACE, ATOM_LAB_SURFACE}:
        print(
            f"LIVE014: {LIVE_CANARY_SURFACE_ENV_VAR} must be {PRODUCTION_SURFACE!r} or "
            f"{ATOM_LAB_SURFACE!r}",
            file=sys.stderr,
        )
        return 2
    if surface == ATOM_LAB_SURFACE:
        access_code = os.environ.get(ATOM_LAB_ACCESS_CODE_ENV_VAR, "").strip()
        if not access_code:
            print(
                f"LIVE013: Atom Lab live canary requires {ATOM_LAB_ACCESS_CODE_ENV_VAR}",
                file=sys.stderr,
            )
            return 2
        cases, exit_code = run_atom_lab(
            args.api_url.rstrip("/"),
            database_url,
            args.timeout,
            max_total_cost_usd=args.max_total_cost_usd,
            access_code=access_code,
            requested_model_id=os.environ.get(ATOM_LAB_MODEL_ID_ENV_VAR) or None,
            decode_database_name=args.database_url_is_percent_encoded,
        )
        report_path = atoms_proof.write_evidence_report(
            cases,
            exit_code,
            output_root=REPO_ROOT / ".agent" / "live-canary" / "atom-lab",
        )
        print(f"Evidence report: {report_path}")
        return exit_code

    coverage_error = atoms_proof.smoke._atom_coverage_error(
        LIVE_ATOM_CASES, labels=_LIVE_ATOM_COVERAGE_LABELS
    ) or _live_composite_coverage_error(LIVE_COMPOSITE_CASES)
    if coverage_error is not None:
        print(coverage_error, file=sys.stderr)
        cases, exit_code = [], 1
    else:
        cases, exit_code = run(
            args.api_url.rstrip("/"), database_url, args.timeout,
            max_total_cost_usd=args.max_total_cost_usd,
            decode_database_name=args.database_url_is_percent_encoded,
            live_canary_token=os.environ.get(LIVE_CANARY_TOKEN_ENV_VAR),
        )

    report_path = atoms_proof.write_evidence_report(
        cases, exit_code, output_root=REPO_ROOT / ".agent" / "live-canary"
    )
    print(f"Evidence report: {report_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
