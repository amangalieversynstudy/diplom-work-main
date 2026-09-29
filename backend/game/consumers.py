"""WebSocket-консьюмер для стриминга выполнения кода в реальном времени.

Протокол: клиент шлёт {"type": "run", "code": "...", "task_id": <id>?}, сервер
шлёт обратно события stdout/stderr/error/exit. Один запуск на соединение,
ограничение кода 100 KB. Безопасность держится на песочнице из runner.py.

Если передан task_id, запуск засчитывается как попытка решения этой code-задачи:
сервер сам сравнивает вывод с эталоном, записывает попытку и перед событием
exit шлёт {"type": "result", "passed": bool, "progress": {...}}. Браузеру
верить нельзя, поэтому эталонный вывод к клиенту вообще не уходит.

Каждый завершившийся запуск (в том числе без task_id) записывается в CodeRun:
исход, тип ошибки, размеры, длительность. Запуски, оборванные самой
инфраструктурой (сбой песочницы, отмена), не засчитываются как попытка.

Частые запуски отсекаются (см. throttles.allow_code_run): сервер шлёт error и
закрывает сокет кодом 4429.
"""

import asyncio
import json
import threading

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .footprint import finish_code_run
from .runner import REASON_RUNNER_ERROR, stream_python_code
from .services import RuleViolation, prepare_code_task
from .throttles import allow_code_run

MAX_CODE_BYTES = 100_000


class RunnerConsumer(AsyncWebsocketConsumer):
    """Стримит выполнение кода в песочнице через WebSocket."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            # 4401 — аналог HTTP 401 в диапазоне WS application errors
            await self.close(code=4401)
            return
        self._running = False
        self._stop_event: threading.Event | None = None
        self._run_task: asyncio.Task | None = None
        await self.accept()

    async def disconnect(self, code):
        # говорим producer-потоку остановиться; watchdog убьёт контейнер
        if self._stop_event is not None:
            self._stop_event.set()
        if self._run_task is not None and not self._run_task.done():
            self._run_task.cancel()

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            await self._emit({"type": "error", "message": "Binary frames not supported"})
            return
        try:
            msg = json.loads(text_data)
        except json.JSONDecodeError:
            await self._emit({"type": "error", "message": "Invalid JSON payload"})
            return

        msg_type = msg.get("type")
        if msg_type == "run":
            await self._handle_run(msg)
        else:
            await self._emit({"type": "error", "message": f"Unknown message type: {msg_type!r}"})

    async def _handle_run(self, msg: dict) -> None:
        if self._running:
            await self._emit({"type": "error", "message": "A run is already in progress"})
            return
        code = msg.get("code")
        if not isinstance(code, str) or not code.strip():
            await self._emit({"type": "error", "message": "Code is empty"})
            return
        if len(code.encode("utf-8")) > MAX_CODE_BYTES:
            await self._emit({
                "type": "error",
                "message": f"Code exceeds {MAX_CODE_BYTES // 1024} KB limit",
            })
            return

        # Слишком частые запуски (спам кнопки Run, скрипты) отсекаем до любой работы.
        if not await sync_to_async(allow_code_run)(self.scope["user"].id):
            await self._emit(
                {
                    "type": "error",
                    "message": "Слишком много запусков подряд. Подождите несколько секунд.",
                    "reason": "rate_limited",
                }
            )
            await self.close(code=4429)
            return

        # Задача (если указана) проверяется ДО запуска: нет доступа — код не
        # исполняется вовсе.
        task = None
        task_id = msg.get("task_id")
        if task_id is not None:
            try:
                task = await database_sync_to_async(prepare_code_task)(
                    self.scope["user"], task_id
                )
            except RuleViolation as exc:
                # No run happens, so no "exit" will follow: close the socket
                # (4403 = refused) so the client leaves its "running" state.
                await self._emit({"type": "error", "message": str(exc.detail)})
                await self.close(code=4403)
                return

        # ставим _running перед стартом задачи, чтобы параллельный receive
        # увидел busy и отбил повторный run
        self._running = True
        self._run_task = asyncio.create_task(self._stream_run(code, task))

    async def _stream_run(self, code: str, task=None) -> None:
        """Гоняет синхронный генератор в треде, асинхронно форвардит события."""
        self._stop_event = threading.Event()
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def producer() -> None:
            try:
                for event in stream_python_code(code, stop_event=self._stop_event):
                    if self._stop_event.is_set():
                        break
                    loop.call_soon_threadsafe(queue.put_nowait, event)
            except Exception as exc:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {
                        "type": "error",
                        "message": f"Runner crashed: {exc}",
                        "reason": REASON_RUNNER_ERROR,
                    },
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

        thread = threading.Thread(target=producer, daemon=True)
        thread.start()

        stdout_parts, stderr_parts, reasons = [], [], set()
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                kind = event.get("type")
                if kind == "stdout":
                    stdout_parts.append(event.get("data") or "")
                elif kind == "stderr":
                    stderr_parts.append(event.get("data") or "")
                elif kind == "error" and event.get("reason"):
                    reasons.add(event["reason"])
                elif kind == "exit":
                    # Запуск дошёл до конца: оценить (если это задача) и записать.
                    # Вердикт идёт раньше exit: клиент закрывает сокет на exit.
                    verdict = await database_sync_to_async(finish_code_run)(
                        self.scope["user"],
                        task,
                        code=code,
                        stdout="".join(stdout_parts),
                        stderr="".join(stderr_parts),
                        exit_code=event.get("code"),
                        duration=event.get("duration"),
                        reasons=reasons,
                    )
                    if verdict is not None:
                        await self._emit({"type": "result", **verdict})
                await self._emit(event)
        except asyncio.CancelledError:
            # disconnect() отменил задачу — гасим producer
            if self._stop_event is not None:
                self._stop_event.set()
            raise
        finally:
            self._running = False
            self._stop_event = None
            self._run_task = None

    async def _emit(self, payload: dict) -> None:
        await self.send(text_data=json.dumps(payload))
