# -*- coding: utf-8 -*-
"""
IZVOR BAZE - odakle se citaju igraci i kamo/kako ide novi PlayerAppearance CSV.

Vrste izvora (cfg = dict):
  {'tip': 'igra'}                                   aktivna baza igre (sider livecpk + CPK-ovi igre)
  {'tip': 'mapa', 'put': 'D:\\baza'}                 mapa s .bin datotekama (trazi Player.bin bilo gdje unutra)
  {'tip': 'cpk',  'put': 'D:\\x\\data_s2627.cpk'}     CPK datoteka (raspakira pesdb + appearance u baze\\<id>\\)
  {'tip': 'csv',  'csv': 'D:\\baza.csv'}             samo CSV iz PES2020 Editora (bez klubova -> trazenje po imenu)
  bilo koja od mapa/cpk/igra + 'csv'                klubovi iz .bin, trenutne ocjene i izlazni format iz tvog CSV-a

Naredbeni redak (ocjene.py, bez_kluba.py, ...):  --baza=<mapa ili .cpk>   --csv-ulaz=<editor.csv>
Svaki izvor ima svoju mapu baze\\<id>\\ (rucni popis, cache trazenja, raspakirani CPK).
"""
import os, sys, csv, json, hashlib, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fl27db as D

def _dat(v):
    v = int(v); return '%d.%d.%d. 0:00:00' % (v % 100, v // 100 % 100, v // 10000) if v else '1.1.0001. 0:00:00'

BAZE = os.path.join(HERE, 'baze')
AKTIVNA = os.path.join(BAZE, 'aktivna.json')
APP_DIR = ('common', 'character0', 'model', 'character', 'appearance')
CFG = None

# ------------------------------------------------------------------ konfiguracija
def cfg_from_opts(opt):
    """--baza / --csv-ulaz iz naredbenog retka; bez njih aktivna.json (sucelje) ili baza igre."""
    if 'baza' in opt or 'csv-ulaz' in opt:
        c = {}
        b = opt.get('baza')
        if isinstance(b, str) and b:
            c['tip'] = 'cpk' if b.lower().endswith('.cpk') else 'mapa'; c['put'] = b
        if isinstance(opt.get('csv-ulaz'), str):
            c['csv'] = opt['csv-ulaz']; c.setdefault('tip', 'csv')
        return normalize(c)
    if 'baza-igre' in opt: return {'tip': 'igra', 'id': 'igra'}
    return aktivna()

def opseg_ids(opt, P=None):
    """--opseg=<json> -> skup ID-eva igraca u opsegu posla (None = cijela baza)."""
    if not isinstance(opt.get('opseg'), str): return None
    o = json.load(open(opt['opseg'], encoding='utf-8'))
    if P is None: P = load_players(CFG or aktivna())[0]
    lige, kl, ig = set(o.get('lige') or []), set(o.get('klubovi') or []), set(o.get('igraci') or [])
    key = lambda p: p.get('league_code') or (('OSTALI:' + p.get('country', '')) if p.get('club_id') else '')
    return {p['id'] for p in P if p['id'] in ig or (p.get('club_id') and p['club_id'] in kl) or (key(p) and key(p) in lige)}

def izlaz_iz_opts(opt, cfg):
    """--izlaz=<mapa> [--od=izlaz]: pripremi izlaznu mapu (kopija cijele baze) i, za --od=izlaz, citaj iz nje.
    Vraca (cfg, izlazna_mapa ili None)."""
    iz = opt.get('izlaz') if isinstance(opt.get('izlaz'), str) else None
    if not iz or cfg['tip'] == 'csv': return cfg, None
    import spremanje as SP
    od = opt.get('od') if isinstance(opt.get('od'), str) else ''
    if od and od != 'izlaz':                       # --od=<mapa>: citaj iz snimke ulaza (posao u vise koraka)
        pes = SP.citaj_iz(od)
        if not pes: raise SystemExit('Nema baze u %s' % od)
        if not SP.citaj_iz(iz): SP.pripremi(iz, cfg, log=lambda s: print(s, flush=True))
        cfg = dict(cfg, citaj=pes); use(cfg); return cfg, iz
    od_izlaza = od == 'izlaz'
    if 'bez-pripreme' in opt and SP.citaj_iz(iz):
        pes = SP.citaj_iz(iz)
    else:
        pes = SP.pripremi(iz, cfg, od_originala=not od_izlaza, log=lambda s: print(s, flush=True))
    if od_izlaza:
        cfg = dict(cfg, citaj=pes); use(cfg)
    return cfg, iz

def normalize(c):
    c = dict(c or {}); c.setdefault('tip', 'igra')
    if c['tip'] != 'igra' and c['tip'] != 'csv' and not c.get('put'): c['tip'] = 'igra'
    key = '%s|%s|%s' % (c['tip'], os.path.abspath(c['put']).lower() if c.get('put') else '', os.path.abspath(c['csv']).lower() if c.get('csv') else '')
    if c['tip'] == 'igra' and not c.get('csv'): c['id'] = 'igra'
    else:
        nm = os.path.splitext(os.path.basename((c.get('put') or c.get('csv') or 'baza').rstrip('\\/')))[0]
        c['id'] = re.sub(r'[^A-Za-z0-9_-]+', '_', nm)[:30] + '_' + hashlib.md5(key.encode()).hexdigest()[:6]
    return c

def aktivna():
    if os.path.exists(AKTIVNA):
        try: return normalize(json.load(open(AKTIVNA, encoding='utf-8')))
        except Exception: pass
    return {'tip': 'igra', 'id': 'igra'}

def postavi_aktivnu(c):
    c = normalize(c); os.makedirs(BAZE, exist_ok=True)
    json.dump(c, open(AKTIVNA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return c

def opis(c):
    t = {'igra': 'Game database', 'mapa': 'Folder', 'cpk': 'CPK', 'csv': 'Editor CSV'}[c['tip']]
    s = t + (': ' + c['put'] if c.get('put') else '')
    if c.get('csv') and c['tip'] != 'csv': s += ' + CSV: ' + c['csv']
    elif c['tip'] == 'csv': s += ': ' + c['csv']
    return s

def mapa(c=None):
    """Radna mapa ovog izvora (rucni popis, cache)."""
    c = c or CFG or aktivna(); p = os.path.join(BAZE, c['id']); os.makedirs(p, exist_ok=True); return p

def use(c):
    """Postavi izvor za ovaj proces (fl27db.BASE itd.)."""
    global CFG
    CFG = normalize(c)
    D.BASE = None
    if CFG['tip'] in ('mapa', 'cpk'):
        D.BASE = pesdb_dir(CFG)
    if CFG.get('citaj'):                 # "krenuti od zadnjeg izlaza": citaj .bin iz izlazne mape (rucni popis i cache ostaju od izvora)
        D.BASE = CFG['citaj']
        import izvoz_csv as X
        a = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(CFG['citaj']))), *APP_DIR, 'PlayerAppearance.bin')
        X.APP_OVERRIDE = a if os.path.isfile(a) else X.APP_OVERRIDE
    return CFG

