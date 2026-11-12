@echo off
chcp 65001 >nul
rem OCJENE ZA CIJELU FL27 BAZU (bez AI-ja)
rem  - skine/osvjezi Transfermarkt za sve lige iz baze (cache 7 dana)
rem  - izracuna ciljni overall formulom (TM -> EA FC 27, ljestvica 0.5)
rem  - proporcionalno skalira atribute i napravi CSV za PES2020 Editor u mapi izvjestaji
rem Dodatne opcije: --skala=0.3   --osvjezi   --baza="D:\neka\baza\common\etc\pesdb"
python "%~dp0ocjene.py" --sve --csv %*
echo.
pause
