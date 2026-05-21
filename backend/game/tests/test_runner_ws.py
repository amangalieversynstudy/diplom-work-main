"""Async tests for the WebSocket runner consumer.

The real Docker sandbox is exercised only via manual smoke testing; here we
patch ``stream_python_code`` so the consumer logic, JWT handshake, and
message protocol are verified deterministically and without Docker.
"""

import asyncio
from unittest.mock import patch

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import RefreshToken


pytestmark = pytest.mark.asyncio


async def _make_user_and_token(username: str, password: str = "pw") -> tuple:
    """Create a Django user and mint a short-lived JWT for them (async-safe)."""
    from users.models import User

    user = await sync_to_async(User.objects.create_user)(
        username=username, password=password
    )
    token = await sync_to_async(
        lambda u: str(RefreshToken.for_user(u).access_token)
    )(user)
    return user, token


def _get_application():
    """Late-import the ASGI application so Django settings are configured first."""
    from core.asgi import application
    return application


async def test_anonymous_connection_refused():
    """Connecting without a token must be rejected with code 4401."""
    communicator = WebsocketCommunicator(_get_application(), "/ws/runner/")
    connected, close_code = await communicator.connect()
    assert connected is False
    assert close_code == 4401


async def test_invalid_token_refused():
    """A malformed JWT must be treated as anonymous → rejected."""
    communicator = WebsocketCommunicator(
        _get_application(), "/ws/runner/?token=not-a-real-jwt"
    )
    connected, close_code = await communicator.connect()
    assert connected is False
    assert close_code == 4401


@pytest.mark.django_db(transaction=True)
async def test_authenticated_run_streams_events():
    """Happy path: authenticated user runs code and receives stdout + exit."""
    _, token = await _make_user_and_token("wstest_ok")

    def fake_stream(code, timeout=15, stop_event=None):
        yield {"type": "stdout", "data": "Hello\n"}
        yield {"type": "stdout", "data": "World\n"}
        yield {"type": "exit", "code": 0, "duration": 0.05}

    with patch("game.consumers.stream_python_code", fake_stream):
        comm = WebsocketCommunicator(
            _get_application(), f"/ws/runner/?token={token}"
        )
        connected, _ = await comm.connect()
        assert connected, "expected JWT-authenticated connection to succeed"

        await comm.send_json_to({"type": "run", "code": "print('Hello')\nprint('World')"})

        first = await comm.receive_json_from()
        assert first == {"type": "stdout", "data": "Hello\n"}

        second = await comm.receive_json_from()
        assert second == {"type": "stdout", "data": "World\n"}

        third = await comm.receive_json_from()
        assert third["type"] == "exit"
        assert third["code"] == 0
        assert third["duration"] == pytest.approx(0.05, abs=0.01)

        await comm.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_stderr_event_forwarded():
    """stderr events must be forwarded unchanged so the UI can colour them."""
    _, token = await _make_user_and_token("wstest_err")

    def fake_stream(code, timeout=15, stop_event=None):
        yield {"type": "stderr", "data": "Traceback (most recent call last):\n"}
        yield {"type": "exit", "code": 1, "duration": 0.01}

    with patch("game.consumers.stream_python_code", fake_stream):
        comm = WebsocketCommunicator(
            _get_application(), f"/ws/runner/?token={token}"
        )
        connected, _ = await comm.connect()
        assert connected

        await comm.send_json_to({"type": "run", "code": "raise RuntimeError()"})

        msg = await comm.receive_json_from()
        assert msg["type"] == "stderr"
        assert "Traceback" in msg["data"]

        exit_msg = await comm.receive_json_from()
        assert exit_msg["type"] == "exit"
        assert exit_msg["code"] == 1

        await comm.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_empty_code_rejected():
    """Empty / whitespace-only code is rejected without invoking the runner."""
    _, token = await _make_user_and_token("wstest_empty")

    with patch("game.consumers.stream_python_code") as mock_stream:
        comm = WebsocketCommunicator(
            _get_application(), f"/ws/runner/?token={token}"
        )
        connected, _ = await comm.connect()
        assert connected

        await comm.send_json_to({"type": "run", "code": "   \n   "})

        msg = await comm.receive_json_from()
        assert msg["type"] == "error"
        assert "empty" in msg["message"].lower()
        assert not mock_stream.called

        await comm.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_invalid_json_rejected():
    """Garbage payload yields an error event, not a crash."""
    _, token = await _make_user_and_token("wstest_json")

    comm = WebsocketCommunicator(
        _get_application(), f"/ws/runner/?token={token}"
    )
    connected, _ = await comm.connect()
    assert connected

    await comm.send_to(text_data="this is not JSON {")

    msg = await comm.receive_json_from()
    assert msg["type"] == "error"
    assert "json" in msg["message"].lower()

    await comm.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_unknown_message_type_rejected():
    _, token = await _make_user_and_token("wstest_unknown")

    comm = WebsocketCommunicator(
        _get_application(), f"/ws/runner/?token={token}"
    )
    connected, _ = await comm.connect()
    assert connected

    await comm.send_json_to({"type": "explode"})
    msg = await comm.receive_json_from()
    assert msg["type"] == "error"
    assert "unknown" in msg["message"].lower()

    await comm.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_concurrent_run_rejected():
    """A second ``run`` while one is in-flight must be rejected, not race."""
    _, token = await _make_user_and_token("wstest_concurrent")

    # Block the producer until we explicitly release it so we can assert the
    # second request is rejected while the first is still running.
    release = asyncio.Event()

    def slow_stream(code, timeout=15, stop_event=None):
        # Yield one chunk, then wait, then exit.
        yield {"type": "stdout", "data": "starting\n"}
        # Synchronously wait until release is set. We can't await here
        # (sync generator), so spin-poll briefly.
        import time
        for _ in range(200):  # max ~2s
            if release.is_set():
                break
            time.sleep(0.01)
        yield {"type": "exit", "code": 0, "duration": 0.1}

    with patch("game.consumers.stream_python_code", slow_stream):
        comm = WebsocketCommunicator(
            _get_application(), f"/ws/runner/?token={token}"
        )
        connected, _ = await comm.connect()
        assert connected

        await comm.send_json_to({"type": "run", "code": "print('one')"})
        first = await comm.receive_json_from()
        assert first["data"] == "starting\n"

        # Second run while the first is still pending → error.
        await comm.send_json_to({"type": "run", "code": "print('two')"})
        rej = await comm.receive_json_from()
        assert rej["type"] == "error"
        assert "already" in rej["message"].lower()

        # Let the producer finish so we drain cleanly.
        release.set()
        exit_msg = await comm.receive_json_from()
        assert exit_msg["type"] == "exit"

        await comm.disconnect()
