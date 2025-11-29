#!/usr/bin/env python3
"""
事件系统完整测试
模拟消息发布和订阅流程
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加 backend 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from events import Event, EventType, get_event_bus, get_subscriber_manager


class MockWebSocket:
    """模拟 WebSocket 连接"""

    def __init__(self, name: str):
        self.name = name
        self.messages: list[str] = []
        self._accepted = False

    async def accept(self):
        self._accepted = True
        print(f"[{self.name}] WebSocket 已连接")

    async def send_text(self, data: str):
        self.messages.append(data)
        parsed = json.loads(data)
        event_type = parsed.get("type", "unknown")
        print(f"[{self.name}] 收到事件: {event_type}")
        if event_type == "message.received":
            payload = parsed.get("payload", {})
            messages = payload.get("messages", [])
            for msg in messages:
                print(f"    -> {msg.get('sender')}: {msg.get('content')}")

    def get_messages(self) -> list[dict]:
        return [json.loads(m) for m in self.messages]


async def test_event_system():
    """测试事件系统"""
    print("=" * 60)
    print("WxEye 事件系统测试")
    print("=" * 60)

    event_bus = get_event_bus()
    subscriber_manager = get_subscriber_manager()

    # 重置状态
    event_bus.reset()

    # ============ 测试 1: 创建订阅者 ============
    print("\n[测试 1] 创建订阅者...")

    ws1 = MockWebSocket("订阅者A (全部事件)")
    ws2 = MockWebSocket("订阅者B (仅消息事件)")

    await subscriber_manager.connect(ws1)
    await subscriber_manager.connect(ws2)

    # 订阅者A 订阅所有事件
    await subscriber_manager.subscribe(ws1, ["*"])

    # 订阅者B 只订阅消息相关事件
    await subscriber_manager.subscribe(ws2, ["message.*"])

    print(f"  订阅者数量: {subscriber_manager.subscriber_count}")
    print("  订阅者A 订阅: *")
    print("  订阅者B 订阅: message.*")

    # ============ 测试 2: 发布消息接收事件 ============
    print("\n[测试 2] 发布 message.received 事件...")

    event = Event.message_received(
        contact="张三",
        messages=[
            {"sender": "张三", "content": "你好，在吗？"},
            {"sender": "张三", "content": "有个事想问你"},
        ],
        screenshot_url="/static/screenshots/test.png",
    )

    await event_bus.emit(event)
    await asyncio.sleep(0.1)  # 等待事件处理

    print(f"  订阅者A 收到 {len(ws1.messages)} 条消息")
    print(f"  订阅者B 收到 {len(ws2.messages)} 条消息")

    # ============ 测试 3: 发布消息发送事件 ============
    print("\n[测试 3] 发布 message.sent 事件...")

    event = Event.message_sent(
        contact="张三",
        text="好的，我看看",
        success=True,
        elapsed_ms=150,
    )

    ws1.messages.clear()
    ws2.messages.clear()

    await event_bus.emit(event)
    await asyncio.sleep(0.1)

    print(f"  订阅者A 收到 {len(ws1.messages)} 条消息")
    print(f"  订阅者B 收到 {len(ws2.messages)} 条消息")

    # ============ 测试 4: 发布联系人事件（订阅者B 不应该收到） ============
    print("\n[测试 4] 发布 contact.online 事件...")

    event = Event.contact_online(
        contact="李四",
        window={"x": 100, "y": 100, "width": 800, "height": 600},
    )

    ws1.messages.clear()
    ws2.messages.clear()

    await event_bus.emit(event)
    await asyncio.sleep(0.1)

    print(f"  订阅者A 收到 {len(ws1.messages)} 条消息 (应该是 1)")
    print(f"  订阅者B 收到 {len(ws2.messages)} 条消息 (应该是 0，因为只订阅 message.*)")

    # ============ 测试 5: 发布监控事件 ============
    print("\n[测试 5] 发布 monitor.started 事件...")

    event = Event.monitor_started(
        contacts=["张三", "李四"],
        interval=0.1,
    )

    ws1.messages.clear()
    ws2.messages.clear()

    await event_bus.emit(event)
    await asyncio.sleep(0.1)

    print(f"  订阅者A 收到 {len(ws1.messages)} 条消息")
    print(f"  订阅者B 收到 {len(ws2.messages)} 条消息")

    # ============ 测试 6: 错误事件 ============
    print("\n[测试 6] 发布 error 事件...")

    event = Event.error(
        code="window_not_found",
        message="找不到联系人窗口",
        contact="王五",
    )

    ws1.messages.clear()
    ws2.messages.clear()

    await event_bus.emit(event)
    await asyncio.sleep(0.1)

    print(f"  订阅者A 收到 {len(ws1.messages)} 条消息")
    print(f"  订阅者B 收到 {len(ws2.messages)} 条消息")

    # ============ 测试 7: 取消订阅 ============
    print("\n[测试 7] 订阅者B 取消订阅...")

    await subscriber_manager.unsubscribe(ws2, ["message.*"])
    subscriptions = await subscriber_manager.get_subscriptions(ws2)
    print(f"  订阅者B 剩余订阅: {subscriptions}")

    # 再发一个消息事件
    event = Event.message_received(
        contact="张三",
        messages=[{"sender": "张三", "content": "测试消息"}],
    )

    ws1.messages.clear()
    ws2.messages.clear()

    await event_bus.emit(event)
    await asyncio.sleep(0.1)

    print(f"  订阅者A 收到 {len(ws1.messages)} 条消息")
    print(f"  订阅者B 收到 {len(ws2.messages)} 条消息 (应该是 0)")

    # ============ 测试 8: 断开连接 ============
    print("\n[测试 8] 断开订阅者...")

    await subscriber_manager.disconnect(ws1)
    await subscriber_manager.disconnect(ws2)

    print(f"  剩余订阅者: {subscriber_manager.subscriber_count}")

    # ============ 总结 ============
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


async def test_event_types():
    """测试事件类型匹配"""
    print("\n" + "=" * 60)
    print("事件类型匹配测试")
    print("=" * 60)

    test_cases = [
        ("message.received", "*", True),
        ("message.received", "message.*", True),
        ("message.received", "message.received", True),
        ("message.received", "contact.*", False),
        ("contact.online", "contact.*", True),
        ("contact.online", "*", True),
        ("contact.online", "message.*", False),
        ("error", "*", True),
        ("error", "error", True),
        ("error", "message.*", False),
    ]

    for event_type, pattern, expected in test_cases:
        result = EventType.match(event_type, pattern)
        status = "✓" if result == expected else "✗"
        print(f"  {status} EventType.match('{event_type}', '{pattern}') = {result}")


async def simulate_chat_flow():
    """模拟完整的聊天流程"""
    print("\n" + "=" * 60)
    print("模拟聊天流程")
    print("=" * 60)

    event_bus = get_event_bus()
    subscriber_manager = get_subscriber_manager()

    # 重置
    event_bus.reset()

    # 创建一个订阅者
    ws = MockWebSocket("AI Agent")
    await subscriber_manager.connect(ws)
    await subscriber_manager.subscribe(ws, ["message.received", "message.sent"])

    print("\n[场景] AI Agent 订阅消息事件，准备自动回复\n")

    # 模拟收到消息
    print("1. 用户「张三」发来消息...")
    await event_bus.emit(Event.message_received(
        contact="张三",
        messages=[
            {"sender": "张三", "content": "你好，请问现在几点了？"},
        ],
    ))
    await asyncio.sleep(0.1)

    # 模拟 AI 处理并回复
    print("\n2. AI Agent 处理消息并发送回复...")
    await event_bus.emit(Event.message_sent(
        contact="张三",
        text="现在是下午3点整。",
        success=True,
        elapsed_ms=120,
    ))
    await asyncio.sleep(0.1)

    # 用户继续发消息
    print("\n3. 用户继续发消息...")
    await event_bus.emit(Event.message_received(
        contact="张三",
        messages=[
            {"sender": "张三", "content": "谢谢！"},
            {"sender": "张三", "content": "再见"},
        ],
    ))
    await asyncio.sleep(0.1)

    # 断开
    await subscriber_manager.disconnect(ws)

    print("\n[流程结束]")
    print(f"  AI Agent 共收到 {len(ws.messages)} 个事件")

    # 打印所有事件
    print("\n  事件列表:")
    for i, msg in enumerate(ws.get_messages(), 1):
        print(f"    {i}. {msg.get('type')}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  WxEye 事件系统测试套件")
    print("=" * 60)

    asyncio.run(test_event_types())
    asyncio.run(test_event_system())
    asyncio.run(simulate_chat_flow())
