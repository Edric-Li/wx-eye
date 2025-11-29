"""
事件类型定义
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """事件类型枚举"""

    # 消息事件
    MESSAGE_RECEIVED = "message.received"  # 收到新消息
    MESSAGE_SENT = "message.sent"  # 消息发送完成

    # 联系人事件
    CONTACT_ONLINE = "contact.online"  # 联系人窗口出现
    CONTACT_OFFLINE = "contact.offline"  # 联系人窗口消失
    CONTACT_ADDED = "contact.added"  # 添加监控联系人
    CONTACT_REMOVED = "contact.removed"  # 移除监控联系人

    # 监控事件
    MONITOR_STARTED = "monitor.started"  # 监控启动
    MONITOR_STOPPED = "monitor.stopped"  # 监控停止

    # 系统事件
    ERROR = "error"  # 错误发生
    LOG = "log"  # 日志消息（兼容旧协议）

    @classmethod
    def match(cls, event_type: str, pattern: str) -> bool:
        """检查事件类型是否匹配模式

        支持通配符:
        - "*" 匹配所有事件
        - "message.*" 匹配所有消息事件
        - "contact.*" 匹配所有联系人事件
        - "monitor.*" 匹配所有监控事件
        """
        if pattern == "*":
            return True

        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return event_type.startswith(prefix + ".")

        return event_type == pattern


class Event(BaseModel):
    """统一事件模型"""

    id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    type: str  # EventType value
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    contact: str | None = None  # 关联的联系人
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "id": self.id,
            "type": self.type,
            "timestamp": self.timestamp,
            "contact": self.contact,
            "payload": self.payload,
        }

    @classmethod
    def message_received(
        cls,
        contact: str,
        messages: list[dict[str, str]],
        screenshot_url: str | None = None,
    ) -> Event:
        """创建消息接收事件"""
        return cls(
            type=EventType.MESSAGE_RECEIVED.value,
            contact=contact,
            payload={
                "messages": messages,
                "message_count": len(messages),
                "screenshot_url": screenshot_url,
            },
        )

    @classmethod
    def message_sent(
        cls,
        contact: str,
        text: str,
        success: bool,
        error: str | None = None,
        elapsed_ms: int = 0,
    ) -> Event:
        """创建消息发送事件"""
        return cls(
            type=EventType.MESSAGE_SENT.value,
            contact=contact,
            payload={
                "text": text,
                "success": success,
                "error": error,
                "elapsed_ms": elapsed_ms,
            },
        )

    @classmethod
    def contact_online(
        cls,
        contact: str,
        window: dict[str, int] | None = None,
    ) -> Event:
        """创建联系人上线事件"""
        return cls(
            type=EventType.CONTACT_ONLINE.value,
            contact=contact,
            payload={"window": window} if window else {},
        )

    @classmethod
    def contact_offline(cls, contact: str) -> Event:
        """创建联系人离线事件"""
        return cls(
            type=EventType.CONTACT_OFFLINE.value,
            contact=contact,
            payload={},
        )

    @classmethod
    def contact_added(cls, contact: str) -> Event:
        """创建联系人添加事件"""
        return cls(
            type=EventType.CONTACT_ADDED.value,
            contact=contact,
            payload={},
        )

    @classmethod
    def contact_removed(cls, contact: str) -> Event:
        """创建联系人移除事件"""
        return cls(
            type=EventType.CONTACT_REMOVED.value,
            contact=contact,
            payload={},
        )

    @classmethod
    def monitor_started(
        cls,
        contacts: list[str],
        interval: float,
    ) -> Event:
        """创建监控启动事件"""
        return cls(
            type=EventType.MONITOR_STARTED.value,
            payload={
                "contacts": contacts,
                "interval": interval,
            },
        )

    @classmethod
    def monitor_stopped(
        cls,
        stats: dict[str, Any] | None = None,
    ) -> Event:
        """创建监控停止事件"""
        return cls(
            type=EventType.MONITOR_STOPPED.value,
            payload={"stats": stats} if stats else {},
        )

    @classmethod
    def error(
        cls,
        code: str,
        message: str,
        contact: str | None = None,
    ) -> Event:
        """创建错误事件"""
        return cls(
            type=EventType.ERROR.value,
            contact=contact,
            payload={
                "code": code,
                "message": message,
            },
        )

    @classmethod
    def log(
        cls,
        level: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> Event:
        """创建日志事件（兼容旧协议）"""
        return cls(
            type=EventType.LOG.value,
            payload={
                "level": level,
                "message": message,
                "extra": extra or {},
            },
        )
