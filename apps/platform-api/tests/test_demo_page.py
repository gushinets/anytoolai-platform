from __future__ import annotations

import asyncio
from http import HTTPStatus
from pathlib import Path

import httpx
from anytoolai_platform_api.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"


async def _get(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=create_app(config_root=CONFIG_ROOT))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(path)


def test_demo_page_exposes_accessible_russian_workflow_surface() -> None:
    response = asyncio.run(_get("/demo"))

    assert response.status_code == HTTPStatus.OK
    assert response.headers["content-type"].startswith("text/html")
    assert "charset=utf-8" in response.headers["content-type"].lower()

    html = response.text
    assert "AnytoolAI — демонстрация рабочих AI-цепочек" in html
    assert '<main id="demo-app"' in html
    assert '<label for="access-code">' in html
    assert 'type="password"' in html
    assert '<section id="workflow-section"' in html
    assert 'name="demo-workflow"' in html
    assert 'for="source-text"' in html
    assert 'id="source-text" maxlength=' not in html
    assert 'id="character-count"' in html
    assert 'id="status-message"' in html
    assert 'aria-live="polite"' in html
    assert 'id="result-panel"' in html
    assert '<details id="technical-proof"' in html
    assert 'id="technical-proof-list"' in html
    assert "Live workflow proof" not in html
    assert ">Live<" not in html
    assert ">Safe<" not in html
    assert "AnytoolAI Platform" not in html


def test_demo_assets_are_same_origin_and_have_expected_content_types() -> None:
    page = asyncio.run(_get("/demo"))
    css = asyncio.run(_get("/demo/demo.css"))
    javascript = asyncio.run(_get("/demo/demo.js"))

    assert '<link rel="stylesheet" href="/demo/demo.css">' in page.text
    assert '<script src="/demo/demo.js" defer></script>' in page.text
    assert css.status_code == HTTPStatus.OK
    assert css.headers["content-type"].startswith("text/css")
    assert javascript.status_code == HTTPStatus.OK
    assert "javascript" in javascript.headers["content-type"]


def test_demo_javascript_keeps_secrets_ephemeral_and_renders_server_data_safely() -> None:
    response = asyncio.run(_get("/demo/demo.js"))

    assert response.status_code == HTTPStatus.OK
    source = response.text
    assert "innerHTML" not in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "textContent" in source
    assert '"X-Demo-Access-Code"' in source
    assert 'fetchJsonBeforeDeadline("/v1/demo/runs"' in source
    assert "`/v1/scenario-sessions/${" in source
    assert "`/v1/results/${" in source
    assert "POLL_INTERVAL_MS = 2000" in source
    assert "RUN_TIMEOUT_MS = 90000" in source
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in source
    assert '"summary": "Краткий итог"' in source
    assert '"call_to_action": "Следующий шаг"' in source
    assert "Технический ID: ${error.scenario_session_id}" in source


def test_demo_styles_cover_mobile_focus_and_reduced_motion() -> None:
    response = asyncio.run(_get("/demo/demo.css"))

    assert response.status_code == HTTPStatus.OK
    css = response.text
    assert "@media (max-width: 600px)" in css
    assert ":focus-visible" in css
    assert ".workflow-card:has(input:focus-visible)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
