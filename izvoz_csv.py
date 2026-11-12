# -*- coding: utf-8 -*-
"""
Izvoz FL27 baze (Player.bin + PlayerAppearance.bin) u CSV istog formata kao
"Export CSV" u Ejogc327 PES2020 Editoru (281 stupac, ';', UTF-8 s BOM).

Raspored polja je preuzet iz tablica samog editora (editor_tablice.json):
  t0 = Player.bin (312 B), stupci 0-148;  t2 = PlayerAppearance.bin (60 B), stupci 151-280.

    python izvoz_csv.py                 -> izvoz aktivne baze igre u izvjestaji\\baza_<datum>.csv
    python izvoz_csv.py izlaz.csv [--baza=mapa]
"""
import os, sys, csv, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fl27db as D

T = json.load(open(os.path.join(HERE, 'editor_tablice.json'), encoding='utf-8'))
HEADER = open(os.path.join(HERE, 'editor_zaglavlje.txt'), encoding='utf-8-sig').read().strip().split(';')
APP_CPK_DIR = 'common/character0/model/character/appearance'
APP_OVERRIDE = None        # izvor.py postavlja tocnu putanju PlayerAppearance.bin za vlastitu bazu

# stupci bez polja u tablici -> vrijednost koju editor upisuje
DEFAULTS = {5: '-1', 107: '0', 141: '0', 142: 'False', 143: '-1', 145: '0', 146: '0', 147: '0', 148: '0',
            149: 'False', 273: '0', 274: '0', 275: '0', 280: '0'}
for c in list(range(125, 141)) + [276, 277, 278, 279]: DEFAULTS[c] = 'False'
DATE_COLS = (118, 119)
U8_COLS = (121,)                          # NationalCaps = cijeli bajt
U32_COLS = (0, 116, 117)                  # Id, YouthClub, OwnerClub
HAIR_COL = 241                            # editor prikazuje boju kose kroz tablicu
HAIR_MAP = {0: 9, 1: 4, 2: 6, 3: 5, 4: 8, 5: 1, 6: 2, 7: 3, 8: 7}
HAIR_INV = {v: k for k, v in HAIR_MAP.items()}

def u32(b, o): return int.from_bytes((bytes(b[o:o + 4]) + b'\0\0\0\0')[:4], 'little')
def field(r, e): return ((u32(r, e[0]) >> e[1]) & ((1 << e[2]) - 1)) + e[3]
def cstr(b): return bytes(b).split(b'\0')[0].decode('utf-8', 'replace')

def fmt_date(v):
    y, m, d = v // 10000, v % 10000 // 100, v % 100
    if y < 1 or m < 1 or d < 1: return '1.1.0001. 0:00:00'
    return '%d.%d.%d. 0:00:00' % (d, m, y)

def parse_date(s):
    s = s.strip().split(' ')[0].rstrip('.')
    d, m, y = (int(x) for x in s.split('.'))
    return 0 if y <= 1 else y * 10000 + m * 100 + d

def player_cols(r):
    out = []
    for c, e in enumerate(T['t0']):
        if not e: out.append(DEFAULTS.get(c, '0'))
        elif c in DATE_COLS: out.append(fmt_date(field(r, e)))
        elif c in U8_COLS: out.append(str(r[e[0]]))
        elif len(e) == 4: out.append(str(field(r, e)))
        elif e[1] == 60: out.append(cstr(r[e[0]:e[0] + 60]))
        elif c in U32_COLS: out.append(str(u32(r, e[0])))
        else: out.append(str(bool(r[e[0]] >> e[1] & 1)))
    return out

def appearance_cols(a):
    out = []
    for j, e in enumerate(T['t2'][1:]):
        c = 151 + j
        if a is None or not e: out.append(DEFAULTS.get(c, '0'))
        elif len(e) == 4:
            v = field(a, e)
            out.append(str(HAIR_MAP.get(v, v) if c == HAIR_COL else v))
        else: out.append(str(bool(a[e[0]] >> e[1] & 1)))
    return out

