@echo off
chcp 65001 >nul
title WxEye - WeChat Monitor

cd /d "%~dp0backend"

:: 检查虚拟环境
if exist ".venv\Scripts\activate.bat" (
    echo [*] 激活虚拟环境...
    call .venv\Scripts\activate.bat
) else (
    echo [*] 创建虚拟环境...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo [*] 安装依赖...
    pip install -r requirements.txt
)

echo.
echo ========================================
echo   WxEye 微信监控服务
echo   http://localhost:8000
echo   按 Ctrl+C 停止服务
echo ========================================
echo.

:: 启动服务
uvicorn main:app --host 0.0.0.0 --port 8000

pause
