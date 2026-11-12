@echo off
chcp 65001 >nul
python "%~dp0tm_overall.py" %*
echo.
pause
