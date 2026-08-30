@echo off
rem Start Medical Image Processing Platform
rem 优先使用本机 conda 环境 python; 不存在时回退到 PATH 中的 python (需已安装依赖)
cd /d "%~dp0"
set PY=D:\Anaconda_Envs\medimg\python.exe
if not exist "%PY%" (
    where python >nul 2>nul && set PY=python
)
if "%PY%"=="" (
    echo [错误] 未找到 Python 解释器。
    echo 请修改本文件开头的 PY 路径为你的 Python 环境, 或先 conda activate medimg 再运行。
    pause
    exit /b 1
)
"%PY%" main.py
if errorlevel 1 (
    echo.
    echo Failed to start. Make sure the Python environment with dependencies exists.
    pause
)
