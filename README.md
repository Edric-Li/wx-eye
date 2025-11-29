# WxEye

微信多联系人窗口视觉监控代理 - 实时监控多个微信独立聊天窗口，使用 AI 分析消息内容并支持自动回复。

## 功能特性

- **多联系人监控**: 同时监控多个微信独立聊天窗口
- **变化检测**: 使用感知哈希算法 (pHash) 检测截图变化
- **AI 消息分析**: 使用 Claude Vision API 识别并提取聊天消息
- **智能去重**: 本地去重算法，只推送真正的新消息
- **消息发送**: 支持自动发送消息，包括 @ 提及群成员
- **事件驱动**: 完整的事件系统，支持订阅消息、联系人状态等事件
- **实时推送**: 通过 WebSocket 实时推送消息和事件
- **跨平台**: 支持 macOS 和 Windows
- **窗口遮挡**: macOS 下即使窗口被遮挡也能正确截取

## 系统要求

- Python 3.12+
- Node.js 18+
- macOS 10.15+ 或 Windows 10+

## 快速开始

### 配置

创建 `backend/.env` 文件：

```env
ANTHROPIC_API_KEY=your-api-key
ANTHROPIC_BASE_URL=https://api.anthropic.com  # 可选，自定义 API 地址
CLAUDE_MODEL=sonnet  # haiku/sonnet/opus，默认 sonnet
ENABLE_AI=true  # 是否启用 AI 分析
```

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000 使用监控界面。

## 使用说明

1. **添加联系人**: 在监控界面输入微信独立聊天窗口的标题（联系人名称）
2. **发现窗口**: 点击"发现窗口"按钮列出当前所有微信聊天窗口
3. **开始监控**: 添加联系人后点击"开始监控"
4. **查看消息**: AI 识别到新消息后会实时推送到界面
5. **发送消息**: 在输入框输入消息发送，支持 `@成员名` 格式提及群成员

## 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (React/TypeScript)                                     │
│  - Monitor.tsx: 主监控面板                                        │
│  - AIMessagePanel: AI 消息展示                                    │
│  - SendMessagePanel: 消息发送                                     │
│  - useWebSocket.ts: WebSocket 连接管理                            │
└─────────────────────────────┬────────────────────────────────────┘
                              │ WebSocket + REST API
┌─────────────────────────────▼────────────────────────────────────┐
│  Backend (FastAPI)                                                │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ MultiContactCaptureEngine                                    │  │
│  │  - 监控多个微信聊天窗口                                        │  │
│  │  - 每个联系人独立的 ImageComparator                           │  │
│  │  - 集成 AIMessageProcessor 进行消息分析                        │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  capture/                    ai/                                   │
│  ├── window.py (窗口定位)     ├── claude_analyzer.py (Vision API) │
│  ├── screenshot.py (截图)     ├── message_deduplicator.py (去重)  │
│  └── comparator.py (pHash)   └── processor.py (处理编排)          │
│                                                                    │
│  events/                     services/                             │
│  ├── types.py (事件定义)      └── message_sender.py (消息发送)     │
│  ├── bus.py (事件总线)                                             │
│  └── subscriber.py (订阅管理)                                      │
└────────────────────────────────────────────────────────────────────┘
```

### 数据流程

1. **窗口检测**: 使用 Quartz (macOS) 或 pygetwindow (Windows) 定位微信窗口
2. **截图捕获**: 即使窗口被遮挡也能正确截取 (macOS CGWindowListCreateImage)
3. **变化检测**: pHash 算法检测显著视觉变化
4. **AI 分析** (启用时):
   - 首次截图作为基准，跳过分析
   - Claude Vision API 识别消息内容
   - 本地去重算法提取新消息
5. **消息发送**: pyautogui UI 自动化，支持 @ 提及

## API 接口

### REST API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 服务状态 |
| `/api/windows` | GET | 列出所有窗口 |
| `/api/windows/wechat` | GET | 查找微信窗口 |
| `/api/wechat/windows` | GET | 列出所有微信聊天窗口 |
| `/api/contacts` | GET | 列出所有监控联系人 |
| `/api/contacts/add?name=xxx` | POST | 添加联系人 |
| `/api/contacts/{name}` | DELETE | 移除联系人 |
| `/api/capture/start` | POST | 启动监控 |
| `/api/capture/stop` | POST | 停止监控 |
| `/api/capture/status` | GET | 获取状态 |
| `/ws` | WebSocket | 实时通信 |

### WebSocket 命令

**事件驱动命令:**

```json
{"command": "subscribe", "events": ["message.received", "message.sent"]}
{"command": "subscribe", "events": ["*"]}
{"command": "unsubscribe", "events": ["contact.online"]}
{"command": "monitor.start", "contacts": ["张三"], "interval": 0.1}
{"command": "monitor.stop"}
{"command": "message.send", "contact": "张三", "text": "你好"}
{"command": "message.send", "contact": "群名", "text": "你好", "at": ["成员1", "成员2"]}
{"command": "contacts.add", "name": "李四"}
{"command": "contacts.remove", "name": "李四"}
{"command": "windows.discover"}
```

**兼容命令:**

```json
{"command": "start", "interval": 0.1}
{"command": "stop"}
{"command": "add_contact", "name": "联系人名称"}
{"command": "remove_contact", "name": "联系人名称"}
{"command": "list_wechat_windows"}
{"command": "reset"}
```

### 事件类型

| 事件 | 描述 |
|------|------|
| `message.received` | 检测到新消息 |
| `message.sent` | 消息发送完成 |
| `contact.online` | 联系人窗口出现 |
| `contact.offline` | 联系人窗口消失 |
| `monitor.started` | 监控已启动 |
| `monitor.stopped` | 监控已停止 |

**事件格式:**

```json
{
  "id": "evt_abc123",
  "type": "message.received",
  "timestamp": "2024-01-15T10:30:00Z",
  "contact": "张三",
  "payload": {
    "messages": [{"sender": "$other", "content": "你好"}],
    "message_count": 1
  }
}
```

消息中的 sender 标识:
- `$self` - 我发送的消息
- `$other` - 私聊中对方发送的消息
- 其他值 - 群聊中发送者的昵称

## 项目结构

```
wxeye/
├── backend/
│   ├── main.py              # FastAPI 入口和监控引擎
│   ├── config.py            # 配置管理
│   ├── capture/
│   │   ├── window.py        # 窗口定位
│   │   ├── screenshot.py    # 截图服务
│   │   └── comparator.py    # 图像对比 (pHash)
│   ├── ai/
│   │   ├── claude_analyzer.py    # Claude Vision 分析
│   │   ├── message_deduplicator.py  # 消息去重
│   │   └── processor.py     # AI 处理编排
│   ├── events/
│   │   ├── types.py         # 事件类型定义
│   │   ├── bus.py           # 事件总线
│   │   └── subscriber.py    # 订阅管理
│   ├── services/
│   │   └── message_sender.py  # 消息发送
│   ├── api/
│   │   ├── routes.py        # REST API
│   │   └── websocket.py     # WebSocket 管理
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Monitor.tsx
│   │   │   ├── ImageViewer.tsx
│   │   │   ├── LogPanel.tsx
│   │   │   ├── AIMessagePanel.tsx
│   │   │   └── SendMessagePanel.tsx
│   │   └── hooks/
│   │       └── useWebSocket.ts
│   └── package.json
└── README.md
```

## 许可证

MIT
