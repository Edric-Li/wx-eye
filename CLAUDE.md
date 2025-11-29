# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WxEye is a WeChat visual monitoring agent that monitors multiple independent WeChat chat windows, detects changes using perceptual hashing (pHash), and optionally analyzes messages using Claude Vision API.

## Commands

### Backend (Python)
```bash
cd backend
source .venv/bin/activate  # or: python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev          # Development server (port 3000)
npm run build        # Production build: tsc && vite build
npm run lint         # ESLint
npm run lint:fix     # ESLint with auto-fix
npm run format       # Prettier format
npm run format:check # Check formatting
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (React/TypeScript)                                     │
│  - Monitor.tsx: main dashboard component                         │
│  - useWebSocket.ts: WebSocket connection & state management      │
│  - ImageViewer, LogPanel, AIMessagePanel, SendMessagePanel       │
└────────────────────���───────┬────────────────────────────────────┘
                             │ WebSocket + REST API
┌────────────────────────────▼────────────────────────────────────┐
│  Backend (FastAPI)         main.py                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ MultiContactCaptureEngine                                    │ │
│  │  - Monitors multiple WeChat chat windows simultaneously      │ │
│  │  - Each contact has its own ImageComparator                  │ │
│  │  - Integrates with AIMessageProcessor for analysis           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  capture/                   ai/                                   │
│  ├── window.py (WindowFinder)  ├── claude_analyzer.py (Vision)  │
│  ├── screenshot.py             ├── message_deduplicator.py      │
│  └── comparator.py (pHash)     └── processor.py (orchestrator)   │
│  api/                       services/                            │
│  ├── routes.py              └── message_sender.py (pyautogui)   │
│  └── websocket.py                                                │
└─────────────────────────────────────────────────────────────────┘
```

### Key Data Flow

1. **Window Detection**: Uses Quartz (macOS) or pygetwindow (Windows) to find WeChat chat windows by title
2. **Screenshot Capture**: Captures window content even when occluded (macOS CGWindowListCreateImage)
3. **Change Detection**: ImageComparator uses pHash to detect significant visual changes
4. **AI Processing Pipeline** (when enabled):
   - ClaudeAnalyzer uses Vision API to extract messages from screenshot
   - MessageDeduplicator identifies new messages via local dedup
5. **Message Sending**: UI automation via pyautogui (click input box, paste, press Enter)

### Configuration

Settings managed via `backend/config.py` using pydantic-settings. Configuration priority: env vars > `.env` file > defaults.

Key env vars:
- `ANTHROPIC_API_KEY`: Required for AI features
- `ANTHROPIC_BASE_URL`: Custom API endpoint (optional)
- `CLAUDE_MODEL`: haiku/sonnet/opus (default: haiku)
- `ENABLE_AI`: Toggle AI analysis (default: true)

### Event System (events/)

WxEye uses an event-driven architecture for external service integration:

```
events/
├── types.py      # Event, EventType definitions
├── bus.py        # EventBus singleton (publish/subscribe)
└── subscriber.py # WebSocket subscriber management
```

**Event Types:**
- `message.received` - New messages detected (with parsed content)
- `message.sent` - Message send completed
- `contact.online` - Contact window appeared
- `contact.offline` - Contact window disappeared
- `monitor.started` / `monitor.stopped`
- `error`, `log`

**Event Format:**
```json
{
  "id": "evt_abc123",
  "type": "message.received",
  "timestamp": "2024-01-15T10:30:00Z",
  "contact": "张三",
  "payload": {
    "messages": [{"sender": "张三", "content": "你好"}],
    "message_count": 1
  }
}
```

### WebSocket Protocol

**New Commands (event-driven):**
```json
{"command": "subscribe", "events": ["message.received", "message.sent"]}
{"command": "subscribe", "events": ["*"]}
{"command": "unsubscribe", "events": ["contact.online"]}
{"command": "monitor.start", "contacts": ["张三"], "interval": 0.1}
{"command": "monitor.stop"}
{"command": "message.send", "contact": "张三", "text": "你好"}
{"command": "contacts.add", "name": "李四"}
{"command": "contacts.remove", "name": "李四"}
{"command": "windows.discover"}
```

**Legacy Commands (still supported):**
- `{"command": "start", "interval": 0.1}` - Start monitoring
- `{"command": "stop"}` - Stop monitoring
- `{"command": "add_contact", "name": "联系人"}` - Add contact
- `{"command": "remove_contact", "name": "联系人"}` - Remove contact
- `{"command": "list_wechat_windows"}` - Discover windows
- `{"command": "reset"}` - Reset counters

**Response Types:** `screenshot`, `log`, `status`, `ai_message` (legacy) + all event types (new)

## Platform-Specific Notes

- **macOS**: Uses pyobjc-framework-Quartz for window enumeration and screenshot capture
- **Windows**: Uses pygetwindow for window detection; mss for screenshots
- Message sender calculates input box position relative to window bounds (bottom center)
