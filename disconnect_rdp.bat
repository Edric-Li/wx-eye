@echo off
REM =====================================================
REM 断开 RDP 但保持桌面会话活跃
REM 使用方法：在断开 RDP 前运行此脚本
REM =====================================================

echo 正在查询当前会话...
query session

echo.
echo 正在将当前会话重定向到 console...
echo 注意：执行后 RDP 窗口会自动关闭，但程序会继续运行

REM 获取当前会话 ID
for /f "tokens=3" %%a in ('query session ^| find ">"') do set SESSION_ID=%%a

echo 当前会话 ID: %SESSION_ID%
echo.
echo 按任意键继续，或 Ctrl+C 取消...
pause

REM 重定向到 console
tscon %SESSION_ID% /dest:console

echo 完成！会话已重定向到 console
