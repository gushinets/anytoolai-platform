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

import argparse
import os
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import atoms_proof  # noqa: E402
from atoms_proof import EvidenceCase  # noqa: E402 -- always defined, unlike `smoke` (see below)

# atoms_proof.smoke is only bound when atoms_proof's own module-load try/except block succeeds
# (mirrors atoms_proof.py's own guarded ATOM_SMOKE_CASES/COMPOSITE_SMOKE_CASES pattern) -- looked
# up lazily via atoms_proof.smoke.* inside run()/main() below, both gated on
# atoms_proof._MODULE_LOAD_ERROR being None, instead of imported here at parse time where a failed
# atoms_proof load would raise a raw ImportError before main() ever gets to print a clean code.

DEFAULT_MAX_TOTAL_COST_USD = 0.50

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

LIVE_ATOM_CASES: tuple[tuple[str, str, dict], ...] = tuple(
    (action_type, LIVE_ATOM_SCENARIO_IDS[action_type], start_input)
    for action_type, _fake_scenario_id, start_input in atoms_proof.ATOM_SMOKE_CASES
)

# fake workflow_id -> live workflow_id/scenario_id. Unlike LIVE_ATOM_SCENARIO_IDS, a mechanical
# transform is safe here: all 3 fake composite workflow_ids uniformly end in "_v1" and their
# scenario_ids uniformly end in "_smoke_v1" (verified against configs/kernel/products/kernel_demo/
# workflows.yaml and scenarios.yaml), unlike the atom-level extract case which lacks a uniform
# suffix pattern.
LIVE_COMPOSITE_WORKFLOW_IDS: dict[str, str] = {
    fake_workflow_id: f"{fake_workflow_id.removesuffix('_v1')}_live_v1"
    for fake_workflow_id, _fake_scenario_id, _start_input in atoms_proof.COMPOSITE_SMOKE_CASES
}
LIVE_COMPOSITE_SCENARIO_IDS: dict[str, str] = {
    fake_scenario_id: f"{fake_scenario_id.removesuffix('_smoke_v1')}_live_smoke_v1"
    for _fake_workflow_id, fake_scenario_id, _start_input in atoms_proof.COMPOSITE_SMOKE_CASES
}

LIVE_COMPOSITE_CASES: tuple[tuple[str, str, dict], ...] = tuple(
    (
        LIVE_COMPOSITE_WORKFLOW_IDS[workflow_id],
        LIVE_COMPOSITE_SCENARIO_IDS[fake_scenario_id],
        start_input,
    )
    for workflow_id, fake_scenario_id, start_input in atoms_proof.COMPOSITE_SMOKE_CASES
)


def _live_composite_workflow_entries() -> list[dict]:
    """Own, live-canary-local parse of workflows.yaml, filtered to the "_live_v1"-suffixed
    composite entries -- the inverse of kernel_demo_smoke.py's _composite_workflow_entries(),
    which permanently excludes them (see that function's docstring). Deliberately not shared with
    or parameterized onto that function: provider selection is a static config fact here, not a
    runtime mode kernel_demo_smoke.py's fake-provider-oriented coverage checks (also used by
    atoms_proof.py and dev-smoke/prod-smoke) need to know about."""
    with atoms_proof.smoke.WORKFLOWS_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return [
        entry
        for entry in data.get("workflows", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("workflow_id"), str)
        and entry["workflow_id"].startswith(atoms_proof.smoke._COMPOSITE_WORKFLOW_ID_PREFIX)
        and entry["workflow_id"].endswith("_live_v1")
    ]


def _live_composite_coverage_error(cases: tuple[tuple[str, str, dict], ...]) -> str | None:
    """Live-canary counterpart of kernel_demo_smoke.py's _composite_coverage_error(), scoped to
    the 3 "_live_v1" composite workflows instead of the 3 fake ones. Reuses that module's
    non-fake-specific pure helpers (case-id unzip, schema-ref derivation, coverage-mismatch
    formatting, the real scenario<->workflow binding from scenarios.yaml) since those only operate
    on already-filtered inputs and encode no fake/live assumption themselves -- only the
    duplicate/shape checks are reimplemented here (not reused), since the shared version's error
    strings hardcode "COMPOSITE_SMOKE_CASES"/"SMOKE010", which would misname the live case list
    and error family in a live-canary failure message."""
    smoke = atoms_proof.smoke
    workflow_ids, scenario_ids = smoke._composite_case_ids(cases)
    for field_name, ids in (("workflow_id", workflow_ids), ("scenario_id", scenario_ids)):
        if len(ids) != len(set(ids)):
            return f"LIVE010: LIVE_COMPOSITE_CASES has duplicate {field_name} entries"
    for config_path in (smoke.WORKFLOWS_CONFIG_PATH, smoke.SCENARIOS_CONFIG_PATH):
        if not config_path.is_file():
            return (
                f"LIVE010: cannot verify required live composite coverage -- {config_path} "
                "not found"
            )
    try:
        entries = _live_composite_workflow_entries()
        required = smoke._composite_required_ids(entries)
        output_schema_ref_by_workflow_id = smoke._composite_schema_ref_by_workflow_id(entries)
        workflow_id_by_scenario_id = smoke._required_composite_workflow_id_by_scenario_id()
    except smoke._COMPOSITE_CONFIG_PARSE_ERRORS as exc:
        return (
            "LIVE010: could not parse composite workflow/scenario config to verify required "
            f"live composite coverage: {exc}"
        )
    missing_schema_ref = sorted(required - output_schema_ref_by_workflow_id.keys())
    if missing_schema_ref:
        return (
            "LIVE010: live composite workflow config validation failed: missing/invalid "
            f"output_schema_ref for workflow(s): {missing_schema_ref}"
        )
    covered = set(workflow_ids)
    if covered != required:
        return smoke._coverage_mismatch_error(
            covered, required, error_code="LIVE010", tuple_name="LIVE_COMPOSITE_CASES",
            kind="live composite workflows",
        )
    for workflow_id, scenario_id in zip(workflow_ids, scenario_ids, strict=True):
        expected_workflow_id = workflow_id_by_scenario_id.get(scenario_id)
        if expected_workflow_id != workflow_id:
            return (
                f"LIVE010: LIVE_COMPOSITE_CASES pairs scenario {scenario_id!r} with workflow "
                f"{workflow_id!r}, but scenarios.yaml binds that scenario to "
                f"{expected_workflow_id!r} -- scenario/workflow mismatch"
            )
    return None


