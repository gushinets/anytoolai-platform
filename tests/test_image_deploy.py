from __future__ import annotations

import json
import os
import subprocess
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from tests.test_runner import load_runner_module


def image_env(tmp_path: Path) -> dict[str, str]:
    return {
        "ANYTOOLAI_API_IMAGE": "kernel-api:reviewed",
        "ANYTOOLAI_WORKER_IMAGE": "kernel-worker:reviewed",
        "ANYTOOLAI_WEB_IMAGE": "kernel-web:origins-v1",
        "ANYTOOLAI_PROFILE_ROOT": str(tmp_path),
        "ANYTOOLAI_PRIVACY_POLICY_URL": "https://example.invalid/privacy",
    }


@pytest.mark.skipif(os.name != "posix", reason="Image installation requires a Linux host")
def test_profile_uses_image_and_translates_only_generated_host_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = load_runner_module()
    env = image_env(tmp_path)
    calls = []

    def run(command: list[str], actual_env: dict[str, str]) -> int:
        calls.append(command)
        name = Path(command[command.index("--output-dir") + 1]).name
        output = tmp_path / name
        output.mkdir()
        (output / "products").mkdir()
        (output / "manifest.json").write_text(
            json.dumps(
                {
                    "generated_products_root": f"/deployment/{name}/products",
                    "source_products_root": "/app/image-products",
                    "container_products_root": "/app/products",
                    "source_fingerprint": "a" * 64,
                    "profile_fingerprint": "b" * 64,
                    "enabled_products": {
                        "proposal_ai": {
                            "provider_policy_ref": "default_text_generation_v1",
                            "quota_policy_ref": None,
                        }
                    },
                }
            )
        )
        return 0

    monkeypatch.setattr(runner, "_validate_image_inputs", lambda env: None)
    monkeypatch.setattr(runner, "_check_source_fingerprint", lambda manifest, env: 0)
    monkeypatch.setattr(runner, "run_with_env", run)
    code, manifest = runner._build_image_deployment_profile(
        "anytoolai-prod", ["proposal_ai"], [], env
    )
    assert code == 0
    assert manifest["source_products_root"] == "/app/image-products"
    assert Path(manifest["generated_products_root"]).is_relative_to(tmp_path)
    assert f"type=bind,source={tmp_path},target=/deployment" in calls[0]
    assert "--network=none" in calls[0] and "--no-sync" in calls[0]
    assert "UV_CACHE_DIR=/tmp/uv-cache" in calls[0]


@pytest.mark.skipif(os.name != "posix", reason="Image installation requires a Linux host")
@pytest.mark.parametrize("symlink_target", ["profile", "manifest", "products"])
def test_image_profile_rejects_symlinks_without_rewriting_external_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, symlink_target: str
) -> None:
    runner = load_runner_module()
    outside = tmp_path / "outside"
    outside.mkdir()
    original = json.dumps({
        "container_products_root": "/app/products",
        "profile_fingerprint": "a" * 64,
        "enabled_products": {},
    })
    sentinel = outside / "manifest.json"
    sentinel.write_text(original, encoding="utf-8")

    def run(command, env):
        name = Path(command[command.index("--output-dir") + 1]).name
        output = tmp_path / name
        if symlink_target == "profile":
            output.symlink_to(outside, target_is_directory=True)
        else:
            output.mkdir()
            if symlink_target == "manifest":
                (output / "manifest.json").symlink_to(sentinel)
            else:
                (output / "manifest.json").write_text(original, encoding="utf-8")
            if symlink_target == "products":
                (output / "products").symlink_to(outside, target_is_directory=True)
            else:
                (output / "products").mkdir()
        return 0

    monkeypatch.setattr(runner, "_validate_image_inputs", lambda env: None)
    monkeypatch.setattr(runner, "_check_source_fingerprint", lambda *args: 0)
    monkeypatch.setattr(runner, "run_with_env", run)
    with pytest.raises(ValueError, match="generated profile"):
        runner._build_image_deployment_profile(
            "anytoolai-prod", ["proposal_ai"], [], image_env(tmp_path)
        )
    assert sentinel.read_text(encoding="utf-8") == original


@pytest.mark.skipif(os.name != "posix", reason="Image installation requires a Linux host")
def test_worker_revision_mismatch_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = load_runner_module()
    revisions = iter(["api-source", "other-source"])
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, next(revisions)),
    )
    with pytest.raises(ValueError, match="same reviewed source"):
        runner._validate_image_inputs(image_env(tmp_path))


def test_image_installation_refuses_windows_before_docker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = load_runner_module()
    monkeypatch.setattr(runner, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *args, **kwargs: pytest.fail("called Docker")
    )
    with pytest.raises(ValueError, match="requires a Linux Docker host"):
        runner._build_image_deployment_profile(
            "anytoolai-prod", ["proposal_ai"], [], image_env(tmp_path)
        )


