"""
微信消息发送服务
使用 UI 自动化发送消息：点击输入框 -> 粘贴 -> 回车
"""

from __future__ import annotations

import asyncio
import logging
import platform
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import pyautogui
import pyperclip

if TYPE_CHECKING:
    from capture import WindowInfo

logger = logging.getLogger(__name__)

# 防止 pyautogui 移动过快
pyautogui.PAUSE = 0.1

# 输入框相对于窗口的位置偏移（微信聊天窗口）
# 输入框在窗口底部，水平居中偏右
INPUT_BOX_OFFSET_FROM_BOTTOM = 60  # 距离窗口底部的像素
INPUT_BOX_HORIZONTAL_RATIO = 0.5   # 水平位置比例（0.5 = 中间）


@dataclass
class SendResult:
    """发送结果"""
    success: bool
    message: str
    elapsed_ms: int = 0
    error: Optional[str] = None


class MessageSender:
    """微信消息发送器

    通过 UI 自动化实现跨平台发送消息：
    1. 点击微信窗口的输入框
    2. 通过剪贴板粘贴消息（支持中文）
    3. 按回车发送
    """

    def __init__(self) -> None:
        """初始化发送器"""
        self.system = platform.system()  # Darwin, Windows, Linux

        # 当前目标窗口信息
        self._current_window: Optional[WindowInfo] = None

        # 统计
        self.total_sent = 0
        self.total_failed = 0

        logger.info(f"消息发送器初始化: platform={self.system}")

    def set_window(self, window: WindowInfo) -> None:
        """设置目标窗口

        Args:
            window: 窗口信息
        """
        self._current_window = window
        logger.info(f"设置目标窗口: {window.title} ({window.x}, {window.y}, {window.width}x{window.height})")

    def _calculate_input_box_position(self) -> tuple[int, int] | None:
        """根据窗口位置计算输入框坐标

        Returns:
            (x, y) 坐标，如果没有窗口信息则返回 None
        """
        if not self._current_window:
            return None

        w = self._current_window
        # 输入框在窗口底部中间
        x = w.x + int(w.width * INPUT_BOX_HORIZONTAL_RATIO)
        y = w.y + w.height - INPUT_BOX_OFFSET_FROM_BOTTOM

        return (x, y)

    def _get_paste_hotkey(self) -> tuple[str, ...]:
        """获取粘贴快捷键"""
        if self.system == "Darwin":
            return ("command", "v")
        else:
            return ("ctrl", "v")

    def _click_input_box(self) -> bool:
        """点击输入框

        Returns:
            是否成功点击
        """
        pos = self._calculate_input_box_position()
        if pos is None:
            logger.warning("窗口信息未设置，无法计算输入框位置")
            return False

        try:
            x, y = pos
            logger.debug(f"点击输入框: ({x}, {y})")
            pyautogui.click(x, y)
            time.sleep(0.1)  # 等待点击生效
            return True
        except Exception as e:
            logger.error(f"点击输入框失败: {e}")
            return False

    def _paste_text(self, text: str) -> bool:
        """通过剪贴板粘贴文本

        Args:
            text: 要粘贴的文本

        Returns:
            是否成功粘贴
        """
        try:
            # 保存原剪贴板内容
            original_clipboard = ""
            try:
                original_clipboard = pyperclip.paste()
            except Exception:
                pass

            # 复制新内容到剪贴板
            pyperclip.copy(text)
            time.sleep(0.05)

            # 粘贴
            hotkey = self._get_paste_hotkey()
            pyautogui.hotkey(*hotkey)
            time.sleep(0.1)

            # 恢复原剪贴板内容（可选）
            # pyperclip.copy(original_clipboard)

            return True
        except Exception as e:
            logger.error(f"粘贴文本失败: {e}")
            return False

    def _press_enter(self) -> bool:
        """按回车发送

        Returns:
            是否成功按下回车
        """
        try:
            pyautogui.press("enter")
            return True
        except Exception as e:
            logger.error(f"按回车失败: {e}")
            return False

    def send_sync(self, text: str) -> SendResult:
        """同步发送消息

        Args:
            text: 要发送的消息文本

        Returns:
            发送结果
        """
        start_time = time.time()

        if not text or not text.strip():
            return SendResult(
                success=False,
                message="消息内容为空",
                error="Empty message",
            )

        text = text.strip()
        logger.info(f"准备发送消息: {text[:50]}{'...' if len(text) > 50 else ''}")

        try:
            # 1. 点击输入框
            if not self._click_input_box():
                self.total_failed += 1
                return SendResult(
                    success=False,
                    message="点击输入框失败",
                    error="Failed to click input box",
                    elapsed_ms=int((time.time() - start_time) * 1000),
                )

            # 2. 粘贴文本
            if not self._paste_text(text):
                self.total_failed += 1
                return SendResult(
                    success=False,
                    message="粘贴文本失败",
                    error="Failed to paste text",
                    elapsed_ms=int((time.time() - start_time) * 1000),
                )

            # 3. 按回车发送
            if not self._press_enter():
                self.total_failed += 1
                return SendResult(
                    success=False,
                    message="按回车失败",
                    error="Failed to press enter",
                    elapsed_ms=int((time.time() - start_time) * 1000),
                )

            elapsed_ms = int((time.time() - start_time) * 1000)
            self.total_sent += 1

            logger.info(f"消息发送成功: {elapsed_ms}ms")

            return SendResult(
                success=True,
                message="发送成功",
                elapsed_ms=elapsed_ms,
            )

        except Exception as e:
            self.total_failed += 1
            logger.error(f"发送消息异常: {e}")
            return SendResult(
                success=False,
                message=f"发送异常: {e}",
                error=str(e),
                elapsed_ms=int((time.time() - start_time) * 1000),
            )

    async def send(self, text: str) -> SendResult:
        """异步发送消息

        Args:
            text: 要发送的消息文本

        Returns:
            发送结果
        """
        # 在线程池中执行同步操作
        return await asyncio.to_thread(self.send_sync, text)

    def get_stats(self) -> dict:
        """获取统计信息"""
        pos = self._calculate_input_box_position()
        return {
            "platform": self.system,
            "current_window": {
                "title": self._current_window.title if self._current_window else None,
                "x": self._current_window.x if self._current_window else None,
                "y": self._current_window.y if self._current_window else None,
                "width": self._current_window.width if self._current_window else None,
                "height": self._current_window.height if self._current_window else None,
            },
            "input_box_position": {
                "x": pos[0] if pos else None,
                "y": pos[1] if pos else None,
            },
            "total_sent": self.total_sent,
            "total_failed": self.total_failed,
        }


# 全局发送器实例
_sender: Optional[MessageSender] = None


def get_sender() -> MessageSender:
    """获取全局发送器实例"""
    global _sender
    if _sender is None:
        _sender = MessageSender()
    return _sender
