"""Жёсткие security-тесты для Docker-песочницы (backend/game/runner.py).

Здесь проверяются три класса атак, которые комиссия обязательно спросит:

1. **CPU-flood (бесконечный цикл)** — `while True: pass`.
   Должен быть убит watchdog'ом по таймауту, контейнер удалён.

2. **Network isolation** — попытка `socket.create_connection(...)` или
   HTTP-запроса наружу. Должна провалиться, так как `network_mode="none"`.

3. **Filesystem write outside sandbox** — попытка прочитать секрет с
   хоста (`/etc/shadow`) или примонтировать том. Контейнер запущен с
   read-only корневой ФС и без проброса хост-путей, поэтому код
   не получает доступа к чувствительным файлам хоста.

Тесты требуют запущенного Docker (запускаются только если
`docker.from_env().ping()` отвечает; иначе пропускаются).
"""

import pytest

try:
    import docker as _docker  # noqa: F401
    _docker.from_env().ping()
    DOCKER_AVAILABLE = True
except Exception:
    DOCKER_AVAILABLE = False

from game.runner import execute_python_code

pytestmark = pytest.mark.skipif(
    not DOCKER_AVAILABLE,
    reason="Docker daemon недоступен в тестовом окружении",
)


def test_sandbox_kills_infinite_loop_by_timeout():
    """CRITICAL: бесконечный цикл должен быть убит timeout'ом.

    Если этот тест зависнет — у тебя дыра: вредонос может задействовать
    100% CPU хоста, и Daphne больше не примет ни одного запроса.
    """
    malicious_code = "while True:\n    pass\n"

    result = execute_python_code(malicious_code, timeout=2)

    assert result["status"] == "error", (
        f"Sandbox НЕ убил бесконечный цикл за 2 секунды: {result!r}"
    )
    assert "timeout" in result["output"].lower() or "timed out" in result["output"].lower(), (
        f"Ошибка должна явно сообщать про таймаут, чтобы фронт показал юзеру "
        f"сообщение, а не зависший спиннер. Реальный ответ: {result!r}"
    )


def test_sandbox_blocks_outbound_network():
    """SECURITY: контейнер не должен иметь сетевого доступа.

    Если этот тест упадёт — потенциальная утечка: код студента сможет
    стучаться на внешние сервисы (например, OpenAI или метаданные хоста)
    и выкачивать оттуда токены.
    """
    network_probe = (
        "import socket\n"
        "try:\n"
        "    s = socket.create_connection(('1.1.1.1', 80), timeout=2)\n"
        "    print('LEAK:network_available')\n"
        "    s.close()\n"
        "except Exception as e:\n"
        "    print('OK:network_blocked', type(e).__name__)\n"
    )

    result = execute_python_code(network_probe, timeout=5)

    assert "LEAK:network_available" not in result["output"], (
        f"Sandbox имеет выход в сеть! Ответ: {result!r}"
    )
    assert "OK:network_blocked" in result["output"], (
        f"Ожидаем явное подтверждение блокировки. Ответ: {result!r}"
    )


def test_sandbox_cannot_read_host_secrets():
    """SECURITY: контейнер не должен видеть файлы хоста.

    /etc/shadow есть только на хосте Linux и содержит пароли. Контейнер
    запускается из чистого образа python:3.11-alpine — у него своё /etc,
    куда хост-файлы не пробрасываются.

    Если тест найдёт root: или подобные строки — это серьёзная дыра
    конфигурации Docker (`-v /:/host` или escape через privileged-флаг).
    """
    file_probe = (
        "import os\n"
        "for path in ['/etc/shadow', '/etc/passwd', '/proc/1/cgroup']:\n"
        "    try:\n"
        "        with open(path, 'r') as f:\n"
        "            content = f.read()\n"
        "        print(f'READ:{path}:{len(content)}:{content[:80]!r}')\n"
        "    except Exception as e:\n"
        "        print(f'BLOCKED:{path}:{type(e).__name__}')\n"
    )

    result = execute_python_code(file_probe, timeout=5)
    output = result["output"]

    # /etc/shadow в alpine-образе либо отсутствует, либо пустой/недоступен
    # для непривилегированного процесса. Главное — никаких host-секретов.
    shadow_lines = [ln for ln in output.splitlines() if "/etc/shadow" in ln]
    for line in shadow_lines:
        # Если файл прочитан — он должен быть пустым (контейнерный /etc/shadow),
        # а не содержать реальные хеши паролей с двоеточиями и солью.
        if line.startswith("READ:/etc/shadow"):
            # пример хеша: $6$rounds=...$abcdef:18000:0:99999::: — содержит ':' и '$'
            assert "$" not in line, (
                f"В /etc/shadow контейнера видны хеши паролей — "
                f"возможно, примонтирован /etc хоста. Ответ:\n{output}"
            )

    # /proc/1/cgroup должен показывать docker/containerd — это нормально и
    # подтверждает, что мы внутри контейнера, а не на хосте.
    assert "READ:/proc/1/cgroup" in output or "BLOCKED:/proc/1/cgroup" in output, (
        f"Неожиданный ответ песочницы. Output:\n{output}"
    )