def test_source_fingerprint_checks_both_selected_images(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = load_runner_module()
    calls = []
    monkeypatch.setattr(runner, "run_with_env", lambda command, env: calls.append(command) or 0)
    assert (
        runner._check_source_fingerprint(
            {"source_products_root": "/app/products", "source_fingerprint": "a" * 64},
            image_env(tmp_path),
        )
        == 0
    )
    assert "kernel-api:reviewed" in calls[0]
    assert "kernel-worker:reviewed" in calls[1]


@pytest.mark.parametrize("network_selector", ["", "1", "invalid"])
def test_frontend_update_never_generates_or_activates_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, network_selector: str
) -> None:
    runner = load_runner_module()
    env = image_env(tmp_path)
    env["ANYTOOLAI_VPS_135_NETWORKS"] = network_selector
    calls = []
    monkeypatch.setattr(runner, "_prod_deployment_lock", nullcontext)
    monkeypatch.setattr(runner, "_resolved_env_file", lambda path: env)
    monkeypatch.setattr(runner, "_validate_image_inputs", lambda env: None)
    monkeypatch.setattr(runner, "run_with_env", lambda command, env: calls.append(command) or 0)
    monkeypatch.setattr(
        runner, "_build_deployment_profile", lambda *args: pytest.fail("regenerated profile")
    )
    if network_selector == "invalid":
        assert runner.prod_web_up() == 1
        assert calls == []
        return
    assert runner.prod_web_up() == 0
    assert (str(runner.COMPOSE_VPS_135_FILE) in calls[0]) is (network_selector == "1")
    assert str(runner.COMPOSE_LIVE_FILE) not in calls[0]
    assert len(calls) == 1
    assert calls[0][-8:] == [
        "up",
        "-d",
        "--no-deps",
        "--no-build",
        "--pull",
        "never",
        "--wait",
        "web-mirror",
    ]


@pytest.mark.parametrize("drain_ok", [True, False])
def test_image_failure_does_not_start_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, drain_ok: bool
) -> None:
    runner = load_runner_module()
    env = image_env(tmp_path)
    env.update(ANYTOOLAI_ENABLED_PRODUCT_IDS="proposal_ai", ANYTOOLAI_UNMETERED_PRODUCT_IDS="")
    manifest = {
        "generated_products_root": str(tmp_path / "freelancer-suite" / "products"),
        "profile_fingerprint": "a" * 64,
    }
    monkeypatch.setattr(
        runner,
        "_deployment_inputs",
        lambda: runner.DeploymentInputs(("proposal_ai",), frozenset(), env),
    )
    monkeypatch.setattr(runner, "_build_deployment_profile", lambda *args: (0, manifest))
    monkeypatch.setattr(runner, "_prod_stack_running", lambda: True)
    lifecycle = []
    monkeypatch.setattr(
        runner, "_prod_quiesce_locked", lambda: lifecycle.append("drain") or (0 if drain_ok else 1)
    )
    monkeypatch.setattr(runner, "_stop_failed_prod_candidate", lambda: lifecycle.append("closed"))
    monkeypatch.setattr(
        runner,
        "_activate_deployment_profile",
        lambda *args, **kwargs: pytest.fail("activated failure"),
    )
    calls = []
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env: calls.append(command) or (1 if command[-1] == "migrate" else 0),
    )
    assert runner._prod_up_locked() == 1
    assert lifecycle == (["drain", "closed"] if drain_ok else ["drain"])
    if drain_ok:
        assert calls[-1][-4:] == ["run", "--rm", "--no-deps", "migrate"]
    else:
        assert calls == []  # A failed drain leaves the old worker alive for recovery.
    assert not any("up" in command and "platform-api" in command for command in calls)


def test_build_workflow_preserves_all_frontend_origins() -> None:
    runner = load_runner_module()
    workflow = yaml.safe_load((runner.ROOT / ".github/workflows/publish-images.yml").read_text())
    jobs = workflow["jobs"]
    assert "'backend'" in jobs["api"]["if"] and "'backend'" in jobs["worker"]["if"]
    script = jobs["web"]["steps"][-1]["run"]
    for name in (
        "PLATFORM_API_BASE_URL",
        "NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS",
        "ANYTOOLAI_WEB_BASE_PATH",
        "NEXT_PUBLIC_PORTAL_AUTHORIZE_URL",
        "ANYTOOLAI_PORTAL_CONSUMER_ID",
        "NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL",
    ):
        assert f'--build-arg "{name}=${name}"' in script


@pytest.mark.skipif(os.name != "posix", reason="GitHub image builds run in bash on Linux")
@pytest.mark.parametrize("policy_url", ["", "/privacy", "javascript:alert(1)",
                                        "https://example.invalid/privacy"])
def test_web_image_validates_and_embeds_privacy_url(tmp_path: Path, policy_url: str) -> None:
    workflow = yaml.safe_load(
        (load_runner_module().ROOT / ".github/workflows/publish-images.yml").read_text()
    )
    step = workflow["jobs"]["web"]["steps"][-1]
    assert step["env"]["NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL"] == (
        "${{ inputs.privacy_policy_url }}"
    )
    calls = tmp_path / "docker-calls"
    stub = tmp_path / "docker"
    stub.write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$DOCKER_CALLS"\n')
    stub.chmod(0o700)
    result = subprocess.run(
        ["bash", "-c", step["run"]],
        env=os.environ | {
            "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
            "DOCKER_CALLS": str(calls),
            "GITHUB_REPOSITORY_OWNER": "example",
            "GITHUB_SHA": "reviewed", "GITHUB_RUN_ID": "1",
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"), "PUBLISH": "false",
            "PLATFORM_API_BASE_URL": "http://platform-api:8000",
            "NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS": "kernel_demo",
            "ANYTOOLAI_WEB_BASE_PATH": "", "ANYTOOLAI_PORTAL_CONSUMER_ID": "platform-kernel",
            "NEXT_PUBLIC_PORTAL_AUTHORIZE_URL": "https://example.invalid/authorize",
            "NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL": policy_url,
        },
        capture_output=True, text=True, check=False,
    )
    if policy_url.startswith("https:"):
        assert result.returncode == 0, result.stderr
        assert f"NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL={policy_url}" in calls.read_text()
    else:
        assert result.returncode != 0
        assert not calls.exists()
