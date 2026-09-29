"""The WebSocket runner grades code tasks on the server.

The runner itself is faked (no Docker); what is verified is that a run tied to a
``task_id`` is checked against the answer key that never leaves the server,
that the attempt is recorded, and that the verdict arrives before ``exit``
(the browser closes the socket on ``exit``).
"""

from unittest.mock import MagicMock, patch

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.asyncio


def _application():
    from core.asgi import application

    return application


@sync_to_async
def _setup(username, *, with_story=False, expected="Charged", min_level=1):
    """A learner plus a mission with an optional story step and one code task."""
    from game.models import Location, Mission, MissionTask, Track
    from users.models import User

    user = User.objects.create_user(username=username, password="pw")
    track = Track.objects.create(slug=f"t-{username}", title="T", is_active=True)
    location = Location.objects.create(track=track, title="L", order=1)
    mission = Mission.objects.create(
        location=location, title="M", order=1, min_level=min_level
    )
    story = None
    if with_story:
        story = MissionTask.objects.create(mission=mission, order=1, task_type="story")
    data = {"language": "python", "starter": "print(1)"}
    if expected is not None:
        data["expected_output"] = expected
    code = MissionTask.objects.create(
        mission=mission, order=2, task_type="code", data=data
    )
    quiz = MissionTask.objects.create(
        mission=mission, order=3, task_type="quiz", data={"correct_answer": "a"}
    )
    token = str(RefreshToken.for_user(user).access_token)
    return {"user": user, "token": token, "code": code, "story": story, "quiz": quiz}


@sync_to_async
def _progress(user, task):
    from game.models import TaskProgress

    return TaskProgress.objects.filter(user=user, task=task).first()


async def _run(ctx, stream, message, *, expect_run=True):
    """Send one run message; return every event up to the terminal one."""
    with patch("game.consumers.stream_python_code", stream):
        comm = WebsocketCommunicator(
            _application(), f"/ws/runner/?token={ctx['token']}"
        )
        connected, _ = await comm.connect()
        assert connected
        await comm.send_json_to({"type": "run", **message})
        events = []
        while True:
            event = await comm.receive_json_from()
            events.append(event)
            if event["type"] in ("exit", "error") and (
                event["type"] == "exit" or not expect_run
            ):
                break
        if not expect_run:
            # a refusal must close the socket: no "exit" will ever follow
            closing = await comm.receive_output(timeout=2)
            assert closing["type"] == "websocket.close"
            event["closed_with"] = closing["code"]
        await comm.disconnect()
    return events


def _stream(stdout, exit_code=0):
    def fake(code, timeout=15, stop_event=None):
        if stdout:
            yield {"type": "stdout", "data": stdout}
        yield {"type": "exit", "code": exit_code, "duration": 0.01}

    return fake


@pytest.mark.django_db(transaction=True)
async def test_correct_run_is_graded_and_verdict_precedes_exit():
    ctx = await _setup("ws_pass")
    events = await _run(ctx, _stream("Charged\n"), {"code": "print('Charged')", "task_id": ctx["code"].id})

    assert [e["type"] for e in events] == ["stdout", "result", "exit"]
    result = events[1]
    assert result["passed"] is True
    assert result["progress"]["status"] == "completed"
    assert result["progress"]["attempts"] == 1

    saved = await _progress(ctx["user"], ctx["code"])
    assert saved.status == "completed"
    assert saved.answer == {"code": "print('Charged')"}


@pytest.mark.django_db(transaction=True)
async def test_answer_key_is_never_sent_to_the_client():
    ctx = await _setup("ws_nokey")
    events = await _run(ctx, _stream("nope\n"), {"code": "print('nope')", "task_id": ctx["code"].id})
    assert "Charged" not in str(events)
    assert "expected" not in str(events)


