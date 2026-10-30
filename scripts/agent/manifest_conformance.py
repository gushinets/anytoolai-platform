"""Bounded local real-Kernel / unchanged-Portal HTTP conformance (ANY-711)."""

from __future__ import annotations

import argparse
import json
import os
import queue
import secrets
import subprocess
import sys
import tempfile
import threading
from collections.abc import Sequence
from contextlib import suppress
from http import HTTPStatus
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROCESS_TIMEOUT_SECONDS = 90
READY_TIMEOUT_SECONDS = 45
STOP_TIMEOUT_SECONDS = 10
REQUEST_TIMEOUT_SECONDS = 5
REGRESSION_TIMEOUT_SECONDS = 120
FAILURES_PER_PROBE = 2
SAFE_ENV_NAMES = (
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TMPDIR",
    "TMP",
    "TEMP",
    "LANG",
    "LC_ALL",
)
Scenario = Literal["ordinary", "test", "reordered", "material", "invalid"]


def isolated_environment() -> dict[str, str]:
    return {name: os.environ[name] for name in SAFE_ENV_NAMES if name in os.environ} | {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    }


def loopback_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or not parsed.port
        or value != f"http://127.0.0.1:{parsed.port}"
    ):
        raise ValueError("probe requires an explicit http://127.0.0.1:<port> origin")
    return value


def peer_paths(root: Path | None, python: Path | None) -> tuple[Path, Path]:
    if root is None or python is None:
        raise ValueError("--portal-root and --portal-python are required for consumer execution")
    root = root.resolve()
    # Do not resolve the interpreter symlink: that would bypass the peer virtualenv.
    python = python.absolute()
    required = (
        root / "apps/api/tests/support/settings.py",
        root / "apps/api/tests/support/kernel.py",
        root / "apps/api/app/integrations/kernel/client.py",
        python,
    )
    if not all(path.is_file() for path in required):
        raise ValueError(
            "Portal sources/interpreter absent; run python3.12 scripts/repo.py sync-api "
            "from Portal root and pass its root .venv interpreter"
        )
    return root, python


def sha(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        env=isolated_environment(),
        capture_output=True,
        text=True,
        check=True,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return result.stdout.strip()


class Producer:
    def __init__(self, scenario: Scenario, token: str, previous: str | None = None) -> None:
        self.scenario = scenario
        environment = isolated_environment() | {"ANY711_CONFORMANCE_TOKEN": token}
        if previous is not None:
            environment["ANY711_PREVIOUS_TOKEN"] = previous
        self.environment = environment
        self.messages: queue.Queue[str | None] = queue.Queue()

    def receive(self) -> dict[str, Any]:
        try:
            line = self.messages.get(timeout=READY_TIMEOUT_SECONDS)
        except queue.Empty:
            raise RuntimeError("producer response deadline exceeded") from None
        if line is None:
            self.logs.seek(0)
            detail = self.logs.read()[-4000:]
            for name in ("ANY711_CONFORMANCE_TOKEN", "ANY711_PREVIOUS_TOKEN"):
                if self.environment.get(name):
                    detail = detail.replace(self.environment[name], "[REDACTED]")
            raise RuntimeError("producer exited before returning evidence:\n" + detail)
        return json.loads(line)

    def command(self, action: str, **values: Any) -> dict[str, Any]:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps({"action": action, **values}) + "\n")
        self.process.stdin.flush()
        return self.receive()

    def _read_output(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.messages.put(line)
        self.messages.put(None)

    def __enter__(self) -> Producer:
        self.workspace = tempfile.TemporaryDirectory(prefix="any711-harness-producer-")
        self.environment.update({name: self.workspace.name for name in ("TMPDIR", "TMP", "TEMP")})
        self.logs = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
        try:
            self.process = subprocess.Popen(
                [sys.executable, str(HERE / "manifest_producer.py"), "--scenario", self.scenario],
                cwd=ROOT,
                env=self.environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self.logs,
                text=True,
            )
        except OSError:
            self.logs.close()
            self.workspace.cleanup()
            raise
        self.reader = threading.Thread(target=self._read_output, daemon=True)
        self.reader.start()
        try:
            self.ready = self.receive()
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self, *error: Any) -> None:
        try:
            if self.process.poll() is None:
                assert self.process.stdin is not None
                try:
                    self.process.stdin.write('{"action":"stop"}\n')
                    self.process.stdin.flush()
                except BrokenPipeError:
                    pass
                try:
                    self.process.wait(timeout=STOP_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=STOP_TIMEOUT_SECONDS)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=STOP_TIMEOUT_SECONDS)
            if (not error or error[0] is None) and self.process.returncode != 0:
                raise RuntimeError("producer failed; no successful conformance evidence")
        finally:
            self.reader.join(timeout=STOP_TIMEOUT_SECONDS)
            for stream in (self.process.stdin, self.process.stdout, self.logs):
                if stream is not None:
                    with suppress(BrokenPipeError):
                        stream.close()
            # The parent also owns child scratch space, even after forced termination.
            self.workspace.cleanup()


