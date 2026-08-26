from __future__ import annotations

import pytest

from anytoolai_platform_core.scenarios.service import (
    LIVE_CANARY_TOKEN_ENV_VAR,
    _live_canary_token_is_valid,
)


def test_live_canary_token_matches_when_configured_and_provided_agree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_CANARY_TOKEN_ENV_VAR, "the-real-token")

    assert _live_canary_token_is_valid("the-real-token") is True


def test_live_canary_token_rejects_a_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_CANARY_TOKEN_ENV_VAR, "the-real-token")

    assert _live_canary_token_is_valid("not-the-real-token") is False


def test_live_canary_token_rejects_when_none_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_CANARY_TOKEN_ENV_VAR, "the-real-token")

    assert _live_canary_token_is_valid(None) is False


def test_live_canary_token_rejects_empty_string_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_CANARY_TOKEN_ENV_VAR, "the-real-token")

    assert _live_canary_token_is_valid("") is False


def test_live_canary_token_fails_closed_when_server_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even a caller who somehow supplies a real-looking token must be rejected if the server
    itself hasn't been configured with its own ANYTOOLAI_LIVE_CANARY_TOKEN -- an unconfigured
    deployment can never accidentally serve an internal_only scenario to anyone."""
    monkeypatch.delenv(LIVE_CANARY_TOKEN_ENV_VAR, raising=False)

    assert _live_canary_token_is_valid("anything") is False


def test_live_canary_token_fails_closed_when_server_token_is_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_CANARY_TOKEN_ENV_VAR, "")

    assert _live_canary_token_is_valid("anything") is False
