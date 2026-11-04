@echo off
chcp 65001 >nul
title 智能学习助手
cd /d "%~dp0"
echo.
echo 智能学习助手 - 启动中...
echo ========================
echo.
echo 访问地址: http://localhost:8501
echo 按 Ctrl+C 停止运行
echo.
if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" -m streamlit run frontend\app.py --server.port 8501
) else (
    python -m streamlit run frontend\app.py --server.port 8501
)
pause
