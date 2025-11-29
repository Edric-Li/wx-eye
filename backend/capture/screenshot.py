"""
截图服务模块
macOS: 使用 CGWindowListCreateImage 直接截取窗口内容
Windows: 使用 PrintWindow API 截取窗口内容（支持被遮挡/最小化的窗口）
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

import mss
from PIL import Image

from .window import WindowInfo

logger = logging.getLogger(__name__)


class ScreenshotService:
    """截图服务"""

    # 裁剪参数：只保留聊天区域，去掉标题栏、输入框和滚动条
    CROP_TOP = 200      # 顶部裁掉的像素（标题栏）
    CROP_BOTTOM = 300   # 底部裁掉的像素（输入框）
    CROP_LEFT = 40      # 左侧裁掉的像素
    CROP_RIGHT = 40     # 右侧裁掉的像素（滚动条）

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

    def _crop_chat_area(self, image: Image.Image) -> Image.Image:
        """裁剪出聊天区域，去掉标题栏、输入框和滚动条

        Args:
            image: 原始截图

        Returns:
            裁剪后的图片（只包含聊天区域）
        """
        width, height = image.size

        # 计算裁剪区域
        left = self.CROP_LEFT
        top = self.CROP_TOP
        right = width - self.CROP_RIGHT
        bottom = height - self.CROP_BOTTOM

        # 确保裁剪区域有效
        if bottom <= top or right <= left:
            logger.warning(f"裁剪区域无效: ({left},{top}) -> ({right},{bottom}), 使用原图")
            return image

        return image.crop((left, top, right, bottom))

    def capture_window(self, window: WindowInfo, crop_chat_area: bool = True) -> Image.Image:
        """截取指定窗口（即使被遮挡也能正确截取）

        Args:
            window: 窗口信息
            crop_chat_area: 是否裁剪聊天区域（去掉标题栏和输入框）

        Returns:
            截图（如果 crop_chat_area=True，则只包含聊天区域）
        """
        if self.platform == "darwin":
            img = self._capture_window_macos(window)
        elif self.platform == "win32":
            img = self._capture_window_windows(window)
        else:
            img = self.capture_region(window.x, window.y, window.width, window.height)

        if crop_chat_area:
            img = self._crop_chat_area(img)

        return img

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

    def _capture_window_windows(self, window: WindowInfo) -> Image.Image:
        """Windows: 使用 PrintWindow API 截取窗口内容（即使最小化/被遮挡）"""
        try:
            import win32con
            import win32gui
            import win32ui
        except ImportError as e:
            logger.error(f"Missing Windows module (pywin32): {e}")
            return self.capture_region(window.x, window.y, window.width, window.height)

        hwnd = window.window_id
        if hwnd is None:
            logger.warning(
                f"Window handle not found for {window.title}, falling back to region capture"
            )
            return self.capture_region(window.x, window.y, window.width, window.height)

        # 如果窗口最小化，需要先恢复它（PrintWindow 对最小化窗口可能返回空白）
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
            time.sleep(0.1)  # 等待窗口渲染完成

        # 获取窗口尺寸（包括边框）
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            logger.warning(f"Invalid window size for {window.title}: {width}x{height}")
            return self.capture_region(window.x, window.y, window.width, window.height)

        # GDI 资源，需要确保清理
        hwnd_dc = None
        mfc_dc = None
        save_dc = None
        bitmap = None

        try:
            # 创建设备上下文
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            # 创建位图
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)

            # 使用 PrintWindow 截取窗口内容
            # PW_RENDERFULLCONTENT (2) 支持 DWM 合成的窗口
            PW_RENDERFULLCONTENT = 2
            result = win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)

            if result == 0:
                # PrintWindow 失败，尝试使用 BitBlt
                logger.warning(f"PrintWindow failed for {window.title}, trying BitBlt")
                save_dc.BitBlt(
                    (0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY
                )

            # 转换为 PIL Image
            bmp_info = bitmap.GetInfo()
            bmp_bits = bitmap.GetBitmapBits(True)
            img = Image.frombuffer(
                "RGB",
                (bmp_info["bmWidth"], bmp_info["bmHeight"]),
                bmp_bits,
                "raw",
                "BGRX",
                0,
                1,
            )

            return img

        except Exception as e:
            logger.error(f"Windows capture failed: {e}")
            return self.capture_region(window.x, window.y, window.width, window.height)

        finally:
            # 确保 GDI 资源被清理，防止泄漏
            if bitmap:
                win32gui.DeleteObject(bitmap.GetHandle())
            if save_dc:
                save_dc.DeleteDC()
            if mfc_dc:
                mfc_dc.DeleteDC()
            if hwnd_dc:
                win32gui.ReleaseDC(hwnd, hwnd_dc)

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
