"""
WebSocket 管理模块
用于实时推送截图和日志到前端
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import datetime
from io import BytesIO
from typing import Any

from fastapi import WebSocket
from PIL import Image

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


# 全局连接管理器实例
manager = ConnectionManager()
