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

        # 已发送消息缓存：用于过滤用户自己发送的消息，避免广播
        # 格式: {contact: [(content, timestamp), ...]}
        self._sent_messages: dict[str, list[tuple[str, float]]] = {}
        self._sent_message_ttl: float = 30.0  # 30秒内的发送消息会被过滤

        logger.info(
            f"AI 处理器初始化: enable_ai={enable_ai}, "
            f"model={model if enable_ai else 'N/A'}"
        )

    def set_callback(self, callback: Callable[[ProcessingResult], Any]) -> None:
        """设置结果回调函数"""
        self._on_result = callback

    def add_sent_message(self, contact: str, text: str) -> None:
        """记录用户发送的消息，用于后续过滤

        发送消息后调用此方法，在 AI 识别新消息时会过滤掉这些已发送的消息，
        避免将用户自己发送的消息作为 message.received 事件广播。

        Args:
            contact: 联系人名称
            text: 发送的消息内容
        """
        if contact not in self._sent_messages:
            self._sent_messages[contact] = []

        self._sent_messages[contact].append((text.strip(), time.time()))
        preview = text[:50] + "..." if len(text) > 50 else text
        logger.debug(f"[{contact}] 记录已发送消息: {preview}")

    def _clean_expired_sent_messages(self, contact: str) -> None:
        """清理过期的已发送消息记录"""
        if contact not in self._sent_messages:
            return

        now = time.time()
        self._sent_messages[contact] = [
            (text, ts) for text, ts in self._sent_messages[contact]
            if now - ts < self._sent_message_ttl
        ]

    def _is_sent_by_user(self, contact: str, content: str) -> bool:
        """检查消息是否是用户发送的

        使用规范化比较，去除首尾空白并压缩连续空白，
        提高 AI 识别结果与原始发送消息的匹配率。
        """
        if contact not in self._sent_messages:
            return False

        # 规范化：去除首尾空白，压缩连续空白
        content_normalized = " ".join(content.split())

        for sent_text, _ in self._sent_messages[contact]:
            sent_normalized = " ".join(sent_text.split())
            if sent_normalized == content_normalized:
                return True
        return False

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

        # Step 3: 过滤掉用户自己发送的消息
        self._clean_expired_sent_messages(contact)
        if new_messages:
            before_filter = len(new_messages)
            new_messages = [
                (sender, content) for sender, content in new_messages
                if not self._is_sent_by_user(contact, content)
            ]
            filtered_count = before_filter - len(new_messages)
            if filtered_count > 0:
                logger.info(f"[{contact}] 过滤掉 {filtered_count} 条用户发送的消息")

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
        """本地去重算法 - 最长后缀序列匹配

        核心思想：找历史消息的最长连续后缀在当前消息中的位置，
        该位置之后的消息就是新消息。

        示例1 - 正常追加:
            历史: [A, B, C]
            当前: [A, B, C, D, E]
            匹配后缀 [A, B, C] 在位置 0-2，新消息: [D, E]

        示例2 - 重复消息:
            历史: [A, B, C]
            当前: [A, B, C, E, C]
            匹配后缀 [A, B, C] 在位置 0-2，新消息: [E, C]

        示例3 - 历史被滚出:
            历史: [A, B, C, D]
            当前: [C, D, E, F]  (A, B 已滚出屏幕)
            匹配后缀 [C, D] 在位置 0-1，新消息: [E, F]

        Args:
            contact: 联系人
            current_messages: 当前识别的消息列表 [(sender, content), ...]

        Returns:
            新增的消息列表
        """
        history = self._message_history.get(contact, [])

        if not history:
            # 首次识别，记录但不作为新消息（避免广播历史）
            self._message_history[contact] = current_messages.copy()
            logger.info(f"[{contact}] 首次识别，记录 {len(current_messages)} 条消息作为基线")
            return []

        if not current_messages:
            return []

        # 最长后缀序列匹配算法
        new_messages = self._find_new_messages_by_suffix_match(history, current_messages)

        # 更新历史：合并而非替换，处理滚动场景
        self._message_history[contact] = self._merge_history(
            history, current_messages, max_size=200
        )

        return new_messages

    def _find_new_messages_by_suffix_match(
        self,
        history: list[tuple[str, str]],
        current: list[tuple[str, str]],
    ) -> list[tuple[str, str]]:
        """通过后缀匹配找出新消息

        从历史的完整序列开始，逐步缩短，找到在当前消息中能匹配的最长后缀。
        """
        if not history or not current:
            return []

        new_start = self._find_overlap_end(history, current)

        if new_start is None:
            # 完全没有重叠
            logger.warning("历史与当前完全无重叠，重置基线并返回当前消息")
            return list(current)

        new_messages = list(current[new_start:])
        if new_messages:
            logger.debug(f"识别新消息: {len(new_messages)} 条")
        return new_messages

    def _find_overlap_end(
        self,
        history: list[tuple[str, str]],
        current: list[tuple[str, str]],
    ) -> int | None:
        """找到历史与当前重叠区域的结束位置

        使用两级匹配策略：
        1. 后缀序列匹配：找历史后缀在当前中的完整匹配
        2. 锚点匹配：找历史中任意一条消息在当前中的位置

        Returns:
            重叠结束后的位置索引（新消息从此开始），无重叠返回 None
        """
        if not history or not current:
            return None

        # 策略1：后缀序列匹配（优先，更精确）
        max_suffix_len = min(len(history), len(current), 50)
        for suffix_len in range(max_suffix_len, 0, -1):
            suffix = history[-suffix_len:]
            match_pos = self._find_sequence(current, suffix)
            if match_pos >= 0:
                logger.debug(f"后缀匹配: len={suffix_len}, pos={match_pos}")
                return match_pos + suffix_len

        # 策略2：锚点匹配（后备，处理 AI 识别差异）
        for anchor_idx in range(len(history) - 1, -1, -1):
            anchor = history[anchor_idx]
            # 从后向前找（取最后出现的位置）
            for pos in range(len(current) - 1, -1, -1):
                if current[pos] == anchor:
                    logger.debug(f"锚点匹配: anchor_idx={anchor_idx}, pos={pos}")
                    return pos + 1

        return None

    def _find_sequence(
        self,
        messages: list[tuple[str, str]],
        sequence: list[tuple[str, str]],
    ) -> int:
        """在消息列表中查找连续序列的起始位置

        Returns:
            匹配的起始位置，未找到返回 -1
        """
        if not sequence or len(sequence) > len(messages):
            return -1

        seq_len = len(sequence)
        for i in range(len(messages) - seq_len + 1):
            if messages[i:i + seq_len] == sequence:
                return i

        return -1

    def _merge_history(
        self,
        history: list[tuple[str, str]],
        current: list[tuple[str, str]],
        max_size: int = 200,
    ) -> list[tuple[str, str]]:
        """合并历史记录

        策略：找历史与当前的重叠区域，然后正确拼接。
        支持滚动场景，保留重复消息。

        示例:
            历史: [A, B, B, C]
            当前: [B, C, D, D]
            重叠: [B, C]
            合并: [A, B, B, C, D, D]
        """
        if not history:
            result = current.copy()
        elif not current:
            result = history.copy()
        else:
            new_start = self._find_overlap_end(history, current)
            if new_start is None:
                # 完全无重叠，用当前替换
                logger.warning("合并历史: 完全无重叠，用当前消息替换历史")
                result = current.copy()
            else:
                # 历史 + 当前新增部分
                result = list(history) + list(current[new_start:])

        # 限制大小
        if len(result) > max_size:
            result = result[-max_size:]
        return result

    def reset(self, contact: str | None = None) -> None:
        """重置处理状态

        Args:
            contact: 指定联系人，为 None 时重置所有
        """
        self.dedup.reset(contact)

        # 重置消息历史和已发送消息缓存
        if contact is None:
            self._message_history.clear()
            self._sent_messages.clear()
            self.stats = ProcessingStats()
        else:
            if contact in self._message_history:
                del self._message_history[contact]
            if contact in self._sent_messages:
                del self._sent_messages[contact]

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
