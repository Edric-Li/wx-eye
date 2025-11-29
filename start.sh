#!/bin/bash

# Auto-WeChat Vision Agent 启动脚本

set -e

echo "🚀 Starting Auto-WeChat Vision Agent..."

# 进入项目目录
cd "$(dirname "$0")"

# 检查是否有 uv，如果没有则安装
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 检查 Node.js 环境
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
fi

# 安装后端依赖 (uv 会自动管理 Python 版本)
echo "📦 Installing backend dependencies..."
cd backend
uv venv --python 3.12 2>/dev/null || uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 启动后端
echo "🐍 Starting backend server on http://localhost:8000..."
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 安装前端依赖
cd ../frontend
echo "📦 Installing frontend dependencies..."
npm install --silent 2>/dev/null || npm install

# 启动前端
echo "⚛️  Starting frontend dev server on http://localhost:3000..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Auto-WeChat Vision Agent is running!"
echo ""
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services..."

# 捕获退出信号
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# 等待
wait
