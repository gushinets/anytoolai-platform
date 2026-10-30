"""Private child process of manifest-conformance; always uses the real API."""

# Import the application only after main establishes the synthetic receiver settings.
# ruff: noqa: PLC0415

from __future__ import annotations

import argparse
import builtins
import io
import json
import logging
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

READY_TIMEOUT_SECONDS = 30
SHUTDOWN_TIMEOUT_SECONDS = 5
POLL_SECONDS = 0.05
EXPECTED_BUNDLE_PRODUCT_ROOTS = 5


def announce(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True), flush=True)


@contextmanager
def configured_app(scenario: str) -> Iterator[Any]:
    import yaml
    from anytoolai_platform_api.bootstrap import DEFAULT_PRODUCT_BUNDLES
    from anytoolai_platform_api.main import create_app
    from anytoolai_platform_core.bootstrap.registry import default_config_root
    from anytoolai_platform_sdk import ProductBundle

    class CopiedBundle(ProductBundle):
        def __init__(self, bundle_id: str, roots: list[Path]) -> None:
            self.bundle_id = bundle_id
            self.roots = roots

        def config_roots(self) -> list[Path]:
            return self.roots

    defaults = DEFAULT_PRODUCT_BUNDLES
    ordinary = create_app(database_url="")
    default_registry = ordinary.state.runtime.config_registry
    if scenario == "ordinary":
        yield ordinary
        return
    with tempfile.TemporaryDirectory(prefix="any711-producer-") as directory:
        root = Path(directory)
        config_root = root / "kernel"
        shutil.copytree(default_config_root(), config_root)
        bundles = []
        product_roots: list[Path] = []
        for bundle in defaults:
            roots = []
            for source in bundle.config_roots():
                destination = root / "bundles" / bundle.bundle_id / source.name
                shutil.copytree(source, destination)
                roots.append(destination)
                product_roots.append(destination)
            bundles.append(CopiedBundle(bundle.bundle_id, roots))
        assert len(product_roots) == EXPECTED_BUNDLE_PRODUCT_ROOTS
        for product_root in product_roots:
            file = product_root / "product.yaml"
            definition = yaml.safe_load(file.read_text(encoding="utf-8"))
            if definition["product_id"] in {"proposal_ai", "brief_decoder"}:
                definition["commercial_admission_enabled"] = True
                for metric in definition["usage_metrics"]:
                    metric["enabled"] = not (
                        scenario == "material"
                        and metric["metric_key"] == "proposal_ai.test_generations"
                    )
                file.write_text(yaml.safe_dump(definition, sort_keys=False), encoding="utf-8")
        if scenario == "reordered":
            for bundle in bundles:
                bundle.roots.reverse()
        if scenario == "invalid":
            file = next(
                root / "product.yaml" for root in product_roots if root.name == "proposal_ai"
            )
            definition = yaml.safe_load(file.read_text(encoding="utf-8"))
            definition["usage_metrics"][0]["enabled"] = "true"
            file.write_text(yaml.safe_dump(definition), encoding="utf-8")
            from anytoolai_platform_core.config.errors import RegistryLoadError

            try:
                create_app(config_root=config_root, database_url="", bundles=bundles)
            except RegistryLoadError:
                announce({"invalid_config_refused": True})
                yield None
                return
            raise AssertionError("invalid producer configuration was accepted")
        application = create_app(config_root=config_root, database_url="", bundles=bundles)
        for following in (create_app(database_url=""), create_app(database_url="", bundles=None)):
            assert following.state.runtime.config_registry.products == default_registry.products
            assert following.state.runtime.loaded_bundles == ordinary.state.runtime.loaded_bundles
        assert DEFAULT_PRODUCT_BUNDLES is defaults
        yield application


