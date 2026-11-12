@echo off
chcp 65001 >nul
rem OCJENE ZA CIJELU BAZU + UBACI U IGRU (novi Player.bin u ocjene_tm\izlaz, prethodni ide u izlaz_povijest)
rem Racuna od ORIGINALNE baze igre, ukljucuje rucni popis, popravak godina/drzavljanstva/visine,
rem ozljede, ugovore/posudbe, brisanje umirovljenih/duplikata (ciscenje.py) i reprezentacije s Transfermarkta.
python "%~dp0ugovori.py" --baza-igre
python "%~dp0ocjene.py" --sve --upisi --csv --baza-igre %*
python "%~dp0reprezentacije.py" --upisi --baza-igre
echo.
pause
