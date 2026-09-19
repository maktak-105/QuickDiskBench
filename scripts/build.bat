@echo off
setlocal
cd /d "%~dp0\.."
python scripts\build.py %*
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Build failed with exit code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)
endlocal