# ------------------------------------------------------------------ pronalazak datoteka
def _find(root, name):
    if os.path.isfile(os.path.join(root, name)): return os.path.join(root, name)
    for dp, dn, fn in os.walk(root):
        for f in fn:
            if f.lower() == name.lower(): return os.path.join(dp, f)
    return None

def pesdb_dir(c):
    if c['tip'] == 'cpk': return raspakiraj(c)
    p = _find(c['put'], 'Player.bin')
    if not p: raise SystemExit('U mapi %s nema Player.bin' % c['put'])
    return os.path.dirname(p)

def appearance_file(c):
    if c['tip'] == 'cpk':
        p = os.path.join(raspakiraj(c), '..', '..', '..', *APP_DIR, 'PlayerAppearance.bin')
        p = os.path.normpath(p)
        return p if os.path.isfile(p) else None
    if c['tip'] == 'mapa':
        return _find(c['put'], 'PlayerAppearance.bin')
    return None

def raspakiraj(c):
    """CPK -> baze\\<id>\\common\\etc\\pesdb + appearance (jednom; ponovno ako je CPK noviji)."""
    out = os.path.join(BAZE, c['id'], 'common', 'etc', 'pesdb')
    stamp = os.path.join(BAZE, c['id'], 'cpk_vrijeme.txt')
    mt = str(os.path.getmtime(c['put']))
    if os.path.isfile(os.path.join(out, 'Player.bin')) and os.path.exists(stamp) and open(stamp).read() == mt:
        return out
    cp = D.PF.Cpk(c['put']); n = 0
    for row in cp.toc:
        dn = (row.get('DirName') or '').replace('\\', '/').strip('/').lower()
        if dn == 'common/etc/pesdb' or dn == '/'.join(APP_DIR):
            dst = os.path.join(BAZE, c['id'], *dn.split('/'), row['FileName'])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, 'wb').write(cp.read(row)); n += 1
    if not os.path.isfile(os.path.join(out, 'Player.bin')):
        raise SystemExit('U CPK-u %s nema common/etc/pesdb/Player.bin' % c['put'])
    open(stamp, 'w').write(mt)
    return out

