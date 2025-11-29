@echo off
chcp 65001 >nul
title WxEye - Build

echo ========================================
echo   WxEye 构建脚本
echo ========================================
echo.

cd /d "%~dp0"

:: ============ 后端 ============
echo [1/4] 配置后端环境...
cd backend

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 创建虚拟环境
if not exist ".venv\Scripts\activate.bat" (
    echo [*] 创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

echo [2/4] 安装后端依赖...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] 安装后端依赖失败
    pause
    exit /b 1
)

cd ..

:: ============ 前端 ============
echo [3/4] 检查前端环境...
cd frontend

:: 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 18+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

:: 安装依赖
if not exist "node_modules" (
    echo [*] 安装前端依赖...
    call npm install
    if errorlevel 1 (
        echo [错误] 安装前端依赖失败
        pause
        exit /b 1
    )
)

echo [4/4] 构建前端...
call npm run build
if errorlevel 1 (
    echo [错误] 前端构建失败
    pause
    exit /b 1
)

cd ..

echo.
echo ========================================
echo   构建完成！
echo   运行 start.bat 启动服务
echo ========================================
echo.

pause
