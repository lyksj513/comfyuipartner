@echo off
chcp 65001 >nul
title 猫仔ComfyUI伴侣

echo.
echo ========================================
echo   🐱 猫仔ComfyUI伴侣 启动中...
echo ========================================
echo.
echo 📝 作品信息：
echo   作者: lovelycateman
echo   来源: www.52pojie.cn
echo   版权: 开源免费，禁止商用
echo.
echo 🚀 功能特性：
echo   - 双图融合模式
echo   - 单图+文件夹融合
echo   - 文件夹交叉融合
echo   - 批量生成模式
echo   - 单图处理模式
echo   - 文件夹批处理模式
echo.
echo ----------------------------------------
echo.

cd /d "%~dp0"

python "猫仔ComfyUI伴侣.py"

if errorlevel 1 (
    echo.
    echo ❌ 启动失败！请检查：
    echo   1. 是否安装了Python
    echo   2. 是否安装了必要的依赖包 (requests)
    echo   3. process_monitor.py文件是否存在
    echo.
    pause
)
