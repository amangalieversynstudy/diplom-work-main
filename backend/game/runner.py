"""Sandboxed Python code execution helpers.

Two entry points are exposed:

* ``execute_python_code(code, timeout=5)`` — synchronous, one-shot. Runs the
  code in an isolated Alpine container and returns the full stdout/stderr
  blob together with a status flag. Used by the REST ``/api/runner/execute/``
  endpoint as a non-streaming fallback (CI / batch / smoke tests).

* ``stream_python_code(code, timeout=15, stop_event=None)`` — generator that
  yields events as the code runs: ``stdout`` / ``stderr`` chunks, an optional
  ``error`` message, and a final ``exit`` event with the return code and
  wall-clock duration. Used by the WebSocket ``RunnerConsumer`` to power the
  interactive terminal UI.

Both functions rely on the same hardening:

* image:        ``python:3.11-alpine``
* memory:       128 MB
* PIDs:         ≤ 64 (fork-bomb mitigation, streaming path only)
* network:      disabled (``network_mode='none'``)
* CPU/timeout:  hard kill after ``timeout`` seconds
* output:       capped at ``MAX_OUTPUT_SIZE`` bytes; container killed if
                exceeded

Decoding is UTF-8 with ``errors='replace'`` so binary noise can never crash
the consumer.
"""

import struct
import threading
import time

import docker
from requests.exceptions import ReadTimeout

# Hard cap on total bytes of stdout+stderr forwarded to the user. Protects
# memory on both server and client; users see a single truncation message
# instead of an OOM.
MAX_OUTPUT_SIZE = 50 * 1024  # 50 KB


# ──────────────────────────────────────────────────────────────────────────
# Synchronous one-shot runner (REST fallback)
# ──────────────────────────────────────────────────────────────────────────

def execute_python_code(code: str, timeout: int = 5) -> dict:
    """Run ``code`` in an isolated container and return the entire output blob.

    Returns ``{"status": "success"|"error", "output": "..."}``. Used by the
    REST endpoint where streaming is unnecessary.
    """
    try:
        client = docker.from_env()
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "output": f"Docker недоступен: {e}"}

    container = None
    try:
        container = client.containers.run(
            image="python:3.11-alpine",
            command=["python", "-c", code],
            detach=True,
            mem_limit="128m",
            network_mode="none",
        )
        result = container.wait(timeout=timeout)
        raw_logs = container.logs(stdout=True, stderr=True)

        if len(raw_logs) > MAX_OUTPUT_SIZE:
            raw_logs = (
                raw_logs[:MAX_OUTPUT_SIZE]
                + b"\n\n... [\xd0\x92\xd0\xab\xd0\x92\xd0\x9e\xd0\x94 \xd0\x9e\xd0\x91\xd0\xa0\xd0\x95\xd0\x97\xd0\x90\xd0\x9d] ..."  # noqa: E501
            )

        logs = raw_logs.decode("utf-8", errors="replace")

        if result.get("StatusCode", 0) == 0:
            return {"status": "success", "output": logs}
        return {"status": "error", "output": logs}

    except ReadTimeout:
        if container is not None:
            try:
                container.kill()
            except Exception:  # noqa: BLE001
                pass
        return {
            "status": "error",
            "output": f"Timeout: Код выполнялся дольше {timeout} секунд и был прерван.",
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "output": f"Ошибка песочницы: {e}"}
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:  # noqa: BLE001
                pass


# ──────────────────────────────────────────────────────────────────────────
# Streaming runner (WebSocket terminal)
# ──────────────────────────────────────────────────────────────────────────

# Docker multiplexed stream header: 8 bytes = [stream_type, 0, 0, 0, size(big-endian uint32)]
# stream_type: 1 = stdout, 2 = stderr.
_FRAME_HEADER = struct.Struct(">BBBBI")


