@echo off
rem ============================================================
rem 医学图像处理平台 - 一键产出 绿色版 + 安装包
rem   1) PyInstaller 生成绿色版  dist\MedImg\MedImg.exe
rem   2) Inno Setup 打包安装包   dist\MedImg-Setup.exe
rem 需要: medimg 环境 + Inno Setup 6 (https://jrsoftware.org/isinfo.php)
rem ============================================================
cd /d "%~dp0"

set PY=D:\Anaconda_Envs\medimg\python.exe
set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe

if not exist "%PY%" (
    echo [错误] 未找到 Python: %PY%
    echo 请确认 conda 环境 medimg 存在, 或修改本脚本开头的 PY 变量
    pause
    exit /b 1
)

echo [1/3] 清理旧产物...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo [2/3] PyInstaller 打包绿色版 (约 2~5 分钟)...
"%PY%" -m PyInstaller --noconfirm --clean MedImg.spec
if errorlevel 1 (
    echo.
    echo [错误] PyInstaller 打包失败, 请查看上方日志
    pause
    exit /b 1
)

if not exist "%ISCC%" (
    echo.
    echo [错误] 未找到 Inno Setup 编译器: %ISCC%
    echo 请先安装 Inno Setup 6 (免费): https://jrsoftware.org/isinfo.php
    echo 绿色版 dist\MedImg\ 已生成, 可直接分发.
    pause
    exit /b 1
)

echo [3/3] Inno Setup 生成安装包...
"%ISCC%" installer.iss
if errorlevel 1 (
    echo.
    echo [错误] 安装包生成失败
    pause
    exit /b 1
)

echo.
echo 全部完成!
echo   绿色版: dist\MedImg\MedImg.exe
echo   安装包: dist\MedImg-Setup.exe
pause
