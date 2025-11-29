"""
微信消息发送服务
使用 UI 自动化发送消息：点击输入框 -> 粘贴 -> 回车
支持消息队列，确保同一时间只有一个发送操作
支持 @ 提及：通过键盘模拟触发联系人选择菜单
"""

from __future__ import annotations

import asyncio
import logging
import platform
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Any

import pyautogui
import pyperclip

if TYPE_CHECKING:
    from capture import WindowInfo

logger = logging.getLogger(__name__)

# 防止 pyautogui 移动过快
pyautogui.PAUSE = 0.1

# Windows DPI 感知设置
# 解决 pygetwindow 与 pyautogui 坐标不一致问题
if platform.system() == "Windows":
    try:
        import ctypes
        # 设置进程为 DPI 感知，确保坐标一致性
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# 输入框相对于窗口的位置偏移（微信聊天窗口）
# 输入框在窗口底部，水平居中偏右
INPUT_BOX_OFFSET_FROM_BOTTOM = 60  # 距离窗口底部的像素
INPUT_BOX_HORIZONTAL_RATIO = 0.5   # 水平位置比例（0.5 = 中间）

# @ 提及相关配置
AT_MENU_WAIT_TIME = 0.3  # 等待 @ 菜单弹出的时间（秒）
AT_SELECT_WAIT_TIME = 0.15  # 等待选择生效的时间（秒）

# 匹配 @ 提及的正则表达式
# - @ 前面不能是字母数字（排除邮箱如 test@example.com）
# - @ 后面跟非空白非@字符
# 例如：@张三 你好 -> 匹配 @张三
#      test@example.com -> 不匹配
AT_PATTERN = re.compile(r'(?<![a-zA-Z0-9])@([^\s@]+)')


@dataclass
class MessageSegment:
    """消息片段"""
    is_mention: bool  # 是否是 @ 提及
    content: str      # 内容（如果是提及，则是被 @ 的名称）


@dataclass
class SendResult:
    """发送结果"""
    success: bool
    message: str
    elapsed_ms: int = 0
    error: Optional[str] = None
    contact: Optional[str] = None


@dataclass
class SendTask:
    """发送任务"""
    text: str
    contact: str
    window: Any  # WindowInfo
    future: asyncio.Future = field(default=None)  # type: ignore