# ------------------------------------------------------------------ citanje igraca
def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f, delimiter=';'))
    if not rows or rows[0][:2] != ['Id', 'Name']:
        raise SystemExit('%s nije CSV iz PES2020 Editora (prvi stupci moraju biti Id;Name)' % path)
    return rows[0], rows[1:]

def _csv_players(path):
    H, R = read_csv(path)
    col = {h: i for i, h in enumerate(H)}
    ac = [col[h] for h in ('OffensiveAwareness', 'BallControl', 'Dribbling', 'TightPossession', 'LowPass', 'LoftedPass',
                           'Finishing', 'Heading', 'PlaceKicking', 'Curl', 'Speed', 'Acceleration', 'KickingPower', 'Jump',
                           'PhysicalContact', 'Balance', 'Stamina', 'DefensiveAwareness', 'BallWinning', 'Aggression',
                           'GKAwareness', 'GKCatching', 'GKClearing', 'GKReflexes', 'GKReach')]
    cmap = D.countries_map()
    P = []
    for i, r in enumerate(R):
        try:
            pos = int(r[col['POS']])
            p = {'idx': i, 'id': int(r[0]), 'name': r[col['Name']], 'shirt': r[col['Shirt']],
                 'nat': cmap.get(int(r[col['Country']] or 0), '?'), 'nat_id': int(r[col['Country']] or 0),
                 'nat2_id': int(r[col['Country2']] or 0), 'nat2': cmap.get(int(r[col['Country2']] or 0), ''), 'nt': [], 'club_id': None, 'club': '', 'league_code': '',
                 'league': 'Bez kluba', 'country': '', 'pos': D.POS[pos] if 0 <= pos < 13 else '?',
                 'pos_rating': [int(r[col[x]]) for x in D.POS], 'age': int(r[col['Age']]),
                 'height': int(r[col['Height']]), 'weight': int(r[col['Weight']]),
                 'attr': {n: int(r[c]) for n, c in zip(D.ANAMES, ac)}}
            p['attr']['_wfa'] = int(r[col['WeakFootAcc']])
            p['foot'] = 1 if r[col['Foot']] == 'True' else 0
            p['wfu'] = int(r[col['WeakFootUsage']])
            p['rep'] = int(r[col['Reputation']]); p['inj'] = int(r[col['InjuryResistance']])
            p['skills'] = {c for c in range(58, 106) if c < len(r) and r[c] == 'True'}
            P.append(p)
        except (ValueError, KeyError):
            continue
    return P

