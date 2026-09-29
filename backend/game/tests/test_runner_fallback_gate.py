"""Тесты «предохранителя» небезопасного fallback'а раннера.

Когда Docker недоступен (типичный прод на Railway), раннер раньше молча
запускал код через subprocess БЕЗ песочницы — это RCE. Теперь поведение
управляется флагом ``RUNNER_ALLOW_UNSAFE_FALLBACK``. Эти тесты НЕ требуют
Docker: мы мокаем ``docker.from_env``, чтобы он «падал», эмулируя прод.
"""

import importlib
import logging
import sys
from unittest.mock import MagicMock, patch

import requests

from game import runner


def _docker_unavailable(*args, **kwargs):
    raise RuntimeError("docker daemon not available (simulated prod)")


def test_execute_refuses_unsafe_fallback_when_disabled(settings):
    """Прод-режим: без Docker и с выключенным флагом код НЕ выполняется."""
    settings.RUNNER_ALLOW_UNSAFE_FALLBACK = False
    with patch.object(runner.docker, "from_env", _docker_unavailable):
        result = runner.execute_python_code("print('should-not-run')")
    assert result["status"] == "error"
    assert "RUNNER_ALLOW_UNSAFE_FALLBACK" in result["output"]
    assert "should-not-run" not in result["output"]


def test_stream_refuses_unsafe_fallback_when_disabled(settings):
    """То же для WebSocket-стриминга: только error + exit(-1), без вывода кода."""
    settings.RUNNER_ALLOW_UNSAFE_FALLBACK = False
    with patch.object(runner.docker, "from_env", _docker_unavailable):
        events = list(runner.stream_python_code("print('should-not-run')"))
    assert any(
        e["type"] == "error" and "RUNNER_ALLOW_UNSAFE_FALLBACK" in e.get("message", "")
        for e in events
    )
    assert events[-1]["type"] == "exit"
    assert events[-1]["code"] == -1
    assert not any("should-not-run" in str(e) for e in events)


def test_execute_allows_subprocess_fallback_when_enabled(settings):
    """Dev-режим: с включённым флагом и без Docker код реально выполняется."""
    settings.RUNNER_ALLOW_UNSAFE_FALLBACK = True
    with patch.object(runner.docker, "from_env", _docker_unavailable):
        result = runner.execute_python_code("print('hello-from-fallback')")
    assert result["status"] == "success"
    assert "hello-from-fallback" in result["output"]


# ── secure defaults ─────────────────────────────────────────────────────────


def test_gate_is_closed_when_the_setting_is_missing(settings):
    """Нет настройки — значит небезопасный режим выключен, а не включён."""
    del settings.RUNNER_ALLOW_UNSAFE_FALLBACK
    assert runner._unsafe_fallback_allowed() is False


def _load_settings_module(name, monkeypatch, **env):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "x" * 50)
    monkeypatch.delenv("RUNNER_ALLOW_UNSAFE_FALLBACK", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    sys.modules.pop(name, None)
    try:
        return importlib.import_module(name)
    finally:
        sys.modules.pop(name, None)


def test_production_settings_disable_the_fallback_by_default(monkeypatch):
    prod = _load_settings_module("core.settings.production", monkeypatch)
    assert prod.RUNNER_ALLOW_UNSAFE_FALLBACK is False


def test_production_fallback_needs_an_explicit_opt_in(monkeypatch):
    prod = _load_settings_module(
        "core.settings.production", monkeypatch, RUNNER_ALLOW_UNSAFE_FALLBACK="True"
    )
    assert prod.RUNNER_ALLOW_UNSAFE_FALLBACK is True


def test_local_settings_allow_the_fallback_for_development(monkeypatch):
    local = _load_settings_module("core.settings.local", monkeypatch)
    assert local.RUNNER_ALLOW_UNSAFE_FALLBACK is True


# ── Judge0 failures must be visible in the logs ─────────────────────────────


def test_judge0_connection_error_is_logged_and_code_is_not_run_locally(
    settings, caplog
):
    settings.RUNNER_ALLOW_UNSAFE_FALLBACK = False
    settings.RUNNER_JUDGE0_URL = "https://judge0.example"
    with patch.object(runner.docker, "from_env", _docker_unavailable), patch.object(
        runner.requests, "post", side_effect=requests.ConnectionError("boom")
    ), caplog.at_level(logging.WARNING, logger="game.runner"):
        result = runner.execute_python_code("print('should-not-run')")
    assert result["status"] == "error"
    assert "should-not-run" not in result["output"]
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "Judge0 request failed" in messages
    assert "refused" in messages


def test_judge0_http_error_is_logged(settings, caplog):
    settings.RUNNER_ALLOW_UNSAFE_FALLBACK = False
    settings.RUNNER_JUDGE0_URL = "https://judge0.example"
    with patch.object(runner.docker, "from_env", _docker_unavailable), patch.object(
        runner.requests, "post", return_value=MagicMock(status_code=503)
    ), caplog.at_level(logging.WARNING, logger="game.runner"):
        events = list(runner.stream_python_code("print('should-not-run')"))
    assert events[-1] == {"type": "exit", "code": -1, "duration": events[-1]["duration"]}
    assert any("HTTP 503" in r.getMessage() for r in caplog.records)


def test_using_the_unsafe_fallback_is_logged(settings, caplog):
    settings.RUNNER_ALLOW_UNSAFE_FALLBACK = True
    settings.RUNNER_JUDGE0_URL = ""
    with patch.object(runner.docker, "from_env", _docker_unavailable), caplog.at_level(
        logging.WARNING, logger="game.runner"
    ):
        runner.execute_python_code("print('dev')")
    assert any("UNSAFE" in r.getMessage() for r in caplog.records)
