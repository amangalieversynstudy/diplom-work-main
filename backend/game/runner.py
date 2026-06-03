"""Запуск Python-кода в изолированном Docker-контейнере (sandbox).

Здесь две функции: execute_python_code — синхронный запуск, отдаёт всё разом
(используется в REST /runner/execute/), и stream_python_code — генератор,
шлёт события по мере выполнения (используется в WebSocket RunnerConsumer).

Лимиты: 128 MB RAM, 64 PID, нет сети, hard-kill по таймауту.
"""

import struct
import subprocess
import sys
import threading
import time

import docker
from requests.exceptions import ReadTimeout


# максимум 50 KB вывода — иначе обрезаем
MAX_OUTPUT_SIZE = 50 * 1024

# ограничения Docker-песочницы (общие для sync и streaming путей)
_SANDBOX_KWARGS = dict(
    mem_limit="128m",
    pids_limit=64,
    network_mode="none",
    read_only=True,                       # корневой ФС только на чтение
    tmpfs={"/tmp": "size=16m,mode=1777"},  # /tmp в памяти, чтобы код мог писать врем. файлы
    cap_drop=["ALL"],                     # снимаем все Linux capabilities
    security_opt=["no-new-privileges"],   # запрет эскалации прав
    nano_cpus=500_000_000,                # 0.5 CPU
)

_RUNNER_DISABLED_MSG = (
    "Запуск кода недоступен в этом окружении: безопасной Docker-песочницы нет, "
    "а небезопасный режим отключён (RUNNER_ALLOW_UNSAFE_FALLBACK=False)."
)


def _unsafe_fallback_allowed() -> bool:
    """Subprocess-фолбэк запускает код БЕЗ изоляции. На проде он запрещён,
    чтобы исключить RCE; локально и в тестах по умолчанию разрешён."""
    try:
        from django.conf import settings
        return bool(getattr(settings, "RUNNER_ALLOW_UNSAFE_FALLBACK", True))
    except Exception:
        return True


def _runner_disabled_result() -> dict:
    return {"status": "error", "output": _RUNNER_DISABLED_MSG}


def _runner_disabled_stream(started_at: float):
    yield {"type": "error", "message": _RUNNER_DISABLED_MSG}
    yield {"type": "exit", "code": -1, "duration": time.time() - started_at}


