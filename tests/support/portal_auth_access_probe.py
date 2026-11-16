"""Local TCP checkpoint driver; external providers and paid execution are out of scope."""

from __future__ import annotations

import json
import socket
import sys
from http import HTTPStatus
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import httpx
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from anytoolai_platform_api.main import create_app
from anytoolai_platform_api.paid_access import AccessSnapshotClient, refresh_authority
from anytoolai_platform_api.portal_session import PortalSessionClient
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.quotas.access_coherence import AccessCoherenceRepository
from anytoolai_platform_core.storage.transactions import build_session_factory, transaction_boundary
from pydantic import SecretStr

from tests.db_support import provision_database


def main() -> None:
    inputs = json.load(sys.stdin)
    with provision_database(
        database_name_prefix="any766_http_access", skip_reason="local TCP access"
    ) as (engine, _, _):
        factory = build_session_factory(engine)
        for case in inputs["consumers"]:
            settings = Settings(
                portal_base_url=inputs["portal_origin"],
                portal_consumer_id=case["consumer_id"],
                portal_access_service_token=SecretStr(case["service_token"]),
            )
            app = create_app(
                config_root=Path("configs/kernel"),
                database_url=engine.url.render_as_string(hide_password=False),
            )
            app.state.settings = settings
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
                server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
                worker = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
                worker.start()
                try:
                    deadline = monotonic() + 10
                    while not server.started:
                        assert worker.is_alive() and monotonic() < deadline, (
                            "Kernel HTTP startup failed"
                        )
                        sleep(0.01)
                    with httpx.Client(trust_env=False) as client:
                        response = client.post(
                            origin + "/v1/portal-session/exchange",
                            json={
                                "code": case["code"],
                                "code_verifier": inputs["verifier"],
                            },
                        )
                        assert response.status_code == HTTPStatus.OK, "Kernel TCP exchange failed"
                        assert response.headers["cache-control"] == "no-store"
                        token = response.json()["access_token"]
                    principal = PortalSessionClient(settings).introspect(token)
                    assert principal.consumer_id == case["consumer_id"]
                    snapshot_client = AccessSnapshotClient(settings)
                    document = snapshot_client.fetch(principal.owner)
                    assert document.consumer_id == principal.consumer_id
                    assert document.consumer_policy_revision == principal.consumer_policy_revision
                    assert {g.product_id for g in document.grants} == set(case["products"])
                    refresh_authority(factory, principal, snapshot_client)
                    with transaction_boundary(factory) as session:
                        row = AccessCoherenceRepository(
                            session, principal.owner, consumer_id=principal.consumer_id
                        ).read()
                        assert row["policy_floor"] == principal.consumer_policy_revision
                        assert row["revision_floor"] == document.access_revision
                        assert row["snapshot"]["consumer_id"] == principal.consumer_id
                finally:
                    server.should_exit = True
                    worker.join(10)
                    assert not worker.is_alive(), "Kernel HTTP cleanup failed"
    print(
        "PASS: two consumer-bound TCP exchanges, live introspections, "
        "V3 snapshots and durable P/R installations"
    )


if __name__ == "__main__":
    main()
