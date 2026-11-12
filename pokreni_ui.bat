@echo off
chcp 65001 >nul
rem Squad Updater: otvara se u vlastitom prozoru; kad zatvoris prozor, program se sam ugasi.
python "%~dp0squad_updater.py"
if errorlevel 1 pause