def stream_python_code(code: str, timeout: int = 15, stop_event=None):
    """Generator: yield runtime events as the code executes.

    Events:
        ``{"type": "stdout"|"stderr", "data": <str>}``
        ``{"type": "error", "message": <str>}``  (infrastructure / overflow / timeout)
        ``{"type": "exit", "code": <int>, "duration": <float seconds>}``

    The generator is fully self-cleaning: container is always removed on exit,
    even if the caller stops iterating early. If ``stop_event`` is provided
    and gets set, the container is killed and iteration stops with a final
    exit event (code -1 if no natural exit was observed).
    """
    started_at = time.time()

    try:
        client = docker.from_env()
    except Exception as e:  # noqa: BLE001
        yield {"type": "error", "message": f"Docker недоступен: {e}"}
        yield {"type": "exit", "code": -1, "duration": time.time() - started_at}
        return

    container = None
    raw_sock = None
    truncated = False
    killed_by_timeout = False
    killed_by_stop = False

    try:
        # Create stopped first so we can attach BEFORE the process starts and
        # never miss the first lines of output.
        container = client.containers.create(
            image="python:3.11-alpine",
            command=["python", "-u", "-c", code],  # -u: unbuffered stdout/stderr
            mem_limit="128m",
            pids_limit=64,
            network_mode="none",
            stdin_open=False,
            tty=False,
        )

        sock = client.api.attach_socket(
            container.id,
            params={"stream": 1, "stdout": 1, "stderr": 1, "logs": 0},
        )
        # docker-py returns either a SocketIO wrapper (has ._sock) or a raw
        # socket depending on the transport (unix vs npipe). Normalize.
        raw_sock = getattr(sock, "_sock", sock)
        raw_sock.settimeout(0.5)

        container.start()

        # ── Watchdog: hard timeout ────────────────────────────────────────
        def _watchdog():
            nonlocal killed_by_timeout
            deadline = time.time() + timeout
            while time.time() < deadline:
                time.sleep(0.25)
                try:
                    container.reload()
                    if container.status == "exited":
                        return
                except Exception:  # noqa: BLE001
                    return
                if stop_event is not None and stop_event.is_set():
                    return
            try:
                container.kill()
                killed_by_timeout = True
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=_watchdog, daemon=True).start()

        # ── Read & demultiplex stream ─────────────────────────────────────
        buffer = b""
        total_bytes = 0

        while True:
            # Honour cooperative cancellation from the consumer.
            if stop_event is not None and stop_event.is_set():
                killed_by_stop = True
                try:
                    container.kill()
                except Exception:  # noqa: BLE001
                    pass
                break

            try:
                chunk = raw_sock.recv(4096)
            except (TimeoutError, OSError):
                # recv timeout. Check if container is done; if so, drain and exit.
                try:
                    container.reload()
                    if container.status == "exited":
                        # One last drain attempt with a slightly longer timeout.
                        raw_sock.settimeout(0.1)
                        try:
                            tail = raw_sock.recv(65536)
                            if tail:
                                buffer += tail
                        except (TimeoutError, OSError):
                            pass
                        break
                except Exception:  # noqa: BLE001
                    break
                continue

            if not chunk:
                break
            buffer += chunk

            # Parse as many complete multiplexed frames as we have.
            while len(buffer) >= 8:
                stream_type, _, _, _, size = _FRAME_HEADER.unpack(buffer[:8])
                if len(buffer) < 8 + size:
                    break
                payload = buffer[8:8 + size]
                buffer = buffer[8 + size:]

                if truncated:
                    continue

                total_bytes += len(payload)
                if total_bytes > MAX_OUTPUT_SIZE:
                    truncated = True
                    yield {
                        "type": "error",
                        "message": f"Вывод обрезан: превышен лимит {MAX_OUTPUT_SIZE // 1024} KB",
                    }
                    try:
                        container.kill()
                    except Exception:  # noqa: BLE001
                        pass
                    break

                text = payload.decode("utf-8", errors="replace")
                yield {
                    "type": "stderr" if stream_type == 2 else "stdout",
                    "data": text,
                }

            if truncated:
                break

        # Flush any trailing complete frames we drained after exit.
        while len(buffer) >= 8 and not truncated:
            stream_type, _, _, _, size = _FRAME_HEADER.unpack(buffer[:8])
            if len(buffer) < 8 + size:
                break
            payload = buffer[8:8 + size]
            buffer = buffer[8 + size:]
            total_bytes += len(payload)
            if total_bytes > MAX_OUTPUT_SIZE:
                truncated = True
                yield {
                    "type": "error",
                    "message": f"Вывод обрезан: превышен лимит {MAX_OUTPUT_SIZE // 1024} KB",
                }
                break
            yield {
                "type": "stderr" if stream_type == 2 else "stdout",
                "data": payload.decode("utf-8", errors="replace"),
            }

        # ── Final exit code ───────────────────────────────────────────────
        try:
            result = container.wait(timeout=2)
            exit_code = int(result.get("StatusCode", -1))
        except Exception:  # noqa: BLE001
            exit_code = -1

        duration = time.time() - started_at

        if killed_by_timeout:
            yield {"type": "error", "message": f"Timeout: код прерван после {timeout}с"}
        elif killed_by_stop:
            yield {"type": "error", "message": "Сессия остановлена клиентом"}

        yield {"type": "exit", "code": exit_code, "duration": duration}

    except Exception as e:  # noqa: BLE001
        yield {"type": "error", "message": f"Ошибка песочницы: {e}"}
        yield {"type": "exit", "code": -1, "duration": time.time() - started_at}
    finally:
        if raw_sock is not None:
            try:
                raw_sock.close()
            except Exception:  # noqa: BLE001
                pass
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:  # noqa: BLE001
                pass