def load_players(c=None):
    """-> (P, raw_player_bin ili None, opis izvora). P = isti oblik kao fl27db.load()."""
    c = use(c or CFG or aktivna())
    if c['tip'] == 'csv':
        return _csv_players(c['csv']), None, opis(c)
    P, raw, src = D.load()
    if c.get('csv'):                       # klubovi iz .bin, ali trenutne ocjene/pozicije iz tvog CSV-a
        by = {p['id']: p for p in _csv_players(c['csv'])}
        keep = []
        for p in P:
            q = by.get(p['id'])
            if q is None: continue
            for k in ('name', 'shirt', 'pos', 'pos_rating', 'age', 'height', 'attr', 'nat', 'nat_id', 'nat2', 'nat2_id', 'foot', 'wfu', 'skills', 'rep', 'inj'): p[k] = q[k]
            p['csv_idx'] = q['idx']; keep.append(p)
        P = keep
    return P, raw, opis(c)

# ------------------------------------------------------------------ izlaz
def export_csv(out, changes, c=None):
    """changes = {player_id: {atribut: vrijednost}}. Zapise PlayerAppearance CSV za editor."""
    c = c or CFG or aktivna()
    import izvoz_csv as X, pes_overall as PO
    if c.get('csv'):
        H, R = read_csv(c['csv'])
        col = {h: i for i, h in enumerate(H)}
        amap = dict(zip(D.ANAMES, [27 + i for i in range(25)]))
        for r in R:
            ch = changes.get(int(r[0])) if r and r[0].isdigit() else None
            if not ch: continue
            for n, v in ch.items():
                if n in amap: r[amap[n]] = str(max(40, min(99, int(v))))
                elif n == '_age' and 'Age' in col: r[col['Age']] = str(int(v))
                elif n == '_height' and 'Height' in col: r[col['Height']] = str(int(v))
                elif n == '_nat' and 'Country' in col: r[col['Country']] = str(int(v))
                elif n == '_nat2' and 'Country2' in col: r[col['Country2']] = str(int(v))
                elif n == '_foot' and 'Foot' in col: r[col['Foot']] = 'True' if v else 'False'
                elif n == '_rep' and 'Reputation' in col: r[col['Reputation']] = str(int(v))
                elif n == '_inj' and 'InjuryResistance' in col: r[col['InjuryResistance']] = str(int(v))
                elif n == '_ugovor' and 'ContractUntil' in col: r[col['ContractUntil']] = _dat(v)
                elif n == '_posudba' and 'LoanUntil' in col: r[col['LoanUntil']] = _dat(v)
                elif n == '_vlasnik' and 'OwnerClub' in col: r[col['OwnerClub']] = str(int(v))
                elif n == '_wfu' and 'WeakFootUsage' in col: r[col['WeakFootUsage']] = str(int(v))
                elif n == '_wfa' and 'WeakFootAcc' in col: r[col['WeakFootAcc']] = str(int(v))
                elif n.startswith('_pos') and D.POS[int(n[4:])] in col: r[col[D.POS[int(n[4:])]]] = str(int(v))
                elif n.startswith('_sk'): r[int(n[3:])] = 'True' if v else 'False'
            if 'OverallStats' in col and r[col['POS']].isdigit() and int(r[col['POS']]) < 13:
                r[col['OverallStats']] = str(PO.overall([int(r[27 + i]) for i in range(25)], int(r[col['WeakFootAcc']]), int(r[col['POS']])))
        with open(out, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';', lineterminator='\r\n'); w.writerow(H); w.writerows(R)
        return len(R)
    use(c)
    X.APP_OVERRIDE = appearance_file(c)
    n, src = X.export(out, X.overall_from_rec, changes=changes)
    return n
