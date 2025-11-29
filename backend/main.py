"""
WxEye - WeChat Visual Monitoring Agent
主入口文件 - 事件驱动架构，支持外部服务订阅

事件类型:
- message.received: 收到新消息
- message.sent: 消息发送完成
- contact.online: 联系人窗口出现
- contact.offline: 联系人窗口消失
- monitor.started: 监控启动
- monitor.stopped: 监控停止
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api import manager, router
from capture import (
    ImageComparator,
    ScreenshotService,
    WindowFinder,
    WindowInfo,
)
from config import get_settings
from events import Event, get_event_bus, get_subscriber_manager
from services.message_sender import get_sender

logger = logging.getLogger(__name__)

# 获取配置
settings = get_settings()

# 获取事件总线和订阅者管理器
event_bus = get_event_bus()
subscriber_manager = get_subscriber_manager()


@dataclass
class ContactMonitor:
    """单个联系人的监控状态"""

    name: str
    comparator: ImageComparator = field(default_factory=ImageComparator)
    total_captures: int = 0
    significant_captures: int = 0
    last_window: WindowInfo | None = None
    is_visible: bool = False


class MultiContactCaptureEngine:
    """多联系人截图引擎

    同时监控多个微信独立聊天窗口，每个联系人独立进行截图对比。
    集成 AI 消息分析功能。
    """

    def __init__(self, screenshot_dir: str = "static/screenshots") -> None:
        self.finder = WindowFinder()
        self.screenshot_service = ScreenshotService(screenshot_dir)

        self.is_running: bool = False
        self.interval: float = 0.1  # 100ms

        # 要监控的联系人列表
        self.contacts: dict[str, ContactMonitor] = {}

        # 统计
        self.total_captures: int = 0
        self.significant_captures: int = 0

        self._task: asyncio.Task[None] | None = None

        # AI 处理器（延迟初始化）
        self._ai_processor: Optional[Any] = None
        self._ai_enabled = settings.is_ai_enabled

    @property
    def ai_processor(self) -> Optional[Any]:
        """延迟初始化 AI 处理器"""
        if self._ai_processor is None and self._ai_enabled:
            try:
                from ai import AIMessageProcessor

                self._ai_processor = AIMessageProcessor(
                    api_key=settings.anthropic_api_key or "",
                    base_url=settings.anthropic_base_url,
                    model=settings.claude_model,
                    enable_ai=settings.is_ai_enabled,
                )
                # 设置回调
                self._ai_processor.set_callback(self._on_ai_result)
                logger.info("AI 处理器初始化成功")
            except ImportError as e:
                logger.warning(f"AI 模块导入失败: {e}")
                self._ai_enabled = False
            except Exception as e:
                logger.error(f"AI 处理器初始化失败: {e}")
                self._ai_enabled = False
        return self._ai_processor

    async def _on_ai_result(self, result: Any) -> None:
        """AI 处理结果回调"""
        await manager.send_ai_result(result)

    def add_contact(self, name: str) -> bool:
        """添加要监控的联系人

        Args:
            name: 联系人名称（微信聊天窗口标题）

        Returns:
            添加成功返回 True，已存在返回 False
        """
        if name not in self.contacts:
            self.contacts[name] = ContactMonitor(name=name)
            logger.info(f"添加联系人: {name}")
            return True
        return False

    def remove_contact(self, name: str) -> bool:
        """移除监控的联系人

        Args:
            name: 联系人名称

        Returns:
            移除成功返回 True，不存在返回 False
        """
        if name in self.contacts:
            del self.contacts[name]
            logger.info(f"移除联系人: {name}")
            return True
        return False

    def get_contacts(self) -> list[str]:
        """获取所有监控的联系人名称列表"""
        return list(self.contacts.keys())

    async def start(self, interval: float = 0.1) -> None:
        """启动截图服务

        Args:
            interval: 截图间隔（秒），默认 0.1 秒
        """
        if self.is_running:
            await manager.send_log("warning", "截图服务已在运行")
            return

        if not self.contacts:
            await manager.send_log("error", "没有添加任何联系人，请先添加联系人")
            return

        self.interval = interval
        self.is_running = True

        # 重置所有联系人的比较器
        for contact in self.contacts.values():
            contact.comparator.reset()

        # 启动 AI 处理器
        if self.ai_processor:
            await self.ai_processor.start()
            await manager.send_log("info", "AI 消息分析已启用")

        contact_names = list(self.contacts.keys())
        ai_status = "已启用" if self._ai_enabled else "未启用"
        logger.info(f"启动多窗口监控: 联系人={contact_names}, 间隔={interval}s, AI={ai_status}")
        await manager.send_log(
            "info",
            f"启动多窗口监控: 联系人={contact_names}, 间隔={interval}s, AI={ai_status}"
        )
        await manager.send_status(
            "starting",
            {
                "contacts": contact_names,
                "interval": interval,
                "ai_enabled": self._ai_enabled,
            },
        )

        # 发布监控启动事件
        await manager.emit_monitor_started(contacts=contact_names, interval=interval)

        self._task = asyncio.create_task(self._capture_loop())

    async def stop(self) -> None:
        """停止截图服务"""
        if not self.is_running:
            return

        self.is_running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        # 停止 AI 处理器
        if self._ai_processor:
            await self._ai_processor.stop()

        logger.info("截图服务已停止")
        await manager.send_log("info", "截图服务已停止")

        # 包含 AI 统计信息
        status_details = {
            "total_captures": self.total_captures,
            "significant_captures": self.significant_captures,
            "contacts": self._get_contacts_status(),
        }
        if self._ai_processor:
            status_details["ai_stats"] = self._ai_processor.get_stats()

        await manager.send_status("stopped", status_details)

        # 发布监控停止事件
        await manager.emit_monitor_stopped(stats=status_details)

    def _get_contacts_status(self) -> list[dict[str, Any]]:
        """获取所有联系人状态"""
        return [
            {
                "name": c.name,
                "is_visible": c.is_visible,
                "total_captures": c.total_captures,
                "significant_captures": c.significant_captures,
            }
            for c in self.contacts.values()
        ]

    async def _capture_loop(self) -> None:
        """截图循环 - 同时监控多个联系人窗口"""
        logger.info(f"开始监控 {len(self.contacts)} 个联系人窗口")
        await manager.send_log("info", f"开始监控 {len(self.contacts)} 个联系人窗口")

        # 跟踪上一次的可见状态，用于检测变化
        prev_visibility: dict[str, bool] = {name: False for name in self.contacts}

        while self.is_running:
            try:
                # 获取所有微信相关窗口（应用名为"微信"的窗口）
                all_wechat_windows = self._get_all_wechat_chat_windows()

                # 为每个联系人查找对应窗口并截图
                visible_contacts = []
                for contact_name, contact in self.contacts.items():
                    # 查找该联系人的窗口（窗口标题 = 联系人名字）
                    window = all_wechat_windows.get(contact_name)

                    if window:
                        was_visible = prev_visibility.get(contact_name, False)
                        contact.is_visible = True
                        contact.last_window = window
                        visible_contacts.append(contact_name)

                        # 检测上线事件（从不可见变为可见）
                        if not was_visible:
                            await manager.emit_contact_online(
                                contact_name,
                                window={
                                    "x": window.x,
                                    "y": window.y,
                                    "width": window.width,
                                    "height": window.height,
                                },
                            )

                        # 截图
                        img = self.screenshot_service.capture_window(window)
                        contact.total_captures += 1
                        self.total_captures += 1

                        # 使用该联系人专属的比较器进行对比
                        result, is_first = contact.comparator.compare_with_last(img)

                        if result.is_significant:
                            # 只在检测到变化时输出日志
                            logger.info(
                                f"[{contact_name}] 检测到变化: distance={result.hash_distance}, "
                                f"threshold={contact.comparator.similar_threshold}"
                            )
                            contact.significant_captures += 1
                            self.significant_captures += 1

                            # 保存时使用联系人名字作为前缀
                            safe_name = contact_name.replace("/", "_").replace("\\", "_")
                            filename = self.screenshot_service.save_screenshot(
                                img, f"contact_{safe_name}"
                            )

                            # 像素级比对检测到变化后，提交给 AI 处理器分析消息内容
                            if self._ai_processor:
                                if is_first:
                                    # 首次截图作为基准，跳过 AI 分析
                                    # 下次变化时的 AI 分析结果会作为基线记录（不广播）
                                    logger.info(
                                        f"[{contact_name}] 首次截图，作为基准跳过 AI 分析"
                                    )
                                else:
                                    await self._ai_processor.submit(
                                        contact_name, img, filename=filename
                                    )
                                    logger.debug(
                                        f"[{contact_name}] 像素变化检测通过，提交给 AI 分析: {result.description}"
                                    )
                            else:
                                # AI 未启用时，直接发送截图（保持原有行为）
                                await manager.send_screenshot(
                                    image=img,
                                    filename=filename,
                                    is_significant=True,
                                    compare_result={
                                        "level": result.level.value,
                                        "hash_distance": int(result.hash_distance),
                                        "description": result.description,
                                        "is_first": is_first,
                                        "contact": contact_name,
                                    },
                                )
                                await manager.send_log(
                                    "info",
                                    f"[{contact_name}] 检测到变化: {result.description}",
                                    {"contact": contact_name, "filename": filename},
                                )
                    else:
                        was_visible = prev_visibility.get(contact_name, False)
                        contact.is_visible = False

                        # 检测离线事件（从可见变为不可见）
                        if was_visible:
                            await manager.emit_contact_offline(contact_name)

                    # 更新可见状态
                    prev_visibility[contact_name] = contact.is_visible

                # 更新状态
                if visible_contacts:
                    await manager.send_status(
                        "running",
                        {
                            "visible_contacts": visible_contacts,
                            "total_contacts": len(self.contacts),
                            "total_captures": int(self.total_captures),
                            "significant_captures": int(self.significant_captures),
                            "contacts": self._get_contacts_status(),
                        },
                    )
                else:
                    await manager.send_status(
                        "paused",
                        {
                            "message": "所有联系人窗口都已隐藏，等待显示...",
                            "total_contacts": len(self.contacts),
                            "total_captures": int(self.total_captures),
                            "significant_captures": int(self.significant_captures),
                            "contacts": self._get_contacts_status(),
                        },
                    )

                await asyncio.sleep(self.interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("截图错误")
                await manager.send_log("error", f"截图错误: {str(e)}")
                await asyncio.sleep(1)

    def _get_all_wechat_chat_windows(self) -> dict[str, WindowInfo]:
        """获取所有微信聊天窗口，返回 {窗口标题: WindowInfo}"""
        result = {}

        if self.finder.platform == "darwin":
            try:
                from Quartz import (
                    CGWindowListCopyWindowInfo,
                    kCGNullWindowID,
                    kCGWindowListOptionOnScreenOnly,
                )

                window_list = CGWindowListCopyWindowInfo(
                    kCGWindowListOptionOnScreenOnly, kCGNullWindowID
                )

                for window in window_list:
                    owner_name = str(window.get("kCGWindowOwnerName", "") or "")
                    window_name = str(window.get("kCGWindowName", "") or "")

                    # 只获取微信应用的窗口，且不是主窗口
                    if owner_name == "微信" and window_name and window_name != "微信":
                        bounds = window.get("kCGWindowBounds", {})
                        if (
                            bounds
                            and bounds.get("Width", 0) > 100
                            and bounds.get("Height", 0) > 100
                        ):
                            window_id = window.get("kCGWindowNumber")
                            pid = window.get("kCGWindowOwnerPID")
                            result[window_name] = WindowInfo(
                                title=window_name,
                                x=int(bounds.get("X", 0)),
                                y=int(bounds.get("Y", 0)),
                                width=int(bounds.get("Width", 0)),
                                height=int(bounds.get("Height", 0)),
                                pid=int(pid) if pid is not None else None,
                                window_id=int(window_id) if window_id is not None else None,
                            )
            except ImportError:
                pass

        elif self.finder.platform == "win32":
            try:
                import pygetwindow as gw

                # Windows 上微信独立聊天窗口的标题就是联系人名字
                for win in gw.getAllWindows():
                    if win.width > 100 and win.height > 100 and win.title:
                        # 需要进一步过滤，只获取微信的窗口
                        # Windows 上可能需要通过进程名判断
                        result[win.title] = WindowInfo(
                            title=win.title,
                            x=win.left,
                            y=win.top,
                            width=win.width,
                            height=win.height,
                        )
            except ImportError:
                pass

        return result

    def get_status(self) -> dict[str, Any]:
        """获取当前状态"""
        status = {
            "is_running": self.is_running,
            "interval": self.interval,
            "total_captures": self.total_captures,
            "significant_captures": self.significant_captures,
            "contacts": self._get_contacts_status(),
            "ai_enabled": self._ai_enabled,
        }
        if self._ai_processor:
            status["ai_stats"] = self._ai_processor.get_stats()
        return status

    def reset_ai(self, contact: str | None = None) -> None:
        """重置 AI 处理器状态"""
        if self._ai_processor:
            self._ai_processor.reset(contact)


# 全局引擎实例
engine = MultiContactCaptureEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 启动时
    Path(settings.screenshot_dir).mkdir(parents=True, exist_ok=True)

    ai_status = "已配置" if settings.is_ai_enabled else "未配置（缺少 API Key）"
    logger.info(f"WxEye started (Multi-Contact + AI Mode), AI: {ai_status}")

    yield

    # 关闭时
    await engine.stop()
    engine.screenshot_service.close()
    logger.info("WxEye stopped")


# 创建 FastAPI 应用
app = FastAPI(
    title="WxEye",
    description="微信多联系人窗口视觉监控代理",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
Path("static/screenshots").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 前端静态文件（如果已构建）
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="frontend_assets")

# API 路由
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """根路径 - 返回前端页面或 API 信息"""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "mode": "multi-contact + ai",
        "ai_enabled": settings.is_ai_enabled,
        "status": engine.get_status(),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket 端点 - 处理客户端连接和命令

    支持新旧两种命令格式:
    - 旧格式: {"command": "start", ...}
    - 新格式: {"command": "monitor.start", ...}

    新增命令:
    - subscribe: 订阅事件 {"command": "subscribe", "events": ["message.received"]}
    - unsubscribe: 取消订阅
    - monitor.start: 启动监控
    - monitor.stop: 停止监控
    - message.send: 发送消息
    - contacts.add: 添加联系人
    - contacts.remove: 移除联系人
    - windows.discover: 发现窗口
    """
    await manager.connect(websocket)

    # 发送当前状态
    await manager.send_status("connected", engine.get_status())

    try:
        while True:
            data = await websocket.receive_json()

            # 处理客户端命令
            command = data.get("command", "")

            # ============ 订阅管理（新协议） ============
            if command == "subscribe":
                events = data.get("events", ["*"])
                await subscriber_manager.subscribe(websocket, events)
                await subscriber_manager.send_to(websocket, {
                    "type": "subscribed",
                    "events": events,
                })

            elif command == "unsubscribe":
                events = data.get("events", [])
                await subscriber_manager.unsubscribe(websocket, events)
                subscriptions = await subscriber_manager.get_subscriptions(websocket)
                await subscriber_manager.send_to(websocket, {
                    "type": "unsubscribed",
                    "events": events,
                    "remaining": list(subscriptions),
                })

            # ============ 监控命令（新格式） ============
            elif command in ("monitor.start", "start"):
                interval = data.get("interval", 0.1)
                contacts = data.get("contacts")
                # 如果指定了联系人列表，先添加
                if contacts:
                    for contact_name in contacts:
                        engine.add_contact(contact_name.strip())
                await engine.start(interval)

            elif command in ("monitor.stop", "stop"):
                await engine.stop()

            elif command in ("monitor.status", "status"):
                await manager.send_status("current", engine.get_status())

            # ============ 消息发送（新格式） ============
            elif command == "message.send":
                text = data.get("text", "").strip()
                contact = data.get("contact", "").strip()
                if text and contact:
                    # 获取联系人的窗口信息
                    if contact not in engine.contacts:
                        await event_bus.emit(Event.error(
                            code="contact_not_monitored",
                            message=f"联系人 '{contact}' 未在监控列表中",
                            contact=contact,
                        ))
                    else:
                        contact_monitor = engine.contacts[contact]
                        if not contact_monitor.last_window:
                            windows = engine._get_all_wechat_chat_windows()
                            if contact in windows:
                                contact_monitor.last_window = windows[contact]

                        if contact_monitor.last_window:
                            sender = get_sender()
                            result = await sender.send(text, contact, contact_monitor.last_window)
                            # 记录已发送的消息，避免被当作新消息广播
                            if result.success and engine.ai_processor:
                                engine.ai_processor.add_sent_message(contact, text)
                            # 发布消息发送事件
                            await manager.emit_message_sent(
                                contact=contact,
                                text=text,
                                success=result.success,
                                error=result.error,
                                elapsed_ms=result.elapsed_ms,
                            )
                        else:
                            await event_bus.emit(Event.error(
                                code="window_not_found",
                                message=f"找不到联系人 '{contact}' 的窗口",
                                contact=contact,
                            ))

            # ============ 联系人管理（新格式） ============
            elif command in ("contacts.add", "add_contact"):
                contact_name = data.get("name", "").strip()
                if contact_name:
                    if engine.add_contact(contact_name):
                        await manager.send_log("info", f"已添加联系人: {contact_name}")
                        # 发布事件
                        await event_bus.emit(Event.contact_added(contact_name))
                    else:
                        await manager.send_log("warning", f"联系人已存在: {contact_name}")
                    await manager.send_status("current", engine.get_status())

            elif command in ("contacts.remove", "remove_contact"):
                contact_name = data.get("name", "").strip()
                if contact_name:
                    if engine.remove_contact(contact_name):
                        await manager.send_log("info", f"已移除联系人: {contact_name}")
                        # 发布事件
                        await event_bus.emit(Event.contact_removed(contact_name))
                    else:
                        await manager.send_log("warning", f"联系人不存在: {contact_name}")
                    await manager.send_status("current", engine.get_status())

            elif command == "contacts.list":
                await manager.send_status("current", engine.get_status())

            # ============ 窗口发现（新格式） ============
            elif command in ("windows.discover", "list_wechat_windows"):
                windows = engine._get_all_wechat_chat_windows()
                await manager.send_log(
                    "info", f"发现 {len(windows)} 个微信聊天窗口: {list(windows.keys())}"
                )
                # 也发送结构化数据
                await subscriber_manager.send_to(websocket, {
                    "type": "windows.discovered",
                    "windows": [
                        {"name": name, "x": w.x, "y": w.y, "width": w.width, "height": w.height}
                        for name, w in windows.items()
                    ],
                })

            # ============ 旧协议兼容 ============
            elif command == "reset":
                for contact in engine.contacts.values():
                    contact.comparator.reset()
                    contact.total_captures = 0
                    contact.significant_captures = 0
                engine.total_captures = 0
                engine.significant_captures = 0
                engine.reset_ai()
                await manager.send_log("info", "所有计数器已重置（包括 AI 状态）")
                await manager.send_status("current", engine.get_status())

            elif command == "ai_stats":
                if engine._ai_processor:
                    stats = engine._ai_processor.get_stats()
                    await manager.send_log("info", f"AI 统计: {stats}")
                else:
                    await manager.send_log("warning", "AI 处理器未启用")

            else:
                # 未知命令
                logger.warning(f"Unknown WebSocket command: {command}")

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
        await manager.send_log("error", f"WebSocket error: {str(e)}")
        await manager.disconnect(websocket)


