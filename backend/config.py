"""
配置管理模块
使用 pydantic-settings 支持环境变量和 .env 文件
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置

    配置优先级：环境变量 > .env 文件 > 默认值

    使用示例:
        settings = get_settings()
        print(settings.anthropic_api_key)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============ 基础配置 ============
    app_name: str = "WxEye"
    app_version: str = "0.3.0"
    debug: bool = False

    # ============ 服务器配置 ============
    host: str = "0.0.0.0"
    port: int = 8000

    # ============ 截图配置 ============
    screenshot_dir: str = "static/screenshots"
    capture_interval: float = 0.5  # 截图间隔（秒）

    # ============ Claude AI 配置 ============
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: Optional[str] = None  # 自定义 API 地址
    claude_model: str = "sonnet"  # haiku / sonnet / opus

    # ============ AI 处理配置 ============
    enable_ai: bool = True  # 是否启用 AI 分析
    ai_max_retries: int = 3
    ai_timeout: float = 30.0

    # ============ 成本控制 ============
    max_ai_calls_per_minute: int = 10  # API 调用限制

    @property
    def is_ai_enabled(self) -> bool:
        """检查 AI 是否可用"""
        return self.enable_ai and bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