def _execute_subprocess_fallback(code: str, timeout: int = 5) -> dict:
    """Fallback без Docker — запускает через subprocess. Используется в средах
    типа Railway, где Docker-in-Docker недоступен. Песочницы нет, поэтому
    подходит только для доверенного кода (демо/защита диплома)."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            timeout=timeout,
            text=True,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        if len(output) > MAX_OUTPUT_SIZE:
            output = output[:MAX_OUTPUT_SIZE] + "\n\n... [ВЫВОД ОБРЕЗАН] ..."
        return {
            "status": "success" if proc.returncode == 0 else "error",
            "output": output,
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "output": f"Timeout: код выполнялся дольше {timeout} сек."}
    except Exception as e:
        return {"status": "error", "output": f"Ошибка выполнения: {e}"}


def _stream_subprocess_fallback(code: str, timeout: int, stop_event, started_at: float):
    """Fallback стриминга через subprocess — построчно читаем stdout/stderr."""
    proc = None
    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        killed_by_timeout = False
        killed_by_stop = False
        deadline = time.time() + timeout
        total_bytes = 0
        truncated = False

        # читаем стрим неблокируясь по таймауту строки
        import selectors
        sel = selectors.DefaultSelector()
        sel.register(proc.stdout, selectors.EVENT_READ, "stdout")
        sel.register(proc.stderr, selectors.EVENT_READ, "stderr")

        while True:
            if time.time() > deadline:
                killed_by_timeout = True
                proc.kill()
                break
            if stop_event is not None and stop_event.is_set():
                killed_by_stop = True
                proc.kill()
                break

            events = sel.select(timeout=0.2)
            if not events and proc.poll() is not None:
                break

            for key, _ in events:
                line = key.fileobj.readline()
                if not line:
                    try:
                        sel.unregister(key.fileobj)
                    except KeyError:
                        pass
                    continue
                total_bytes += len(line)
                if total_bytes > MAX_OUTPUT_SIZE and not truncated:
                    truncated = True
                    yield {"type": "error", "message": f"Вывод обрезан: лимит {MAX_OUTPUT_SIZE // 1024} KB"}
                    proc.kill()
                    break
                if not truncated:
                    yield {"type": key.data, "data": line}

            if truncated:
                break

        # добиваем остатки
        try:
            out, err = proc.communicate(timeout=1)
            if out and not truncated:
                yield {"type": "stdout", "data": out}
            if err and not truncated:
                yield {"type": "stderr", "data": err}
        except subprocess.TimeoutExpired:
            proc.kill()

        exit_code = proc.returncode if proc.returncode is not None else -1
        duration = time.time() - started_at

        if killed_by_timeout:
            yield {"type": "error", "message": f"Timeout: код прерван после {timeout}с"}
        elif killed_by_stop:
            yield {"type": "error", "message": "Сессия остановлена клиентом"}

        yield {"type": "exit", "code": exit_code, "duration": duration}

    except Exception as e:
        yield {"type": "error", "message": f"Ошибка выполнения: {e}"}
        yield {"type": "exit", "code": -1, "duration": time.time() - started_at}
    finally:
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass


def execute_python_code(code: str, timeout: int = 5) -> dict:
    """Запускает код в контейнере и возвращает весь вывод одним блоком."""
    try:
        client = docker.from_env()
    except Exception:
        if not _unsafe_fallback_allowed():
            return _runner_disabled_result()
        return _execute_subprocess_fallback(code, timeout)

    container = None
    try:
        container = client.containers.run(
            image="python:3.11-alpine",
            command=["python", "-c", code],
            detach=True,
            **_SANDBOX_KWARGS,
        )
        result = container.wait(timeout=timeout)
        raw_logs = container.logs(stdout=True, stderr=True)

        if len(raw_logs) > MAX_OUTPUT_SIZE:
            raw_logs = raw_logs[:MAX_OUTPUT_SIZE] + "\n\n... [ВЫВОД ОБРЕЗАН] ...".encode("utf-8")

        logs = raw_logs.decode("utf-8", errors="replace")

        if result.get("StatusCode", 0) == 0:
            return {"status": "success", "output": logs}
        return {"status": "error", "output": logs}

    except ReadTimeout:
        if container is not None:
            try:
                container.kill()
            except Exception:
                pass
        return {
            "status": "error",
            "output": f"Timeout: код выполнялся дольше {timeout} сек.",
        }
    except Exception as e:
        return {"status": "error", "output": f"Ошибка песочницы: {e}"}
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass


# заголовок мультиплексного потока Docker: 8 байт, первый — тип (1=stdout, 2=stderr)
_FRAME_HEADER = struct.Struct(">BBBBI")


def stream_python_code(code: str, timeout: int = 15, stop_event=None):
    """Генератор: выдаёт события по мере выполнения кода.

    События:
        {"type": "stdout"|"stderr", "data": ...}
        {"type": "error", "message": ...}
        {"type": "exit", "code": int, "duration": float}
    """
    started_at = time.time()

    try:
        client = docker.from_env()
    except Exception:
        # Docker недоступен. Subprocess-фолбэк не изолирован — на проде запрещён.
        if not _unsafe_fallback_allowed():
            yield from _runner_disabled_stream(started_at)
            return
        yield from _stream_subprocess_fallback(code, timeout, stop_event, started_at)
        return

    container = None
    raw_sock = None
    truncated = False
    killed_by_timeout = False
    killed_by_stop = False

    try:
        # создаём контейнер до старта, чтобы успеть подключить сокет
        container = client.containers.create(
            image="python:3.11-alpine",
            command=["python", "-u", "-c", code],  # -u: без буферизации stdout
            stdin_open=False,
            tty=False,
            **_SANDBOX_KWARGS,
        )

        sock = client.api.attach_socket(
            container.id,
            params={"stream": 1, "stdout": 1, "stderr": 1, "logs": 0},
        )
        # docker-py возвращает либо обёртку с _sock, либо сырой сокет
        raw_sock = getattr(sock, "_sock", sock)
        raw_sock.settimeout(0.5)

        container.start()

        # watchdog для таймаута
        def _watchdog():
            nonlocal killed_by_timeout
            deadline = time.time() + timeout
            while time.time() < deadline:
                time.sleep(0.25)
                try:
                    container.reload()
                    if container.status == "exited":
                        return
                except Exception:
                    return
                if stop_event is not None and stop_event.is_set():
                    return
            try:
                container.kill()
                killed_by_timeout = True
            except Exception:
                pass

        threading.Thread(target=_watchdog, daemon=True).start()

        # читаем поток
        buffer = b""
        total_bytes = 0

        while True:
            # проверка на отмену от клиента
            if stop_event is not None and stop_event.is_set():
                killed_by_stop = True
                try:
                    container.kill()
                except Exception:
                    pass
                break

            try:
                chunk = raw_sock.recv(4096)
            except (TimeoutError, OSError):
                # таймаут recv — смотрим, может контейнер уже закончил
                try:
                    container.reload()
                    if container.status == "exited":
                        # последняя попытка добрать хвост
                        raw_sock.settimeout(0.1)
                        try:
                            tail = raw_sock.recv(65536)
                            if tail:
                                buffer += tail
                        except (TimeoutError, OSError):
                            pass
                        break
                except Exception:
                    break
                continue

            if not chunk:
                break
            buffer += chunk

            # парсим все целые фреймы из буфера
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
                        "message": f"Вывод обрезан: лимит {MAX_OUTPUT_SIZE // 1024} KB",
                    }
                    try:
                        container.kill()
                    except Exception:
                        pass
                    break

                text = payload.decode("utf-8", errors="replace")
                yield {
                    "type": "stderr" if stream_type == 2 else "stdout",
                    "data": text,
                }

            if truncated:
                break

        # добиваем хвост буфера если что-то осталось
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
                    "message": f"Вывод обрезан: лимит {MAX_OUTPUT_SIZE // 1024} KB",
                }
                break
            yield {
                "type": "stderr" if stream_type == 2 else "stdout",
                "data": payload.decode("utf-8", errors="replace"),
            }

        # финальный exit-код
        try:
            result = container.wait(timeout=2)
            exit_code = int(result.get("StatusCode", -1))
        except Exception:
            exit_code = -1

        duration = time.time() - started_at

        if killed_by_timeout:
            yield {"type": "error", "message": f"Timeout: код прерван после {timeout}с"}
        elif killed_by_stop:
            yield {"type": "error", "message": "Сессия остановлена клиентом"}

        yield {"type": "exit", "code": exit_code, "duration": duration}

    except Exception as e:
        yield {"type": "error", "message": f"Ошибка песочницы: {e}"}
        yield {"type": "exit", "code": -1, "duration": time.time() - started_at}
    finally:
        if raw_sock is not None:
            try:
                raw_sock.close()
            except Exception:
                pass
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass
