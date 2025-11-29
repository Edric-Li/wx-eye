# WxEye

微信多联系人窗口视觉监控代理 - 实时监控多个微信独立聊天窗口，检测变化并保存截图。

## 功能特性

- **多联系人监控**: 同时监控多个微信独立聊天窗口
- **变化检测**: 使用感知哈希算法 (pHash) 检测截图变化
- **独立对比**: 每个联系人独立进行截图对比，互不干扰
- **实时推送**: 通过 WebSocket 实时推送截图和日志到前端
- **跨平台**: 支持 macOS 和 Windows
- **窗口遮挡**: macOS 使用 CGWindowListCreateImage 直接截取窗口内容，即使被遮挡也能正确截取

## 系统要求

- Python 3.12+
- Node.js 18+
- macOS 10.15+ 或 Windows 10+

## 快速开始

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\Activate.ps1
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
4. **查看截图**: 检测到变化时会自动保存并显示截图

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Backend (Python)                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌────────────┐             │
│  │  Window  │───▶│Screenshot│───▶│ Comparator │             │
│  │  Finder  │    │  Service │    │  (Hash)    │             │
│  └──────────┘    └──────────┘    └─────┬──────┘             │
│       │                                 │                    │
│       │ 定位微信窗口              不同则保存                │
│       │                                 ▼                    │
│       │              ┌─────────────────────────────┐        │
│       │              │   WebSocket + REST API      │        │
└───────┼──────────────└──────────────┬──────────────┘────────┘
        │                             │
        │                             ▼
        │              ┌─────────────────────────────┐
        │              │     Frontend (React)        │
        │              │  ┌─────────┐ ┌───────────┐  │
        │              │  │ 截图展示 │ │ 日志面板  │  │
        └──────────────│  └─────────┘ └───────────┘  │
                       └─────────────────────────────┘
```

## API 接口

### REST API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 服务状态 |
| `/api/windows` | GET | 列出所有窗口 |
| `/api/windows/wechat` | GET | 查找微信窗口 |
| `/api/contacts` | GET | 列出所有监控联系人 |
| `/api/contacts/add?name=xxx` | POST | 添加联系人 |
| `/api/contacts/{name}` | DELETE | 移除联系人 |
| `/api/wechat/windows` | GET | 列出所有微信聊天窗口 |
| `/api/capture/start` | POST | 启动监控 |
| `/api/capture/stop` | POST | 停止监控 |
| `/api/capture/status` | GET | 获取状态 |
| `/ws` | WebSocket | 实时通信 |

### WebSocket 命令

```json
{"command": "start", "interval": 0.1}
{"command": "stop"}
{"command": "status"}
{"command": "add_contact", "name": "联系人名称"}
{"command": "remove_contact", "name": "联系人名称"}
{"command": "list_wechat_windows"}
{"command": "reset"}
```

## 项目结构

```
wxeye/
├── backend/
│   ├── main.py              # FastAPI 入口和引擎
│   ├── capture/
│   │   ├── window.py        # 窗口定位
│   │   ├── screenshot.py    # 截图服务
│   │   └── comparator.py    # 图像对比
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
│   │   │   └── LogPanel.tsx
│   │   └── hooks/
│   │       └── useWebSocket.ts
│   └── package.json
└── README.md
```

## 后续计划

- [ ] AI 视觉分析（识别界面元素位置）
- [ ] 系统级鼠标/键盘控制
- [ ] 自动化任务脚本

## 许可证

MIT
