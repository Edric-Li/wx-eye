"""
截图服务模块
macOS: 使用 CGWindowListCreateImage 直接截取窗口内容
Windows: 使用 mss 截取屏幕区域
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

import mss
from PIL import Image

from .window import WindowInfo

logger = logging.getLogger(__name__)


class ScreenshotService:
    """截图服务"""

    def __init__(self, save_dir: str = "static/screenshots") -> None:
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._sct: mss.mss | None = None
        self.platform = sys.platform

    @property
    def sct(self) -> mss.mss:
        """懒加载 mss 实例"""
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

    def capture_region(self, x: int, y: int, width: int, height: int) -> Image.Image:
        """截取指定屏幕区域（可能被遮挡）"""
        monitor = {"left": x, "top": y, "width": width, "height": height}
        sct_img = self.sct.grab(monitor)
        return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    def capture_window(self, window: WindowInfo) -> Image.Image:
        """截取指定窗口（即使被遮挡也能正确截取）"""
        if self.platform == "darwin":
            return self._capture_window_macos(window)
        else:
            return self.capture_region(window.x, window.y, window.width, window.height)

    def _capture_window_macos(self, window: WindowInfo) -> Image.Image:
        """macOS: 使用 CGWindowListCreateImage 直接截取窗口内容"""
        try:
            from Quartz import (
                CGRectNull,
                CGWindowListCreateImage,
                kCGWindowImageBoundsIgnoreFraming,
                kCGWindowListOptionIncludingWindow,
            )
            from Quartz.CoreGraphics import CGImageGetHeight, CGImageGetWidth

            # 优先使用已有的 window_id
            window_id = window.window_id
            if window_id is None:
                window_id = self._get_window_id_macos(window)

            if window_id is None:
                logger.warning(
                    f"Window ID not found for {window.title}, falling back to region capture"
                )
                return self.capture_region(window.x, window.y, window.width, window.height)

            # 使用 CGWindowListCreateImage 截取特定窗口
            cg_image = CGWindowListCreateImage(
                CGRectNull,
                kCGWindowListOptionIncludingWindow,
                window_id,
                kCGWindowImageBoundsIgnoreFraming,
            )

            if cg_image is None:
                logger.warning(f"CGWindowListCreateImage returned None for {window.title}")
                return self.capture_region(window.x, window.y, window.width, window.height)

            # 将 CGImage 转换为 PIL Image
            width = CGImageGetWidth(cg_image)
            height = CGImageGetHeight(cg_image)

            if width == 0 or height == 0:
                logger.warning(f"Empty image for {window.title}")
                return self.capture_region(window.x, window.y, window.width, window.height)

            # 使用 NSBitmapImageRep 转换
            from Cocoa import NSBitmapImageFileTypePNG, NSBitmapImageRep

            bitmap_rep = NSBitmapImageRep.alloc().initWithCGImage_(cg_image)
            png_data = bitmap_rep.representationUsingType_properties_(
                NSBitmapImageFileTypePNG, None
            )

            img = Image.open(BytesIO(png_data))
            return img.convert("RGB")

        except ImportError as e:
            logger.error(f"Missing macOS framework: {e}")
            return self.capture_region(window.x, window.y, window.width, window.height)
        except Exception as e:
            logger.error(f"macOS capture failed: {e}")
            return self.capture_region(window.x, window.y, window.width, window.height)

    def _get_window_id_macos(self, window: WindowInfo) -> int | None:
        """获取 macOS 窗口的 window ID"""
        try:
            from Quartz import (
                CGWindowListCopyWindowInfo,
                kCGNullWindowID,
                kCGWindowListOptionAll,
            )

            window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID)

            # 先按名称和位置精确匹配
            for win in window_list:
                owner_name = str(win.get("kCGWindowOwnerName", "") or "")
                window_name = str(win.get("kCGWindowName", "") or "")
                bounds = win.get("kCGWindowBounds", {})

                if window_name == window.title and owner_name == "微信" and bounds:
                    x_match = abs(int(bounds.get("X", 0)) - window.x) < 10
                    y_match = abs(int(bounds.get("Y", 0)) - window.y) < 10
                    if x_match and y_match:
                        return int(win.get("kCGWindowNumber", 0))

            # 只按名称匹配
            for win in window_list:
                window_name = str(win.get("kCGWindowName", "") or "")
                owner_name = str(win.get("kCGWindowOwnerName", "") or "")
                if window_name == window.title and owner_name == "微信":
                    return int(win.get("kCGWindowNumber", 0))

            return None

        except Exception as e:
            logger.error(f"Failed to get window ID: {e}")
            return None

    def capture_full_screen(self, monitor_index: int = 1) -> Image.Image:
        """截取整个屏幕"""
        monitor = self.sct.monitors[monitor_index]
        sct_img = self.sct.grab(monitor)
        return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    def save_screenshot(self, img: Image.Image, prefix: str = "screenshot") -> str:
        """保存截图，返回文件路径"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{prefix}_{timestamp}.png"
        filepath = self.save_dir / filename

        img.save(filepath, "PNG", optimize=True)
        return str(filepath)

    def image_to_bytes(self, img: Image.Image, format: str = "PNG") -> bytes:
        """将图片转换为字节"""
        buffer = BytesIO()
        img.save(buffer, format=format)
        return buffer.getvalue()

    def cleanup_old_screenshots(self, keep_count: int = 100) -> None:
        """清理旧截图，只保留最新的 N 张"""
        files = sorted(self.save_dir.glob("*.png"), key=lambda f: f.stat().st_mtime)
        if len(files) > keep_count:
            for f in files[:-keep_count]:
                f.unlink()

    def close(self) -> None:
        """关闭资源"""
        if self._sct:
            self._sct.close()
            self._sct = None
