@echo off
chcp 65001 >nul
title WxEye - WeChat Monitor

cd /d "%~dp0backend"

:: 检查是否已构建
if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 请先运行 build.bat 构建项目
    pause
    exit /b 1
)

:: 激活虚拟环境
call .venv\Scripts\activate.bat

:: 检查前端是否已构建
if not exist "..\frontend\dist\index.html" (
    echo [警告] 前端未构建，请先运行 build.bat
    echo [*] 将以仅后端模式启动...
    echo.
)

echo.
echo ========================================
echo   WxEye 微信监控服务
echo   http://localhost:8000
echo   按 Ctrl+C 停止服务
echo ========================================
echo.

:: 启动服务
python -m uvicorn main:app --host 0.0.0.0 --port 8000

pause
