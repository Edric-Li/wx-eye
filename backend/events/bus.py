"""
事件总线 - 发布/订阅模式
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Callable, Any

if TYPE_CHECKING:
    from .types import Event

logger = logging.getLogger(__name__)


class EventBus:
    """事件总线

    单例模式，用于在应用各组件之间传递事件。
    支持异步事件处理。
    """

    _instance: "EventBus | None" = None
    _initialized: bool = False

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if EventBus._initialized:
            return
        EventBus._initialized = True

        # 事件处理器: {event_pattern: [handler, ...]}
        self._handlers: dict[str, list[Callable[[Event], Any]]] = {}

        # 全局处理器（接收所有事件）
        self._global_handlers: list[Callable[[Event], Any]] = []

        # 事件队列（用于异步批量处理）
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._is_running = False
        self._task: asyncio.Task | None = None

        logger.info("EventBus initialized")

    def on(self, event_pattern: str, handler: Callable[[Event], Any]) -> None:
        """注册事件处理器

        Args:
            event_pattern: 事件模式，支持通配符
                - "*" 匹配所有事件
                - "message.*" 匹配所有消息事件
                - "message.received" 精确匹配
            handler: 事件处理函数，可以是同步或异步
        """
        if event_pattern == "*":
            self._global_handlers.append(handler)
        else:
            if event_pattern not in self._handlers:
                self._handlers[event_pattern] = []
            self._handlers[event_pattern].append(handler)

        logger.debug(f"Registered handler for pattern: {event_pattern}")

    def off(self, event_pattern: str, handler: Callable[[Event], Any]) -> None:
        """移除事件处理器"""
        if event_pattern == "*":
            if handler in self._global_handlers:
                self._global_handlers.remove(handler)
        elif event_pattern in self._handlers:
            if handler in self._handlers[event_pattern]:
                self._handlers[event_pattern].remove(handler)

    async def emit(self, event: Event) -> None:
        """发布事件

        立即触发所有匹配的处理器（异步执行）。
        """
        from .types import EventType

        logger.debug(f"Emitting event: {event.type} (id={event.id})")

        # 收集所有匹配的处理器
        handlers: list[Callable[[Event], Any]] = []

        # 全局处理器
        handlers.extend(self._global_handlers)

        # 精确匹配
        if event.type in self._handlers:
            handlers.extend(self._handlers[event.type])

        # 通配符匹配
        for pattern, pattern_handlers in self._handlers.items():
            if pattern.endswith(".*") and EventType.match(event.type, pattern):
                handlers.extend(pattern_handlers)

        # 执行所有处理器
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Event handler error: {e}", exc_info=True)

    def emit_sync(self, event: Event) -> None:
        """同步发布事件（用于非异步上下文）

        创建一个任务来异步处理事件。
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event))
        except RuntimeError:
            # 没有运行中的事件循环，使用队列
            logger.warning("No running event loop, event queued")

    async def start(self) -> None:
        """启动事件处理（可选的后台处理模式）"""
        if self._is_running:
            return
        self._is_running = True
        logger.info("EventBus started")

    async def stop(self) -> None:
        """停止事件处理"""
        if not self._is_running:
            return
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("EventBus stopped")

    def reset(self) -> None:
        """重置事件总线（用于测试）

        清除所有注册的处理器，但保留单例实例。
        """
        self._handlers.clear()
        self._global_handlers.clear()


# 全局事件总线实例
event_bus = EventBus()


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    return event_bus
