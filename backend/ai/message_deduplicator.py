"""
消息去重模块
用于识别新增消息，避免重复处理
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """单条聊天消息"""

    sender: str
    content: str
    time: Optional[str] = None
    raw_text: str = ""

    def __hash__(self) -> int:
        # 使用发送者和内容生成哈希
        return hash((self.sender, self.content))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChatMessage):
            return False
        return self.sender == other.sender and self.content == other.content


@dataclass
class DeduplicationResult:
    """去重结果"""

    new_messages: list[ChatMessage] = field(default_factory=list)
    total_current: int = 0
    total_history: int = 0
    is_first_scan: bool = False


class MessageDeduplicator:
    """消息去重器

    对比历史消息，识别新增消息。

    示例:
        历史: [A, B, C, D]
        当前: [B, C, D, E, F]
        新增: [E, F]
    """

    def __init__(self, max_history: int = 100) -> None:
        """初始化去重器

        Args:
            max_history: 每个联系人保留的最大历史消息数
        """
        self._max_history = max_history
        # 联系人 -> 历史消息列表
        self._history: dict[str, list[str]] = {}
        # 联系人 -> 历史消息集合（用于快速查找）
        self._history_set: dict[str, set[str]] = {}

    def extract_new_messages(
        self,
        contact: str,
        current_messages: list[str],
    ) -> DeduplicationResult:
        """提取新增消息

        Args:
            contact: 联系人名称
            current_messages: 当前截图中识别出的消息列表

        Returns:
            去重结果
        """
        history = self._history.get(contact, [])
        history_set = self._history_set.get(contact, set())

        result = DeduplicationResult(
            total_current=len(current_messages),
            total_history=len(history),
        )

        if not history:
            # 首次扫描
            result.is_first_scan = True
            result.new_messages = [
                ChatMessage(sender="", content=msg, raw_text=msg)
                for msg in current_messages
            ]
            logger.info(f"[{contact}] 首次扫描，共 {len(current_messages)} 条消息")
        else:
            # 找出新消息（不在历史中的）
            for msg in current_messages:
                normalized = self._normalize_message(msg)
                if normalized and normalized not in history_set:
                    result.new_messages.append(
                        ChatMessage(sender="", content=msg, raw_text=msg)
                    )

            if result.new_messages:
                logger.info(
                    f"[{contact}] 发现 {len(result.new_messages)} 条新消息 "
                    f"(当前 {len(current_messages)}, 历史 {len(history)})"
                )

        # 更新历史
        self._update_history(contact, current_messages)

        return result

    def _normalize_message(self, msg: str) -> str:
        """标准化消息用于比较"""
        # 去除首尾空白，压缩连续空白
        return " ".join(msg.split())

    def _update_history(self, contact: str, messages: list[str]) -> None:
        """更新历史记录"""
        normalized = [self._normalize_message(m) for m in messages if m.strip()]

        # 限制历史大小
        if len(normalized) > self._max_history:
            normalized = normalized[-self._max_history:]

        self._history[contact] = normalized
        self._history_set[contact] = set(normalized)

    def parse_messages_from_text(self, raw_text: str) -> list[str]:
        """从 OCR 文字中解析消息列表

        微信聊天格式通常是：
        - 发送者名称
        - 时间（可选）
        - 消息内容

        Args:
            raw_text: OCR 提取的原始文字

        Returns:
            消息列表
        """
        lines = raw_text.strip().split("\n")
        messages: list[str] = []
        current_message: list[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否是新消息的开始
            if self._is_message_boundary(line) and current_message:
                # 保存之前的消息
                msg = " ".join(current_message)
                if msg:
                    messages.append(msg)
                current_message = [line]
            else:
                current_message.append(line)

        # 保存最后一条消息
        if current_message:
            msg = " ".join(current_message)
            if msg:
                messages.append(msg)

        return messages

    def _is_message_boundary(self, line: str) -> bool:
        """判断是否是消息边界（新消息的开始）

        启发式规则：
        1. 包含时间戳 (HH:MM 格式)
        2. 是系统消息（包含特定关键词）
        """
        # 时间戳模式：10:30, 下午3:45, 昨天 10:30 等
        time_patterns = [
            r"\d{1,2}:\d{2}",  # 10:30
            r"上午|下午|凌晨|早上|中午|晚上",  # 时间段
            r"昨天|今天|星期[一二三四五六日]",  # 日期
        ]

        for pattern in time_patterns:
            if re.search(pattern, line):
                return True

        return False

    def parse_structured_messages(
        self, raw_text: str
    ) -> list[ChatMessage]:
        """解析为结构化消息

        尝试从 OCR 文字中提取发送者、时间和内容。

        Args:
            raw_text: OCR 提取的原始文字

        Returns:
            结构化消息列表
        """
        lines = raw_text.strip().split("\n")
        messages: list[ChatMessage] = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # 尝试解析时间
            time_match = re.search(r"(\d{1,2}:\d{2})", line)

            if time_match:
                time_str = time_match.group(1)
                # 时间之前可能是发送者名称
                before_time = line[:time_match.start()].strip()
                after_time = line[time_match.end():].strip()

                sender = before_time if before_time else "未知"

                # 收集消息内容（可能跨多行）
                content_parts = [after_time] if after_time else []
                i += 1

                # 继续收集直到下一个时间戳
                while i < len(lines):
                    next_line = lines[i].strip()
                    if not next_line:
                        i += 1
                        continue
                    if re.search(r"\d{1,2}:\d{2}", next_line):
                        break
                    content_parts.append(next_line)
                    i += 1

                content = " ".join(content_parts)
                if content:
                    messages.append(ChatMessage(
                        sender=sender,
                        content=content,
                        time=time_str,
                        raw_text=line,
                    ))
            else:
                i += 1

        return messages

    def reset(self, contact: str | None = None) -> None:
        """重置历史记录

        Args:
            contact: 指定联系人，为 None 时重置所有
        """
        if contact is None:
            self._history.clear()
            self._history_set.clear()
            logger.info("已重置所有联系人的消息历史")
        else:
            self._history.pop(contact, None)
            self._history_set.pop(contact, None)
            logger.info(f"已重置联系人 [{contact}] 的消息历史")

    def get_history_count(self, contact: str) -> int:
        """获取联系人的历史消息数量"""
        return len(self._history.get(contact, []))
