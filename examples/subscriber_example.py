#!/usr/bin/env python3
"""
WxEye 订阅者示例
演示如何通过 WebSocket 订阅事件并处理消息

使用方法:
    python examples/subscriber_example.py

依赖:
    pip install websockets
"""

import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("请先安装 websockets: pip install websockets")
    sys.exit(1)


async def main():
    """主函数"""
    uri = "ws://localhost:8000/ws"

    print(f"连接到 {uri}...")

    async with websockets.connect(uri) as ws:
        print("已连接!")

        # 1. 订阅感兴趣的事件
        await ws.send(json.dumps({
            "command": "subscribe",
            "events": ["message.received", "message.sent", "error"]
        }))

        # 等待订阅确认
        response = await ws.recv()
        print(f"订阅确认: {response}")

        # 2. 添加要监控的联系人
        contact_name = input("输入要监控的联系人名称 (微信聊天窗口标题): ").strip()
        if contact_name:
            await ws.send(json.dumps({
                "command": "contacts.add",
                "name": contact_name
            }))

        # 3. 开始监控
        await ws.send(json.dumps({
            "command": "monitor.start",
            "interval": 0.1
        }))
        print("监控已启动，等待事件...")
        print("(按 Ctrl+C 退出)\n")

        # 4. 接收并处理事件
        try:
            async for message in ws:
                data = json.loads(message)
                event_type = data.get("type", "")

                # 处理新消息事件
                if event_type == "message.received":
                    contact = data.get("contact", "未知")
                    messages = data.get("payload", {}).get("messages", [])
                    print(f"\n{'='*50}")
                    print(f"[{contact}] 收到 {len(messages)} 条新消息:")
                    for msg in messages:
                        sender = msg.get("sender", "?")
                        content = msg.get("content", "")
                        print(f"  {sender}: {content}")
                    print(f"{'='*50}\n")

                    # 示例: 自动回复
                    # if should_reply(messages):
                    #     reply = generate_reply(messages)
                    #     await ws.send(json.dumps({
                    #         "command": "message.send",
                    #         "contact": contact,
                    #         "text": reply
                    #     }))

                # 处理消息发送完成事件
                elif event_type == "message.sent":
                    payload = data.get("payload", {})
                    success = payload.get("success", False)
                    text = payload.get("text", "")[:30]
                    if success:
                        print(f"[发送成功] {text}...")
                    else:
                        print(f"[发送失败] {text}... 错误: {payload.get('error')}")

                # 处理错误事件
                elif event_type == "error":
                    payload = data.get("payload", {})
                    print(f"[错误] {payload.get('code')}: {payload.get('message')}")

                # 其他事件类型
                elif event_type in ("contact.online", "contact.offline"):
                    contact = data.get("contact", "")
                    status = "上线" if event_type == "contact.online" else "离线"
                    print(f"[联系人{status}] {contact}")

                elif event_type in ("monitor.started", "monitor.stopped"):
                    print(f"[监控状态] {event_type}")

                # 旧协议兼容 (status, log, screenshot 等)
                elif event_type in ("status", "log", "screenshot", "ai_message"):
                    # 忽略旧协议消息，或按需处理
                    pass

        except KeyboardInterrupt:
            print("\n正在停止...")
            await ws.send(json.dumps({"command": "monitor.stop"}))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已退出")