@app.post("/api/contacts/add")
async def add_contact(name: str) -> dict[str, Any]:
    """添加监控联系人"""
    if engine.add_contact(name):
        return {"message": f"Contact added: {name}", "contacts": engine.get_contacts()}
    return {"message": f"Contact already exists: {name}", "contacts": engine.get_contacts()}


@app.delete("/api/contacts/{name}")
async def remove_contact(name: str) -> dict[str, Any]:
    """移除监控联系人"""
    if engine.remove_contact(name):
        return {"message": f"Contact removed: {name}", "contacts": engine.get_contacts()}
    return {"message": f"Contact not found: {name}", "contacts": engine.get_contacts()}


@app.get("/api/contacts")
async def list_contacts() -> dict[str, Any]:
    """列出所有监控联系人"""
    return {"contacts": engine.get_contacts(), "status": engine._get_contacts_status()}


@app.get("/api/wechat/windows")
async def list_wechat_windows() -> dict[str, Any]:
    """列出当前所有微信聊天窗口"""
    windows = engine._get_all_wechat_chat_windows()
    return {
        "windows": [
            {"name": name, "x": w.x, "y": w.y, "width": w.width, "height": w.height}
            for name, w in windows.items()
        ]
    }


@app.post("/api/capture/start")
async def start_capture(interval: float = 0.1) -> dict[str, Any]:
    """启动截图服务"""
    await engine.start(interval)
    return {"message": "Capture started", "status": engine.get_status()}


