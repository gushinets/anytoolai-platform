from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from dataclasses import replace
from datetime import datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import yaml
from anytoolai_platform_api import bootstrap, main
from anytoolai_platform_api.dependencies import get_config_registry
from anytoolai_platform_api.main import create_app
from anytoolai_platform_api.manifest_auth import PortalPrincipal, authenticate_portal
from anytoolai_platform_api.schemas import ErrorResponse
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.config.errors import RegistryLoadError
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.providers.gateway import ProviderGateway
from anytoolai_platform_core.storage.transactions import SessionFactory, transaction_boundary
from anytoolai_platform_sdk import ProductBundle
from fastapi import FastAPI

CONFIG_ROOT = Path(__file__).resolve().parents[3] / "configs" / "kernel"
TOKEN = "current-portal-test-token-" + "a" * 32
PREVIOUS = "previous-portal-test-token-" + "b" * 32
WRONG = "another-connection-test-token-" + "c" * 32
PATH = "/internal/v1/capability-manifest"
URL = PATH + "?tenant_id=anytoolai&region=ru"
PRODUCTS = {
    "kernel_demo",
    "proposal_ai",
    "client_update_writer",
    "brief_decoder",
    "acceptance_builder",
    "task_finder",
}


@pytest.fixture(autouse=True)
def isolated_boundary_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ANYTOOLAI_TENANT_ID",
        "ANYTOOLAI_REGION",
        "ANYTOOLAI_PORTAL_SERVICE_TOKEN",
        "ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS",
        "ANYTOOLAI_ENABLED_PRODUCT_IDS",
        "ANYTOOLAI_DEPLOYMENT_ACTIVATION_NAME",
        "ANYTOOLAI_DEPLOYMENT_ACTIVATION_MARKER",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANYTOOLAI_PORTAL_SERVICE_TOKEN", TOKEN)


class ManifestTestClient:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(self.app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, url, **kwargs)

        return asyncio.run(send())

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)


def client_for_app(**kwargs: Any) -> ManifestTestClient:
    return ManifestTestClient(create_app(database_url="", **kwargs))


