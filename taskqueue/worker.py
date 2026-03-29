# ============================================================================
# IIStudio — Воркер очереди задач
# ============================================================================

from __future__ import annotations

import asyncio
from typing import Any, Optional

from taskqueue.task_queue import TaskQueue, TaskStatus
from utils.logger import logger


class Worker:
    """Асинхронный воркер для обработки задач из очереди."""

    def __init__(
        self,
        queue: TaskQueue,
        concurrency: int = 5,
        name: str = "worker",
    ) -> None:
        self.queue = queue
        self.concurrency = concurrency
        self.name = name
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._semaphore = asyncio.Semaphore(concurrency)

    async def start(self) -> None:
        """Запустить воркер."""
        self._running = True
        logger.info("Воркер '{}' запущен (concurrency={})", self.name, self.concurrency)
        for i in range(self.concurrency):
            task = asyncio.create_task(self._loop(f"{self.name}-{i}"))
            self._tasks.append(task)

    async def stop(self) -> None:
        """Остановить воркер."""
        self._running = False
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Воркер '{}' остановлен", self.name)

    async def _loop(self, worker_id: str) -> None:
        """Основной цикл воркера."""
        while self._running:
            try:
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            if task.status == TaskStatus.CANCELLED:
                self.queue.task_done()
                continue

            await self.queue.update_status(task.task_id, TaskStatus.IN_PROGRESS)
            logger.debug("[{}] Выполняю задачу {}", worker_id, task.task_id)

            try:
                async with self._semaphore:
                    if asyncio.iscoroutinefunction(task.func):
                        result = await task.func(*task.args, **task.kwargs)
                    else:
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(
                            None, lambda: task.func(*task.args, **task.kwargs)
                        )

                await self.queue.update_status(task.task_id, TaskStatus.DONE, result=result)
                logger.debug("[{}] Задача {} выполнена", worker_id, task.task_id)

            except Exception as e:
                logger.error("[{}] Задача {} упала: {}", worker_id, task.task_id, e)
                await self.queue.update_status(
                    task.task_id, TaskStatus.FAILED, error=str(e)
                )
            finally:
                self.queue.task_done()
