#!/usr/bin/env python3
"""临时脚本：停止监控"""
import asyncio
import json
import websockets

async def stop_monitoring():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        # 发送停止命令
        await websocket.send(json.dumps({"command": "stop"}))
        print("[OK] Sent stop command")

        # 等待响应
        response = await websocket.recv()
        print(f"[OK] Server response: {response}")

if __name__ == "__main__":
    asyncio.run(stop_monitoring())
