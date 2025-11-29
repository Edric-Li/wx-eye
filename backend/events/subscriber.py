"""
WebSocket 订阅者管理
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from .types import Event, EventType
from .bus import get_event_bus

logger = logging.getLogger(__name__)


@dataclass
class Subscriber:
    """WebSocket 订阅者"""

    websocket: WebSocket
    subscriptions: set[str] = field(default_factory=set)  # 订阅的事件模式

    def is_subscribed(self, event_type: str) -> bool:
        """检查是否订阅了指定事件类型"""
        for pattern in self.subscriptions:
            if EventType.match(event_type, pattern):
                return True
        return False


class SubscriberManager:
    """WebSocket 订阅者管理器

    管理所有 WebSocket 连接，支持事件过滤订阅。
    """

    def __init__(self) -> None:
        self._subscribers: dict[WebSocket, Subscriber] = {}
        self._lock = asyncio.Lock()
        self._registered = False

    async def connect(self, websocket: WebSocket) -> Subscriber:
        """接受新的 WebSocket 连接

        默认订阅所有事件。
        """
        await websocket.accept()

        async with self._lock:
            subscriber = Subscriber(
                websocket=websocket,
                subscriptions={"*"},  # 默认订阅所有事件
            )
            self._subscribers[websocket] = subscriber

            # 确保注册到事件总线
            self._ensure_registered()

        logger.info(f"Subscriber connected. Total: {len(self._subscribers)}")
        return subscriber

    def _ensure_registered(self) -> None:
        """确保已注册到事件总线"""
        event_bus = get_event_bus()
        # 检查是否已经注册（通过检查 handler 是否在 global_handlers 中）
        if self._on_event not in event_bus._global_handlers:
            event_bus.on("*", self._on_event)
            self._registered = True
            logger.info("SubscriberManager registered to EventBus")

    async def disconnect(self, websocket: WebSocket) -> None:
        """断开连接"""
        async with self._lock:
            if websocket in self._subscribers:
                del self._subscribers[websocket]

        logger.info(f"Subscriber disconnected. Total: {len(self._subscribers)}")

    async def subscribe(
        self,
        websocket: WebSocket,
        events: list[str],
    ) -> None:
        """订阅事件

        Args:
            websocket: WebSocket 连接
            events: 要订阅的事件模式列表
        """
        async with self._lock:
            if websocket in self._subscribers:
                subscriber = self._subscribers[websocket]
                # 清除旧订阅，使用新的
                subscriber.subscriptions.clear()
                subscriber.subscriptions.update(events)
                logger.info(f"Subscriber updated subscriptions: {events}")

    async def unsubscribe(
        self,
        websocket: WebSocket,
        events: list[str],
    ) -> None:
        """取消订阅

        Args:
            websocket: WebSocket 连接
            events: 要取消的事件模式列表
        """
        async with self._lock:
            if websocket in self._subscribers:
                subscriber = self._subscribers[websocket]
                for event in events:
                    subscriber.subscriptions.discard(event)
                logger.info(f"Subscriber unsubscribed: {events}")

    async def get_subscriptions(self, websocket: WebSocket) -> set[str]:
        """获取当前订阅列表"""
        async with self._lock:
            if websocket in self._subscribers:
                return self._subscribers[websocket].subscriptions.copy()
            return set()

    async def _on_event(self, event: Event) -> None:
        """事件处理器 - 广播给匹配的订阅者"""
        await self.broadcast_event(event)

    async def broadcast_event(self, event: Event) -> None:
        """广播事件给匹配的订阅者"""
        if not self._subscribers:
            return

        data = json.dumps(event.to_dict(), ensure_ascii=False)
        disconnected: list[WebSocket] = []

        # 复制订阅者列表以避免迭代时修改
        subscribers_copy = list(self._subscribers.items())
        sent_count = 0

        for websocket, subscriber in subscribers_copy:
            # 检查是否订阅了该事件
            if not subscriber.is_subscribed(event.type):
                continue

            try:
                await websocket.send_text(data)
                sent_count += 1
            except Exception as e:
                logger.debug(f"Failed to send to subscriber: {e}")
                disconnected.append(websocket)

        if sent_count > 0:
            logger.debug(f"Broadcast event [{event.type}] to {sent_count} subscriber(s)")

        # 清理断开的连接
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self._subscribers.pop(ws, None)

    async def broadcast_raw(self, message: dict[str, Any]) -> None:
        """广播原始消息（兼容旧协议）

        此方法发送给所有连接，不进行事件过滤。
        """
        if not self._subscribers:
            return

        data = json.dumps(message, ensure_ascii=False)
        disconnected: list[WebSocket] = []
        sent_count = 0
        msg_type = message.get("type", "unknown")

        for websocket in list(self._subscribers.keys()):
            try:
                await websocket.send_text(data)
                sent_count += 1
            except Exception:
                disconnected.append(websocket)

        if sent_count > 0:
            logger.debug(f"Broadcast raw [{msg_type}] to {sent_count} subscriber(s)")

        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self._subscribers.pop(ws, None)

    async def send_to(self, websocket: WebSocket, message: dict[str, Any]) -> bool:
        """发送消息给特定订阅者

        Returns:
            发送成功返回 True
        """
        try:
            data = json.dumps(message, ensure_ascii=False)
            await websocket.send_text(data)
            return True
        except Exception as e:
            logger.debug(f"Failed to send: {e}")
            return False

    @property
    def subscriber_count(self) -> int:
        """当前订阅者数量"""
        return len(self._subscribers)


# 全局订阅者管理器实例
subscriber_manager = SubscriberManager()


def get_subscriber_manager() -> SubscriberManager:
    """获取全局订阅者管理器实例"""
    return subscriber_manager
