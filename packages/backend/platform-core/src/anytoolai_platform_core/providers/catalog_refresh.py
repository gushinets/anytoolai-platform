from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.orm import Session, sessionmaker

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.providers.catalog import (
    ModelCapabilityOverride,
    build_openai_gpt_catalog,
)
from anytoolai_platform_core.providers.catalog_repository import ModelCatalogRepository
from anytoolai_platform_core.providers.catalog_settings import (
    model_catalog_refresh_deadline_seconds,
)
from anytoolai_platform_core.storage.transactions import transaction_boundary

_SAFE_REFRESH_ERROR = "Upstream model catalog refresh failed."
logger = logging.getLogger(__name__)


class ModelCatalogSource(Protocol):
    async def fetch_openai_model_ids(self) -> Sequence[str]: ...
    async def fetch_litellm_metadata(self) -> Mapping[str, Any]: ...


class ModelCatalogRefreshService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        account_scope: str,
        source: ModelCatalogSource,
        overrides: Mapping[str, ModelCapabilityOverride],
        ttl: timedelta,
        retry_after: timedelta,
        lease_duration: timedelta,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._account_scope = account_scope
        self._source = source
        self._overrides = overrides
        self._ttl = ttl
        self._retry_after = retry_after
        self._lease_duration = lease_duration
        self._now = now

    async def refresh_if_due(self) -> None:
        claimed_at = self._now()
        with transaction_boundary(self._session_factory) as session:
            refresh_is_due = ModelCatalogRepository(session).refresh_is_due(
                self._account_scope,
                now=claimed_at,
            )
        if not refresh_is_due:
            return

        with transaction_boundary(self._session_factory) as session:
            lease = ModelCatalogRepository(session).claim_refresh(
                self._account_scope,
                now=claimed_at,
                lease_duration=self._lease_duration,
            )
        if lease is None:
            return

        try:
            refresh_deadline_seconds = model_catalog_refresh_deadline_seconds(self._lease_duration)
            async with asyncio.timeout(refresh_deadline_seconds):
                model_ids = await self._source.fetch_openai_model_ids()
                metadata = await self._source.fetch_litellm_metadata()
            completed_at = self._now()
            items = build_openai_gpt_catalog(
                account_model_ids=model_ids,
                litellm_metadata=metadata,
                overrides=self._overrides,
                fetched_at=completed_at,
            )
            with transaction_boundary(self._session_factory) as session:
                ModelCatalogRepository(session).complete_refresh(
                    lease,
                    snapshot_id=new_id("model_catalog_snapshot"),
                    items=items,
                    now=completed_at,
                    ttl=self._ttl,
                )
        except Exception:
            logger.exception(
                "model catalog refresh failed",
                extra={"account_scope": self._account_scope},
            )
            failed_at = self._now()
            with transaction_boundary(self._session_factory) as session:
                ModelCatalogRepository(session).fail_refresh(
                    lease,
                    error=_SAFE_REFRESH_ERROR,
                    now=failed_at,
                    retry_after=self._retry_after,
                )
