@echo off
chcp 65001 >nul
title WxEye - WeChat Monitor

echo [*] 切换到 backend 目录...
cd /d "%~dp0backend"
if errorlevel 1 (
    echo [错误] 找不到 backend 目录
    pause
    exit /b 1
)

echo [*] 当前目录: %cd%

:: 检查 Python
echo [*] 检查 Python...
python --version
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 检查虚拟环境
if exist ".venv\Scripts\activate.bat" (
    echo [*] 激活虚拟环境...
    call .venv\Scripts\activate.bat
) else (
    echo [*] 创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    call .venv\Scripts\activate.bat

    echo [*] 安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 安装依赖失败
        pause
        exit /b 1
    )
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
if errorlevel 1 (
    echo.
    echo [错误] 服务启动失败
)

pause