def read(
    client: ManifestTestClient,
    *,
    token: str = TOKEN,
    url: str = URL,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return client.get(url, headers={"Authorization": f"Bearer {token}", **(headers or {})})


def test_complete_ordinary_output_uses_real_registry_and_independent_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANYTOOLAI_ENABLED_PRODUCT_IDS", "proposal_ai")
    client = client_for_app()
    response = read(client, headers={"X-Request-ID": "req_manifest"})
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert set(body) == {
        "schema_version",
        "tenant_id",
        "region",
        "manifest_version",
        "generated_at",
        "products",
        "usage_metrics",
    }
    assert {p["product_id"] for p in body["products"]} == PRODUCTS
    assert all(not p["enabled"] for p in body["products"])
    assert body["usage_metrics"] == [
        {
            "metric_key": "brief_decoder.test_analyses",
            "product_id": "brief_decoder",
            "unit": "analysis",
            "enabled": False,
        },
        {
            "metric_key": "proposal_ai.test_generations",
            "product_id": "proposal_ai",
            "unit": "generation",
            "enabled": False,
        },
    ]
    semantic = {k: v for k, v in body.items() if k not in {"generated_at", "manifest_version"}}
    canonical = json.dumps(semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert body["manifest_version"] == "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    assert body["manifest_version"] == (
        "sha256:478761c681d02330ed052aabe5e1b472dc1c2ee56d79a568a8009f4b4503a694"
    )
    assert datetime.fromisoformat(body["generated_at"]).utcoffset() == timedelta(0)
    assert response.headers["X-Request-ID"] == "req_manifest"
    assert response.headers["Cache-Control"] == "no-store"
    assert client.app.state.runtime.storage.session_factory is None


@pytest.mark.parametrize("authorization", [None, "", "Basic abc", "Bearer", f"Bearer {WRONG}"])
def test_configured_authentication_failure_challenges_without_leaking(
    authorization: str | None,
) -> None:
    client = client_for_app()
    headers = {"Authorization": authorization} if authorization is not None else {}
    response = client.get(URL, headers=headers)
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "service_unauthorized"
    assert TOKEN not in response.text and WRONG not in response.text


def test_duplicate_authorization_headers_are_rejected() -> None:
    response = client_for_app().get(
        URL,
        headers=[
            ("Authorization", f"Bearer {TOKEN}"),
            ("Authorization", f"Bearer {WRONG}"),
        ],
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize(
    "url",
    [
        PATH + "?tenant_id=other&region=ru",
        PATH + "?tenant_id=anytoolai&region=eu",
        URL + "&region=ru",
        URL + "&tenant_id=anytoolai",
    ],
)
def test_authenticated_wrong_or_ambiguous_scope_is_forbidden(url: str) -> None:
    response = read(client_for_app(), url=url)
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["error"]["code"] == "manifest_forbidden"
    assert "WWW-Authenticate" not in response.headers


@pytest.mark.parametrize(
    "principal",
    [
        PortalPrincipal("other", "ru"),
        PortalPrincipal("anytoolai", "eu"),
        PortalPrincipal("anytoolai", "ru", permissions=frozenset()),
        PortalPrincipal("anytoolai", "ru", caller="user"),
    ],
)
def test_principal_must_have_caller_scope_and_operation_authority(
    principal: PortalPrincipal,
) -> None:
    client = client_for_app()
    client.app.dependency_overrides[authenticate_portal] = lambda: principal
    assert read(client).status_code == HTTPStatus.FORBIDDEN


def test_rotation_accepts_two_tokens_then_revokes_previous_on_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS", PREVIOUS)
    client = client_for_app()
    assert read(client).status_code == HTTPStatus.OK
    assert read(client, token=PREVIOUS).status_code == HTTPStatus.OK
    monkeypatch.delenv("ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS")
    restarted = client_for_app()
    assert read(restarted).status_code == HTTPStatus.OK
    assert read(restarted, token=PREVIOUS).status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize(
    "foreign_env",
    [
        "ANYTOOLAI_DEMO_ACCESS_CODE",
        "ANYTOOLAI_ATOM_LAB_ACCESS_CODE",
        "ANYTOOLAI_LIVE_CANARY_TOKEN",
        "ANYTOOLAI_KERNEL_SERVICE_TOKEN",
    ],
)
def test_other_credentials_do_not_authorize_manifest(
    monkeypatch: pytest.MonkeyPatch, foreign_env: str
) -> None:
    monkeypatch.setenv(foreign_env, WRONG)
    client = client_for_app()
    assert read(client, token=WRONG).status_code == HTTPStatus.UNAUTHORIZED
    assert (
        client.get(URL, headers={"X-Atom-Lab-Access-Code": WRONG}).status_code
        == HTTPStatus.UNAUTHORIZED
    )


@pytest.mark.parametrize(
    "origin", ["https://portal.test", "chrome-extension://" + "a" * 32, "null", ""]
)
@pytest.mark.parametrize("method", ["GET", "OPTIONS"])
def test_browser_requests_are_rejected_without_any_cors_headers(
    monkeypatch: pytest.MonkeyPatch, origin: str, method: str
) -> None:
    monkeypatch.setenv("ANYTOOLAI_API_CORS_ORIGINS", "https://portal.test")
    response = client_for_app().request(
        method,
        URL,
        headers={
            "Origin": origin,
            "Authorization": f"Bearer {TOKEN}",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert not any(h.startswith("access-control-") for h in response.headers)
    assert response.headers["Cache-Control"] == "no-store"


def test_missing_receiver_config_disables_only_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANYTOOLAI_PORTAL_SERVICE_TOKEN")
    client = client_for_app()
    assert read(client).status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert client.get("/v1/products/kernel_demo/runtime-config").status_code == HTTPStatus.OK
    # The guest route reaches its ordinary storage gate, independent of manifest credentials.
    response = client.post("/v1/identity/guest", json={})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"]["code"] == "runtime_storage_unavailable"


@pytest.mark.parametrize(
    "value", ["", "short", "a" * 257, "a" * 31 + " ", "a" * 32 + "\n", "т" * 32]
)
def test_explicit_malformed_secrets_fail_startup_without_exposure(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("ANYTOOLAI_PORTAL_SERVICE_TOKEN", value)
    with pytest.raises(ValueError) as error:
        create_app(database_url="")
    assert "input_value=" not in str(error.value)
    assert TOKEN not in str(error.value)


def test_rotation_configuration_requires_distinct_current_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS", TOKEN)
    with pytest.raises(ValueError, match="must differ"):
        Settings.from_env()
    monkeypatch.delenv("ANYTOOLAI_PORTAL_SERVICE_TOKEN")
    with pytest.raises(ValueError, match="requires a current"):
        Settings.from_env()
    monkeypatch.setenv("ANYTOOLAI_PORTAL_SERVICE_TOKEN", TOKEN)
    monkeypatch.setenv("ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS", "bad previous token")
    with pytest.raises(ValueError):
        Settings.from_env()
    settings = Settings(portal_service_token=TOKEN, portal_service_token_previous=PREVIOUS)
    assert TOKEN not in repr(settings) and PREVIOUS not in repr(settings)
    assert TOKEN not in settings.model_dump_json()


@pytest.mark.parametrize(
    "env,value",
    [
        ("ANYTOOLAI_TENANT_ID", "other"),
        ("ANYTOOLAI_REGION", "eu"),
        ("ANYTOOLAI_REGION", ""),
        ("ANYTOOLAI_TENANT_ID", " anytoolai "),
    ],
)
def test_unregistered_or_malformed_trusted_scope_fails_startup(
    monkeypatch: pytest.MonkeyPatch, env: str, value: str
) -> None:
    monkeypatch.setenv(env, value)
    with pytest.raises(ValueError):
        create_app(database_url="")


def test_configured_future_zone_works_without_ru_branch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "kernel"
    shutil.copytree(CONFIG_ROOT, root)
    (root / "regions.yaml").write_text(
        "default_region: eu\nregions:\n  - region: eu\n    display_name: Test EU\n"
    )
    (root / "default_tenant.yaml").write_text("tenant_id: testtenant\ndisplay_name: Test tenant\n")
    monkeypatch.setenv("ANYTOOLAI_REGION", "eu")
    monkeypatch.setenv("ANYTOOLAI_TENANT_ID", "testtenant")
    client = client_for_app(config_root=root)
    response = read(client, url=PATH + "?tenant_id=testtenant&region=eu")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["region"] == "eu"
    assert response.json()["tenant_id"] == "testtenant"
    assert read(client).status_code == HTTPStatus.FORBIDDEN
    assert client.app.state.settings.default_region == "eu"


def test_activation_gate_also_protects_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "active"
    monkeypatch.setenv("ANYTOOLAI_DEPLOYMENT_ACTIVATION_NAME", "candidate")
    monkeypatch.setenv("ANYTOOLAI_DEPLOYMENT_ACTIVATION_MARKER", str(marker))
    client = client_for_app()
    response = read(client)
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"]["code"] == "deployment_not_active"
    assert client.get("/v1/products/kernel_demo/runtime-config").status_code == HTTPStatus.OK
    marker.write_text("candidate\n")
    assert read(client).status_code == HTTPStatus.OK


def test_producer_failure_is_safe_and_can_recover() -> None:
    client = client_for_app()

    def broken_registry():
        raise RuntimeError("injected registry failure")

    client.app.dependency_overrides[get_config_registry] = broken_registry
    response = read(client, headers={"X-Request-ID": "req_failure"})
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.json()["error"]["code"] == "internal_server_error"
    assert response.headers["X-Request-ID"] == "req_failure"
    assert response.headers["Cache-Control"] == "no-store"
    assert "injected" not in response.text and TOKEN not in response.text
    assert "products" not in response.json()
    client.app.dependency_overrides.clear()
    assert read(client).status_code == HTTPStatus.OK


def test_retries_concurrency_and_new_app_preserve_version_without_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(database_url="")
    forbidden_provider = AsyncMock(side_effect=AssertionError("manifest must not call providers"))
    monkeypatch.setattr(ProviderGateway, "request", forbidden_provider)
    forbidden_storage = Mock(side_effect=AssertionError("manifest must not access storage"))
    app.state.runtime = replace(
        app.state.runtime,
        storage=bootstrap.RuntimeStorageDependencies(
            session_factory=forbidden_storage,
        ),
    )

    async def concurrent_reads():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            return await asyncio.gather(
                *(client.get(URL, headers={"Authorization": f"Bearer {TOKEN}"}) for _ in range(12))
            )

    responses = asyncio.run(concurrent_reads())
    assert all(r.status_code == HTTPStatus.OK for r in responses)
    versions = {r.json()["manifest_version"] for r in responses}
    assert versions == {read(client_for_app()).json()["manifest_version"]}
    forbidden_storage.assert_not_called()
    forbidden_provider.assert_not_called()


class TemporaryBundle(ProductBundle):
    bundle_id = "temporary_fixture"

    def __init__(self, root: Path) -> None:
        self.root = root

    def config_roots(self) -> list[Path]:
        return [self.root]


def test_factory_explicit_temporary_composition_uses_loader_without_mutating_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "kernel"
    shutil.copytree(CONFIG_ROOT, root)
    product_root = tmp_path / "fixture_product"
    shutil.copytree(Path(__file__).parent / "fixtures" / "fixture_product", product_root)
    product_file = product_root / "product.yaml"
    product = yaml.safe_load(product_file.read_text())
    product["commercial_admission_enabled"] = True
    product["usage_metrics"] = [{"metric_key": "fixture.test", "unit": "test", "enabled": True}]
    product_file.write_text(yaml.safe_dump(product))
    bundles = [TemporaryBundle(product_root)]
    defaults = bootstrap.DEFAULT_PRODUCT_BUNDLES
    build_runtime = Mock(wraps=main.build_runtime)
    monkeypatch.setattr(main, "build_runtime", build_runtime)
    explicit = client_for_app(config_root=root, bundles=bundles)
    assert build_runtime.call_args.kwargs["bundles"] is bundles
    assert explicit.app.state.runtime.loaded_bundles == [
        "platform_actions",
        "kernel_demo",
        "temporary_fixture",
    ]
    assert read(explicit).json()["products"] == [
        {"product_id": "fixture_product", "enabled": True},
        {"product_id": "kernel_demo", "enabled": False},
    ]
    assert read(explicit).json()["usage_metrics"][0]["metric_key"] == "fixture.test"
    assert set(client_for_app(bundles=[]).app.state.runtime.config_registry.products) == {
        "kernel_demo"
    }
    for client in (client_for_app(), client_for_app(bundles=None)):
        assert set(client.app.state.runtime.config_registry.products) == PRODUCTS
    assert bootstrap.DEFAULT_PRODUCT_BUNDLES is defaults
    assert bundles[0].root == product_root
    product["usage_metrics"][0]["enabled"] = "false"
    product_file.write_text(yaml.safe_dump(product))
    with pytest.raises(RegistryLoadError):
        create_app(config_root=root, database_url="", bundles=bundles)


def test_guest_identity_uses_trusted_ru_scope_without_manifest_credentials(
    monkeypatch: pytest.MonkeyPatch, session_factory: SessionFactory
) -> None:
    monkeypatch.delenv("ANYTOOLAI_PORTAL_SERVICE_TOKEN")
    client = client_for_app()
    client.app.state.runtime = replace(
        client.app.state.runtime,
        storage=bootstrap.RuntimeStorageDependencies(session_factory=session_factory),
    )
    response = client.post("/v1/identity/guest")
    assert response.status_code == HTTPStatus.OK
    guest_id = response.json()["guest_id"]
    with transaction_boundary(session_factory) as session:
        repository = GuestIdentityRepository(session)
        assert repository.get(guest_id, tenant_id="anytoolai", region="ru") is not None
        assert repository.get(guest_id, tenant_id="anytoolai", region="default") is None
    assert read(client).status_code == HTTPStatus.SERVICE_UNAVAILABLE


def test_openapi_declares_named_models_and_bearer_auth() -> None:
    schema = create_app(database_url="").openapi()
    operation = schema["paths"][PATH]["get"]
    assert operation["security"] == [{"PortalServiceBearer": []}]
    assert schema["components"]["securitySchemes"]["PortalServiceBearer"]["scheme"] == "bearer"
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/CapabilityManifestResponse"
    )
    assert TOKEN not in json.dumps(schema)


@pytest.mark.parametrize("url", [PATH + "?tenant_id=anytoolai", PATH + "?region=ru"])
def test_query_validation_error_matches_openapi_error_contract(url: str) -> None:
    client = client_for_app()
    response = read(client, url=url, headers={"X-Request-ID": "req_manifest_validation"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    ErrorResponse.model_validate(response.json())
    assert response.json()["error"]["code"] == "request_validation_failed"
    assert response.headers["X-Request-ID"] == "req_manifest_validation"
    assert response.headers["Cache-Control"] == "no-store"
    operation = client.app.openapi()["paths"][PATH]["get"]
    assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }


def test_compose_receiver_secrets_are_api_only_and_prod_keeps_loopback() -> None:
    base = (CONFIG_ROOT.parents[1] / "infra/compose/docker-compose.yml").read_text()
    services = yaml.safe_load(base)["services"]
    for name in ("ANYTOOLAI_PORTAL_SERVICE_TOKEN", "ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS"):
        assert name in services["platform-api"]["environment"]
        assert all(
            name not in service.get("environment", {})
            for key, service in services.items()
            if key != "platform-api"
        )
    prod = (CONFIG_ROOT.parents[1] / "infra/compose/docker-compose.prod.yml").read_text()
    assert '"127.0.0.1:${ANYTOOLAI_PROD_API_PORT:-8000}:8000"' in prod