class MessageSender:
    """微信消息发送器

    通过 UI 自动化实现跨平台发送消息：
    1. 点击微信窗口的输入框
    2. 通过剪贴板粘贴消息（支持中文）
    3. 按回车发送

    支持消息队列，确保同一时间只有一个发送操作。
    """

    def __init__(self) -> None:
        """初始化发送器"""
        self.system = platform.system()  # Darwin, Windows, Linux

        # 当前目标窗口信息
        self._current_window: Optional[WindowInfo] = None

        # 消息队列
        self._queue: asyncio.Queue[SendTask] = asyncio.Queue()
        self._processing = False
        self._lock = asyncio.Lock()

        # 统计
        self.total_sent = 0
        self.total_failed = 0
        self.queue_size = 0

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

            # 获取屏幕尺寸进行验证
            screen_width, screen_height = pyautogui.size()
            logger.info(f"屏幕尺寸: {screen_width}x{screen_height}, 点击坐标: ({x}, {y})")

            # 验证坐标是否在屏幕范围内
            if x < 0 or y < 0 or x >= screen_width or y >= screen_height:
                logger.error(
                    f"点击坐标超出屏幕范围: ({x}, {y}), "
                    f"屏幕: {screen_width}x{screen_height}"
                )
                return False

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

    def _parse_message_segments(self, text: str) -> list[MessageSegment]:
        """解析消息，分离普通文本和 @ 提及

        Args:
            text: 原始消息文本

        Returns:
            消息片段列表
        """
        segments: list[MessageSegment] = []
        last_end = 0

        for match in AT_PATTERN.finditer(text):
            start, end = match.span()

            # 添加 @ 之前的普通文本
            if start > last_end:
                plain_text = text[last_end:start]
                if plain_text:
                    segments.append(MessageSegment(is_mention=False, content=plain_text))

            # 添加 @ 提及
            mention_name = match.group(1)
            segments.append(MessageSegment(is_mention=True, content=mention_name))

            last_end = end

        # 添加最后剩余的普通文本
        if last_end < len(text):
            remaining = text[last_end:]
            if remaining:
                segments.append(MessageSegment(is_mention=False, content=remaining))

        # 如果没有 @ 提及，整个消息作为普通文本（非空时）
        if not segments and text:
            segments.append(MessageSegment(is_mention=False, content=text))

        return segments

    def _has_mentions(self, text: str) -> bool:
        """检查消息是否包含 @ 提及

        Args:
            text: 消息文本

        Returns:
            是否包含 @ 提及
        """
        return bool(AT_PATTERN.search(text))

    def _type_at_symbol(self) -> bool:
        """输入 @ 符号

        使用 pyautogui.typewrite 输入 ASCII 字符 @

        Returns:
            是否成功
        """
        try:
            pyautogui.typewrite("@", interval=0.02)
            return True
        except Exception as e:
            logger.error(f"输入 @ 符号失败: {e}")
            return False

    def _type_mention(self, name: str) -> bool:
        """通过键盘模拟输入 @ 提及

        流程：
        1. 输入 @ 字符触发联系人选择菜单
        2. 等待菜单弹出
        3. 输入名称进行筛选
        4. 按回车选中第一个匹配项

        注意：微信选择联系人后会自动添加空格，
        如果原消息 @ 后有空格，可能会出现双空格

        Args:
            name: 要 @ 的联系人名称

        Returns:
            是否成功
        """
        try:
            logger.debug(f"输入 @ 提及: {name}")

            # 1. 输入 @ 字符触发菜单
            if not self._type_at_symbol():
                return False

            time.sleep(AT_MENU_WAIT_TIME)  # 等待菜单弹出

            # 2. 通过剪贴板输入名称（支持中文）
            pyperclip.copy(name)
            hotkey = self._get_paste_hotkey()
            pyautogui.hotkey(*hotkey)
            time.sleep(AT_SELECT_WAIT_TIME)

            # 3. 按回车选中第一个匹配项
            pyautogui.press("enter")
            time.sleep(AT_SELECT_WAIT_TIME)

            logger.debug(f"@ 提及输入完成: {name}")
            return True

        except Exception as e:
            logger.error(f"输入 @ 提及失败: {e}")
            return False

    def _send_with_mentions(self, text: str) -> bool:
        """发送包含 @ 提及的消息

        Args:
            text: 消息文本

        Returns:
            是否成功
        """
        segments = self._parse_message_segments(text)
        logger.info(f"消息分段: {len(segments)} 个片段")

        prev_was_mention = False

        for i, seg in enumerate(segments):
            if seg.is_mention:
                # @ 提及：使用键盘模拟
                logger.debug(f"片段 {i+1}: @ 提及 '{seg.content}'")
                success = self._type_mention(seg.content)
                if not success:
                    logger.warning(f"@ 提及 '{seg.content}' 可能未成功")
                    # 继续尝试，不中断
                # 只有成功时才标记，避免错误移除下一段开头空格
                prev_was_mention = success
            else:
                # 普通文本：使用粘贴
                content = seg.content

                # 如果前一个是 @ 提及，微信会自动添加空格
                # 所以我们需要去掉文本开头的空格避免双空格
                if prev_was_mention and content.startswith(" "):
                    content = content[1:]
                    logger.debug("去掉开头空格，避免双空格")

                if content:  # 确保还有内容要粘贴
                    logger.debug(f"片段 {i+1}: 普通文本 '{content[:20]}{'...' if len(content) > 20 else ''}'")
                    if not self._paste_text(content):
                        return False

                prev_was_mention = False

        return True

    def send_sync(self, text: str, contact: str = "") -> SendResult:
        """同步发送消息

        Args:
            text: 要发送的消息文本
            contact: 联系人名称

        Returns:
            发送结果
        """
        start_time = time.time()

        if not text or not text.strip():
            return SendResult(
                success=False,
                message="消息内容为空",
                error="Empty message",
                contact=contact,
            )

        text = text.strip()
        logger.info(f"[{contact}] 准备发送消息: {text[:50]}{'...' if len(text) > 50 else ''}")

        try:
            # 1. 点击输入框
            if not self._click_input_box():
                self.total_failed += 1
                return SendResult(
                    success=False,
                    message="点击输入框失败",
                    error="Failed to click input box",
                    elapsed_ms=int((time.time() - start_time) * 1000),
                    contact=contact,
                )

            # 2. 输入消息内容
            has_mentions = self._has_mentions(text)
            if has_mentions:
                # 包含 @ 提及：使用分段处理
                logger.info(f"[{contact}] 检测到 @ 提及，使用分段输入")
                if not self._send_with_mentions(text):
                    self.total_failed += 1
                    return SendResult(
                        success=False,
                        message="输入消息失败",
                        error="Failed to input message with mentions",
                        elapsed_ms=int((time.time() - start_time) * 1000),
                        contact=contact,
                    )
            else:
                # 普通消息：直接粘贴
                if not self._paste_text(text):
                    self.total_failed += 1
                    return SendResult(
                        success=False,
                        message="粘贴文本失败",
                        error="Failed to paste text",
                        elapsed_ms=int((time.time() - start_time) * 1000),
                        contact=contact,
                    )

            # 3. 按回车发送
            if not self._press_enter():
                self.total_failed += 1
                return SendResult(
                    success=False,
                    message="按回车失败",
                    error="Failed to press enter",
                    elapsed_ms=int((time.time() - start_time) * 1000),
                    contact=contact,
                )

            elapsed_ms = int((time.time() - start_time) * 1000)
            self.total_sent += 1

            logger.info(f"[{contact}] 消息发送成功: {elapsed_ms}ms")

            return SendResult(
                success=True,
                message="发送成功",
                elapsed_ms=elapsed_ms,
                contact=contact,
            )

        except Exception as e:
            self.total_failed += 1
            logger.error(f"[{contact}] 发送消息异常: {e}")
            return SendResult(
                success=False,
                message=f"发送异常: {e}",
                error=str(e),
                elapsed_ms=int((time.time() - start_time) * 1000),
                contact=contact,
            )

    async def send(self, text: str, contact: str, window: Any) -> SendResult:
        """异步发送消息（加入队列）

        Args:
            text: 要发送的消息文本
            contact: 联系人名称
            window: 窗口信息

        Returns:
            发送结果
        """
        if not text or not text.strip():
            return SendResult(
                success=False,
                message="消息内容为空",
                error="Empty message",
                contact=contact,
            )

        # 创建任务并加入队列
        loop = asyncio.get_running_loop()
        task = SendTask(
            text=text.strip(),
            contact=contact,
            window=window,
            future=loop.create_future(),
        )

        await self._queue.put(task)
        self.queue_size = self._queue.qsize()
        logger.info(f"[{contact}] 消息已加入队列，当前队列长度: {self.queue_size}")

        # 启动队列处理（如果还没启动）
        asyncio.create_task(self._process_queue())

        # 等待任务完成
        result = await task.future
        return result

    async def _process_queue(self) -> None:
        """处理发送队列"""
        async with self._lock:
            if self._processing:
                return  # 已有处理任务在运行
            self._processing = True

        try:
            while not self._queue.empty():
                task = await self._queue.get()
                self.queue_size = self._queue.qsize()

                logger.info(f"[{task.contact}] 开始处理发送任务，剩余队列: {self.queue_size}")

                try:
                    # 设置目标窗口
                    self.set_window(task.window)

                    # 在线程池中执行同步发送
                    result = await asyncio.to_thread(self.send_sync, task.text, task.contact)

                    # 设置结果
                    task.future.set_result(result)

                except Exception as e:
                    logger.error(f"[{task.contact}] 发送任务异常: {e}")
                    task.future.set_result(SendResult(
                        success=False,
                        message=f"发送异常: {e}",
                        error=str(e),
                        contact=task.contact,
                    ))

                finally:
                    self._queue.task_done()

                # 发送间隔，避免操作过快
                await asyncio.sleep(0.3)

        finally:
            self._processing = False

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
            "queue_size": self._queue.qsize(),
            "is_processing": self._processing,
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
