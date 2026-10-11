"""F1/F2 of the pre-launch review: hidden checks of different learners must not
queue on one shared thread, and one learner holds at most one run at a time."""
import asyncio
import threading
import time
from types import SimpleNamespace
from unittest import mock

import pytest
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.cache import cache

from game import consumers, services, throttles


def _fake_stream(code, stop_event=None):
    yield {"type": "exit", "code": 0, "duration": 0.01}


async def _run_once(user, results, task_id=None):
    com = WebsocketCommunicator(consumers.RunnerConsumer.as_asgi(), "/ws/run/")
    com.scope["user"] = user
    ok, _ = await com.connect()
    assert ok
    await com.send_json_to({"type": "run", "code": "print(1)", **({"task_id": task_id} if task_id else {})})
    msgs = []
    while True:
        msg = await com.receive_json_from(timeout=10)
        msgs.append(msg)
        if msg["type"] in ("exit", "error"):
            break
    results[user.pk] = msgs
    await com.disconnect()


@pytest.mark.django_db(transaction=True)
def test_hidden_checks_of_different_learners_run_in_parallel():
    User = get_user_model()
    users = [User.objects.create_user(f"par_{i}", password="x" * 12) for i in range(2)]
    cache.clear()
    threads = set()

    def slow_check(user, task, code, stdout, exit_code):
        threads.add(threading.get_ident())
        time.sleep(1.0)  # stands for the Judge0 round trip
        return services.NOT_CHECKED

    async def both():
        start = time.monotonic()
        res = {}
        await asyncio.gather(*(_run_once(u, res, task_id=1) for u in users))
        return time.monotonic() - start

    task = SimpleNamespace(pk=1)
    with mock.patch.object(consumers, "stream_python_code", _fake_stream), \
            mock.patch.object(consumers, "prepare_code_task", lambda u, t: task), \
            mock.patch.object(consumers, "precheck_hidden", slow_check), \
            mock.patch.object(consumers, "finish_code_run", lambda *a, **k: None):
        elapsed = asyncio.run(both())
    assert len(threads) == 2
    assert elapsed < 1.8


@pytest.mark.django_db(transaction=True)
def test_second_concurrent_run_of_same_learner_is_refused_other_learner_passes():
    User = get_user_model()
    a = User.objects.create_user("inf_a", password="x" * 12)
    b = User.objects.create_user("inf_b", password="x" * 12)
    cache.clear()

    def slow_stream(code, stop_event=None):
        time.sleep(0.6)
        yield {"type": "exit", "code": 0, "duration": 0.01}

    async def scenario():
        res = {}
        first = asyncio.create_task(_run_once(a, res))
        await asyncio.sleep(0.2)
        # same learner, second connection while the first run is going
        second = {}
        await _run_once(a, second)
        other = {}
        await _run_once(b, other)
        await first
        return res, second, other

    with mock.patch.object(consumers, "stream_python_code", slow_stream):
        res, second, other = asyncio.run(scenario())
    refused = second[a.pk][-1]
    assert refused["type"] == "error" and refused["reason"] == "already_running"
    assert res[a.pk][-1]["type"] == "exit"
    assert other[b.pk][-1]["type"] == "exit"
    assert cache.get(f"runner:inflight:{a.pk}") is None  # released afterwards


def test_inflight_slot_is_per_learner():
    cache.clear()
    assert throttles.acquire_run(7) is True
    assert throttles.acquire_run(7) is False
    assert throttles.acquire_run(8) is True
    throttles.release_run(7)
    assert throttles.acquire_run(7) is True


@pytest.mark.django_db
def test_rest_run_refuses_second_run_and_releases_on_exception():
    from rest_framework.test import APIClient
    client = APIClient(raise_request_exception=True)
    User = get_user_model()
    user = User.objects.create_user("rest_inf", password="x" * 12)
    client.force_authenticate(user)
    cache.clear()
    url = "/api/runner/execute/"
    with mock.patch("game.runner.execute_python_code", return_value={"status": "success", "output": "1"}):
        assert throttles.acquire_run(user.pk)
        r = client.post(url, {"code": "print(1)"}, format="json")
        assert r.status_code == 429
        throttles.release_run(user.pk)
        r = client.post(url, {"code": "print(1)"}, format="json")
        assert r.status_code == 200
        assert cache.get(f"runner:inflight:{user.pk}") is None
    with mock.patch("game.runner.execute_python_code", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            client.post(url, {"code": "print(1)"}, format="json")
    assert cache.get(f"runner:inflight:{user.pk}") is None
