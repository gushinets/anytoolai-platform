"""Focused coverage for the platform-worker console entrypoint (`main.py`).

`build_worker`/`WorkerSettings.from_env` are monkeypatched throughout -- these tests are
about the entrypoint's own control flow (signal registration, dispose-on-exit), not the
worker's runtime behavior, which is covered elsewhere.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from anytoolai_platform_worker import main as worker_main


class _FakeWorker:
    def __init__(self) -> None:
        self.disposed = False
        self.request_shutdown_calls = 0

    def request_shutdown(self) -> None:
        self.request_shutdown_calls += 1

    async def run_forever(self) -> None:
        return None

    def dispose(self) -> None:
        self.disposed = True


class _NoSignalSupportLoop:
    """Stands in for Windows' `ProactorEventLoop`, which does not implement this at all."""

    def add_signal_handler(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError


def test_register_sigterm_handler_swallows_not_implemented_error() -> None:
    # Must not raise -- this is exactly the path Windows takes today.
    worker_main._register_sigterm_handler(_NoSignalSupportLoop(), lambda: None)


def test_register_sigterm_handler_registers_callback_on_supported_loops() -> None:
    registered: list[tuple[Any, Any]] = []

    class _SupportedLoop:
        def add_signal_handler(self, sig: Any, callback: Any) -> None:
            registered.append((sig, callback))

    callback = lambda: None  # noqa: E731
    worker_main._register_sigterm_handler(_SupportedLoop(), callback)

    assert len(registered) == 1
    assert registered[0][1] is callback


def test_run_disposes_worker_even_when_sigterm_registration_is_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_worker = _FakeWorker()
    monkeypatch.setattr(worker_main, "build_worker", lambda **_kwargs: fake_worker)
    monkeypatch.setattr(
        worker_main.WorkerSettings,
        "from_env",
        classmethod(lambda _cls: worker_main.WorkerSettings(database_url="sqlite://unused")),
    )
    monkeypatch.setattr(asyncio, "get_running_loop", _NoSignalSupportLoop)

    asyncio.run(worker_main.run())

    assert fake_worker.disposed


def test_run_disposes_worker_when_run_forever_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_worker = _FakeWorker()

    async def _boom() -> None:
        raise RuntimeError("boom")

    fake_worker.run_forever = _boom  # type: ignore[method-assign]
    monkeypatch.setattr(worker_main, "build_worker", lambda **_kwargs: fake_worker)
    monkeypatch.setattr(
        worker_main.WorkerSettings,
        "from_env",
        classmethod(lambda _cls: worker_main.WorkerSettings(database_url="sqlite://unused")),
    )
    monkeypatch.setattr(asyncio, "get_running_loop", _NoSignalSupportLoop)

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(worker_main.run())

    assert fake_worker.disposed
