"""
AI 模块 - 聊天记录智能分析

包含:
- MessageDeduplicator: 消息去重与增量识别
- ClaudeAnalyzer: Claude Vision API 分析
- AIMessageProcessor: 集成处理器
"""

from .message_deduplicator import MessageDeduplicator, ChatMessage
from .claude_analyzer import ClaudeAnalyzer, AnalysisResult
from .processor import AIMessageProcessor

__all__ = [
    "MessageDeduplicator",
    "ChatMessage",
    "ClaudeAnalyzer",
    "AnalysisResult",
    "AIMessageProcessor",
]
