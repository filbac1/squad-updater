@echo off
chcp 65001 >nul
rem Provjera sustava (testovi). Ne dira igru ni bazu.
python "%~dp0provjera.py"
echo.
pause
