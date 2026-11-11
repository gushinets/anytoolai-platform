from __future__ import annotations

import json
import subprocess
from contextlib import nullcontext
from pathlib import Path

import pytest
import yaml

from tests.test_runner import load_runner_module


def image_env(tmp_path: Path) -> dict[str, str]:
    return {
        "ANYTOOLAI_API_IMAGE": "kernel-api:reviewed",
        "ANYTOOLAI_WORKER_IMAGE": "kernel-worker:reviewed",
        "ANYTOOLAI_WEB_IMAGE": "kernel-web:origins-v1",
        "ANYTOOLAI_PROFILE_ROOT": str(tmp_path),
    }


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


def test_frontend_update_never_generates_or_activates_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = load_runner_module()
    env = image_env(tmp_path)
    calls = []
    monkeypatch.setattr(runner, "_prod_deployment_lock", nullcontext)
    monkeypatch.setattr(runner, "_resolved_env_file", lambda path: env)
    monkeypatch.setattr(runner, "_validate_image_inputs", lambda env: None)
    monkeypatch.setattr(runner, "run_with_env", lambda command, env: calls.append(command) or 0)
    monkeypatch.setattr(
        runner, "_build_deployment_profile", lambda *args: pytest.fail("regenerated profile")
    )
    assert runner.prod_web_up() == 0
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
    ):
        assert f'--build-arg "{name}=${name}"' in script
