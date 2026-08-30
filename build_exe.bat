@echo off
rem ============================================================
rem 医学图像处理平台 - 打包脚本 (PyInstaller, onedir + 无控制台)
rem 产物: dist\MedImg\MedImg.exe
rem 验证: dist\MedImg\MedImg.exe --selftest  (输出 SELFTEST OK)
rem 说明: 需先在 medimg 环境安装 pyinstaller (见 requirements.txt)
rem ============================================================
cd /d "%~dp0"

set PY=D:\Anaconda_Envs\medimg\python.exe
if not exist "%PY%" (
    where python >nul 2>nul && set PY=python
)
if "%PY%"=="" (
    echo [错误] 未找到 Python 解释器。
    echo 请修改本脚本开头的 PY 变量为你的 Python 环境, 或先 conda activate medimg 再运行。
    pause
    exit /b 1
)

echo [1/3] 清理旧产物...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo [2/3] 开始打包 (约需 2~5 分钟, 请耐心等待)...
"%PY%" -m PyInstaller --noconfirm --clean MedImg.spec
if errorlevel 1 (
    echo.
    echo [错误] 打包失败, 请查看上方日志
    pause
    exit /b 1
)

echo [3/3] 打包完成!
echo.
echo   程序: dist\MedImg\MedImg.exe
echo   验证: dist\MedImg\MedImg.exe --selftest
echo   分发: 将 dist\MedImg 整个文件夹压缩为 zip 即可
pause