@pytest.mark.django_db(transaction=True)
async def test_wrong_output_counts_an_attempt_without_completing():
    ctx = await _setup("ws_wrong")
    message = {"code": "print('Nope')", "task_id": ctx["code"].id}

    first = await _run(ctx, _stream("Nope\n"), message)
    assert first[1]["passed"] is False
    assert first[1]["progress"]["status"] == "in_progress"

    second = await _run(ctx, _stream("", exit_code=1), message)
    assert second[-2]["passed"] is False
    assert second[-2]["progress"]["attempts"] == 2

    saved = await _progress(ctx["user"], ctx["code"])
    assert (saved.status, saved.attempts, saved.best_score) == ("in_progress", 2, 0)


@pytest.mark.django_db(transaction=True)
async def test_run_without_task_id_is_not_graded():
    ctx = await _setup("ws_free")
    events = await _run(ctx, _stream("Charged\n"), {"code": "print('Charged')"})
    assert [e["type"] for e in events] == ["stdout", "exit"]
    assert await _progress(ctx["user"], ctx["code"]) is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("task_id", [999999, "1", 1.5, True, [1]])
async def test_unknown_or_malformed_task_id_never_runs_the_code(task_id):
    ctx = await _setup("ws_bad")
    stream = MagicMock()
    events = await _run(
        ctx, stream, {"code": "print(1)", "task_id": task_id}, expect_run=False
    )
    assert events[-1]["type"] == "error"
    stream.assert_not_called()


@pytest.mark.django_db(transaction=True)
async def test_only_code_tasks_can_be_run_for_grading():
    ctx = await _setup("ws_quiz")
    stream = MagicMock()
    events = await _run(
        ctx, stream, {"code": "print(1)", "task_id": ctx["quiz"].id}, expect_run=False
    )
    assert events[-1]["type"] == "error"
    stream.assert_not_called()


@pytest.mark.django_db(transaction=True)
async def test_locked_step_is_refused_before_the_code_runs():
    ctx = await _setup("ws_locked", with_story=True)  # story (step 1) not done yet
    stream = MagicMock()
    events = await _run(
        ctx, stream, {"code": "print('Charged')", "task_id": ctx["code"].id}, expect_run=False
    )
    assert events[-1]["type"] == "error"
    assert events[-1]["closed_with"] == 4403
    assert "previous" in events[-1]["message"].lower()
    stream.assert_not_called()
    assert await _progress(ctx["user"], ctx["code"]) is None


@pytest.mark.django_db(transaction=True)
async def test_level_gate_is_enforced_on_the_runner():
    ctx = await _setup("ws_level", min_level=9)
    stream = MagicMock()
    events = await _run(
        ctx, stream, {"code": "print(1)", "task_id": ctx["code"].id}, expect_run=False
    )
    assert events[-1]["type"] == "error"
    stream.assert_not_called()


# ── end to end: real code, real subprocess, real grading ───────────────────


def _no_docker(*args, **kwargs):
    raise RuntimeError("docker daemon not available")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "source, passed",
    [
        ("print('Charged')", True),
        ("print('Not charged')", False),
        ("raise RuntimeError('boom')", False),
        ("print('Charged'); import sys; sys.exit(3)", False),
    ],
)
async def test_real_run_is_graded_end_to_end(settings, source, passed):
    from game import runner

    settings.RUNNER_ALLOW_UNSAFE_FALLBACK = True  # local subprocess, dev only
    settings.RUNNER_JUDGE0_URL = ""
    ctx = await _setup(f"ws_e2e_{abs(hash(source))}")

    with patch.object(runner.docker, "from_env", _no_docker):
        events = await _run(
            ctx, runner.stream_python_code, {"code": source, "task_id": ctx["code"].id}
        )

    result = next(e for e in events if e["type"] == "result")
    assert result["passed"] is passed
    assert events.index(result) < len(events) - 1  # verdict arrives before exit
    assert events[-1]["type"] == "exit"
    saved = await _progress(ctx["user"], ctx["code"])
    assert saved.status == ("completed" if passed else "in_progress")
    assert saved.attempts == 1
