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
    assert "не засчитана" in result["output"]  # said to the learner in plain words
    assert "RUNNER_ALLOW_UNSAFE_FALLBACK" not in result["output"]  # the technical reason stays in the log
    assert "should-not-run" not in result["output"]


def test_stream_refuses_unsafe_fallback_when_disabled(settings):
    """То же для WebSocket-стриминга: только error + exit(-1), без вывода кода."""
    settings.RUNNER_ALLOW_UNSAFE_FALLBACK = False
    with patch.object(runner.docker, "from_env", _docker_unavailable):
        events = list(runner.stream_python_code("print('should-not-run')"))
    assert any(
        e["type"] == "error" and "не засчитана" in e.get("message", "")
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
    monkeypatch.setenv("ALLOWED_HOSTS", "testserver")
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
    settings, caplog, monkeypatch
):
    monkeypatch.setattr(runner, "_JUDGE0_PAUSE", 0)
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


def test_judge0_http_error_is_logged(settings, caplog, monkeypatch):
    monkeypatch.setattr(runner, "_JUDGE0_PAUSE", 0)
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


# ── the local streaming fallback itself (dev only, works on Windows too) ────


def _stream_locally(settings, code, timeout=15):
    settings.RUNNER_ALLOW_UNSAFE_FALLBACK = True
    settings.RUNNER_JUDGE0_URL = ""
    with patch.object(runner.docker, "from_env", _docker_unavailable):
        return list(runner.stream_python_code(code, timeout=timeout))


def test_local_stream_forwards_stdout_stderr_and_exit_code(settings):
    events = _stream_locally(
        settings,
        "import sys\nprint('out')\nprint('err', file=sys.stderr)\nsys.exit(3)",
    )
    assert {"type": "stdout", "data": "out\n"} in events
    assert {"type": "stderr", "data": "err\n"} in events
    assert events[-1]["type"] == "exit"
    assert events[-1]["code"] == 3


def test_local_stream_kills_an_endless_loop_on_timeout(settings):
    events = _stream_locally(settings, "while True:\n    pass", timeout=1)
    assert any(e["type"] == "error" and "Timeout" in e["message"] for e in events)
    assert events[-1]["type"] == "exit"
    assert events[-1]["code"] != 0


def test_local_stream_truncates_runaway_output(settings):
    events = _stream_locally(
        settings, "for _ in range(5000):\n    print('x' * 80)", timeout=10
    )
    assert any(e["type"] == "error" and "обрезан" in e["message"] for e in events)
    streamed = sum(len(e["data"]) for e in events if e["type"] == "stdout")
    assert streamed <= runner.MAX_OUTPUT_SIZE
    assert events[-1]["type"] == "exit"


# ── a class pressing "Run" together: busy answers are retried, the queue is bounded ────


def _ok_response():
    return MagicMock(
        status_code=201,
        json=lambda: {"stdout": "NAo=", "stderr": None, "compile_output": None, "status": {"id": 3}},  # "4\n" in base64
    )


def _judge0_only(settings, monkeypatch):
    monkeypatch.setattr(runner, "_JUDGE0_PAUSE", 0)
    settings.RUNNER_ALLOW_UNSAFE_FALLBACK = False
    settings.RUNNER_JUDGE0_URL = "https://judge0.example"


def test_a_busy_judge0_is_retried_and_the_learner_never_notices(settings, monkeypatch):
    _judge0_only(settings, monkeypatch)
    answers = [MagicMock(status_code=429), requests.ConnectionError("blip"), _ok_response()]
    with patch.object(runner.docker, "from_env", _docker_unavailable), patch.object(
        runner.requests, "post", side_effect=answers
    ) as post:
        result = runner.execute_python_code("print(2 + 2)")
    assert result == {"status": "success", "output": "4\n"}
    assert post.call_count == 3


def test_a_judge0_that_stays_busy_gives_up_after_the_tries(settings, monkeypatch):
    _judge0_only(settings, monkeypatch)
    with patch.object(runner.docker, "from_env", _docker_unavailable), patch.object(
        runner.requests, "post", return_value=MagicMock(status_code=429)
    ) as post:
        result = runner.execute_python_code("print(2 + 2)")
    assert result["status"] == "error" and result["infra"] is True
    assert post.call_count == runner._JUDGE0_TRIES


def test_a_refusal_that_is_not_about_load_is_not_retried(settings, monkeypatch):
    _judge0_only(settings, monkeypatch)
    with patch.object(runner.docker, "from_env", _docker_unavailable), patch.object(
        runner.requests, "post", return_value=MagicMock(status_code=400)
    ) as post:
        runner.execute_python_code("print(2 + 2)")
    assert post.call_count == 1


def test_a_full_queue_gives_up_without_calling_judge0(settings, monkeypatch):
    _judge0_only(settings, monkeypatch)
    monkeypatch.setattr(runner, "_JUDGE0_WAIT_FOR_SLOT", 0.01)
    monkeypatch.setattr(runner, "_JUDGE0_SLOTS", runner.threading.BoundedSemaphore(1))
    runner._JUDGE0_SLOTS.acquire()  # somebody else is running
    with patch.object(runner.docker, "from_env", _docker_unavailable), patch.object(
        runner.requests, "post", return_value=_ok_response()
    ) as post:
        result = runner.execute_python_code("print(2 + 2)")
    assert result["infra"] is True and post.call_count == 0


def test_code_with_russian_text_is_sent_in_base64_and_the_answer_decoded(settings, monkeypatch):
    """ce.judge0.com refuses plain JSON with non-ASCII source; the code and the answer travel in base64."""
    import base64

    _judge0_only(settings, monkeypatch)
    answer = MagicMock(
        status_code=201,
        json=lambda: {
            "stdout": base64.b64encode("Привет, мир!\n".encode()).decode(),
            "stderr": None,
            "compile_output": None,
            "status": {"id": 3},
        },
    )
    with patch.object(runner.docker, "from_env", _docker_unavailable), patch.object(
        runner.requests, "post", return_value=answer
    ) as post:
        result = runner.execute_python_code('print("Привет, мир!")')
    assert result == {"status": "success", "output": "Привет, мир!\n"}
    sent = post.call_args.kwargs
    assert "base64_encoded=true" in post.call_args.args[0]
    assert base64.b64decode(sent["json"]["source_code"]).decode() == 'print("Привет, мир!")'
