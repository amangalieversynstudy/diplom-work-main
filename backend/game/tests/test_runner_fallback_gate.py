"""Тесты «предохранителя» небезопасного fallback'а раннера.

Когда Docker недоступен (типичный прод на Railway), раннер раньше молча
запускал код через subprocess БЕЗ песочницы — это RCE. Теперь поведение
управляется флагом ``RUNNER_ALLOW_UNSAFE_FALLBACK``. Эти тесты НЕ требуют
Docker: мы мокаем ``docker.from_env``, чтобы он «падал», эмулируя прод.
"""

from unittest.mock import patch

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
