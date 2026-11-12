# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: pyinstaller SquadUpdater.spec  ->  dist\SquadUpdater\SquadUpdater.exe (mapa se šalje kao .zip)
import os
from PyInstaller.utils.hooks import collect_submodules

MODULI = ['ui', 'app_api', 'ocjene', 'izvor', 'fl27db', 'provjera_faca', 'spremanje', 'katalog', 'reprezentacije', 'ugovori',
          'ozljede', 'ciscenje', 'bez_kluba', 'tm_igrac', 'tm_api', 'tm_overall', 'tm_podaci', 'model_ea27', 'ea_atributi',
          'ea_dodatno', 'overall', 'pes_overall', 'izvoz_csv', 'katalog_liga', 'ea27', 'koza', 'lang', 'osvjezi_podatke', 'version', 'repr_rucno', 'postave', 'imena', 'mreza', 'napredak', 'objasni']
DATA = [('app.html', '.'), ('ui.html', '.'), ('editor_tablice.json', '.'), ('editor_zaglavlje.txt', '.'),
        ('model_ea27.pkl', '.'), ('ea_atributi.json', '.'), ('kalibracija.json', '.'),
        ('cache/ea_fc27.json', 'cache'), ('cache/katalog_liga.json', 'cache'), ('cache/tm_povijest.json', 'cache'),
        ('cache/tm_drzavljanstva.json', 'cache'),
        # paket pocetnih podataka: novi korisnik ne skida ~90 min ozljeda; tm_nat_ids treba liga-API za drzavljanstva
        ('cache/ozljede.json', 'cache'), ('cache/ozljede_t.json', 'cache'), ('cache/tm_nat_ids.json', 'cache'), ('cache/ea_datum.txt', 'cache'), ('UPUTE_EN.md', '.'), ('ikona_256.png', '.'), ('ea27_kontekst.json', '.')]
DATA = [d for d in DATA if os.path.exists(d[0])]

a = Analysis(['squad_updater.py'], pathex=['.'], datas=DATA,
             hiddenimports=MODULI + collect_submodules('sklearn.ensemble') + collect_submodules('sklearn.utils') + ['openpyxl', 'tkinter', 'tkinter.filedialog'],
             excludes=['cv2', 'torch', 'onnxruntime', 'rembg', 'matplotlib', 'IPython', 'pytest', 'pandas'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='SquadUpdater', console=False, icon='SquadUpdater.ico')
coll = COLLECT(exe, a.binaries, a.datas, name='SquadUpdater')
