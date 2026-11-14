"""One bounded reverse-HTTP lane, independent of workflow execution time."""

import json
import logging
import os
import re
from http import HTTPStatus
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from anytoolai_platform_core.quotas.consumer_binding import check_consumer_binding
from anytoolai_platform_core.quotas.exhaustion import (
    DeliveryError,
    claim_exhaustion,
    settle_exhaustion,
)
from anytoolai_platform_core.storage.db import create_sync_engine
from anytoolai_platform_core.storage.transactions import SessionFactory, build_session_factory
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from sqlalchemy.engine import Engine

DELIVERY_TIMEOUT_SECONDS = 2
SERVER_ERROR_LIMIT = 600
ASCII_GRAPHIC_START = 33
logger = logging.getLogger(__name__)


class ExhaustionSettings(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)
    base_url: str
    service_token: SecretStr = Field(repr=False)
    tenant_id: str = Field(min_length=1)
    region: str = Field(min_length=1)
    consumer_id: str = Field(default="platform-kernel", pattern=r"^[a-z][a-z0-9-]{0,63}$")
    app_env: str = "dev"

    @model_validator(mode="after")
    def validate_connection(self) -> "ExhaustionSettings":
        url = urlsplit(self.base_url)
        if (
            not url.hostname
            or url.username is not None
            or url.password is not None
            or url.path not in ("", "/")
            or url.query
            or url.fragment
            or url.port == 0
            or any(
                character.isspace() or ord(character) < ASCII_GRAPHIC_START
                for character in self.base_url
            )
            or not (
                url.scheme == "https"
                or (
                    self.app_env in {"dev", "test"}
                    and url.scheme == "http"
                    and url.hostname in {"localhost", "127.0.0.1", "::1"}
                )
            )
            or re.fullmatch(
                r"[A-Za-z0-9._~+/-]{32,256}={0,2}", self.service_token.get_secret_value()
            )
            is None
        ):
            raise ValueError(
                "Exhaustion delivery requires a trusted Portal origin and service credential"
            )
        return self

    @classmethod
    def from_env(cls) -> "ExhaustionSettings | None":
        enabled = os.getenv("ANYTOOLAI_PORTAL_EXHAUSTION_DELIVERY_ENABLED", "false").lower()
        if enabled not in {"true", "false"}:
            raise ValueError("ANYTOOLAI_PORTAL_EXHAUSTION_DELIVERY_ENABLED requires true/false")
        if enabled == "false":
            return None
        return cls(
            base_url=os.getenv("ANYTOOLAI_PORTAL_BASE_URL", ""),
            service_token=SecretStr(os.getenv("ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN", "")),
            tenant_id=os.getenv("ANYTOOLAI_TENANT_ID", "anytoolai"),
            region=os.getenv("ANYTOOLAI_REGION", "ru"),
            consumer_id=os.getenv("ANYTOOLAI_PORTAL_CONSUMER_ID", "platform-kernel"),
            app_env=os.getenv("ANYTOOLAI_APP_ENV", "dev"),
        )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


class ExhaustionDelivery:
    def __init__(
        self,
        factory: SessionFactory,
        settings: ExhaustionSettings,
        *,
        owned_engine: Engine | None = None,
    ) -> None:
        self.factory, self.settings, self.owned_engine = factory, settings, owned_engine

    def deliver_once(self) -> bool:
        with self.factory() as session:
            # Never claim or send another consumer's history. Missing bindings
            # precede first paid use; recheck next tick instead of binding here.
            if not check_consumer_binding(session, self.settings.consumer_id):
                return False
        claim = claim_exhaustion(self.factory, self.settings.tenant_id, self.settings.region)
        if claim is None:
            return False
        # SQL is closed before transport. Redirects/proxies cannot receive secrets.
        error: DeliveryError | None = None
        http_status: int | None = None
        request = Request(
            self.settings.base_url.rstrip("/") + "/internal/v1/allowance-exhaustions",
            data=json.dumps(claim.event.wire()).encode(),
            method="POST",
            headers={
                "Authorization": "Bearer " + self.settings.service_token.get_secret_value(),
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
            },
        )
        try:
            with build_opener(ProxyHandler({}), _NoRedirect()).open(
                request,
                timeout=DELIVERY_TIMEOUT_SECONDS,
            ) as response:
                http_status = response.status
                if response.status != HTTPStatus.NO_CONTENT:
                    error = "http_permanent"
        except HTTPError as failure:
            http_status = failure.code
            error = (
                "http_retryable"
                if failure.code == HTTPStatus.TOO_MANY_REQUESTS
                or (HTTPStatus.INTERNAL_SERVER_ERROR <= failure.code < SERVER_ERROR_LIMIT)
                else "http_permanent"
            )
            failure.close()
        except (URLError, TimeoutError, OSError, HTTPException):
            error = "transport"
        settled = settle_exhaustion(self.factory, claim, error=error, http_status=http_status)
        if settled and error == "http_permanent":
            logger.error("worker.allowance_exhaustion_parked", extra={"outbox_id": claim.id})
        return True

    def dispose(self) -> None:
        if self.owned_engine is not None:
            self.owned_engine.dispose()


def build_exhaustion_delivery(engine: Engine, settings: ExhaustionSettings) -> ExhaustionDelivery:
    # A workflow may hold its transaction throughout provider I/O. Delivery owns one
    # separate connection with finite checkout/connect/SQL waits, never that transaction.
    delivery_engine = create_sync_engine(
        engine.url,
        pool_size=1,
        max_overflow=0,
        pool_timeout=DELIVERY_TIMEOUT_SECONDS,
        connect_args={
            "connect_timeout": DELIVERY_TIMEOUT_SECONDS,
            "options": "-c statement_timeout=2000 -c lock_timeout=2000",
        },
    )
    return ExhaustionDelivery(
        build_session_factory(delivery_engine), settings, owned_engine=delivery_engine
    )
