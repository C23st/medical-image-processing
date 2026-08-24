@echo off
rem Start Medical Image Processing Platform (medimg environment)
cd /d "%~dp0"
"D:\Anaconda_Envs\medimg\python.exe" main.py
if errorlevel 1 (
    echo.
    echo Failed to start. Make sure the medimg environment exists at D:\Anaconda_Envs\medimg
    pause
)
