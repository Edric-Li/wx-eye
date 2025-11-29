# Auto-WeChat Vision Agent 启动脚本 (Windows PowerShell)

Write-Host "🚀 Starting Auto-WeChat Vision Agent..." -ForegroundColor Cyan

# 检查 Python 环境
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python not found. Please install Python 3.9+" -ForegroundColor Red
    exit 1
}

# 检查 Node.js 环境
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Node.js not found. Please install Node.js 18+" -ForegroundColor Red
    exit 1
}

# 获取脚本目录
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 安装后端依赖
Write-Host "📦 Installing backend dependencies..." -ForegroundColor Yellow
Set-Location backend

if (-not (Test-Path "venv")) {
    python -m venv venv
}

.\venv\Scripts\Activate.ps1
pip install -r requirements.txt -q

# 启动后端
Write-Host "🐍 Starting backend server on http://localhost:8000..." -ForegroundColor Green
$backend = Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" -PassThru -NoNewWindow

# 安装前端依赖
Set-Location ..\frontend
Write-Host "📦 Installing frontend dependencies..." -ForegroundColor Yellow
npm install --silent

# 启动前端
Write-Host "⚛️  Starting frontend dev server on http://localhost:3000..." -ForegroundColor Green
$frontend = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -PassThru -NoNewWindow

Write-Host ""
Write-Host "✅ Auto-WeChat Vision Agent is running!" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop all services..." -ForegroundColor Yellow

# 等待用户中断
try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
}
