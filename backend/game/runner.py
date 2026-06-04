"""Запуск Python-кода в изолированном Docker-контейнере (sandbox).

Здесь две функции: execute_python_code — синхронный запуск, отдаёт всё разом
(используется в REST /runner/execute/), и stream_python_code — генератор,
шлёт события по мере выполнения (используется в WebSocket RunnerConsumer).

Лимиты: 128 MB RAM, 64 PID, нет сети, hard-kill по таймауту.
"""

import os
import struct
import subprocess
import sys
import tempfile
import threading
import time

import docker
import requests
from requests.exceptions import ReadTimeout

try:  # POSIX-only; used to cap CPU/memory/procs of the local fallback
    import resource
except ImportError:  # pragma: no cover - non-POSIX dev boxes
    resource = None

try:
    import signal
except ImportError:  # pragma: no cover
    signal = None


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


# ─── Piston: внешняя песочница (emkc.org) ─────────────────────────────────
# Когда Docker недоступен, код уходит в Piston. Он исполняется НЕ на нашем
# сервере, поэтому секреты/ФС приложения недоступны. Стриминга у Piston нет —
# отдаёт весь вывод разом, что для коротких учебных скриптов нормально.

def _piston_settings():
    try:
        from django.conf import settings
        url = (getattr(settings, "RUNNER_PISTON_URL", "") or "").rstrip("/")
        version = getattr(settings, "RUNNER_PISTON_PYTHON_VERSION", "") or "3.10.0"
        return url, version
    except Exception:
        return "", "3.10.0"


def _piston_run(code: str, timeout: int):
    """Гоняет код в Piston. Возвращает {stdout, stderr, code, signal} или None,
    если Piston не сконфигурирован/недоступен/ответил ошибкой (тогда вызывающий
    уходит в локальный фолбэк)."""
    url, version = _piston_settings()
    if not url:
        return None
    try:
        resp = requests.post(
            f"{url}/execute",
            json={
                "language": "python",
                "version": version,
                "files": [{"content": code}],
                "run_timeout": max(1, timeout) * 1000,
                "compile_timeout": 10_000,
            },
            timeout=max(1, timeout) + 15,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        run = data.get("run")
        if not isinstance(run, dict):
            return None
        return {
            "stdout": run.get("stdout") or "",
            "stderr": run.get("stderr") or "",
            "code": run.get("code") if run.get("code") is not None else -1,
            "signal": run.get("signal"),
        }
    except Exception:
        return None


def _execute_via_piston(code: str, timeout: int):
    r = _piston_run(code, timeout)
    if r is None:
        return None
    output = (r["stdout"] or "") + (r["stderr"] or "")
    if len(output) > MAX_OUTPUT_SIZE:
        output = output[:MAX_OUTPUT_SIZE] + "\n\n... [ВЫВОД ОБРЕЗАН] ..."
    return {"status": "success" if r["code"] == 0 else "error", "output": output}


def _stream_via_piston(code: str, timeout: int, started_at: float):
    """Возвращает СПИСОК событий (stdout/stderr/exit) или None, если Piston
    недоступен. Не генератор — чтобы вызывающий мог отличить «нет Piston» от
    «Piston дал пустой вывод» и корректно уйти в фолбэк."""
    r = _piston_run(code, timeout)
    if r is None:
        return None
    out = r["stdout"] or ""
    err = r["stderr"] or ""
    if len(out) > MAX_OUTPUT_SIZE:
        out = out[:MAX_OUTPUT_SIZE] + "\n\n... [ВЫВОД ОБРЕЗАН] ..."
    events = []
    if out:
        events.append({"type": "stdout", "data": out})
    if err:
        events.append({"type": "stderr", "data": err})
    if r.get("signal"):
        events.append({
            "type": "error",
            "message": f"Процесс остановлен сигналом {r['signal']} (таймаут или лимит ресурсов).",
        })
    events.append({"type": "exit", "code": r["code"], "duration": time.time() - started_at})
    return events


# ─── усиление локального subprocess-фолбэка ───────────────────────────────
# Не полноценная песочница, но снимает главные риски: очищенное окружение
# (секреты приложения недоступны), rlimits на CPU/память/файлы/процессы,
# отдельная сессия процессов (kill всей группы) и временный рабочий каталог.

def _scrubbed_env(home: str) -> dict:
    """Окружение БЕЗ секретов приложения (GEMINI_API_KEY, креды БД, JWT-ключ)."""
    return {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HOME": home,
        "TMPDIR": home,
        "PATH": "/usr/bin:/bin",
    }


def _make_rlimit_preexec(timeout: int):
    """preexec_fn: ставит rlimits в дочернем процессе. Делает ТОЛЬКО syscalls
    setrlimit (без аллокаций/локов), поэтому безопасно в многопоточном сервере."""
    cpu = max(1, timeout) + 1

    def _preexec():
        limits = [
            (resource.RLIMIT_CPU, (cpu, cpu)),
            (resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024)),
            (resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024)),
            (resource.RLIMIT_CORE, (0, 0)),
        ]
        try:
            limits.append((resource.RLIMIT_NPROC, (100, 100)))
        except Exception:
            pass
        for res, val in limits:
            try:
                resource.setrlimit(res, val)
            except Exception:
                pass

    return _preexec


