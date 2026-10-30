"""Kernel-owned, test-only Portal bootstrap. No Portal imports before isolation."""

# Application/dependency imports must stay behind the pre-import isolation boundary.
# ruff: noqa: PLC0415

from __future__ import annotations

import argparse
import asyncio
import builtins
import importlib.util
import io
import json
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch

LBX_FIELDS = (
    "lbx_base_url",
    "lbx_server_username",
    "lbx_server_password",
    "lbx_widget_signing_secret",
    "lbx_seller_organization_id",
    "lbx_webhook_auth_header",
    "lbx_webhook_auth_value",
)
CONCURRENT_READS = 8
DEFAULT_DISABLED_DIGEST = "sha256:478761c681d02330ed052aabe5e1b472dc1c2ee56d79a568a8009f4b4503a694"


def assert_safe_settings(configuration: Any) -> None:
    assert configuration.billing_worker_enabled is False
    assert configuration.lbx_webhook_enabled is False
    for field in LBX_FIELDS:
        value = getattr(configuration, field)
        assert (value.get_secret_value() if hasattr(value, "get_secret_value") else value) == ""
    assert configuration.sentry_dsn == configuration.sentry_release == ""
    assert (
        configuration.smtp_host == configuration.smtp_username == configuration.smtp_password == ""
    )


