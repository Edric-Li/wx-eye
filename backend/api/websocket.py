"""
WebSocket 管理模块
用于实时推送截图、日志和 AI 分析结果到前端
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import datetime
from io import BytesIO
from typing import Any, TYPE_CHECKING

from fastapi import WebSocket
from PIL import Image

if TYPE_CHECKING:
    from ai.processor import ProcessingResult

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器

    管理多个 WebSocket 客户端连接，支持广播消息到所有连接。
    """

    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """断开连接"""
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """广播消息给所有连接的客户端"""
        if not self.active_connections:
            return

        data = json.dumps(message, ensure_ascii=False)
        disconnected: set[WebSocket] = set()

        for connection in self.active_connections.copy():
            try:
                await connection.send_text(data)
            except Exception:
                disconnected.add(connection)

        # 清理断开的连接
        if disconnected:
            async with self._lock:
                self.active_connections -= disconnected

    async def send_screenshot(
        self,
        image: Image.Image,
        filename: str,
        is_significant: bool,
        compare_result: dict[str, Any] | None = None,
    ) -> None:
        """发送截图更新到所有客户端

        Args:
            image: PIL 图片对象
            filename: 保存的文件名
            is_significant: 是否是有意义的变化
            compare_result: 对比结果详情
        """
        # 压缩图片用于传输
        buffer = BytesIO()
        # 缩小图片以减少传输量
        thumbnail = image.copy()
        thumbnail.thumbnail((800, 600), Image.Resampling.LANCZOS)
        thumbnail.save(buffer, format="JPEG", quality=80)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()

        message = {
            "type": "screenshot",
            "timestamp": datetime.now().isoformat(),
            "filename": filename,
            "is_significant": is_significant,
            "image_data": f"data:image/jpeg;base64,{image_base64}",
            "compare_result": compare_result,
        }

        await self.broadcast(message)

    async def send_log(self, level: str, message: str, extra: dict[str, Any] | None = None) -> None:
        """发送日志到所有客户端

        Args:
            level: 日志级别 (info, warning, error)
            message: 日志消息
            extra: 额外信息
        """
        log_message = {
            "type": "log",
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "extra": extra or {},
        }

        await self.broadcast(log_message)

    async def send_status(self, status: str, details: dict[str, Any] | None = None) -> None:
        """发送状态更新到所有客户端

        Args:
            status: 状态名称
            details: 状态详情
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
        """发送 AI 分析的新消息到所有客户端

        Args:
            contact: 联系人名称
            new_messages: 新消息列表 [{"sender": str, "content": str, "time": str}, ...]
            summary: 消息摘要
            processing_stats: 处理统计信息
        """
        message = {
            "type": "ai_message",
            "timestamp": datetime.now().isoformat(),
            "contact": contact,
            "new_messages": new_messages,
            "summary": summary,
            "message_count": len(new_messages),
            "processing_stats": processing_stats or {},
        }

        await self.broadcast(message)

        # 同时发送日志
        if new_messages:
            await self.send_log(
                "info",
                f"[{contact}] AI 识别到 {len(new_messages)} 条新消息: {summary}",
                {"contact": contact, "message_count": len(new_messages)},
            )

    async def send_ai_result(self, result: ProcessingResult) -> None:
        """发送 AI 处理结果

        处理逻辑（像素级比对已在 main.py 完成）：
        - 发送截图给前端
        - 去重过滤（无新消息）：只发送截图，不发送消息
        - AI 分析成功：发送截图 + 发送新消息
        - AI 分析失败：发送截图 + 发送错误日志

        Args:
            result: AI 处理结果对象
        """
        # 发送截图给前端
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

        if result.stage == "dedup_filtered":
            # 去重过滤：无新消息
            await self.send_log(
                "info",
                f"[{result.contact}] 无新消息（可能是历史消息）",
                {"contact": result.contact, "ai_time_ms": result.ai_time_ms},
            )
            return

        if result.error:
            await self.send_log(
                "error",
                f"[{result.contact}] AI 分析失败: {result.error}",
                {"contact": result.contact},
            )
            return

        if result.new_messages:
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


# 全局连接管理器实例
manager = ConnectionManager()