def _hardened_popen_kwargs(timeout: int, cwd: str) -> dict:
    kwargs = {"env": _scrubbed_env(cwd), "cwd": cwd}
    if os.name == "posix":
        kwargs["start_new_session"] = True  # отдельная сессия → kill группы
        if resource is not None:
            kwargs["preexec_fn"] = _make_rlimit_preexec(timeout)
    return kwargs


def _kill_proc_tree(proc) -> None:
    """Убивает процесс вместе с детьми (по группе, если POSIX)."""
    try:
        if os.name == "posix" and hasattr(os, "killpg") and signal is not None:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            return
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def _execute_subprocess_fallback(code: str, timeout: int = 5) -> dict:
    """Локальный фолбэк без Docker (резерв на случай недоступности Piston).
    Усилен: очищенное окружение без секретов, rlimits, отдельная сессия,
    временный cwd. Не полноценная песочница — исходящую сеть и чтение мира не
    блокирует, поэтому включается только под флагом RUNNER_ALLOW_UNSAFE_FALLBACK."""
    try:
        with tempfile.TemporaryDirectory(prefix="runner_") as cwd:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", code],
                capture_output=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                **_hardened_popen_kwargs(timeout, cwd),
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
    """Локальный стриминг-фолбэк через subprocess (резерв, если Piston недоступен).
    Усилен так же, как _execute_subprocess_fallback: очищенное окружение,
    rlimits, отдельная сессия (kill всей группы), временный cwd."""
    proc = None
    tmp = tempfile.TemporaryDirectory(prefix="runner_")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-I", "-u", "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **_hardened_popen_kwargs(timeout, tmp.name),
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
                _kill_proc_tree(proc)
                break
            if stop_event is not None and stop_event.is_set():
                killed_by_stop = True
                _kill_proc_tree(proc)
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
                    _kill_proc_tree(proc)
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
            _kill_proc_tree(proc)

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
            _kill_proc_tree(proc)
        try:
            tmp.cleanup()
        except Exception:
            pass


def execute_python_code(code: str, timeout: int = 5) -> dict:
    """Запускает код в контейнере и возвращает весь вывод одним блоком."""
    try:
        client = docker.from_env()
    except Exception:
        # Docker недоступен (напр. Railway). Сначала пробуем Piston —
        # код исполнится вне нашего сервера, секреты/ФС в безопасности.
        piston = _execute_via_piston(code, timeout)
        if piston is not None:
            return piston
        # Piston не сконфигурирован/недоступен — локальный фолбэк (под флагом).
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
        # Docker недоступен (напр. Railway). Сначала Piston — код вне сервера.
        # Piston не стримит, поэтому отдаём накопленные события списком разом.
        piston_events = _stream_via_piston(code, timeout, started_at)
        if piston_events is not None:
            yield from piston_events
            return
        # Piston недоступен. Subprocess-фолбэк не изолирован — на проде запрещён.
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
