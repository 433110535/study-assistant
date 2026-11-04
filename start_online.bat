@echo off
chcp 65001 >nul
title 智能学习助手 - 内网穿透
echo.
echo 智能学习助手 - 外网访问启动
echo ========================
echo.
echo 正在启动内网穿透...
echo 启动后会显示一个外网访问地址，发给同学即可访问
echo.
echo 按 Ctrl+C 停止运行
echo.
cpolar http 8501
pause
