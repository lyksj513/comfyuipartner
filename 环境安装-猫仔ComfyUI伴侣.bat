@echo off
chcp 65001 >nul
title 猫仔ComfyUI伴侣 - 环境安装向导

echo =============================================
echo   🐱 猫仔ComfyUI伴侣 环境安装向导
echo =============================================
echo.
echo 功能：
echo   1. 检测 Python/py 是否可用
echo   2. 自动创建本地虚拟环境 .venv
echo   3. 在 .venv 中安装依赖（requests）
echo   4. 校验依赖是否可导入
echo.

:: Step 1: 定位到脚本所在目录
cd /d "%~dp0"

:: Step 2: 检测 Python 可用性
set "PY_CMD="
where python >nul 2>nul && set "PY_CMD=python"
if "%PY_CMD%"=="" (
    where py >nul 2>nul && set "PY_CMD=py"
)

if "%PY_CMD%"=="" (
    echo ❌ 未检测到 Python/py 命令。
    echo 请先安装 Python 3.8+，并在安裝时勾选「Add python.exe to PATH」。
    echo 下载地址: https://www.python.org/downloads/windows/
    echo 安装完后重新运行本脚本。
    pause
    exit /b 1
)

echo ✓ 检测到 Python: %PY_CMD%

:: Step 3: 检查 Python 版本 >= 3.8
for /f "usebackq tokens=1,2,3 delims=." %%a in (`%PY_CMD% -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"`) do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)

if %PY_MAJOR% LSS 3 (
    echo ❌ Python 版本过低，需要 3.8 及以上。
    pause
    exit /b 1
) else if %PY_MAJOR%==3 if %PY_MINOR% LSS 8 (
    echo ❌ Python 版本过低，需要 3.8 及以上。
    pause
    exit /b 1
)

echo ✓ Python 版本满足要求: %PY_MAJOR%.%PY_MINOR%

:: Step 4: 创建/复用虚拟环境 .venv
if not exist ".venv" (
    echo 🔧 正在创建虚拟环境 .venv ...
    %PY_CMD% -m venv .venv
    if errorlevel 1 goto :venv_fail
) else (
    echo ✓ 已检测到 .venv，直接复用
)

set "VENV_PY=.venv\Scripts\python.exe"
if not exist "%VENV_PY%" goto :venv_fail

echo ✓ 虚拟环境就绪: %VENV_PY%

:: Step 5: 升级 pip（可选）
"%VENV_PY%" -m pip install --upgrade pip >nul

:: Step 6: 安装依赖
echo 📦 正在安装依赖: requests
"%VENV_PY%" -m pip install --no-warn-script-location -q -U requests
if errorlevel 1 goto :pip_fail

:: Step 7: 校验导入
"%VENV_PY%" - <<"PYCODE"
import importlib
missing = []
for mod in ["requests", "tkinter"]:
    try:
        importlib.import_module(mod)
    except Exception as e:
        missing.append(f"{mod}: {e}")

if missing:
    import sys
    print("❌ 依赖校验失败:")
    for m in missing:
        print("  -", m)
    sys.exit(1)
else:
    print("✓ 依赖校验通过 (requests, tkinter)")
PYCODE
if errorlevel 1 goto :validate_fail

echo.
echo ✅ 环境已准备就绪！
echo 下一步建议：
echo   1) 双击「启动-猫仔ComfyUI伴侣.bat」启动程序（已在仓库根目录）
echo   2) 若想确保使用虚拟环境，可将启动脚本中的 python 改为 .venv\Scripts\python.exe
echo.
pause
exit /b 0

:venv_fail
echo ❌ 创建或检测虚拟环境失败，请检查 Python 是否完整安装。
pause
exit /b 1

:pip_fail
echo ❌ 依赖安装失败，请检查网络或pip源。
pause
exit /b 1

:validate_fail
echo ❌ 依赖校验失败，请检查上方提示。
pause
exit /b 1