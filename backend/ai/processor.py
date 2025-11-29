"""
AI 消息处理器
整合 Claude Vision 分析与本地去重的处理流水线
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from PIL import Image

from .message_deduplicator import MessageDeduplicator
from .claude_analyzer import ClaudeAnalyzer, AnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStats:
    """处理统计"""

    total_submitted: int = 0
    dedup_filtered: int = 0  # 去重过滤（无新消息）
    ai_analyzed: int = 0  # AI 分析次数
    ai_failed: int = 0  # AI 分析失败
    total_new_messages: int = 0  # 识别的新消息总数


@dataclass
class ProcessingResult:
    """单次处理结果"""

    contact: str
    stage: str = ""  # "dedup_filtered", "ai_analyzed", "ai_failed"
    new_messages: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    ai_time_ms: int = 0
    tokens_used: int = 0
    error: Optional[str] = None
    # 图片引用，用于在回调中发送截图
    image: Optional[Image.Image] = field(default=None, repr=False)
    # 保存的文件名
    filename: Optional[str] = None


class AIMessageProcessor:
    """AI 消息处理器

    处理流程：
    1. Claude AI 识别截图中的消息
    2. 本地去重算法（比对历史，提取新消息）

    特点：
    - 串行处理队列（避免并发和 API 限流）
    - 本地去重，更精确可靠
    """

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "sonnet",
        enable_ai: bool = True,
    ) -> None:
        """初始化处理器

        Args:
            api_key: Anthropic API Key
            base_url: 自定义 API 地址（可选）
            model: Claude 模型选择
            enable_ai: 是否启用 AI 分析
        """
        self.dedup = MessageDeduplicator()
        self.claude: ClaudeAnalyzer | None = None
        self.enable_ai = enable_ai

        if enable_ai and api_key:
            self.claude = ClaudeAnalyzer(api_key=api_key, base_url=base_url, model=model)

        # 处理队列: (contact, image, callback, filename)
        self._queue: asyncio.Queue[tuple[str, Image.Image, Optional[Callable], Optional[str]]] = asyncio.Queue()
        self._is_running = False
        self._task: asyncio.Task | None = None

        # 统计
        self.stats = ProcessingStats()

        # 回调函数（处理完成时调用）
        self._on_result: Optional[Callable[[ProcessingResult], Any]] = None

        # 本地去重：每个联系人的历史消息
        self._message_history: dict[str, list[tuple[str, str]]] = {}

        logger.info(
            f"AI 处理器初始化: enable_ai={enable_ai}, "
            f"model={model if enable_ai else 'N/A'}"
        )

    def set_callback(self, callback: Callable[[ProcessingResult], Any]) -> None:
        """设置结果回调函数"""
        self._on_result = callback

    async def start(self) -> None:
        """启动处理队列"""
        if self._is_running:
            return

        self._is_running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("AI 处理器已启动")

    async def stop(self) -> None:
        """停止处理队列"""
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

        logger.info("AI 处理器已停止")

    async def submit(
        self,
        contact: str,
        image: Image.Image,
        callback: Optional[Callable[[ProcessingResult], Any]] = None,
        filename: Optional[str] = None,
    ) -> None:
        """提交图片到处理队列

        Args:
            contact: 联系人名称
            image: 截图图片
            callback: 可选的单次回调
            filename: 保存的文件名（用于回调中发送截图）
        """
        await self._queue.put((contact, image, callback, filename))
        self.stats.total_submitted += 1

    async def _process_loop(self) -> None:
        """处理循环"""
        while self._is_running:
            try:
                # 等待队列中的任务
                contact, image, callback, filename = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )

                # 处理
                result = await self._process_single(contact, image, filename)

                # 触发回调
                if callback:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(result)
                        else:
                            callback(result)
                    except Exception as e:
                        logger.error(f"回调执行失败: {e}")

                if self._on_result:
                    try:
                        if asyncio.iscoroutinefunction(self._on_result):
                            await self._on_result(result)
                        else:
                            self._on_result(result)
                    except Exception as e:
                        logger.error(f"全局回调执行失败: {e}")

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"处理循环错误: {e}")

    async def _process_single(
        self,
        contact: str,
        image: Image.Image,
        filename: Optional[str] = None,
    ) -> ProcessingResult:
        """处理单张图片

        流程：像素级比对已在 main.py 完成，这里直接进行 AI 分析 + 本地去重
        """
        total_start = time.time()
        result = ProcessingResult(contact=contact)
        # 保存图片引用和文件名，用于回调中发送截图
        result.image = image
        result.filename = filename

        logger.info(f"[{contact}] ========== 开始处理截图 ==========")
        logger.info(f"[{contact}] 图片尺寸: {image.size[0]}x{image.size[1]}")

        # Step 1: AI 识别截图中的所有消息
        if not (self.enable_ai and self.claude):
            result.stage = "ai_disabled"
            total_time = int((time.time() - total_start) * 1000)
            logger.info(f"[{contact}] ========== 处理结束 (AI未启用): 总耗时 {total_time}ms ==========")
            return result

        logger.info(f"[{contact}] [Step 1/2] 开始 AI 分析...")
        ai_start = time.time()
        ai_result = await self.claude.analyze(
            contact=contact,
            image=image,
            previous_messages=None,  # 不传历史，AI只负责识别
        )
        ai_actual_time = int((time.time() - ai_start) * 1000)

        result.ai_time_ms = ai_result.processing_time_ms
        result.tokens_used = ai_result.tokens_used
        logger.info(f"[{contact}] [Step 1/2] AI 分析完成: {ai_actual_time}ms, tokens={result.tokens_used}")

        if ai_result.error:
            result.stage = "ai_failed"
            result.error = ai_result.error
            self.stats.ai_failed += 1
            total_time = int((time.time() - total_start) * 1000)
            logger.error(f"[{contact}] ========== 处理结束 (AI失败): 总耗时 {total_time}ms, 错误={ai_result.error} ==========")
            return result

        # Step 2: 本地去重算法
        logger.info(f"[{contact}] [Step 2/2] 开始本地去重...")
        dedup_start = time.time()
        current_messages = [
            (msg.get("sender", ""), msg.get("content", ""))
            for msg in ai_result.new_messages
        ]

        new_messages = self._local_dedup(contact, current_messages)
        dedup_time = int((time.time() - dedup_start) * 1000)
        logger.info(f"[{contact}] [Step 2/2] 本地去重完成: {dedup_time}ms, 原始消息={len(current_messages)}条, 新消息={len(new_messages)}条")

        if not new_messages:
            result.stage = "dedup_filtered"
            self.stats.dedup_filtered += 1
            total_time = int((time.time() - total_start) * 1000)
            logger.info(f"[{contact}] ========== 处理结束 (去重过滤): 总耗时 {total_time}ms ==========")
            return result

        # 有新消息
        result.stage = "ai_analyzed"
        result.new_messages = [
            {"sender": sender, "content": content}
            for sender, content in new_messages
        ]
        self.stats.ai_analyzed += 1
        self.stats.total_new_messages += len(new_messages)

        total_time = int((time.time() - total_start) * 1000)
        logger.info(
            f"[{contact}] ========== 处理完成: 识别到 {len(new_messages)} 条新消息 ==========\n"
            f"    总耗时: {total_time}ms\n"
            f"    - AI分析: {result.ai_time_ms}ms\n"
            f"    - 去重: {dedup_time}ms"
        )

        return result

    def _local_dedup(
        self,
        contact: str,
        current_messages: list[tuple[str, str]],
    ) -> list[tuple[str, str]]:
        """本地去重算法

        比对当前消息和历史消息，找出新增的消息。
        微信消息是追加到底部的，所以只需要找尾部新增的部分。

        Args:
            contact: 联系人
            current_messages: 当前识别的消息列表 [(sender, content), ...]

        Returns:
            新增的消息列表
        """
        history = self._message_history.get(contact, [])

        if not history:
            # 首次识别，全部作为新消息
            self._message_history[contact] = current_messages.copy()
            return current_messages

        if not current_messages:
            return []

        # 找到历史消息在当前消息中的位置
        # 策略：找最长的尾部匹配
        new_messages = []

        # 方法：从当前消息末尾向前找，直到找到与历史末尾匹配的位置
        history_set = set(history)

        # 简单方法：找出不在历史中的消息（保持顺序）
        # 但要考虑相同内容可能出现多次

        # 更好的方法：序列比对，找尾部新增
        # 假设历史是 [A, B, C]，当前是 [A, B, C, D, E]
        # 那么新增是 [D, E]

        # 找到历史最后一条在当前列表中的位置
        if history:
            last_history = history[-1]
            last_match_idx = -1

            # 从后向前找历史最后一条消息的位置
            for i in range(len(current_messages) - 1, -1, -1):
                if current_messages[i] == last_history:
                    last_match_idx = i
                    break

            if last_match_idx >= 0:
                # 找到了，新消息是 last_match_idx 之后的
                new_messages = current_messages[last_match_idx + 1:]
            else:
                # 没找到历史最后一条，可能是滚动了
                # 尝试找任意匹配点
                for i in range(len(current_messages) - 1, -1, -1):
                    if current_messages[i] in history_set:
                        new_messages = current_messages[i + 1:]
                        break
                else:
                    # 完全没有匹配，可能是新对话，全部作为新消息
                    new_messages = current_messages

        # 更新历史
        self._message_history[contact] = current_messages.copy()

        return new_messages

    def reset(self, contact: str | None = None) -> None:
        """重置处理状态

        Args:
            contact: 指定联系人，为 None 时重置所有
        """
        self.dedup.reset(contact)

        # 重置消息历史
        if contact is None:
            self._message_history.clear()
            self.stats = ProcessingStats()
        elif contact in self._message_history:
            del self._message_history[contact]

        logger.info(f"已重置处理状态: {contact or '全部'}")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        stats = {
            "total_submitted": self.stats.total_submitted,
            "dedup_filtered": self.stats.dedup_filtered,
            "ai_analyzed": self.stats.ai_analyzed,
            "ai_failed": self.stats.ai_failed,
            "total_new_messages": self.stats.total_new_messages,
            "queue_size": self._queue.qsize(),
            "is_running": self._is_running,
        }

        if self.claude:
            stats["claude"] = self.claude.get_stats()

        # 计算过滤率
        if self.stats.total_submitted > 0:
            filtered = self.stats.dedup_filtered
            stats["filter_rate"] = f"{filtered / self.stats.total_submitted * 100:.1f}%"

        return stats
