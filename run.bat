@echo off
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 microsound.py
) else (
    python microsound.py
)

exit /b %ERRORLEVEL%
