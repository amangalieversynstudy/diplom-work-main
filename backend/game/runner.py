"""Запуск Python-кода в изолированном Docker-контейнере (sandbox).

Здесь две функции: execute_python_code — синхронный запуск, отдаёт всё разом
(используется в REST /runner/execute/), и stream_python_code — генератор,
шлёт события по мере выполнения (используется в WebSocket RunnerConsumer).

Лимиты: 128 MB RAM, 64 PID, нет сети, hard-kill по таймауту.
"""

import struct
import threading
import time

import docker
from requests.exceptions import ReadTimeout


# максимум 50 KB вывода — иначе обрезаем
MAX_OUTPUT_SIZE = 50 * 1024


def execute_python_code(code: str, timeout: int = 5) -> dict:
    """Запускает код в контейнере и возвращает весь вывод одним блоком."""
    try:
        client = docker.from_env()
    except Exception as e:
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
            raw_logs = raw_logs[:MAX_OUTPUT_SIZE] + b"\n\n... [ВЫВОД ОБРЕЗАН] ..."

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
    except Exception as e:
        yield {"type": "error", "message": f"Docker недоступен: {e}"}
        yield {"type": "exit", "code": -1, "duration": time.time() - started_at}
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