def consumer(
    peer: tuple[Path, Path],
    token: str,
    *,
    mode: str = "probe",
    url: str | None = None,
    scenario: str = "test",
    expected_error: str | None = None,
) -> dict[str, Any]:
    root, python = peer
    command = [
        str(python),
        str(HERE / "manifest_consumer.py"),
        "--portal-root",
        str(root),
        "--mode",
        mode,
    ]
    if url is not None:
        command.extend(["--kernel-base-url", loopback_origin(url), "--scenario", scenario])
    if expected_error is not None:
        command.extend(["--expected-error", expected_error])
    with tempfile.TemporaryDirectory(prefix="any711-harness-consumer-") as directory:
        environment = isolated_environment() | {"ANY711_CONFORMANCE_TOKEN": token}
        environment.update({name: directory for name in ("TMPDIR", "TMP", "TEMP")})
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=REGRESSION_TIMEOUT_SECONDS
            if mode == "regressions"
            else PROCESS_TIMEOUT_SECONDS,
        )
    if result.returncode:
        # The child has only synthetic settings; never relay an arbitrary environment dump.
        print(
            result.stdout.replace(token, "[REDACTED]") if token else result.stdout,
            end="",
            flush=True,
        )
        print(
            result.stderr.replace(token, "[REDACTED]") if token else result.stderr,
            end="",
            file=sys.stderr,
            flush=True,
        )
        raise RuntimeError("isolated Portal process failed; check its dependencies and assertions")
    if mode != "probe":
        print(result.stdout, end="", flush=True)
        return {}
    return json.loads(result.stdout)


def compare_registry(producer: Producer, decoded: dict[str, Any]) -> None:
    assert producer.ready["default_composition_preserved"]
    for key in ("products", "usage_metrics"):
        assert decoded[key] == producer.ready["inventory"][key]
    assert decoded["manifest_version"] == producer.ready["manifest_version"]


def raw_security_checks(url: str, token: str) -> None:
    with httpx.Client(base_url=url, trust_env=False, timeout=REQUEST_TIMEOUT_SECONDS) as client:
        path = "/internal/v1/capability-manifest"
        params = {"tenant_id": "anytoolai", "region": "ru"}
        for headers in ({}, {"Authorization": "Bearer " + secrets.token_urlsafe(32)}):
            response = client.get(path, params=params, headers=headers)
            assert response.status_code == HTTPStatus.UNAUTHORIZED
            assert response.headers["www-authenticate"] == "Bearer"
        for scope in (
            {"tenant_id": "other", "region": "ru"},
            {"tenant_id": "anytoolai", "region": "eu"},
        ):
            response = client.get(path, params=scope, headers={"Authorization": "Bearer " + token})
            assert response.status_code == HTTPStatus.FORBIDDEN
        response = client.get(
            path, params=params, headers={"Authorization": "Bearer " + token, "Origin": "null"}
        )
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.headers["cache-control"] == "no-store"
        assert not any(name.startswith("access-control-") for name in response.headers)


def automated(peer: tuple[Path, Path]) -> None:
    token, previous = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    print(f"PRODUCER_SHA={sha(ROOT)} CONSUMER_SHA={sha(peer[0])}", flush=True)
    consumer(peer, token, mode="isolation")
    versions = {}
    for scenario in ("ordinary", "test", "reordered", "material"):
        with Producer(scenario, token, previous if scenario == "test" else None) as producer:
            url = producer.ready["url"]
            decoded = consumer(
                peer, token, url=url, scenario="test" if scenario == "reordered" else scenario
            )
            compare_registry(producer, decoded)
            versions[scenario] = decoded["manifest_version"]
            if scenario == "test":
                raw_security_checks(url, token)
                compare_registry(producer, consumer(peer, previous, url=url))
                consumer(
                    peer,
                    secrets.token_urlsafe(32),
                    url=url,
                    expected_error="kernel_authentication_failed",
                )
                producer.command("fail", count=FAILURES_PER_PROBE)
                safe_failure_check(url, token)
                # One remaining 500 is retried by the unchanged Portal client over TCP.
                compare_registry(producer, consumer(peer, token, url=url))
                producer.command("fail", count=FAILURES_PER_PROBE)
                consumer(peer, token, url=url, expected_error="kernel_unavailable")
                compare_registry(producer, consumer(peer, token, url=url))
            stats = producer.command("stats")
            assert not any(stats["side_effect_calls"].values())
            if scenario == "test":
                assert stats["injected_failures"] == FAILURES_PER_PROBE * 2
        print(
            f"REAL_HTTP_{scenario.upper()}=PASS manifest_version={versions[scenario]}", flush=True
        )
    assert versions["test"] == versions["reordered"]
    assert versions["ordinary"] != versions["test"]
    assert versions["material"] not in {versions["ordinary"], versions["test"]}
    with Producer("test", token) as restarted:
        compare_registry(restarted, consumer(peer, token, url=restarted.ready["url"]))
        consumer(
            peer,
            previous,
            url=restarted.ready["url"],
            expected_error="kernel_authentication_failed",
        )
        assert restarted.ready["manifest_version"] == versions["test"]
        restarted.command("stats")
    with Producer("invalid", token) as invalid:
        assert invalid.ready == {"invalid_config_refused": True}
    print("AUTH_SCOPE_ROTATION_RECOVERY_RESTART_CONCURRENCY=PASS SIDE_EFFECT_CALLS=0", flush=True)
    consumer(peer, token, mode="regressions")
    print("REAL_LOCAL_KERNEL_PORTAL_HTTP=PASS", flush=True)
    print("VOCABULARY=TEST_ONLY CORRUPT_PAYLOADS=INJECTED_CONSUMER_REGRESSIONS", flush=True)
    print("DEPLOYED_TLS=NOT_RUN PRODUCTION_COMMERCIAL_APPROVAL=NOT_ESTABLISHED", flush=True)


def safe_failure_check(url: str, token: str) -> None:
    response = httpx.get(
        url + "/internal/v1/capability-manifest?tenant_id=anytoolai&region=ru",
        headers={"Authorization": "Bearer " + token, "X-Request-ID": "any711-safe-failure"},
        trust_env=False,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.json()["error"]["code"] == "internal_server_error"
    assert response.headers["x-request-id"] == "any711-safe-failure"
    assert response.headers["cache-control"] == "no-store"
    assert "products" not in response.json()
    assert token not in response.text and "synthetic" not in response.text


def serve_test(token: str) -> None:
    with Producer("test", token) as producer:
        print(json.dumps(producer.ready, sort_keys=True), flush=True)
        print(f"PRODUCER_SHA={sha(ROOT)} VOCABULARY=TEST_ONLY", flush=True)
        while producer.process.poll() is None:
            threading.Event().wait(REQUEST_TIMEOUT_SECONDS)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("automated", "serve-test", "probe", "regressions", "isolation"),
        default="automated",
    )
    parser.add_argument("--portal-root", type=Path)
    parser.add_argument("--portal-python", type=Path)
    parser.add_argument("--kernel-base-url", type=loopback_origin)
    args = parser.parse_args(argv)
    try:
        if args.mode == "automated":
            automated(peer_paths(args.portal_root, args.portal_python))
        elif args.mode in {"isolation", "regressions"}:
            consumer(peer_paths(args.portal_root, args.portal_python), "", mode=args.mode)
        else:
            token = os.environ.get("ANY711_CONFORMANCE_TOKEN")
            if not token:
                raise ValueError(
                    "manual modes require an environment-only disposable ANY711_CONFORMANCE_TOKEN"
                )
            if args.mode == "serve-test":
                serve_test(token)
            else:
                if args.kernel_base_url is None:
                    raise ValueError("probe requires --kernel-base-url")
                peer = peer_paths(args.portal_root, args.portal_python)
                result = consumer(
                    peer,
                    token,
                    url=args.kernel_base_url,
                )
                print(f"CONSUMER_SHA={sha(peer[0])}", flush=True)
                print(json.dumps(result, sort_keys=True), flush=True)
                print("REAL_LOCAL_KERNEL_PORTAL_HTTP=PASS VOCABULARY=TEST_ONLY", flush=True)
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError, RuntimeError, AssertionError, subprocess.SubprocessError) as error:
        print(f"MANIFEST_CONFORMANCE=FAIL ({type(error).__name__})", file=sys.stderr)
        if isinstance(error, (ValueError, RuntimeError)):
            print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
