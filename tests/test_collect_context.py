from __future__ import annotations

import json
from pathlib import Path

from tests.module_loading import load_cached_module


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "agent" / "collect_context.py"
    return load_cached_module("collect_context_module", path)


def test_sanitize_text_removes_assignments_bearer_tokens_and_emails() -> None:
    module = load_module()
    sanitized = module.sanitize_text(
        "token=abc authorization:Bearer xyz person@example.com password=hunter2"
    )

    assert "abc" not in sanitized
    assert "xyz" not in sanitized
    assert "person@example.com" not in sanitized
    assert "hunter2" not in sanitized


def test_collect_includes_useful_sections_without_failure_secrets(monkeypatch, tmp_path) -> None:
    module = load_module()
    identity = module.runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    failure = tmp_path / "failure.txt"
    failure.write_text("authorization=Bearer secret person@example.com", encoding="utf-8")
    monkeypatch.delenv("ANYTOOLAI_POSTGRES_DB", raising=False)
    monkeypatch.setattr(module.runner, "runtime_identity", lambda: identity)
    monkeypatch.setattr(module.runner, "_compose_env", lambda value: {})
    monkeypatch.setattr(
        module.runner,
        "_compose_command",
        lambda value, *args: ["docker", *args],
    )
    monkeypatch.setattr(module, "_tool_versions", lambda: {"python": {"output": "3.12"}})
    monkeypatch.setattr(module, "_active_plans", lambda: [{"file": "plan.md", "state": "active"}])
    monkeypatch.setattr(
        module,
        "_run",
        lambda command, env=None: {"command": list(command), "exit_code": 0, "output": "ok"},
    )

    payload = module.collect(failure_file=failure)
    serialized = json.dumps(payload)

    assert payload["runtime"]["api_url"] == "http://127.0.0.1:18123"
    assert payload["runtime"]["database_endpoint"].endswith(":15555/anytoolai")
    assert payload["active_plans"]
    assert "secret" not in serialized
    assert "person@example.com" not in serialized


def test_collect_reflects_configured_database_name(monkeypatch, tmp_path) -> None:
    module = load_module()
    identity = module.runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    monkeypatch.setenv("ANYTOOLAI_POSTGRES_DB", "myproject")
    monkeypatch.setattr(module.runner, "runtime_identity", lambda: identity)
    monkeypatch.setattr(module.runner, "_compose_env", lambda value: {})
    monkeypatch.setattr(
        module.runner,
        "_compose_command",
        lambda value, *args: ["docker", *args],
    )
    monkeypatch.setattr(module, "_tool_versions", lambda: {"python": {"output": "3.12"}})
    monkeypatch.setattr(module, "_active_plans", lambda: [])
    monkeypatch.setattr(
        module,
        "_run",
        lambda command, env=None: {"command": list(command), "exit_code": 0, "output": "ok"},
    )

    payload = module.collect()

    assert payload["runtime"]["database_endpoint"] == "postgresql://127.0.0.1:15555/myproject"


def test_write_bundle_uses_repository_local_output(monkeypatch, tmp_path) -> None:
    module = load_module()
    monkeypatch.setattr(module, "collect", lambda **kwargs: {"safe": True})

    target = module.write_bundle(output_root=tmp_path)

    assert target.parent == tmp_path
    assert json.loads(target.read_text(encoding="utf-8")) == {"safe": True}


def test_write_bundle_captures_timestamp_before_calling_collect(monkeypatch, tmp_path) -> None:
    """The filename's timestamp must reflect when write_bundle() was called, not when collect()
    (which can take ~20s via docker compose logs/ps) finished -- regression coverage for the
    ordering fix in docs/exec-plans/active/any-220-atom-runtime-proof-cli.md's decision log
    (third code review pass): a prior refactor had silently moved the timestamp to after
    collect()."""
    module = load_module()
    call_order: list[str] = []

    class _FakeDatetime:
        @staticmethod
        def now(tz=None):
            call_order.append("now")
            import datetime as real_datetime

            return real_datetime.datetime(2026, 1, 1, tzinfo=tz)

    def _fake_collect(**kwargs):
        call_order.append("collect")
        return {"safe": True}

    monkeypatch.setattr(module, "datetime", _FakeDatetime)
    monkeypatch.setattr(module, "collect", _fake_collect)

    module.write_bundle(output_root=tmp_path)

    assert call_order == ["now", "collect"]
