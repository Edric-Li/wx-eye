#!/usr/bin/env python3
"""
WebSocket 集成测试
启动服务器并测试真实的 WebSocket 通信
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from httpx_ws import aconnect_ws


async def test_websocket_integration():
    """测试 WebSocket 集成"""
    print("=" * 60)
    print("WebSocket 集成测试")
    print("=" * 60)

    base_url = "http://localhost:8000"
    ws_url = "ws://localhost:8000/ws"

    # 检查服务器是否运行
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/")
            if response.status_code != 200:
                print("服务器未运行，请先启动: uvicorn main:app")
                return
            print(f"服务器状态: {response.json().get('name')} v{response.json().get('version')}")
    except Exception as e:
        print(f"无法连接服务器: {e}")
        print("请先启动: uvicorn main:app --reload")
        return

    # 测试 WebSocket 连接
    print("\n[测试 1] 连接 WebSocket...")
    async with httpx.AsyncClient() as client:
        async with aconnect_ws(ws_url, client) as ws:
            # 应该收到 connected 状态
            msg = await asyncio.wait_for(ws.receive_json(), timeout=5)
            print(f"  收到: {msg.get('type')} - {msg.get('status')}")
            assert msg.get("type") == "status"
            assert msg.get("status") == "connected"

            # 测试订阅（订阅所有事件以便接收 log、contact.added 等）
            print("\n[测试 2] 订阅事件...")
            await ws.send_json({
                "command": "subscribe",
                "events": ["*"]
            })
            msg = await asyncio.wait_for(ws.receive_json(), timeout=5)
            print(f"  收到: {msg.get('type')} - events={msg.get('events')}")
            assert msg.get("type") == "subscribed"

            # 测试添加联系人
            print("\n[测试 3] 添加联系人...")
            await ws.send_json({
                "command": "contacts.add",
                "name": "测试联系人"
            })
            # 收到多个消息（log, status, contact.added 等）
            received = []
            try:
                while True:
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=1)
                    received.append(msg.get('type'))
                    print(f"  收到: {msg.get('type')}")
            except asyncio.TimeoutError:
                pass
            print(f"  共收到 {len(received)} 条消息")

            # 测试窗口发现
            print("\n[测试 4] 发现窗口...")
            await ws.send_json({
                "command": "windows.discover"
            })
            # 收到消息
            received = []
            try:
                while True:
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=1)
                    received.append(msg.get('type'))
                    print(f"  收到: {msg.get('type')}")
                    if msg.get("type") == "windows.discovered":
                        windows = msg.get("windows", [])
                        print(f"    发现 {len(windows)} 个窗口")
            except asyncio.TimeoutError:
                pass
            print(f"  共收到 {len(received)} 条消息")

            # 测试移除联系人
            print("\n[测试 5] 移除联系人...")
            await ws.send_json({
                "command": "contacts.remove",
                "name": "测试联系人"
            })
            received = []
            try:
                while True:
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=1)
                    received.append(msg.get('type'))
                    print(f"  收到: {msg.get('type')}")
            except asyncio.TimeoutError:
                pass
            print(f"  共收到 {len(received)} 条消息")

            print("\n" + "=" * 60)
            print("集成测试完成!")
            print("=" * 60)


async def test_event_emission():
    """测试事件发布（通过直接调用 EventBus）"""
    print("\n" + "=" * 60)
    print("事件发布测试（需要服务器运行）")
    print("=" * 60)

    base_url = "http://localhost:8000"
    ws_url = "ws://localhost:8000/ws"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/")
            if response.status_code != 200:
                print("服务器未运行")
                return
    except Exception:
        print("服务器未运行")
        return

    # 连接 WebSocket
    async with httpx.AsyncClient() as client:
        async with aconnect_ws(ws_url, client) as ws:
            # 等待初始状态
            await ws.receive_json()

            # 订阅所有事件
            await ws.send_json({"command": "subscribe", "events": ["*"]})
            await ws.receive_json()

            print("\n现在可以从另一个终端发布测试事件...")
            print("例如运行: python -c \"")
            print("from events import Event, get_event_bus")
            print("import asyncio")
            print("async def test():")
            print("    bus = get_event_bus()")
            print("    await bus.emit(Event.message_received('测试', [{'sender': 'A', 'content': 'Hi'}]))")
            print("asyncio.run(test())\"")
            print("\n等待事件 (Ctrl+C 退出)...")

            try:
                while True:
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=30)
                    print(f"收到事件: {msg.get('type')}")
                    if msg.get("type") == "message.received":
                        payload = msg.get("payload", {})
                        for m in payload.get("messages", []):
                            print(f"  {m.get('sender')}: {m.get('content')}")
            except asyncio.TimeoutError:
                print("超时，未收到事件")
            except KeyboardInterrupt:
                print("\n已退出")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--listen", action="store_true", help="监听模式，等待事件")
    args = parser.parse_args()

    if args.listen:
        asyncio.run(test_event_emission())
    else:
        try:
            asyncio.run(test_websocket_integration())
        except ImportError as e:
            print(f"缺少依赖: {e}")
            print("请安装: pip install httpx httpx-ws")