def _cumulative_estimated_cost(cases: list[EvidenceCase]) -> float:
    """Sums estimated_cost across every step of every case so far. None (a step whose
    provider_calls row predates cost tracking, or a still-fake case) contributes 0, not a
    TypeError -- matches how the rest of this ledger is nullable-by-default."""
    return sum(
        step.estimated_cost or 0.0 for case in cases for step in case.steps
    )


def run(
    api_url: str, database_url: str, timeout: float, *, max_total_cost_usd: float
) -> tuple[list[EvidenceCase], int]:
    """Runs LIVE_ATOM_CASES then LIVE_COMPOSITE_CASES against a live api_url/database_url, as one
    combined, kind-tagged queue -- atoms first, then composites -- so a single cumulative
    estimated_cost cap and a single chained case_timeout apply across both without duplicating the
    per-case loop for each group. Once the cap trips (LIVE001), every remaining case is marked
    failed instead of silently dropped, regardless of whether it's still in the atom queue or
    hasn't reached the composite queue yet -- so composite_total in the evidence report always
    reflects all 3 composites, even if none of them actually ran."""
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

    engine = atoms_proof._build_engine(database_url)
    cases: list[EvidenceCase] = []
    case_timeout = timeout
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

            total_cost = _cumulative_estimated_cost(cases)
            if total_cost > max_total_cost_usd:
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
        exit_code = (
            0 if atom_passed == atom_total and composite_passed == composite_total else 1
        )
        return cases, exit_code
    finally:
        engine.dispose()


def main() -> int:
    if atoms_proof._MODULE_LOAD_ERROR is not None:
        print(atoms_proof._MODULE_LOAD_ERROR, file=sys.stderr)
        return 1

    try:
        default_timeout = atoms_proof._default_timeout()
    except ValueError as exc:
        print(f"LIVE005: ANYTOOLAI_SMOKE_TIMEOUT must be a number: {exc}", file=sys.stderr)
        return 2

    try:
        raw_max_cost = os.environ.get("ANYTOOLAI_LIVE_CANARY_MAX_COST_USD")
        default_max_cost = (
            DEFAULT_MAX_TOTAL_COST_USD if raw_max_cost is None else float(raw_max_cost)
        )
    except ValueError as exc:
        print(
            f"LIVE006: ANYTOOLAI_LIVE_CANARY_MAX_COST_USD must be a number: {exc}",
            file=sys.stderr,
        )
        return 2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "api_url", help="Base URL of a live platform-api, e.g. http://127.0.0.1:8000"
    )
    parser.add_argument(
        "--database-url-env",
        required=True,
        metavar="ENV_VAR",
        help="Name of an environment variable holding the PostgreSQL URL for the same stack's "
        "database -- the URL itself is read from the environment, not passed here, since it can "
        "embed credentials that argv/process listings would otherwise expose.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=default_timeout,
        help="Seconds to wait for each scenario to complete (default: %(default)s, "
        "also settable via ANYTOOLAI_SMOKE_TIMEOUT)",
    )
    parser.add_argument(
        "--max-total-cost-usd",
        type=float,
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

    coverage_error = atoms_proof.smoke._atom_coverage_error(
        LIVE_ATOM_CASES
    ) or _live_composite_coverage_error(LIVE_COMPOSITE_CASES)
    if coverage_error is not None:
        print(coverage_error, file=sys.stderr)
        cases, exit_code = [], 1
    else:
        cases, exit_code = run(
            args.api_url.rstrip("/"), database_url, args.timeout,
            max_total_cost_usd=args.max_total_cost_usd,
        )

    report_path = atoms_proof.write_evidence_report(
        cases, exit_code, output_root=REPO_ROOT / ".agent" / "live-canary"
    )
    print(f"Evidence report: {report_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
