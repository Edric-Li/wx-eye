"""
跨平台窗口定位模块
支持 macOS 和 Windows
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass
class WindowInfo:
    """窗口信息"""

    title: str
    x: int
    y: int
    width: int
    height: int
    pid: int | None = None
    window_id: int | None = None  # macOS: window number, Windows: hwnd

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "title": self.title,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "pid": self.pid,
            "window_id": self.window_id,
        }


class WindowFinder:
    """跨平台窗口查找器"""

    def __init__(self) -> None:
        self.platform = sys.platform

    def find_windows_by_name(self, name: str) -> list[WindowInfo]:
        """根据窗口名称模糊查找窗口"""
        if self.platform == "darwin":
            return self._find_windows_macos(name, exact_match=False)
        elif self.platform == "win32":
            return self._find_windows_windows(name)
        else:
            raise NotImplementedError(f"Platform {self.platform} not supported")

    def find_windows_by_name_exact(self, name: str) -> list[WindowInfo]:
        """根据窗口名称精确查找窗口"""
        if self.platform == "darwin":
            return self._find_windows_macos(name, exact_match=True)
        elif self.platform == "win32":
            return self._find_windows_windows_exact(name)
        else:
            return []

    def _find_windows_macos(self, name: str, exact_match: bool = False) -> list[WindowInfo]:
        """macOS 窗口查找"""
        try:
            from Quartz import (
                CGWindowListCopyWindowInfo,
                kCGNullWindowID,
                kCGWindowListOptionOnScreenOnly,
            )
        except ImportError as err:
            raise ImportError(
                "Please install pyobjc-framework-Quartz: pip install pyobjc-framework-Quartz"
            ) from err

        windows: list[WindowInfo] = []
        window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)

        for window in window_list:
            window_name = str(window.get("kCGWindowName", "") or "")
            owner_name = str(window.get("kCGWindowOwnerName", "") or "")

            # 精确匹配或模糊匹配
            if exact_match:
                matched = window_name == name or owner_name == name
            else:
                matched = name.lower() in window_name.lower() or name.lower() in owner_name.lower()

            if matched:
                bounds = window.get("kCGWindowBounds", {})
                if bounds:
                    pid = window.get("kCGWindowOwnerPID")
                    window_id = window.get("kCGWindowNumber")
                    windows.append(
                        WindowInfo(
                            title=window_name or owner_name,
                            x=int(bounds.get("X", 0)),
                            y=int(bounds.get("Y", 0)),
                            width=int(bounds.get("Width", 0)),
                            height=int(bounds.get("Height", 0)),
                            pid=int(pid) if pid is not None else None,
                            window_id=int(window_id) if window_id is not None else None,
                        )
                    )

        # 过滤掉太小的窗口（可能是菜单栏图标等）
        return [w for w in windows if w.width > 100 and w.height > 100]

    def _find_windows_windows(self, name: str) -> list[WindowInfo]:
        """Windows 窗口模糊查找"""
        try:
            import pygetwindow as gw
        except ImportError as err:
            raise ImportError("Please install pygetwindow: pip install pygetwindow") from err

        windows: list[WindowInfo] = []
        all_windows = gw.getWindowsWithTitle(name)

        for win in all_windows:
            if win.width > 100 and win.height > 100:
                # 获取窗口句柄 (hwnd)
                hwnd = getattr(win, "_hWnd", None)
                windows.append(
                    WindowInfo(
                        title=win.title,
                        x=win.left,
                        y=win.top,
                        width=win.width,
                        height=win.height,
                        window_id=hwnd,
                    )
                )

        return windows

    def _find_windows_windows_exact(self, name: str) -> list[WindowInfo]:
        """Windows 窗口精确查找"""
        try:
            import pygetwindow as gw
        except ImportError:
            return []

        windows: list[WindowInfo] = []
        all_windows = gw.getWindowsWithTitle(name)

        for win in all_windows:
            if win.title == name and win.width > 100 and win.height > 100:
                hwnd = getattr(win, "_hWnd", None)
                windows.append(
                    WindowInfo(
                        title=win.title,
                        x=win.left,
                        y=win.top,
                        width=win.width,
                        height=win.height,
                        window_id=hwnd,
                    )
                )

        return windows

    def find_wechat_window(self) -> WindowInfo | None:
        """查找微信主窗口"""
        search_names = ["微信", "WeChat"]

        for name in search_names:
            windows = self.find_windows_by_name_exact(name)
            if windows:
                # 优先选择标题完全匹配的窗口
                exact_title_match = [w for w in windows if w.title == name]
                if exact_title_match:
                    return max(exact_title_match, key=lambda w: w.width * w.height)
                return max(windows, key=lambda w: w.width * w.height)

        return None

    def list_all_windows(self) -> list[WindowInfo]:
        """列出所有窗口（调试用）"""
        if self.platform == "darwin":
            return self._list_all_windows_macos()
        elif self.platform == "win32":
            return self._list_all_windows_windows()
        else:
            return []

    def _list_all_windows_macos(self) -> list[WindowInfo]:
        """列出 macOS 所有窗口"""
        try:
            from Quartz import (
                CGWindowListCopyWindowInfo,
                kCGNullWindowID,
                kCGWindowListOptionOnScreenOnly,
            )
        except ImportError:
            return []

        windows: list[WindowInfo] = []
        window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)

        for window in window_list:
            bounds = window.get("kCGWindowBounds", {})
            if bounds and bounds.get("Width", 0) > 100 and bounds.get("Height", 0) > 100:
                pid = window.get("kCGWindowOwnerPID")
                window_id = window.get("kCGWindowNumber")
                windows.append(
                    WindowInfo(
                        title=str(
                            window.get("kCGWindowName", "")
                            or window.get("kCGWindowOwnerName", "Unknown")
                        ),
                        x=int(bounds.get("X", 0)),
                        y=int(bounds.get("Y", 0)),
                        width=int(bounds.get("Width", 0)),
                        height=int(bounds.get("Height", 0)),
                        pid=int(pid) if pid is not None else None,
                        window_id=int(window_id) if window_id is not None else None,
                    )
                )

        return windows

    def _list_all_windows_windows(self) -> list[WindowInfo]:
        """列出 Windows 所有窗口"""
        try:
            import pygetwindow as gw
        except ImportError:
            return []

        windows: list[WindowInfo] = []
        for win in gw.getAllWindows():
            if win.width > 100 and win.height > 100 and win.title:
                hwnd = getattr(win, "_hWnd", None)
                windows.append(
                    WindowInfo(
                        title=win.title,
                        x=win.left,
                        y=win.top,
                        width=win.width,
                        height=win.height,
                        window_id=hwnd,
                    )
                )

        return windows