def serve(scenario: str) -> int:  # noqa: PLR0915 -- one bounded test-resource lifecycle
    import uvicorn
    from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies
    from anytoolai_platform_api.dependencies import get_config_registry
    from anytoolai_platform_core.products.capabilities import project_capability_manifest
    from anytoolai_platform_core.providers.gateway import ProviderGateway
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session

    with ExitStack() as stack:
        guards = {
            "provider": AsyncMock(side_effect=AssertionError("provider call forbidden")),
            "storage": Mock(side_effect=AssertionError("storage access forbidden")),
            "engine": Mock(side_effect=AssertionError("database connection forbidden")),
        }
        stack.enter_context(patch.object(ProviderGateway, "request", guards["provider"]))
        stack.enter_context(patch.object(Engine, "connect", guards["engine"]))
        for method in ("execute", "add", "flush", "commit"):
            guard = Mock(side_effect=AssertionError("database operation forbidden"))
            guards[f"session_{method}"] = guard
            stack.enter_context(patch.object(Session, method, guard))
        app = stack.enter_context(configured_app(scenario))
        # Silence request logs; the protocol emits only bounded, nonsecret evidence.
        logging.disable(logging.CRITICAL)
        if app is None:
            return 0
        registry = app.state.runtime.config_registry
        assert app.state.runtime.storage.session_factory is None
        app.state.runtime = replace(
            app.state.runtime,
            storage=RuntimeStorageDependencies(session_factory=guards["storage"]),
        )
        projection = project_capability_manifest(registry, tenant_id="anytoolai", region="ru")
        failures = {"remaining": 0, "observed": 0}
        lock = threading.Lock()

        def registry_with_injected_failure() -> Any:
            with lock:
                if failures["remaining"]:
                    failures["remaining"] -= 1
                    failures["observed"] += 1
                    raise RuntimeError("synthetic producer failure")
            return registry

        # This substitutes only a failing resource dependency, never the endpoint,
        # transport, projection or response model. Healthy requests use the registry.
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            config = uvicorn.Config(
                app,
                log_config=None,
                access_log=False,
                lifespan="on",
                timeout_graceful_shutdown=SHUTDOWN_TIMEOUT_SECONDS,
            )
            server = uvicorn.Server(config)
            thread = threading.Thread(
                target=server.run, kwargs={"sockets": [listener]}, daemon=True
            )
            thread.start()
            try:
                deadline = time.monotonic() + READY_TIMEOUT_SECONDS
                while not server.started:
                    if not thread.is_alive() or time.monotonic() >= deadline:
                        raise RuntimeError("real Kernel startup did not become ready")
                    time.sleep(POLL_SECONDS)
                announce(
                    {
                        "url": f"http://127.0.0.1:{listener.getsockname()[1]}",
                        "scenario": scenario,
                        "inventory": asdict(projection),
                        "manifest_version": projection.manifest_version,
                        "default_composition_preserved": True,
                    }
                )
                for line in sys.stdin:
                    command = json.loads(line)
                    if command["action"] == "fail":
                        with lock:
                            failures["remaining"] = command["count"]
                        app.dependency_overrides[get_config_registry] = (
                            registry_with_injected_failure
                        )
                        announce({"fault_armed": command["count"]})
                    elif command["action"] == "stats":
                        counts = {key: guard.call_count for key, guard in guards.items()}
                        assert not any(counts.values()), "manifest request attempted a side effect"
                        announce(
                            {"side_effect_calls": counts, "injected_failures": failures["observed"]}
                        )
                    elif command["action"] == "stop":
                        break
                    else:
                        raise ValueError("unknown producer control action")
            finally:
                server.should_exit = True
                thread.join(timeout=SHUTDOWN_TIMEOUT_SECONDS * 2)
                if thread.is_alive():
                    raise RuntimeError("real Kernel shutdown deadline exceeded")
                assert not any(guard.call_count for guard in guards.values())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=("ordinary", "test", "reordered", "material", "invalid"),
        required=True,
    )
    args = parser.parse_args()
    # This child is started with an allowlist before importing any application.
    os.environ["ANYTOOLAI_PORTAL_SERVICE_TOKEN"] = os.environ["ANY711_CONFORMANCE_TOKEN"]
    previous = os.environ.get("ANY711_PREVIOUS_TOKEN")
    if previous:
        os.environ["ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS"] = previous
    original_open, original_io_open = builtins.open, io.open

    def guard_open(original: Any, file: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(file, (str, bytes, os.PathLike)):
            name = os.fsdecode(file).replace("\\", "/").rsplit("/", 1)[-1]
            if name == ".env" or name.startswith(".env."):
                raise AssertionError("producer dotenv content read attempted")
        return original(file, *args, **kwargs)

    with (
        patch.object(builtins, "open", lambda *a, **kw: guard_open(original_open, *a, **kw)),
        patch.object(io, "open", lambda *a, **kw: guard_open(original_io_open, *a, **kw)),
    ):
        return serve(args.scenario)


if __name__ == "__main__":
    raise SystemExit(main())
