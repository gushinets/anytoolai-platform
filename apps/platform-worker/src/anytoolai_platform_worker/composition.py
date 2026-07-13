"""Production composition root for the A11 DB-backed workflow worker."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from anytoolai_platform_actions.structured_llm.executor import StructuredLlmActionExecutor
from anytoolai_platform_core.actions.repository import ActionRunRepository
from anytoolai_platform_core.actions.runner import ActionRunner, ActionRunService
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.gateway import (
    ProviderGateway,
    build_default_provider_adapters,
)
from anytoolai_platform_core.providers.policies import ProviderPolicyResolver
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.storage.db import create_sync_engine
from anytoolai_platform_core.storage.transactions import build_session_factory
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_core.workflows.runner import (
    SequentialWorkflowRunner,
    WorkflowJobService,
)
from sqlalchemy.orm import Session, sessionmaker

from anytoolai_platform_worker.handlers.run_workflow import RunWorkflowHandler
from anytoolai_platform_worker.queues import DatabaseJobQueue
from anytoolai_platform_worker.worker import Worker


def build_worker(
    *,
    database_url: str | None = None,
    session_factory: sessionmaker[Session] | None = None,
    config_root: Path | None = None,
    config_registry: ConfigRegistry | None = None,
    provider_adapters: Mapping[str, Any] | None = None,
    poll_interval_seconds: float = 1.0,
) -> Worker:
    """Build the production graph, with explicit test seams for DB and provider adapters."""

    if session_factory is None:
        if not database_url:
            raise ValueError("database_url is required when session_factory is not provided")
        session_factory = build_session_factory(create_sync_engine(database_url))

    registry = config_registry or build_config_registry(config_root)
    adapters = dict(provider_adapters or build_default_provider_adapters(config_root))

    def runner_factory(session: Session) -> SequentialWorkflowRunner:
        event_emitter = EventEmitter(EventLogRepository(session))
        artifact_repository = ArtifactRepository(session)
        artifact_service = ArtifactService(artifact_repository, event_emitter)
        provider_gateway = ProviderGateway(
            adapters,
            policy_resolver=ProviderPolicyResolver(registry),
            provider_call_repository=ProviderCallRepository(session),
            event_emitter=event_emitter,
        )
        structured_executor = StructuredLlmActionExecutor(
            config_registry=registry,
            provider_gateway=provider_gateway,
            artifact_service=artifact_service,
        )
        action_runner = ActionRunner(
            session=session,
            config_registry=registry,
            action_run_service=ActionRunService(
                ActionRunRepository(session),
                event_emitter,
            ),
            executors={structured_executor.executor_id: structured_executor},
            artifact_repository=artifact_repository,
        )
        return SequentialWorkflowRunner(
            session=session,
            config_registry=registry,
            job_service=WorkflowJobService(JobRepository(session), event_emitter),
            action_runner=action_runner,
            artifact_service=artifact_service,
            event_emitter=event_emitter,
        )

    handler = RunWorkflowHandler(
        session_factory=session_factory,
        runner_factory=runner_factory,
    )
    return Worker(
        handler,
        job_queue=DatabaseJobQueue(session_factory),
        poll_interval_seconds=poll_interval_seconds,
    )