@app.post("/api/capture/stop")
async def stop_capture() -> dict[str, Any]:
    """停止截图服务"""
    await engine.stop()
    return {"message": "Capture stopped", "status": engine.get_status()}


@app.get("/api/capture/status")
async def capture_status() -> dict[str, Any]:
    """获取截图服务状态"""
    return engine.get_status()


@app.get("/api/ai/status")
async def ai_status() -> dict[str, Any]:
    """获取 AI 处理器状态"""
    return {
        "enabled": engine._ai_enabled,
        "configured": settings.is_ai_enabled,
        "model": settings.claude_model,
        "stats": engine._ai_processor.get_stats() if engine._ai_processor else None,
    }


@app.post("/api/ai/reset")
async def reset_ai(contact: str | None = None) -> dict[str, Any]:
    """重置 AI 处理器状态"""
    engine.reset_ai(contact)
    return {
        "message": f"AI 状态已重置: {contact or '全部'}",
        "stats": engine._ai_processor.get_stats() if engine._ai_processor else None,
    }


# ============ 消息发送 API ============


@app.post("/api/message/send")
async def send_message(text: str, contact: str) -> dict[str, Any]:
    """发送微信消息到指定联系人

    通过 UI 自动化发送消息。消息会加入队列，确保同一时间只有一个发送操作。

    Args:
        text: 要发送的消息文本
        contact: 联系人名称（必须是正在监控的联系人）
    """
    # 获取联系人的窗口信息
    if contact not in engine.contacts:
        return {
            "success": False,
            "message": f"联系人 '{contact}' 未在监控列表中",
            "error": "Contact not monitored",
        }

    contact_monitor = engine.contacts[contact]
    if not contact_monitor.last_window:
        # 尝试重新获取窗口
        windows = engine._get_all_wechat_chat_windows()
        if contact in windows:
            contact_monitor.last_window = windows[contact]
        else:
            return {
                "success": False,
                "message": f"找不到联系人 '{contact}' 的窗口，请确保聊天窗口已打开",
                "error": "Window not found",
            }

    sender = get_sender()
    result = await sender.send(text, contact, contact_monitor.last_window)

    # 记录已发送的消息，避免被当作新消息广播
    if result.success and engine.ai_processor:
        engine.ai_processor.add_sent_message(contact, text)

    # 发布消息发送事件
    await manager.emit_message_sent(
        contact=contact,
        text=text,
        success=result.success,
        error=result.error,
        elapsed_ms=result.elapsed_ms,
    )

    return {
        "success": result.success,
        "message": result.message,
        "elapsed_ms": result.elapsed_ms,
        "error": result.error,
        "contact": result.contact,
    }


@app.get("/api/message/stats")
async def message_stats() -> dict[str, Any]:
    """获取消息发送统计"""
    sender = get_sender()
    return sender.get_stats()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
    )