@contextmanager
def isolated_portal(portal_root: Path) -> Iterator[dict[str, Any]]:
    """Keep both dotenv patches active through imports, explicit config and pytest.

    The read guards deliberately fail, rather than silently discard dotenv data.
    Validation still runs through the original BaseSettings constructor.
    """
    if "app.core.settings" in sys.modules:
        raise RuntimeError("Portal isolation must precede the first settings import")
    sys.path[:0] = [str(portal_root / "apps/api"), str(portal_root)]
    spec = importlib.util.spec_from_file_location(
        "any711_test_settings", portal_root / "apps/api/tests/support/settings.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Portal stdlib test-setting helper is unavailable")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    overrides = {field.upper(): "" for field in LBX_FIELDS}
    overrides.update(
        BILLING_WORKER_ENABLED="false",
        LBX_WEBHOOK_ENABLED="false",
        KERNEL_BASE_URL="",
        KERNEL_SERVICE_TOKEN="",
        KERNEL_MOCK_ENABLED="false",
        SMTP_HOST="",
        SMTP_USERNAME="",
        SMTP_PASSWORD="",
    )
    helper.configure_api_test_environment(**overrides)

    import dotenv
    from pydantic_settings import BaseSettings

    original_init = BaseSettings.__init__
    evidence: dict[str, Any] = {"dotenv_calls": [], "env_file_arguments": []}

    def no_dotenv(*args: Any, **kwargs: Any) -> bool:
        evidence["dotenv_calls"].append(str(args[0]) if args else None)
        return False

    def without_env_file(self: Any, *args: Any, **kwargs: Any) -> None:
        evidence["env_file_arguments"].append(kwargs.get("_env_file"))
        kwargs["_env_file"] = None
        original_init(self, *args, **kwargs)

    def guard_open(original: Any, file: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(file, (str, bytes, os.PathLike)):
            name = os.fsdecode(file).replace("\\", "/").rsplit("/", 1)[-1]
            if name == ".env" or name.startswith(".env."):
                raise AssertionError("dotenv content read attempted")
        return original(file, *args, **kwargs)

    original_open, original_io_open = builtins.open, io.open
    with ExitStack() as stack:
        stack.enter_context(patch.object(dotenv, "load_dotenv", no_dotenv))
        stack.enter_context(patch.object(BaseSettings, "__init__", without_env_file))
        stack.enter_context(
            patch.object(builtins, "open", lambda *a, **kw: guard_open(original_open, *a, **kw))
        )
        stack.enter_context(
            patch.object(io, "open", lambda *a, **kw: guard_open(original_io_open, *a, **kw))
        )
        from app.core.settings import settings

        assert_safe_settings(settings)
        yield evidence


def isolation_regression(portal_root: Path) -> None:
    """Redirect only the loader's settings-file resolution to a synthetic tree.

    No developer dotenv is read, modified or renamed. Read spies also act as
    regression tripwires if either suppression patch is removed.
    """
    from pydantic_settings.sources import DotEnvSettingsSource

    with tempfile.TemporaryDirectory(prefix="any711-poison-") as directory:
        root = Path(directory)
        poison = root / ".env"
        poison.write_text(
            "BILLING_WORKER_ENABLED=true\nLBX_WEBHOOK_ENABLED=true\n"
            "LBX_BASE_URL=https://poison.invalid\nLBX_SERVER_USERNAME=poison\n"
            "LBX_SERVER_PASSWORD=poison\nSMTP_HOST=poison.invalid\n"
            "SENTRY_RELEASE=poison\n",
            encoding="utf-8",
        )
        settings_file = portal_root / "apps/api/app/core/settings.py"
        original_resolve = Path.resolve
        original_read = DotEnvSettingsSource._read_env_files
        env_files: list[Any] = []

        def resolve(path: Path, *args: Any, **kwargs: Any) -> Path:
            if path == settings_file:
                return root / "settings.py"
            return original_resolve(path, *args, **kwargs)

        def read(source: Any) -> dict[str, Any]:
            env_files.append(source.env_file)
            assert source.env_file is None, "Pydantic dotenv loading was not disabled"
            return original_read(source)

        with (
            patch.object(Path, "resolve", resolve),
            patch.object(DotEnvSettingsSource, "_read_env_files", read),
            isolated_portal(portal_root) as evidence,
        ):
            from app.core.settings import Settings, settings
            from apps.api.tests.support.kernel import kernel_settings

            explicit = kernel_settings(kernel_base_url="", kernel_service_token="")
            assert_safe_settings(settings)
            assert_safe_settings(explicit)
            assert evidence["dotenv_calls"] == [str(poison)]
            assert str(poison) in evidence["env_file_arguments"]
            assert env_files and all(value is None for value in env_files)
            # A later explicit path must also be suppressed by the original wrapper.
            assert_safe_settings(Settings(_env_file=poison))
            # Exercise the spies themselves: both actual readers must be caught.
            import dotenv

            for reader in (poison.read_text, lambda: dotenv.dotenv_values(poison)):
                try:
                    reader()
                except AssertionError as error:
                    assert str(error) == "dotenv content read attempted"
                else:
                    raise AssertionError("dotenv read spy did not fire")
            asyncio.run(check_no_lbx(explicit))
    print("PORTAL_DOTENV_ISOLATION=PASS", flush=True)


async def check_no_lbx(configuration: Any) -> None:
    from app.composition.sources import source_resources

    async with source_resources(configuration) as sources:
        assert sources.lbx is None


async def probe(base_url: str, scenario: str, expected_error: str | None) -> dict[str, Any]:
    from app.composition.sources import source_resources
    from app.domains.catalog.contracts import SourceProvenance
    from app.integrations.kernel.client import KernelError
    from apps.api.tests.support.kernel import (
        EXPECTED_DIGEST,
        independent_digest,
        kernel_settings,
        manifest_fixture,
    )

    configuration = kernel_settings(
        kernel_base_url=base_url,
        kernel_service_token=os.environ["ANY711_CONFORMANCE_TOKEN"],
        kernel_mock_enabled=False,
        kernel_max_retries=1,
    )
    assert_safe_settings(configuration)
    expected = manifest_fixture()
    if scenario == "ordinary":
        for item in (*expected["products"], *expected["usage_metrics"]):
            item["enabled"] = False
        assert independent_digest(expected) == DEFAULT_DISABLED_DIGEST
    elif scenario == "material":
        next(
            item
            for item in expected["usage_metrics"]
            if item["metric_key"] == "proposal_ai.test_generations"
        )["enabled"] = False
    else:
        assert independent_digest(expected) == EXPECTED_DIGEST
    digest = independent_digest(expected)

    async with source_resources(configuration) as sources:
        assert sources.lbx is None

        async def fetch() -> Any:
            async with sources.preflight.operation() as budget:
                return await sources.require_kernel().fetch_manifest(budget=budget)

        try:
            first = await fetch()
        except KernelError as error:
            assert expected_error == error.code, "unexpected typed consumer error"
            return {"error": error.code}
        assert expected_error is None, "consumer unexpectedly accepted a failed request"
        second = await fetch()
        concurrent = await asyncio.gather(*(fetch() for _ in range(CONCURRENT_READS)))
        for manifest in (first, second, *concurrent):
            assert manifest.provenance is SourceProvenance.CONFIGURED_SOURCE
            assert (manifest.tenant_id, manifest.region) == ("anytoolai", "ru")
            assert manifest.manifest_version == digest
            products = sorted(
                (asdict(item) for item in manifest.products), key=lambda p: p["product_id"]
            )
            metrics = sorted(
                (asdict(item) for item in manifest.usage_metrics), key=lambda m: m["metric_key"]
            )
            assert products == sorted(expected["products"], key=lambda p: p["product_id"])
            assert metrics == sorted(expected["usage_metrics"], key=lambda m: m["metric_key"])
            assert manifest.generated_at.utcoffset() is not None
        assert first.generated_at != second.generated_at
        assert sources.preflight.active_count == sources.preflight.waiting_count == 0
    assert sources.preflight.closed
    return {"manifest_version": digest, "products": products, "usage_metrics": metrics}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portal-root", required=True, type=Path)
    parser.add_argument("--mode", choices=("probe", "regressions", "isolation"), default="probe")
    parser.add_argument("--kernel-base-url")
    parser.add_argument("--scenario", choices=("ordinary", "test", "material"), default="test")
    parser.add_argument("--expected-error")
    args = parser.parse_args()
    if args.mode == "isolation":
        isolation_regression(args.portal_root)
        return 0
    with isolated_portal(args.portal_root):
        if args.mode == "regressions":
            import pytest

            return pytest.main(
                [
                    "-o",
                    "addopts=",
                    "-p",
                    "anyio.pytest_plugin",
                    "-p",
                    "no:cacheprovider",
                    "-q",
                    str(args.portal_root / "apps/api/tests/test_kernel_manifest_client.py"),
                    str(args.portal_root / "apps/api/tests/test_source_composition.py"),
                ]
            )
        print(
            json.dumps(asyncio.run(probe(args.kernel_base_url, args.scenario, args.expected_error)))
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