def load_bins():
    """Vrati (player_bin, appearance_bin, izvori) iz aktivne baze igre ili --baza mape."""
    if D.BASE:
        P = D.PF.wesys(open(os.path.join(D.BASE, 'Player.bin'), 'rb').read()); srcP = D.BASE
    else:
        db, src = D.PF.load_db(D.roots(), D.PF.game_cpks(), names=('Player.bin',))
        P, srcP = db['Player.bin'], src['Player.bin']
    A, srcA = None, None
    if APP_OVERRIDE and os.path.isfile(APP_OVERRIDE):
        return P, D.PF.wesys(open(APP_OVERRIDE, 'rb').read()), (srcP, APP_OVERRIDE)
    cands = []
    if D.BASE:
        up = D.BASE
        for _ in range(4):
            cands.append(os.path.join(up, 'PlayerAppearance.bin'))
            cands.append(os.path.join(up, *APP_CPK_DIR.split('/'), 'PlayerAppearance.bin'))
            up = os.path.dirname(up)
    for r in D.roots():
        cands.append(os.path.join(r, *APP_CPK_DIR.split('/'), 'PlayerAppearance.bin'))
    for p in cands:
        if os.path.isfile(p):
            A, srcA = D.PF.wesys(open(p, 'rb').read()), p; break
    if A is None:
        order = sorted(D.PF.game_cpks(), key=lambda p: (os.path.basename(os.path.dirname(p)).lower() == 'download',
                                                        os.path.getmtime(p)), reverse=True)
        for path in order:
            try: c = D.PF.Cpk(path)
            except Exception: continue
            for row in c.toc:
                if row.get('FileName') == 'PlayerAppearance.bin' and (row.get('DirName') or '').replace('\\', '/').strip('/') == APP_CPK_DIR:
                    A, srcA = D.PF.wesys(c.read(row)), path; break
            if A is not None: break
    return P, A, (srcP, srcA)

ATTR_COL = {n: 27 + i for i, n in enumerate(D.ANAMES)}      # stupci 27-51 = 25 atributa

def export(path, overall_fn=None, changes=None):
    """overall_fn(rec_bytes) -> int za stupac OverallStats (ako None, ostaje prazno).
    changes = {player_id: {naziv_atributa: nova_vrijednost}} -> upisuje se u CSV (baza se NE dira)."""
    changes = changes or {}
    P, A, src = load_bins()
    app = {}
    if A is not None:
        for i in range(len(A) // 60):
            a = A[i * 60:(i + 1) * 60]; app[u32(a, 0)] = a
    n = 0
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';', lineterminator='\r\n')
        w.writerow(HEADER)
        for i in range(len(P) // D.REC):
            r = P[i * D.REC:(i + 1) * D.REC]
            ch = changes.get(u32(r, 8))
            if ch:
                r = D.apply_changes(bytearray(r), ch)
            row = player_cols(r) + ['False', str(overall_fn(r)) if overall_fn else ''] + appearance_cols(app.get(u32(r, 8)))
            w.writerow(row); n += 1
    return n, src

def overall_from_rec(r):
    import pes_overall as PO
    pos = D.getf(r, 54, 2, 4)
    if pos >= 13: return 0
    return PO.overall([D.getf(r, b, s, 6, 40) for nm, b, s in D.ATTR], D.getf(r, 57, 6, 2, 1), pos)

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import izvor as IZ
    OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    cfg = IZ.use(IZ.cfg_from_opts(OPT))
    tag = '' if cfg['id'] == 'igra' else cfg['id'] + '_'
    out = args[0] if args else os.path.join(HERE, 'izvjestaji', 'baza_%s%s.csv' % (tag, datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    n = IZ.export_csv(out, {}, cfg)
    print('Baza: %s' % IZ.opis(cfg))
    print('Izvezeno %d igraca -> %s' % (n, out))
