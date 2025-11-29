"""
REST API 路由
提供窗口查找和截图管理的 REST 接口
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from capture import WindowFinder

router = APIRouter()
finder = WindowFinder()


class WindowResponse(BaseModel):
    """窗口信息响应"""

    title: str
    x: int
    y: int
    width: int
    height: int
    pid: int | None = None


class CaptureConfig(BaseModel):
    """截图配置"""

    interval: float = 0.1  # 截图间隔（秒）
    window_name: str = "微信"  # 目标窗口名
    auto_cleanup: bool = True  # 自动清理旧截图
    keep_count: int = 100  # 保留截图数量


class CaptureStatus(BaseModel):
    """截图服务状态"""

    is_running: bool
    window_found: bool
    window_info: WindowResponse | None = None
    total_captures: int = 0
    significant_captures: int = 0
    config: CaptureConfig | None = None


@router.get("/windows", response_model=list[WindowResponse])
async def list_windows():
    """列出所有窗口"""
    windows = finder.list_all_windows()
    return [
        WindowResponse(title=w.title, x=w.x, y=w.y, width=w.width, height=w.height, pid=w.pid)
        for w in windows
    ]


@router.get("/windows/search/{name}", response_model=list[WindowResponse])
async def search_windows(name: str):
    """搜索指定名称的窗口"""
    windows = finder.find_windows_by_name(name)
    return [
        WindowResponse(title=w.title, x=w.x, y=w.y, width=w.width, height=w.height, pid=w.pid)
        for w in windows
    ]


@router.get("/windows/wechat", response_model=WindowResponse | None)
async def find_wechat():
    """查找微信窗口"""
    window = finder.find_wechat_window()
    if not window:
        return None
    return WindowResponse(
        title=window.title,
        x=window.x,
        y=window.y,
        width=window.width,
        height=window.height,
        pid=window.pid,
    )


@router.get("/screenshots", response_model=list[str])
async def list_screenshots():
    """列出所有截图文件"""
    screenshot_dir = Path("static/screenshots")
    if not screenshot_dir.exists():
        return []

    files = sorted(screenshot_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [str(f) for f in files[:50]]  # 只返回最新的50个


@router.delete("/screenshots")
async def clear_screenshots():
    """清空所有截图"""
    screenshot_dir = Path("static/screenshots")
    if screenshot_dir.exists():
        for f in screenshot_dir.glob("*.png"):
            f.unlink()
    return {"message": "Screenshots cleared"}
