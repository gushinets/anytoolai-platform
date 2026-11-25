"""Read v1 results written before A04 and A05 required authored text on publication."""

import asyncio
from http import HTTPStatus

import pytest
from anytoolai_platform_core.storage.transactions import transaction_boundary
from test_results_api import _create_test_app, _request, _seed_result


@pytest.mark.parametrize(
    ("schema_ref", "content", "expected"),
    [
        (
            "kernel.schemas.issue_detection_output_v1",
            {
                "issues": [
                    {"category": "scope", "severity": "low", "description": " "},
                    {
                        "category": "scope",
                        "severity": "low",
                        "description": "Scope?",
                        "evidence": "\ufeff",
                    },
                ]
            },
            HTTPStatus.OK,
        ),
        (
            "kernel.schemas.generate_questions_output_v1",
            {
                "questions": [
                    {
                        "category": "scope",
                        "priority": "low",
                        "source_issue_index": 0,
                        "question": "\ufeff",
                        "rationale": " ",
                    },
                ]
            },
            HTTPStatus.OK,
        ),
        (
            "kernel.schemas.issue_detection_output_v1",
            {
                "issues": [
                    {"category": "scope", "severity": "low", "description": ""},
                ]
            },
            HTTPStatus.NOT_FOUND,
        ),
        ("kernel.schemas.generate_questions_output_v1", {"questions": [{}]}, HTTPStatus.NOT_FOUND),
    ],
)
def test_saved_atom_results_follow_the_historical_read_contract(
    session_factory, schema_ref, content, expected
):
    app = _create_test_app(session_factory)
    registry = app.state.runtime.config_registry
    workflows = {
        w.workflow_id for w in registry.workflows.values() if w.output_schema_ref == schema_ref
    }
    scenarios = {s.workflow_id: s.scenario_id for s in registry.scenarios.values()}
    assert workflows
    for workflow_id in workflows:
        with transaction_boundary(session_factory) as session:
            _, _, artifact_id = _seed_result(
                session,
                workflow_id=workflow_id,
                schema_ref=schema_ref,
                scenario_id=scenarios[workflow_id],
                content_json=content,
            )
        response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
        assert response.status_code == expected, (workflow_id, response.text)
        if expected == HTTPStatus.OK:
            assert response.json()["output"] == content
        else:
            assert response.json()["error"]["code"] == "result_artifact_unavailable"
