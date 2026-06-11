from anytoolai_platform_core.events.envelope import EventEnvelope
from anytoolai_platform_core.events.taxonomy import PLATFORM_EVENTS


def test_event_envelope_has_required_dimensions() -> None:
    fields = set(EventEnvelope.__dataclass_fields__)
    required = {"event_id", "event_type", "timestamp", "tenant_id", "region", "scenario_session_id", "job_id", "workflow_id", "action_type", "artifact_id", "handoff_id"}
    assert required <= fields


def test_event_taxonomy_contains_required_client_events() -> None:
    required = {"client.result_copied", "client.next_action_clicked"}
    assert required <= PLATFORM_EVENTS
