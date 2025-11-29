"""
WebSocket 管理模块
重构为事件驱动架构，支持订阅/过滤

兼容旧协议的同时，支持新的事件订阅模式。
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime
from io import BytesIO
from typing import Any, TYPE_CHECKING

from PIL import Image

from events import Event, get_event_bus, get_subscriber_manager

if TYPE_CHECKING:
    from ai.processor import ProcessingResult

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器

    封装 SubscriberManager，提供兼容旧协议的接口。
    所有事件发送都通过 EventBus 进行。
    """

    def __init__(self) -> None:
        self._subscriber_manager = get_subscriber_manager()
        self._event_bus = get_event_bus()

    @property
    def active_connections(self) -> int:
        """活跃连接数"""
        return self._subscriber_manager.subscriber_count

    async def connect(self, websocket) -> None:
        """接受新的 WebSocket 连接"""
        await self._subscriber_manager.connect(websocket)

    async def disconnect(self, websocket) -> None:
        """断开连接"""
        await self._subscriber_manager.disconnect(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """广播原始消息（兼容旧协议）"""
        await self._subscriber_manager.broadcast_raw(message)

    # ============ 事件发送方法 ============

    async def send_screenshot(
        self,
        image: Image.Image,
        filename: str,
        is_significant: bool,
        compare_result: dict[str, Any] | None = None,
    ) -> None:
        """发送截图更新

        兼容旧协议，同时发布事件。
        """
        # 压缩图片用于传输
        buffer = BytesIO()
        thumbnail = image.copy()
        thumbnail.thumbnail((800, 600), Image.Resampling.LANCZOS)
        thumbnail.save(buffer, format="JPEG", quality=80)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()

        # 兼容旧协议的消息格式
        message = {
            "type": "screenshot",
            "timestamp": datetime.now().isoformat(),
            "filename": filename,
            "is_significant": is_significant,
            "image_data": f"data:image/jpeg;base64,{image_base64}",
            "compare_result": compare_result,
        }

        await self.broadcast(message)

    async def send_log(
        self,
        level: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """发送日志

        通过 EventBus 发布日志事件。
        """
        event = Event.log(level=level, message=message, extra=extra)
        await self._event_bus.emit(event)

    async def send_status(
        self,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """发送状态更新

        兼容旧协议格式。
        """
        status_message = {
            "type": "status",
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "details": details or {},
        }

        await self.broadcast(status_message)

    async def send_ai_message(
        self,
        contact: str,
        new_messages: list[dict[str, Any]],
        summary: str = "",
        processing_stats: dict[str, Any] | None = None,
    ) -> None:
        """发送 AI 分析的新消息

        同时发布 message.received 事件。
        注意：过滤掉发送人是"我"的消息，不广播自己发送的内容。
        """
        # 过滤掉自己发送的消息（AI 返回 $self 表示自己）
        filtered_messages = [
            msg for msg in new_messages
            if msg.get("sender") != "$self"
        ]

        # 如果过滤后没有消息，直接返回
        if not filtered_messages:
            return

        # 兼容旧协议
        message = {
            "type": "ai_message",
            "timestamp": datetime.now().isoformat(),
            "contact": contact,
            "new_messages": filtered_messages,
            "summary": summary,
            "message_count": len(filtered_messages),
            "processing_stats": processing_stats or {},
        }
        await self.broadcast(message)

        # 发布新事件
        event = Event.message_received(
            contact=contact,
            messages=filtered_messages,
            screenshot_url=None,  # 可以从 processing_stats 获取
        )
        await self._event_bus.emit(event)

    async def send_ai_result(self, result: ProcessingResult) -> None:
        """发送 AI 处理结果

        处理逻辑：
        - 发送截图给前端
        - 去重过滤（无新消息）：只发送截图，不发送消息
        - AI 分析成功：发送截图 + 发送新消息
        - AI 分析失败：发送截图 + 发送错误日志
        """
        screenshot_url = None

        # 发送截图
        if result.image and result.filename:
            await self.send_screenshot(
                image=result.image,
                filename=result.filename,
                is_significant=True,
                compare_result={
                    "level": "different",
                    "description": "检测到画面变化",
                    "contact": result.contact,
                    "stage": result.stage,
                },
            )
            screenshot_url = f"/static/screenshots/{result.filename}"

        if result.stage == "dedup_filtered":
            # 去重过滤：无新消息
            await self.send_log(
                "info",
                f"[{result.contact}] 无新消息（可能是历史消息）",
                {"contact": result.contact, "ai_time_ms": result.ai_time_ms},
            )
            return

        if result.error:
            # 发布错误事件
            event = Event.error(
                code="ai_analysis_failed",
                message=result.error,
                contact=result.contact,
            )
            await self._event_bus.emit(event)

            await self.send_log(
                "error",
                f"[{result.contact}] AI 分析失败: {result.error}",
                {"contact": result.contact},
            )
            return

        if result.new_messages:
            # 发送消息（兼容旧协议）
            await self.send_ai_message(
                contact=result.contact,
                new_messages=result.new_messages,
                summary=result.summary,
                processing_stats={
                    "ai_time_ms": result.ai_time_ms,
                    "tokens_used": result.tokens_used,
                    "stage": result.stage,
                },
            )

            # 同时发送日志（兼容旧协议）
            await self.send_log(
                "info",
                f"[{result.contact}] AI 识别到 {len(result.new_messages)} 条新消息",
                {"contact": result.contact, "message_count": len(result.new_messages)},
            )

    # ============ 新事件 API ============

    async def emit_message_sent(
        self,
        contact: str,
        text: str,
        success: bool,
        error: str | None = None,
        elapsed_ms: int = 0,
    ) -> None:
        """发布消息发送事件"""
        event = Event.message_sent(
            contact=contact,
            text=text,
            success=success,
            error=error,
            elapsed_ms=elapsed_ms,
        )
        await self._event_bus.emit(event)

    async def emit_contact_online(
        self,
        contact: str,
        window: dict[str, int] | None = None,
    ) -> None:
        """发布联系人上线事件"""
        event = Event.contact_online(contact=contact, window=window)
        await self._event_bus.emit(event)

    async def emit_contact_offline(self, contact: str) -> None:
        """发布联系人离线事件"""
        event = Event.contact_offline(contact=contact)
        await self._event_bus.emit(event)

    async def emit_monitor_started(
        self,
        contacts: list[str],
        interval: float,
    ) -> None:
        """发布监控启动事件"""
        event = Event.monitor_started(contacts=contacts, interval=interval)
        await self._event_bus.emit(event)

    async def emit_monitor_stopped(
        self,
        stats: dict[str, Any] | None = None,
    ) -> None:
        """发布监控停止事件"""
        event = Event.monitor_stopped(stats=stats)
        await self._event_bus.emit(event)


# 全局连接管理器实例
manager = ConnectionManager()
