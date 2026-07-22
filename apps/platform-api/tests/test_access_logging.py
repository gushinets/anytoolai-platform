from __future__ import annotations

import json
import socket
import threading
from http import HTTPStatus
from pathlib import Path
from time import monotonic, sleep
from urllib.request import Request, urlopen

import uvicorn
from fastapi import FastAPI

REPO_ROOT = Path(__file__).resolve().parents[3]
API_DOCKERFILE = REPO_ROOT / "infra" / "docker" / "platform-api.Dockerfile"


def _platform_api_command() -> list[str]:
    command_line = next(
        line
        for line in API_DOCKERFILE.read_text(encoding="utf-8").splitlines()
        if line.startswith("CMD ")
    )
    command = json.loads(command_line.removeprefix("CMD "))
    assert isinstance(command, list)
    return command


def test_platform_api_disables_real_uvicorn_access_logger_for_handoff_urls(capfd) -> None:
    command = _platform_api_command()
    assert "--no-access-log" in command

    token = "hnd_real_bearer_token_must_not_be_logged"
    app = FastAPI()

    @app.api_route("/v1/handoffs/{handoff_token}", methods=["GET"])
    @app.api_route("/v1/handoffs/{handoff_token}/accept", methods=["POST"])
    @app.api_route("/v1/handoffs/{handoff_token}/decline", methods=["POST"])
    async def handoff_route(handoff_token: str) -> dict[str, str]:
        return {"status": "ok"}

    server_socket = socket.socket()
    server_socket.bind(("127.0.0.1", 0))
    port = server_socket.getsockname()[1]
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        access_log="--no-access-log" not in command,
        log_level="info",
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [server_socket]},
        daemon=True,
    )
    thread.start()

    try:
        deadline = monotonic() + 5
        while not server.started and monotonic() < deadline:
            sleep(0.01)
        assert server.started

        for method, path in (
            ("GET", f"/v1/handoffs/{token}"),
            ("POST", f"/v1/handoffs/{token}/accept"),
            ("POST", f"/v1/handoffs/{token}/decline"),
        ):
            request = Request(f"http://127.0.0.1:{port}{path}", method=method)
            with urlopen(request, timeout=5) as response:
                assert response.status == HTTPStatus.OK
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        server_socket.close()

    assert not thread.is_alive()
    captured = capfd.readouterr()
    emitted = captured.out + captured.err

    assert token not in emitted
    assert "/v1/handoffs/" not in emitted
