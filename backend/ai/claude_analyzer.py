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
        return """提取微信聊天截图中的消息。用XML格式返回。

规则：
1. 绿色气泡 → 发送者="$self"
2. 白色气泡 → 发送者=气泡上方的昵称文字
3. 白色气泡如果看不到上方的昵称，跳过该消息不要提取
4. 忽略灰色引用气泡

注意：截图顶部第一条消息如果昵称被截断不可见，必须跳过！不要猜测！

格式：
<messages>
<m><s>发送者</s><c>消息内容</c></m>
</messages>

示例：
<messages>
<m><s>无趣.</s><c>99</c></m>
<m><s>无趣.</s><c>a</c></m>
</messages>

只返回XML，不要任何其他内容。"""

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

    def _normalize_json_quotes(self, json_text: str) -> str:
        """规范化 JSON 字符串中的引号

        Claude 有时会在 JSON 输出中混用中文引号和英文引号，导致解析失败。
        这个方法会智能地处理这种情况。

        Args:
            json_text: 原始 JSON 文本

        Returns:
            规范化后的 JSON 文本
        """
        # 简单策略：直接将中文引号替换为英文引号
        # 这对于 JSON 结构来说是安全的，因为：
        # 1. 如果中文引号是 JSON 边界符，替换成英文引号是正确的
        # 2. 如果中文引号在字符串内容中，替换成英文引号后需要转义
        #
        # 但是情况2比较复杂，我们采用另一种策略：
        # 将中文引号替换成一个安全的占位符，解析成功后再还原

        # 检查是否包含中文引号
        if '\u201c' not in json_text and '\u201d' not in json_text:
            # 没有中文引号，直接返回
            return json_text

        # 尝试先直接解析，如果成功就不需要处理
        try:
            json.loads(json_text)
            return json_text
        except json.JSONDecodeError:
            pass

        # 策略：将中文引号成对替换
        # 在 JSON 中，字符串边界的引号总是成对出现的：["...", "..."]
        # 我们需要找到这些结构边界处的中文引号并替换为英文引号

        result = []
        i = 0
        in_string = False
        string_start_char = None

        while i < len(json_text):
            char = json_text[i]

            if not in_string:
                # 不在字符串内
                if char == '"':
                    in_string = True
                    string_start_char = '"'
                    result.append(char)
                elif char == '\u201c':  # 中文左引号作为字符串开始
                    in_string = True
                    string_start_char = '\u201c'
                    result.append('"')  # 替换为英文引号
                else:
                    result.append(char)
            else:
                # 在字符串内
                if char == '\\' and i + 1 < len(json_text):
                    # 转义序列，跳过下一个字符
                    result.append(char)
                    result.append(json_text[i + 1])
                    i += 2
                    continue
                elif (string_start_char == '"' and char == '"') or \
                     (string_start_char == '\u201c' and char == '\u201d'):
                    # 字符串结束
                    in_string = False
                    string_start_char = None
                    result.append('"')  # 统一用英文引号结束
                elif char in '\u201c\u201d':
                    # 字符串内部的中文引号，需要转义
                    result.append('\\"')
                else:
                    result.append(char)

            i += 1

        normalized = ''.join(result)

        # 验证规范化后的 JSON 是否有效
        try:
            json.loads(normalized)
            return normalized
        except json.JSONDecodeError:
            # 如果还是失败，尝试最后的简单替换策略
            # 直接替换所有中文引号为英文引号
            simple_replace = json_text.replace('\u201c', '"').replace('\u201d', '"')
            simple_replace = simple_replace.replace('\u2018', "'").replace('\u2019', "'")
            return simple_replace

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

        # 尝试解析 XML
        try:
            # 提取 XML 部分（可能被包裹在 markdown 代码块中）
            xml_text = raw_text
            if "```xml" in raw_text:
                start = raw_text.find("```xml") + 6
                end = raw_text.find("```", start)
                xml_text = raw_text[start:end].strip()
            elif "```" in raw_text:
                start = raw_text.find("```") + 3
                end = raw_text.find("```", start)
                xml_text = raw_text[start:end].strip()

            # 确保有 messages 根元素
            if "<messages>" not in xml_text:
                # 可能只返回了消息内容，尝试包装
                if "<m>" in xml_text:
                    xml_text = f"<messages>{xml_text}</messages>"

            result.new_messages = self._parse_xml_messages(xml_text)
            result.has_new_content = len(result.new_messages) > 0

            # 记录 AI 原始输出用于调试
            logger.info(f"[{contact}] [AI] 原始输出: {raw_text[:500]}")

        except Exception as e:
            # 如果 XML 解析失败，尝试回退到 JSON 解析（兼容旧响应）
            try:
                result.new_messages = self._parse_json_fallback(raw_text)
                result.has_new_content = len(result.new_messages) > 0
                logger.info(f"[{contact}] [AI] XML解析失败，JSON回退成功")
            except Exception as json_e:
                logger.warning(f"[{contact}] 解析失败: XML={e}, JSON={json_e}\nAI 原始回复:\n{raw_text}")
                result.error = f"解析失败: {e}"

        return result

    def _parse_xml_messages(self, xml_text: str) -> list[dict[str, Any]]:
        """解析 XML 格式的消息"""
        import re

        messages = []
        # 使用正则表达式提取消息，比 XML 解析器更宽容
        pattern = r'<m>\s*<s>(.*?)</s>\s*<c>(.*?)</c>\s*</m>'
        matches = re.findall(pattern, xml_text, re.DOTALL)

        for sender, content in matches:
            # 清理可能的 CDATA 或转义
            sender = sender.strip()
            content = content.strip()
            # 处理 XML 实体
            content = content.replace('&lt;', '<').replace('&gt;', '>')
            content = content.replace('&amp;', '&').replace('&quot;', '"')
            messages.append({"sender": sender, "content": content})

        return messages

    def _parse_json_fallback(self, raw_text: str) -> list[dict[str, Any]]:
        """JSON 回退解析（用于兼容旧格式响应）"""
        json_text = raw_text
        if "```json" in raw_text:
            start = raw_text.find("```json") + 7
            end = raw_text.find("```", start)
            json_text = raw_text[start:end].strip()
        elif "```" in raw_text:
            start = raw_text.find("```") + 3
            end = raw_text.find("```", start)
            json_text = raw_text[start:end].strip()

        # 规范化引号
        json_text = self._normalize_json_quotes(json_text)

        data = json.loads(json_text)

        if isinstance(data, list):
            return [
                {"sender": msg[0], "content": msg[1]}
                for msg in data
                if isinstance(msg, list) and len(msg) >= 2
            ]
        return []

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
