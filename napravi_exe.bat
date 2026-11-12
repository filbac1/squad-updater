@echo off
rem Squad Updater: zapakiraj aplikaciju (PyInstaller) -> dist\SquadUpdater\ + SquadUpdater.zip na Desktopu
cd /d "%~dp0"
python -m unittest discover -s testovi || (echo TESTOVI NISU PROSLI - ne pakiram. & pause & goto :eof)
python -m PyInstaller --noconfirm --clean SquadUpdater.spec || goto :eof
powershell -NoProfile -Command "Compress-Archive -Path 'dist\SquadUpdater' -DestinationPath \"$env:USERPROFILE\Desktop\SquadUpdater.zip\" -Force"
echo Gotovo: %USERPROFILE%\Desktop\SquadUpdater.zip
pause
