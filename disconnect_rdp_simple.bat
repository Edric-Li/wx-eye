@echo off
REM 简化版：直接断开 RDP 但保持会话活跃
REM 执行后 RDP 会自动关闭，程序继续在后台运行

for /f "tokens=3" %%a in ('query session ^| find ">"') do (
    tscon %%a /dest:console
)
