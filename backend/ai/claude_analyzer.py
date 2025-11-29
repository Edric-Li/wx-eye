"""
Claude AI 分析器
使用 Claude Vision API 分析聊天截图
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Optional

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """AI 分析结果"""

    contact: str
    new_messages: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    has_new_content: bool = False
    raw_response: str = ""
    tokens_used: int = 0
    processing_time_ms: int = 0
    error: Optional[str] = None


class ClaudeAnalyzer:
    """Claude Vision 分析器

    使用 Claude API 分析聊天截图，提取结构化消息。
    支持串行处理以避免并发问题和 API 限流。
    """

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "sonnet",
        max_retries: int = 3,
        timeout: float = 30.0,
    ) -> None:
        """初始化分析器

        Args:
            api_key: Anthropic API Key
            base_url: 自定义 API 地址（可选）
            model: 模型选择 (haiku/sonnet/opus)
            max_retries: 最大重试次数
            timeout: 请求超时时间（秒）
        """
        import anthropic

        # 支持自定义 API 地址
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = anthropic.Anthropic(**client_kwargs)
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout
        self.base_url = base_url

        # 串行锁：确保同一时间只处理一个请求
        self._lock = asyncio.Lock()

        # 统计
        self.total_requests = 0
        self.total_tokens = 0

        logger.info(f"Claude 分析器初始化: model={self.model}")

    def _image_to_base64(self, image: Image.Image) -> tuple[str, str]:
        """将 PIL Image 转为 base64

        Args:
            image: PIL Image 对象（已经裁剪过，只包含聊天区域）

        Returns:
            (base64_string, media_type)
        """
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return base64_str, "image/png"

    def _build_prompt(
        self,
        previous_messages: list[str] | None = None,
    ) -> str:
        """构建分析提示词"""
        return """提取微信聊天截图中的消息。返回JSON数组。

规则：
1. 绿色气泡 → 发送者="$self"
2. 白色气泡 → 发送者=气泡上方的昵称文字
3. 白色气泡如果看不到上方的昵称，跳过该消息不要提取
4. 忽略灰色引用气泡

注意：截图顶部第一条消息如果昵称被截断不可见，必须跳过！不要猜测！

格式：[["发送者", "消息内容"], ...]
示例：[["无趣.", "99"], ["无趣.", "a"]]
只返回JSON"""

    async def analyze(
        self,
        contact: str,
        image: Image.Image,
        previous_messages: list[str] | None = None,
    ) -> AnalysisResult:
        """分析聊天截图

        使用串行锁确保同一时间只有一个分析请求。

        Args:
            contact: 联系人名称
            image: 聊天截图
            previous_messages: 历史消息（用于去重）

        Returns:
            分析结果
        """
        async with self._lock:
            return await self._do_analyze(contact, image, previous_messages)

    async def _do_analyze(
        self,
        contact: str,
        image: Image.Image,
        previous_messages: list[str] | None = None,
    ) -> AnalysisResult:
        """实际的分析逻辑"""
        start_time = time.time()
        result = AnalysisResult(contact=contact)

        # 转换图片为 Base64
        encode_start = time.time()
        base64_image, media_type = self._image_to_base64(image)
        encode_time = (time.time() - encode_start) * 1000
        logger.info(f"[{contact}] [AI] 图片编码为 Base64: {encode_time:.1f}ms, 大小={len(base64_image) // 1024}KB")

        prompt = self._build_prompt(previous_messages)

        # 重试逻辑
        last_error = None
        for attempt in range(self.max_retries):
            try:
                api_start = time.time()
                logger.info(f"[{contact}] [AI] 开始调用 Claude API (尝试 {attempt + 1}/{self.max_retries})...")

                response = await asyncio.to_thread(
                    self._call_api,
                    base64_image,
                    media_type,
                    prompt,
                )

                api_time = (time.time() - api_start) * 1000
                logger.info(f"[{contact}] [AI] Claude API 响应耗时: {api_time:.1f}ms")

                # 解析响应
                parse_start = time.time()
                result = self._parse_response(contact, response)
                parse_time = (time.time() - parse_start) * 1000
                logger.debug(f"[{contact}] [AI] 响应解析耗时: {parse_time:.1f}ms")

                result.processing_time_ms = int((time.time() - start_time) * 1000)

                self.total_requests += 1
                self.total_tokens += result.tokens_used

                logger.info(
                    f"[{contact}] [AI] 分析完成: "
                    f"{len(result.new_messages)} 条消息, "
                    f"{result.tokens_used} tokens, "
                    f"总耗时={result.processing_time_ms}ms (编码={encode_time:.0f}ms, API={api_time:.0f}ms, 解析={parse_time:.0f}ms)"
                )

                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    f"[{contact}] [AI] 分析失败 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))  # 指数退避

        # 所有重试都失败
        result.error = str(last_error)
        result.processing_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[{contact}] AI 分析最终失败: {last_error}")

        return result

    def _call_api(
        self,
        base64_image: str,
        media_type: str,
        prompt: str,
    ) -> dict[str, Any]:
        """调用 Claude API（同步）"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_image,
                            },
                        },
                    ],
                }
            ],
        )

        content = response.content[0].text
        logger.info(f"[AI] 原始输出: {content}")

        return {
            "content": content,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }

    def _parse_response(
        self,
        contact: str,
        response: dict[str, Any],
    ) -> AnalysisResult:
        """解析 API 响应"""
        result = AnalysisResult(contact=contact)

        raw_text = response.get("content", "")
        result.raw_response = raw_text

        usage = response.get("usage", {})
        result.tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

        # 尝试解析 JSON
        try:
            # 提取 JSON 部分（可能被包裹在 markdown 代码块中）
            json_text = raw_text
            if "```json" in raw_text:
                start = raw_text.find("```json") + 7
                end = raw_text.find("```", start)
                json_text = raw_text[start:end].strip()
            elif "```" in raw_text:
                start = raw_text.find("```") + 3
                end = raw_text.find("```", start)
                json_text = raw_text[start:end].strip()

            data = json.loads(json_text)

            # 解析二维数组格式：[["sender", "content"], ...]
            if isinstance(data, list):
                result.new_messages = [
                    {"sender": msg[0], "content": msg[1]}
                    for msg in data
                    if isinstance(msg, list) and len(msg) >= 2
                ]
            else:
                result.new_messages = []

            result.has_new_content = len(result.new_messages) > 0

            # 记录 AI 原始输出用于调试
            logger.info(f"[{contact}] [AI] 原始输出: {raw_text[:500]}")

        except json.JSONDecodeError as e:
            logger.warning(f"[{contact}] JSON 解析失败: {e}\nAI 原始回复:\n{raw_text}")
            result.error = f"JSON 解析失败: {e}"

        return result

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "model": self.model,
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self._estimate_cost(),
        }

    def _estimate_cost(self) -> float:
        """估算成本（USD）"""
        # Claude 3 定价（大约）
        # Haiku: $0.25/$1.25 per MTok
        # Sonnet: $3/$15 per MTok
        # Opus: $15/$75 per MTok
        if "haiku" in self.model:
            rate = 0.00075  # 平均
        elif "sonnet" in self.model:
            rate = 0.009
        else:
            rate = 0.045

        return (self.total_tokens / 1000) * rate
