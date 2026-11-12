# -*- coding: utf-8 -*-
"""
API nove aplikacije (app.html): projekt (baza + izlazna mapa), pregled/filteri nad katalogom igrača,
detalj igrača, izvoz, posao (opseg + promjene -> koraci), povijest poslova, postavke.

ui.py prvo pita ovaj modul (get / post); vraća None ako adresa nije njegova.
"""
import os, sys, json, csv, io, time, struct, datetime, threading, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
POSTAVKE = os.path.join(HERE, 'postavke.json')
DOCS = os.path.join(os.path.expanduser('~'), 'Documents')

def _jl(p, d=None):
    try: return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError): return d

def _jw(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + '.novo', 'w', encoding='utf-8') as f: json.dump(o, f, ensure_ascii=False, indent=1)
    os.replace(p + '.novo', p)

# ------------------------------------------------------------------ postavke i projekt
def postavke():
    d = {'jezik': 'en', 'igra_cilj': '', 'tm_razmak': 0.5}
    d.update(_jl(POSTAVKE, {}) or {})
    return d

def cfg():
    import izvor as IZ
    return IZ.aktivna()

def projekt_put(c=None):
    import izvor as IZ
    return os.path.join(IZ.mapa(c or cfg()), 'projekt.json')

def igra_radi():
    """Je li igra pokrenuta? (tada se u njezine datoteke ne smije pisati)"""
    try:
        import subprocess
        o = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, creationflags=0x08000000, timeout=10).stdout.lower()
        return any(n in o for n in ('fl_2027.exe', 'pes2021.exe'))
    except Exception:
        return False

def projekt():
    import izvor as IZ, spremanje as SP
    c = cfg(); pr = _jl(projekt_put(c), {}) or {}
    if not pr.get('izlaz'):
        nm = os.path.splitext(os.path.basename((c.get('put') or c.get('csv') or 'game database').rstrip('\\/')))[0] or 'database'
        pr['izlaz'] = os.path.join(DOCS, 'Squad Updater', nm + ' (updated)')
        pr['predlozeno'] = True
    info = _jl(os.path.join(pr['izlaz'], SP.OZNAKA), None) if pr.get('izlaz') else None
    return {'baza': c, 'opis': IZ.opis(c), 'tip': c['tip'], 'izlaz': pr['izlaz'], 'predlozeno': pr.get('predlozeno', False),
            'izlaz_postoji': bool(SP.citaj_iz(pr['izlaz'])), 'izlaz_info': info, 'katalog': katalog()['meta'],
            'greska': (globals().get('STATE') or {}).get('greska'), 'igra_radi': igra_radi(), 'igra': igra_stanje(pr['izlaz']),
            'postavke': postavke(), 'verzija': __import__('version').VERSION}

def igra_stanje(izlaz):
    """Sto je u igri: mapa u koju se kopira, je li isto kao nova baza, kad je zadnje kopirano, edit file."""
    import spremanje as SP
    d = postavke(); g = d.get('igra_cilj')
    save = SP.save_mapa(d.get('igra_dir'), d.get('save_dir'))
    isto = SP.isto_u_igri(izlaz, g) if g and SP.citaj_iz(izlaz) else {}
    return {'cilj': g, 'u_igri': SP.u_igri(g) if g else None, 'isto': isto,
            'azurno': bool(isto) and all(isto.values()), 'edit': SP.edit_stanje(save),
            'edit_reset': d.get('edit_reset', True)}

def reprezentacije_sve():
    """Sve reprezentacije iz zadnjeg izracuna: status, ulaze/izlaze prema ORIGINALU, sastav po linijama, tko nedostaje (s TM id-em)."""
    import glob
    R = _jl(os.path.join(HERE, 'izvjestaji', 'reprezentacije_zadnje.json'), None) or {}
    idx = {}
    for f in glob.glob(os.path.join(HERE, 'cache', 'reprezentacije', '*.json')):
        for q in _jl(f, []) or []:
            if q.get('ime'): idx.setdefault(q['ime'], q)
    byid = {x['id']: x for x in katalog()['igraci']}
    out = []
    for t in R.get('timovi', []):
        nema = []
        for n in t.get('nema') or []:
            ime = n.split(' (')[0]; q = idx.get(ime) or {}
            nema.append({'ime': ime, 'razlog': 'other_team' if '(' in n else 'not_in_db', 'tm_id': q.get('tm_id'), 'poz': q.get('poz'), 'god': q.get('god')})
        uids = {u['id'] for u in t.get('ulaze', [])}
        sast = []
        for x in t.get('sastav') or []:
            k = byid.get(x['id']) or {}
            sast.append(dict(x, novi=x['id'] in uids, drz=k.get('drz'), ovr0=k.get('ovr0'), dob=k.get('dob')))
        out.append({'tim': t['tim'], 'id': t.get('id'), 'status': t.get('status'), 'pozvanih': t.get('pozvanih'), 'u_bazi': t.get('u_bazi'),
                    'ulaze': t.get('ulaze', []), 'izlaze': t.get('izlaze', []), 'sastav': sast, 'nema': nema, 'rucno': t.get('rucno')})
    return {'vrijeme': R.get('vrijeme'), 'timovi': out}

def statistika():
    """Lige (prosjek prije/poslije, najveci skok/pad) i klubovi (prosjek najboljih 11 prije/poslije)."""
    LEG = ('Classics', 'ML Default')
    L = [x for x in katalog()['igraci'] if x.get('ovr') is not None and x.get('ovr0') is not None and not any(t in (x.get('klub') or '') for t in LEG)]
    lig = collections.defaultdict(list); klub = collections.defaultdict(list)
    for x in L:
        lig[x['liga']].append(x)
        if x.get('klub_id') and x.get('klub'): klub[(x['klub_id'], x['klub'], x['liga'])].append(x)
    avg = lambda v: round(sum(v) / len(v), 1) if v else None
    lige = []
    for n, xs in lig.items():
        if len(xs) < 11: continue
        d = sorted(xs, key=lambda x: x['ovr'] - x['ovr0'])
        lige.append({'liga': n, 'igraca': len(xs), 'prije': avg([x['ovr0'] for x in xs]), 'poslije': avg([x['ovr'] for x in xs]),
                     'promijenjeno': sum(1 for x in xs if x['ovr'] != x['ovr0']),
                     'skok': {'id': d[-1]['id'], 'ime': d[-1]['ime'], 'd': d[-1]['ovr'] - d[-1]['ovr0']},
                     'pad': {'id': d[0]['id'], 'ime': d[0]['ime'], 'd': d[0]['ovr'] - d[0]['ovr0']}})
    lige.sort(key=lambda r: -(r['poslije'] or 0))
    klubovi = []
    for (kid, kn, ln), xs in klub.items():
        if len(xs) < 11: continue
        b0 = avg(sorted((x['ovr0'] for x in xs), reverse=True)[:11]); b1 = avg(sorted((x['ovr'] for x in xs), reverse=True)[:11])
        top = max(xs, key=lambda x: x['ovr'])
        klubovi.append({'id': kid, 'klub': kn, 'liga': ln, 'igraca': len(xs), 'prije': b0, 'poslije': b1,
                        'razlika': round(b1 - b0, 1), 'najbolji': {'id': top['id'], 'ime': top['ime'], 'ovr': top['ovr']}})
    klubovi.sort(key=lambda r: -r['poslije'])
    return {'lige': lige, 'klubovi': klubovi}

def izvjestaj_xlsx():
    """Excel sa svim promjenama: ocjene (+ promjene atributa), reprezentacije, drzavljanstva, lige, klubovi."""
    import fl27db as D, spremanje as SP
    from openpyxl import Workbook
    pr = projekt(); pes = SP.citaj_iz(pr['izlaz']) if pr['izlaz_postoji'] else None
    def recs(raw):
        return {struct.unpack_from('<I', raw, i * D.REC + 8)[0]: raw[i * D.REC:(i + 1) * D.REC] for i in range(len(raw) // D.REC)}
    db, _ = D.load_files(('Player.bin',)); A0 = recs(db['Player.bin'])
    A1 = recs(D.PF.wesys(open(os.path.join(pes, 'Player.bin'), 'rb').read())) if pes else {}
    wb = Workbook(write_only=True)
    ws = wb.create_sheet('Players')
    ws.append(['ID', 'Name', 'Club', 'League', 'Nationality', 'Position', 'Age', 'Overall before', 'Overall after', 'Change']
              + ['%s (change)' % n for n in D.ANAMES])
    for x in katalog()['igraci']:
        r0, r1 = A0.get(x['id']), A1.get(x['id'])
        if r0 is None or r1 is None or r0 == r1: continue
        dd = [D.getf(r1, b, s_, 6, 40) - D.getf(r0, b, s_, 6, 40) for _, b, s_ in D.ATTR]
        ws.append([x['id'], x['ime'], x['klub'], x['liga'], x['drz'], x['poz'], x['dob'], x['ovr0'], x['ovr'],
                   (x['ovr'] or 0) - (x['ovr0'] or 0)] + [v or None for v in dd])
    wr = wb.create_sheet('National teams')
    wr.append(['Team', 'Status', 'Called up', 'In database', 'In', 'Out', 'Missing from database'])
    for t in reprezentacije_sve()['timovi']:
        wr.append([t['tim'], t['status'], t['pozvanih'], t['u_bazi'], ', '.join(u['ime'] for u in t['ulaze']),
                   ', '.join(u['ime'] for u in t['izlaze']), ', '.join(n['ime'] for n in t['nema'])])
    wn = wb.create_sheet('Nationality'); wn.append(['ID', 'Name', 'Before', 'Now (first)', 'Second'])
    for x in (_jl(os.path.join(HERE, 'izvjestaji', 'drzavljanstva_zadnje.json'), {}) or {}).get('igraci', []):
        wn.append([x['id'], x['ime'], x['prije'], x['sada'], x.get('druga')])
    S = statistika()
    wl = wb.create_sheet('Leagues'); wl.append(['League', 'Players', 'Average before', 'Average after', 'Changed'])
    for r in S['lige']: wl.append([r['liga'], r['igraca'], r['prije'], r['poslije'], r['promijenjeno']])
    wk = wb.create_sheet('Clubs'); wk.append(['Club', 'League', 'Players', 'Best XI before', 'Best XI after', 'Change'])
    for r in S['klubovi']: wk.append([r['klub'], r['liga'], r['igraca'], r['prije'], r['poslije'], r['razlika']])
    b = io.BytesIO(); wb.save(b); return b.getvalue()

def pregled():
    """Sazetak zadnjeg posla za pocetnu stranicu: sto se promijenilo, reprezentacije, drzavljanstva."""
    H = [h for h in povijest() if not h.get('vrsta')]; zadnji = H[0] if H else None
    L = katalog()['igraci']
    ch = [x for x in L if x.get('ovr') is not None and x.get('ovr0') is not None and x['ovr'] != x['ovr0']]
    gore = sum(1 for x in ch if x['ovr'] > x['ovr0']); dolje = len(ch) - gore
    top = sorted(ch, key=lambda x: -abs(x['ovr'] - x['ovr0']))[:8]
    st = collections.Counter(s_ for x in L for s_ in x.get('st', []))
    R = _jl(os.path.join(HERE, 'izvjestaji', 'reprezentacije_zadnje.json'), None) or {}
    tim = []
    for t in R.get('timovi', []):
        if t.get('status') == 'promijenjeno':
            tim.append({'tim': t['tim'], 'ulaze': [x['ime'] for x in t.get('ulaze', [])], 'izlaze': [x['ime'] for x in t.get('izlaze', [])],
                        'pozvanih': t.get('pozvanih'), 'u_bazi': t.get('u_bazi'), 'nema': len(t.get('nema') or []),
                        'sastav': [{'ime': x['ime'], 'poz': x['poz'], 'ovr': x['ovr'], 'broj': x.get('broj'), 'klub': x.get('klub')} for x in t.get('sastav', [])]})
    rs = collections.Counter(t.get('status') for t in R.get('timovi', []))
    DZ = _jl(os.path.join(HERE, 'izvjestaji', 'drzavljanstva_zadnje.json'), None) or {}
    return {'posao': zadnji, 'igraca': len(L), 'promijenjeno': len(ch), 'gore': gore, 'dolje': dolje,
            'top': [{'id': x['id'], 'ime': x['ime'], 'klub': x['klub'], 'ovr0': x['ovr0'], 'ovr': x['ovr']} for x in top],
            'status': dict(st), 'repr': {'vrijeme': R.get('vrijeme'), 'promijenjeno': len(tim), 'isto': rs.get('isto', 0),
                                         'preskoceno': rs.get('premalo', 0) + rs.get('prazno', 0) + rs.get('nepovezano', 0), 'timovi': tim},
            'drzavljanstva': DZ.get('igraci', []), 'meta': katalog()['meta']}

# ------------------------------------------------------------------ katalog u memoriji
AA_PING = {'t': 0.0, 'zatvara': 0.0}
KAT = {'mtime': None, 'igraci': [], 'meta': None, 'opcije': None}
KLOCK = threading.Lock()

def katalog():
    import katalog as K
    f = K.datoteka(cfg())
    if not os.path.exists(f):
        KAT.update(mtime=None, igraci=[], meta=None, opcije=None); return KAT
    mt = os.path.getmtime(f)
    with KLOCK:
        if KAT['mtime'] != (f, mt):
            d = _jl(f, {'igraci': [], 'meta': None})
            L = d['igraci']
            lg = collections.Counter((x['liga_k'], x['liga']) for x in L if x['liga_k'])
            kl = collections.Counter((x['klub_id'], x['klub'], x['liga']) for x in L if x['klub_id'])
            rp = collections.Counter(r for x in L for r in x['repr'])
            dr = collections.Counter(x['drz'] for x in L)
            KAT.update(mtime=(f, mt), igraci=L, meta=d['meta'], opcije={
                'lige': [{'k': k, 'n': n_, 'c': c} for (k, n_), c in sorted(lg.items(), key=lambda x: -x[1])],
                'klubovi': [{'id': i, 'n': n_, 'l': l, 'c': c} for (i, n_, l), c in sorted(kl.items(), key=lambda x: x[0][1])],
                'repr': [{'n': n_, 'c': c} for n_, c in sorted(rp.items())],
                'drzave': [{'n': n_, 'c': c} for n_, c in sorted(dr.items())]})
    return KAT

def filtriraj(q):
    """q = dict filtera (iz URL-a ili JSON-a) -> popis igrača."""
    L = katalog()['igraci']
    g = lambda k: (q.get(k) or '').strip() if isinstance(q.get(k), str) else q.get(k)
    s = (g('q') or '').lower()
    lige = set(filter(None, (g('liga') or '').split('|')))
    klubovi = {int(x) for x in (g('klub') or '').split('|') if x.strip().lstrip('-').isdigit()}
    drz = set(filter(None, (g('drz') or '').split('|')))
    rep = set(filter(None, (g('repr') or '').split('|')))
    poz = set(filter(None, (g('poz') or '').split(',')))
    st = [x for x in (g('st') or '').split(',') if x]
    nst = [x for x in (g('nst') or '').split(',') if x]
    num = lambda k, d: int(g(k)) if str(g(k) or '').lstrip('-').isdigit() else d
    a0, a1, o0, o1, dmin = num('dob_od', 0), num('dob_do', 99), num('ovr_od', 0), num('ovr_do', 99), num('delta', 0)
    ug = num('ug', 0)
    sid = int(s) if s.isdigit() else None
    out = []
    for x in L:
        if s and not (sid == x['id'] or s in x['ime'].lower() or s in (x['klub'] or '').lower()): continue
        if lige and x['liga_k'] not in lige: continue
        if klubovi and x['klub_id'] not in klubovi: continue
        if drz and x['drz'] not in drz: continue
        if rep and not rep.intersection(x['repr']): continue
        if poz and x['poz'] not in poz: continue
        if not (a0 <= (x['dob'] or 0) <= a1): continue
        if not (o0 <= (x['ovr'] or 0) <= o1): continue
        if st and not all(t in x['st'] for t in st): continue
        if nst and any(t in x['st'] for t in nst): continue
        if dmin and (x['ovr'] is None or x['ovr0'] is None or abs(x['ovr'] - x['ovr0']) < dmin): continue
        if ug and not (x['ug'] and x['ug'] // 10000 == ug): continue
        out.append(x)
    srt = g('sort') or 'vr'
    rev = (g('dir') or 'desc') == 'desc'
    key = {'ime': lambda x: x['ime'].lower(), 'klub': lambda x: (x['klub'] or '').lower(), 'dob': lambda x: x['dob'] or 0,
           'ovr': lambda x: x['ovr'] or 0, 'ovr0': lambda x: x['ovr0'] or 0, 'vr': lambda x: x['vr'] or 0,
           'delta': lambda x: (x['ovr'] or 0) - (x['ovr0'] or 0), 'ug': lambda x: x['ug'] or 0, 'poz': lambda x: x['poz']}.get(srt, lambda x: x['vr'] or 0)
    out.sort(key=key, reverse=rev)
    return out

def stranica(q):
    L = filtriraj(q)
    n = min(int(q.get('n') or 50), 500); p = max(int(q.get('page') or 1), 1)
    return {'ukupno': len(L), 'page': p, 'n': n, 'igraci': L[(p - 1) * n: p * n], 'meta': KAT['meta']}

def izvoz(q, fmt):
    L = filtriraj(q)
    cols = [('id', 'ID'), ('ime', 'Name'), ('klub', 'Club'), ('liga', 'League'), ('drz', 'Nationality'), ('poz', 'Position'),
            ('dob', 'Age'), ('ovr0', 'Overall (input)'), ('ovr', 'Overall (now)'), ('vr', 'TM value EUR'), ('ug', 'Contract until'),
            ('pos_do', 'Loan until'), ('vlasnik', 'Loan from'), ('tm', 'Transfermarkt ID'), ('st', 'Status')]
    val = lambda x, k: ', '.join(x[k]) if k == 'st' else ', '.join(x['repr']) if k == 'repr' else x.get(k)
    if fmt == 'xlsx':
        from openpyxl import Workbook
        wb = Workbook(write_only=True); ws = wb.create_sheet('Players'); ws.append([c[1] for c in cols])
        for x in L: ws.append([val(x, k) for k, _ in cols])
        b = io.BytesIO(); wb.save(b); return b.getvalue()
    s = io.StringIO(); w = csv.writer(s, delimiter=';'); w.writerow([c[1] for c in cols])
    for x in L: w.writerow([val(x, k) for k, _ in cols])
    return ('﻿' + s.getvalue()).encode('utf-8')

# ------------------------------------------------------------------ detalj igrača
def igrac(pid):
    import fl27db as D, izvor as IZ, spremanje as SP, overall as O, glob
    c = IZ.use(cfg()); pid = int(pid)
    x = next((y for y in katalog()['igraci'] if y['id'] == pid), None)
    if x is None: raise FileNotFoundError(pid)
    def rec(base):
        db, _ = D.load_files(('Player.bin',)) if base is None else ({'Player.bin': D.PF.wesys(open(os.path.join(base, 'Player.bin'), 'rb').read())}, None)
        raw = db['Player.bin']
        for i in range(len(raw) // D.REC):
            if struct.unpack_from('<I', raw, i * D.REC + 8)[0] == pid: return raw[i * D.REC:(i + 1) * D.REC]
        return None
    def attrs(r):
        if r is None: return None
        a = {n: D.getf(r, b, s, 6, 40) for n, b, s in D.ATTR}
        a.update({'Weak foot usage': D.getf(r, 56, 6, 2, 1), 'Weak foot accuracy': D.getf(r, 57, 6, 2, 1),
                  'Injury resistance': D.getf(r, 57, 2, 2, 1), 'Reputation': D.getf(r, 56, 3, 3, 1),
                  'Age': D.getf(r, 51, 0, 6, 15), 'Height': D.getf(r, 27, 0, 8, 100)})
        return a
    CM = D.countries_map()
    def podaci(r):
        if r is None: return None
        n1, n2 = D.getf(r, 29, 1, 9), D.getf(r, 28, 0, 9)
        return {'nat': CM.get(n1, ''), 'nat2': CM.get(n2, '') if n2 else '', 'ugovor': D.getf(r, 12, 0, 27) or None,
                'posudba': D.getf(r, 16, 0, 27) or None, 'vlasnik': D.getf(r, 4, 0, 32) or None,
                'foot': 'L' if D.getf(r, 64, 2, 1) else 'R', 'pos': D.POS[D.getf(r, 54, 2, 4)] if D.getf(r, 54, 2, 4) < 13 else '?',
                'pos_ocjene': [D.getf(r, b, s_, 2) for b, s_ in D.POS_RATING]}
    r0 = rec(None)
    pr = projekt(); pes = SP.citaj_iz(pr['izlaz']) if pr['izlaz_postoji'] else None
    r1 = rec(pes) if pes else None
    mapa = IZ.mapa(c)
    ru = (_jl(os.path.join(mapa, 'rucne.json'), {}) or {}).get(str(pid))
    zp = (_jl(os.path.join(mapa, 'za_provjeru.json'), {}) or {}).get(str(pid))
    tmq = None
    if x['tm']:
        for f in glob.glob(os.path.join(HERE, 'cache', 'tm_*_20*.json')):
            d = _jl(f)
            if isinstance(d, dict):
                tmq = next((q for q in d.get('players', []) if q['tm_id'] == x['tm']), None)
                if tmq: tmq = dict(tmq, name=tmq['name'].split('<')[0].strip()); break
    kako = ('manual list (%s)' % ru.get('izvor', 'manual')) if ru else ('league squad on Transfermarkt' if x['tm'] else None)
    return {'igrac': x, 'prije': attrs(r0), 'sada': attrs(r1) if r1 is not None else None,
        'pod0': podaci(r0), 'pod1': podaci(r1), 'tm': tmq or (ru and {
        'name': ru.get('tm_ime'), 'club': ru.get('klub'), 'value': ru.get('vrijednost'), 'age': ru.get('godine')}),
        'kako': kako, 'za_provjeru': zp, 'tm_link': 'https://www.transfermarkt.com/-/profil/spieler/%s' % x['tm'] if x['tm'] else None}

def objasnjenje(pid):
    """'Zasto ova ocjena?' za igraca iz baze (preko TM id-a); skala = klizac iz zadnjeg posla."""
    import izvor as IZ, objasni as OB
    x = next((y for y in katalog()['igraci'] if y['id'] == int(pid)), None)
    if x is None or not x.get('tm'): return {'ima': False, 'razlog': 'not_matched'}
    H = _jl(os.path.join(IZ.mapa(cfg()), 'poslovi.json'), []) or []
    sk = next((h.get('skala') for h in H if h.get('skala') is not None), None)
    r = OB.objasni(x['tm'], sk)
    if not r: return {'ima': False, 'razlog': 'no_value'}
    rucno = str(x['id']) in (_jl(os.path.join(IZ.mapa(cfg()), 'rucne.json'), {}) or {})
    return dict(r, ima=True, baza=x.get('ovr'), zakljucan='zakljucan' in x['st'], rucno=rucno)

def zakljucaj(pid, da):
    import izvor as IZ
    f = os.path.join(IZ.mapa(cfg()), 'zakljucani.json')
    z = set(_jl(f, []) or [])
    (z.add if da else z.discard)(int(pid)); _jw(f, sorted(z))
    _oznaci(int(pid), 'zakljucan', da)

def _oznaci(pid, st, da):
    for x in katalog()['igraci']:
        if x['id'] == pid:
            if da and st not in x['st']: x['st'].append(st)
            if not da and st in x['st']: x['st'].remove(st)

def ponisti(pid):
    """Vrati igrača u izlaznoj mapi na zapis iz ulazne baze i zaključaj ga."""
    import fl27db as D, izvor as IZ, spremanje as SP
    c = IZ.use(cfg()); pid = int(pid)
    pr = projekt(); pes = SP.citaj_iz(pr['izlaz']) if pr['izlaz_postoji'] else None
    if not pes: raise SystemExit('There is no output database yet.')
    raw0 = D.load_files(('Player.bin',))[0]['Player.bin']
    r0 = next((raw0[i * D.REC:(i + 1) * D.REC] for i in range(len(raw0) // D.REC) if struct.unpack_from('<I', raw0, i * D.REC + 8)[0] == pid), None)
    if r0 is None: raise SystemExit('Player %d is not in the input database.' % pid)
    out = bytearray(D.PF.wesys(open(os.path.join(pes, 'Player.bin'), 'rb').read()))
    for i in range(len(out) // D.REC):
        if struct.unpack_from('<I', out, i * D.REC + 8)[0] == pid:
            out[i * D.REC:(i + 1) * D.REC] = r0; break
    else:
        raise SystemExit('Player %d was removed in the output; run the job again without cleanup.' % pid)
    SP.zapisi(pr['izlaz'], {'Player.bin': bytes(out)}, posao={'korak': 'undo', 'igrac': pid}, log=lambda s: None)
    zakljucaj(pid, True); _oznaci(pid, 'promijenjen', False)
    for x in katalog()['igraci']:
        if x['id'] == pid: x['ovr'] = x['ovr0']

# ------------------------------------------------------------------ posao
OPCIJE = ['ratings', 'data', 'ea_profile', 'ea_extra', 'reputation', 'injuries', 'contracts', 'market_value', 'national', 'lineups', 'search', 'cleanup']
BK_PRAVILA = 2      # = bez_kluba.PRAVILA (verzija pravila uparivanja)
OCJENE_OPS = {'ratings', 'data', 'ea_profile', 'ea_extra', 'reputation', 'injuries', 'contracts', 'market_value', 'cleanup'}

def opseg_igraci(op):
    """op = {'tip': 'sve'|'lige'|'klubovi'|'filter', ...} -> popis igrača iz kataloga."""
    t = op.get('tip', 'sve'); L = katalog()['igraci']
    if t == 'sve': return L
    if t == 'lige': s = set(op.get('lige') or []); return [x for x in L if x['liga_k'] in s]
    if t == 'klubovi':
        s = set(op.get('klubovi') or []); rp = set(op.get('repr') or [])
        return [x for x in L if x['klub_id'] in s or rp.intersection(x['repr'])]
    if t == 'filter': return filtriraj(op.get('filter') or {})
    return L

# izmjerene brzine (11.11.2026., 26.395 igraca; isto racunalo i mreza) - poslije se kalibriraju prema stvarnim poslovima (tempo.json)
BRZINA = {'liga_api': 2.5,          # s po ligi (Transfermarkt API)
          'uparivanje': 20.0,       # s za 26.000 igraca (uparivanje s TM-om, bez izracuna)
          'zapis': 60.0,            # s za 26.000 igraca (izracun ocjena + atributi + Excel + zapis)
          'ugovori': 180.0,         # igraca u sekundi (profili + povijest transfera, 32 niti)
          'ozljede': 230.0,         # igraca u minuti (web stranice, ~4/s)
          'trazenje': 200.0,        # igraca u minuti (pojedinacno traženje, web)
          'repr': 60.0}             # s za sve reprezentacije (hladno)

def _tempo():
    import izvor as IZ
    return _jl(os.path.join(IZ.mapa(cfg()), 'tempo.json'), {}) or {}

def procjena(op, opc):
    """Realna procjena po koracima: koliko je zaista potrebno skinuti (predmemorija se uzima u obzir) x izmjerene brzine."""
    import glob, time as _t, ozljede as OZ, ugovori as UG, ocjene as OC
    L = opseg_igraci(op); n = len(L); opc = set(opc)
    lige = {x['liga_k'] for x in L if x['liga_k']}
    tmk = [OC.TM_KOD[k] for k in lige if k in OC.TM_KOD]
    now = _t.time()
    def svjeza(c):
        fs = glob.glob(os.path.join(HERE, 'cache', 'tm_%s_*.json' % c))
        return bool(fs) and now - max(os.path.getmtime(f) for f in fs) < 7 * 86400
    stare = [c for c in set(tmk) if not svjeza(c)]
    tm_poznato = [x for x in L if x['tm']]
    hladno = not tm_poznato and n > 0                       # jos nikad uparivano -> TM id-eva ne znamo; ocjena: ~80 % igraca je na TM-u
    oz = OZ.ucitaj() if 'injuries' in opc else {}
    I = UG._load(UG.F_IGR) if 'contracts' in opc else {}
    ok = lambda c, k: now - c.get(str(k), {}).get('t', 0) < 7 * 86400 if isinstance(c.get(str(k)), dict) else str(k) in c
    ima_tm = len(tm_poznato) if not hladno else int(0.8 * n)
    oz_t = OZ.ucitaj_t() if 'injuries' in opc else {}
    # hladno: TM id-eve jos ne znamo; paket pocetnih podataka vec pokriva dio igraca (najmanje 10 % se ipak skida)
    treba_oz = (max(int(ima_tm * 0.1), ima_tm - len(oz)) if hladno else sum(1 for x in tm_poznato if OZ.zastarjelo(x['tm'], oz, oz_t, now))) if 'injuries' in opc else 0
    treba_ug = (ima_tm if hladno else sum(1 for x in tm_poznato if not ok(I, x['tm']))) if 'contracts' in opc else 0
    treba_tr = 0
    if 'search' in opc:
        done = _jl(os.path.join(__import__('izvor').mapa(cfg()), 'bez_kluba_trazeno.json'), {}) or {}
        stara = ((_jl(os.path.join(__import__('izvor').mapa(cfg()), 'bez_kluba_pravila.json'), {}) or {}).get('verzija', 1) < BK_PRAVILA)
        treba_tr = sum(1 for x in L if 'nije_na_tm' in x['st'] and (str(x['id']) not in done or (stara and done.get(str(x['id'])) is None)))
    need_ids = bool({'injuries', 'contracts', 'cleanup'} & opc)
    ocj = bool(OCJENE_OPS & opc)
    B = BRZINA; f = _tempo(); S = []
    add = lambda name, sec: S.append({'n': name, 'min': round(max(sec, 0) * f.get(name, 1.0) / 60, 1), 'sec': sec})
    if not ocj and not need_ids and 'national' not in opc and 'search' not in opc: pass
    add('Prepare output folder', 3 + n / 26000 * 2)
    if 'search' in opc: add('Find unrated players on Transfermarkt', treba_tr / B['trazenje'] * 60)
    if need_ids: add('Match players with Transfermarkt', len(stare) * B['liga_api'] + B['uparivanje'] * max(n, 1) / 26000 + 8)
    if 'contracts' in opc: add('Download contracts and loans', treba_ug / B['ugovori'] + (3 if treba_ug else 0))
    if 'injuries' in opc: add('Download injury history', treba_oz / B['ozljede'] * 60)
    if 'cleanup' in opc: add('Find retired players and duplicates', 20 if n else 0)
    if ocj: add('Write new database', len(stare) * B['liga_api'] * (0 if need_ids else 1) + B['uparivanje'] * max(n, 1) / 26000 + B['zapis'] * max(n, 1) / 26000)
    if 'data' in opc: add('Names with accents', 6)
    if 'national' in opc: add('National teams', B['repr'] if n else 0)
    if 'lineups' in opc: add('Best starting line-ups', 5)
    add('Update player list', 3 + n / 26000 * 3)
    tot = sum(x['min'] for x in S)
    return {'igraca': n, 'lige': len(lige), 'minute': round(tot, 1), 'koraci': S, 'hladno': hladno,
            'treba': {'ozljede': treba_oz, 'ugovori': treba_ug, 'lige': len(stare), 'trazenje': treba_tr}}

def posao(b, start_job, py):
    """b = {opseg, opcije, od: 'original'|'izlaz', izlaz, u_igru, skala} -> pokreće korake. py(script) -> naredba."""
    import izvor as IZ
    c = cfg(); mapa = IZ.mapa(c)
    opc = [o for o in b.get('opcije') or [] if o in OPCIJE]
    if not opc: raise SystemExit('Choose at least one change.')
    izl = (b.get('izlaz') or '').strip().strip('"')
    if b.get('u_igru') and c['tip'] != 'csv' and igra_radi(): raise SystemExit('The game is running. Close it first, or untick “Also copy into the game”.')
    if c['tip'] != 'csv':
        if not izl: raise SystemExit('Choose where to save the new database.')
        if c.get('put') and os.path.normcase(os.path.abspath(izl)) == os.path.normcase(os.path.abspath(c['put'])):
            raise SystemExit('The output folder must be different from the input database.')
        pj = _jl(projekt_put(c), {}) or {}; pj['izlaz'] = izl; _jw(projekt_put(c), pj)
    op = b.get('opseg') or {'tip': 'sve'}
    L = opseg_igraci(op)
    if not L and katalog()['igraci']: raise SystemExit('No players in the chosen scope.')
    sc = []
    if op.get('tip', 'sve') != 'sve':
        f = os.path.join(mapa, 'opseg_posla.json')
        o = {'igraci': [x['id'] for x in L]}
        if op.get('tip') == 'lige': o = {'lige': op.get('lige') or []}
        if op.get('tip') == 'klubovi':
            o = {'klubovi': list(op.get('klubovi') or []), 'igraci': [x['id'] for x in L]}
        o['klubovi'] = sorted(set(o.get('klubovi', [])) | set(_repr_ids(op)))
        _jw(f, o); sc = ['--opseg=' + f]
    od = b.get('od') == 'izlaz'
    k = []
    if c['tip'] == 'csv':
        if OCJENE_OPS & set(opc) or 'search' in opc:
            if 'search' in opc: k.append(('Find players on Transfermarkt', py('bez_kluba.py') + ['--neocijenjeni'] + sc))
            k.append(('Ratings and data', py('ocjene.py') + (['--sve'] if not sc else []) + sc + _flags(opc, b) + ['--csv=' + (izl or os.path.join(DOCS, 'updated_database.csv'))]))
    else:
        snap = os.path.join(mapa, 'ulaz_posla')
        k.append(('Prepare output folder', py('spremanje.py') + ['--pripremi', '--izlaz=' + izl] + (['--od=izlaz'] if od else [])))
        ulaz = ['--od=' + snap] if od else ['--bez-pripreme']
        if 'search' in opc: k.append(('Find unrated players on Transfermarkt', py('bez_kluba.py') + ['--neocijenjeni'] + sc))
        need_ids = {'injuries', 'contracts', 'cleanup'} & set(opc)
        if need_ids:
            k.append(('Match players with Transfermarkt', py('ocjene.py') + (['--sve'] if not sc else []) + sc + ['--samo-uparivanje']))
            if 'contracts' in opc: k.append(('Download contracts and loans', py('ugovori.py') + sc))
            if 'injuries' in opc: k.append(('Download injury history', py('ozljede.py') + sc))
            if 'cleanup' in opc: k.append(('Find retired players and duplicates', py('ciscenje.py') + sc))
        if OCJENE_OPS & set(opc):
            k.append(('Write new database', py('ocjene.py') + (['--sve'] if not sc else []) + sc + _flags(opc, b) + ['--izlaz=' + izl] + ulaz))
        if 'data' in opc:
            k.append(('Names with accents', py('imena.py') + ['--izlaz=' + izl]))
        if 'national' in opc:
            k.append(('National teams', py('reprezentacije.py') + sc + ['--izlaz=' + izl] + (['--od=izlaz'] if (OCJENE_OPS & set(opc) or not od) else ['--od=' + snap])))
        if 'lineups' in opc:
            k.append(('Best starting line-ups', py('postave.py') + ['--izlaz=' + izl]))
        k.append(('Update player list', py('katalog.py') + ['--izlaz=' + izl]))
        cilj = postavke().get('igra_cilj')
        if b.get('u_igru') and cilj: k.append(('Copy into game', py('spremanje.py') + ['--izlaz=' + izl, '--u-igru=' + cilj] + _reset_arg(b)))
    IME = {'ratings': 'ratings', 'data': 'player data', 'ea_profile': 'EA attributes', 'ea_extra': 'EA foot/skills', 'reputation': 'reputation',
           'injuries': 'injuries', 'contracts': 'contracts', 'market_value': 'market value', 'national': 'national teams', 'lineups': 'best line-ups', 'search': 'player search', 'cleanup': 'cleanup'}
    naziv = 'Job: %s · %s' % (_opis_opsega(op, len(L)), ', '.join(IME[o] for o in opc))
    E = procjena(op, opc)
    ok = start_job(naziv, 'posao', None, k)
    if ok:
        h = os.path.join(mapa, 'poslovi.json'); H = _jl(h, []) or []
        H.insert(0, {'vrijeme': datetime.datetime.now().isoformat(timespec='seconds'), 'opseg': op, 'opseg_opis': _opis_opsega(op, len(L)),
                     'opcije': opc, 'od': b.get('od') or 'original', 'izlaz': izl, 'u_igru': bool(b.get('u_igru') and cilj),
                     'skala': b.get('skala'), 'koraci': [x[0] for x in k], 'status': 'running',
                     'procjena_min': E['minute'], 'est': {x['n']: x['sec'] for x in E['koraci']}})
        _jw(h, H[:100])
    return ok

def _reset_arg(b):
    """--reset-edit=<save mapa> kad korisnik zeli novi edit file (zadano: da, ako je save mapa pronadena)."""
    import spremanje as SP
    d = postavke(); r = b.get('reset_edit', d.get('edit_reset', True))
    sv = SP.save_mapa(d.get('igra_dir'), d.get('save_dir')) if r else None
    return ['--reset-edit=' + sv] if sv else []

def _repr_ids(op):
    if not op.get('repr'): return []
    import fl27db as D, struct as st
    db, _ = D.load_files(('Team.bin',)); T = db['Team.bin']; want = set(op['repr'])
    return [st.unpack_from('<I', T, i * 1532 + 8)[0] for i in range(len(T) // 1532) if D.PF.cstr(T[i * 1532 + 368:i * 1532 + 438]) in want]

def _flags(opc, b):
    f = []
    for o, fl in (('ratings', '--bez-ocjena'), ('data', '--bez-podataka'), ('ea_profile', '--bez-ea-profila'), ('ea_extra', '--bez-ea-dodataka'),
                  ('reputation', '--bez-reputacije'), ('injuries', '--bez-ozljeda'), ('contracts', '--bez-ugovora'), ('cleanup', '--bez-brisanja')):
        if o not in opc: f.append(fl)
    if 'market_value' in opc: f.append('--trzisna-vrijednost')
    if b.get('skala') is not None: f.append('--skala=%.2f' % float(b['skala']))
    return f

def _opis_opsega(op, n):
    t = op.get('tip', 'sve')
    if t == 'sve': return 'whole database (%d players)' % n
    if t == 'lige': return '%d league(s), %d players' % (len(op.get('lige') or []), n)
    if t == 'klubovi': return '%d club(s)/team(s), %d players' % (len(op.get('klubovi') or []) + len(op.get('repr') or []), n)
    return 'filtered players (%d)' % n

def zavrsi_posao(izlaz_kod, trajanja=None):
    """ui.py zove kad posao završi: status u povijesti + kalibracija procjene (stvarno / procijenjeno po koraku)."""
    import izvor as IZ
    h = os.path.join(IZ.mapa(cfg()), 'poslovi.json'); H = _jl(h, []) or []
    if H and H[0].get('status') == 'running':
        H[0]['status'] = 'done' if izlaz_kod == 0 else 'failed'; H[0]['kraj'] = datetime.datetime.now().isoformat(timespec='seconds')
        H[0]['trajanja'] = {k: round(v, 1) for k, v in (trajanja or {}).items()}
        _jw(h, H)
        if izlaz_kod == 0 and trajanja:
            tf = os.path.join(IZ.mapa(cfg()), 'tempo.json'); f = _jl(tf, {}) or {}
            for nm, sec in trajanja.items():
                est = (H[0].get('est') or {}).get(nm)
                if est and est >= 20 and sec >= 5:                      # kratke korake ne kalibriramo (sum)
                    r = min(5.0, max(0.3, sec / est)); f[nm] = round(0.5 * f[nm] + 0.5 * r, 3) if nm in f else round(r, 3)
            _jw(tf, f)
    try: ocisti_izvjestaje()
    except Exception: pass

ZADRZI_IZVJESTAJA = 10
def ocisti_izvjestaje(zadrzi=None, probno=False, mapa=None):
    """Izvjestaji s datumom u imenu (ocjene_SVE_2026-11-10_140007.xlsx ...): po vrsti ostaje najnovijih `zadrzi`.
    Datoteke bez datuma (npr. *_zadnje.json) se ne diraju. -> {'obrisano': n, 'mb': oslobodeno}"""
    import re, glob
    zadrzi = zadrzi or int(postavke().get('zadrzi_izvjestaja') or ZADRZI_IZVJESTAJA)
    mapa = mapa or os.path.join(HERE, 'izvjestaji')
    grupe = collections.defaultdict(list)
    for f in glob.glob(os.path.join(mapa, '*')):
        m = re.match(r'(.+?)_(\d{4}-\d{2}-\d{2}(?:_\d{6})?)(\..+)$', os.path.basename(f))
        if m and os.path.isfile(f): grupe[(m.group(1), m.group(3))].append((m.group(2), f))
    granica = float(postavke().get('izvjestaji_mb') or IZVJESTAJI_MB) * 1e6
    brisi, ostaju = [], []
    for fs in grupe.values():
        fs = sorted(fs, reverse=True)
        brisi += [f for _, f in fs[zadrzi:]]
        ostaju += [(d, f) for d, f in fs[1:zadrzi]]                     # najnoviji od svake vrste ostaje uvijek
    vel = lambda f: os.path.getsize(f) if os.path.exists(f) else 0
    ukupno = sum(vel(f) for f in glob.glob(os.path.join(mapa, '*')) if os.path.isfile(f)) - sum(vel(f) for f in brisi)
    for _, f in sorted(ostaju):                                        # najstariji prvi, dok ne padne ispod granice
        if ukupno <= granica: break
        brisi.append(f); ukupno -= vel(f)
    n = mb = 0
    for f in brisi:
        mb += vel(f) / 1e6; n += 1
        if not probno:
            try: os.remove(f)
            except OSError: n -= 1
    return {'obrisano': n, 'mb': round(mb, 1)}

IZVJESTAJI_MB = 250

VANJSKI_KORACI = {'ocjene': 'Write new database', 'reprezentacije': 'National teams', 'ugovori': 'Download contracts and loans',
                  'drzavljanstvo prema reprezentaciji': 'Nationality from national team', 'legende vracene na original': 'Legends restored',
                  'najbolja postava': 'Best starting line-ups', 'imena s dijakritikom': 'Names with accents', 'rucne izmjene reprezentacija': 'Apply national team edits'}

def povijest():
    """Poslovi iz aplikacije + kopiranja/vracanja igre + koraci napravljeni izvan aplikacije (iz baza_info.json nove baze)."""
    import izvor as IZ, spremanje as SP
    c = cfg(); H = _jl(os.path.join(IZ.mapa(c), 'poslovi.json'), []) or []
    try:
        izl = (_jl(projekt_put(c), {}) or {}).get('izlaz')
        info = _jl(os.path.join(izl, SP.OZNAKA), None) if izl else None
        if info and info.get('poslovi'):
            nrm = lambda p: os.path.normcase(os.path.normpath(p or ''))
            app = [h for h in H if not h.get('vrsta') and nrm(h.get('izlaz')) == nrm(izl)]
            if any(h.get('status') == 'running' for h in app): vani = []
            else:
                gr = max((h.get('kraj') or h.get('vrijeme') or '' for h in app), default='')
                vani = [p for p in info['poslovi'] if (p.get('vrijeme') or '') > gr]
            if vani:
                kor = []
                for p in vani:
                    n = VANJSKI_KORACI.get(p.get('korak'), p.get('korak') or '?')
                    if n not in kor: kor.append(n)
                H.append({'vrijeme': vani[0]['vrijeme'], 'kraj': vani[-1]['vrijeme'], 'vrsta': 'vanjski', 'opseg_opis': 'Changes made outside the app',
                          'opcije': [], 'izlaz': izl, 'koraci': kor, 'status': 'done'})
        g = postavke().get('igra_cilj'); u = SP.u_igri(g) if g else None
        if u and u.get('vrijeme'):                     # kopiranje izvan aplikacije (ili starija verzija): zapis iz mape igre
            t = datetime.datetime.fromisoformat(u['vrijeme'])
            blizu = lambda s: s and abs((datetime.datetime.fromisoformat(s) - t).total_seconds()) < 180
            if not any(h.get('u_igru') and (blizu(h.get('vrijeme')) or blizu(h.get('kraj'))) for h in H):
                H.append({'vrijeme': u['vrijeme'], 'kraj': u['vrijeme'], 'vrsta': 'kopija', 'opseg_opis': 'Copied into the game', 'opcije': [],
                          'izlaz': u.get('izvor'), 'u_igru': True, 'koraci': ['Copy into game'], 'status': 'done'})
        H.sort(key=lambda h: h.get('vrijeme') or '', reverse=True)
    except Exception:
        pass
    return H

def _hist_dodaj(vrsta, opis, izlaz, korak):
    """Kopiranje u igru / vracanje igre kao zapis u povijesti (status zavrsava zavrsi_posao)."""
    import izvor as IZ
    h = os.path.join(IZ.mapa(cfg()), 'poslovi.json'); H = _jl(h, []) or []
    H.insert(0, {'vrijeme': datetime.datetime.now().isoformat(timespec='seconds'), 'vrsta': vrsta, 'opseg_opis': opis, 'opcije': [],
                 'izlaz': izlaz, 'u_igru': vrsta == 'kopija', 'koraci': [korak], 'status': 'running'})
    _jw(h, H[:100])

def repr_sastav(tid):
    """Trenutni sastav reprezentacije u novoj bazi (ili tvojoj, ako nove nema) + rucne izmjene, za uredivanje."""
    import repr_rucno as RR, struct as st
    tid = int(tid); pr = projekt(); c = cfg()
    raw = RR.trenutni(pr['izlaz']) if pr['izlaz_postoji'] else None
    db, countries, teams, national = RR.kontekst()
    if tid not in national: return None
    if raw is None: raw = db['PlayerAssignment.bin']
    recs = sorted([r for r in RR._recs(raw) if r[2] == tid], key=RR._slot)
    byid = {x['id']: x for x in katalog()['igraci']}
    e = RR.ucitaj(c).get(str(tid)) or {}
    OS = (_jl(os.path.join(pr['izlaz'], '_rucno', 'osnova.json'), {}) or {}).get(str(tid)) or {}
    osn = {p for p, n in OS.get('sastav') or []} or {r[1] for r in recs}
    ig = lambda i: {k: (byid.get(i) or {}).get(k) for k in ('ime', 'poz', 'ovr', 'ovr0', 'klub', 'drz', 'dob')}
    return {'id': tid, 'tim': teams[tid], 'nova_baza': pr['izlaz_postoji'], 'min': RR.MINS, 'max': RR.MAXS,
            'sastav': [dict(ig(r[1]), id=r[1], broj=RR._broj(r), dodan=r[1] not in osn) for r in recs],
            'maknuti': [dict(ig(i), id=i) for i in e.get('makni') or [] if i in osn],
            'rucno': {'dodaj': e.get('dodaj') or [], 'makni': e.get('makni') or [], 'brojevi': e.get('brojevi') or {}}}

def _hist_makni():
    import izvor as IZ
    h = os.path.join(IZ.mapa(cfg()), 'poslovi.json'); H = _jl(h, []) or []
    if H and H[0].get('vrsta') and H[0].get('status') == 'running': _jw(h, H[1:])

# ------------------------------------------------------------------ podaci o ocjenama i verzija
def podaci_stanje():
    """Starost EA ocjena i formule + procjena osvjezavanja."""
    import glob, model_ea27 as ME
    ea = os.path.join(HERE, 'cache', 'ea_fc27.json')
    out = {'ea_datum': None, 'ea_dana': None, 'ea_n': None, 'model': None}
    if os.path.exists(ea):
        dz = os.path.join(HERE, 'cache', 'ea_datum.txt')
        try: d0 = datetime.date.fromisoformat(open(dz).read().strip())
        except (OSError, ValueError): d0 = None
        if d0 is None:                                   # nema zapisa: datum formule, inace datum datoteke
            try: d0 = datetime.date.fromisoformat(ME.load()['info']['datum'])
            except Exception: d0 = datetime.date.fromtimestamp(os.path.getmtime(ea))
        out['ea_datum'] = d0.isoformat(); out['ea_dana'] = (datetime.date.today() - d0).days
    try:
        I = ME.load()['info']
        out['model'] = {'datum': I['datum'], 'n': I['n'], 'greska': round(I['greska'], 2), 'unutar3': round(I['unutar3'] * 100), 'lige': len(I['lige']), 'ea': I.get('ea')}
        out['ea_n'] = I['n']
    except Exception as e:
        out['model_greska'] = str(e)
    now = time.time(); stare = 0; kodovi = []
    try:
        import osvjezi_podatke as OP
        kodovi = OP.kodovi()
        for c in kodovi:
            fs = glob.glob(os.path.join(HERE, 'cache', 'tm_%s_*.json' % c))
            if not fs or now - max(os.path.getmtime(f) for f in fs) > 7 * 86400: stare += 1
    except Exception: pass
    out['tm_lige'] = len(kodovi); out['tm_lige_stare'] = stare
    out['procjena_min'] = round(25 + 0.7 * stare + 3)
    out['star'] = out['ea_dana'] is None or out['ea_dana'] > 60
    return out

def osvjezi_podatke(start_job, py):
    import datetime as dt
    part = os.path.join(HERE, 'cache', 'ea_fc27.json.part')
    if os.path.exists(part): os.remove(part)           # svjeze ocjene, ne nastavak stare
    os.environ['SU_KAL_DATUM'] = dt.date.today().isoformat()
    k = [('Download EA ratings', py('ea27.py')), ('Download Transfermarkt leagues', py('osvjezi_podatke.py') + ['--lige']),
         ('Learn the formula', py('osvjezi_podatke.py') + ['--ucenje'])]
    return start_job('Update ratings data', 'podaci', None, k)

def verzija(provjeri):
    import version as V, urllib.request
    out = {'verzija': V.VERSION}
    if not provjeri: return out
    url = (postavke().get('update_url') or V.DEFAULT_UPDATE_URL or '').strip()
    if not url: out['url_nije_postavljen'] = True; return out
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'SquadUpdater/' + V.VERSION}), timeout=15) as r:
            d = json.load(r)
        num = lambda v: tuple(int(x) for x in str(v).split('.') if x.isdigit())
        out['zadnja'] = d.get('version'); out['url'] = d.get('url'); out['biljeske'] = d.get('notes')
        out['nova'] = bool(d.get('version')) and num(d['version']) > num(V.VERSION)
    except Exception as e:
        out['greska'] = 'Could not check for updates (%s).' % e
    return out

# ------------------------------------------------------------------ HTTP
def get(path, q):
    g = lambda k, d=None: q.get(k, [d])[0]
    flat = {k: v[0] for k, v in q.items()}
    if path == '/api/v2/projekt': return 200, projekt()
    if path == '/api/v2/igraci': return 200, stranica(flat)
    if path == '/api/v2/opcije': return 200, katalog()['opcije'] or {}
    if path == '/api/v2/igrac': return 200, igrac(g('id'))
    if path == '/api/v2/objasni': return 200, objasnjenje(g('id'))
    if path == '/api/v2/formula': return 200, formula_stanje()
    if path == '/api/v2/povijest': return 200, povijest()
    if path == '/api/v2/pregled': return 200, pregled()
    if path == '/api/v2/reprezentacije': return 200, reprezentacije_sve()
    if path == '/api/v2/repr_sastav':
        r = repr_sastav(g('id'))
        return (200, r) if r else (404, {'greska': 'This is not a national team.'})
    if path == '/api/v2/statistika': return 200, statistika()
    if path == '/api/v2/izvjestaj':
        return 200, izvjestaj_xlsx(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', \
               {'Content-Disposition': 'attachment; filename="squad_updater_changes.xlsx"'}
    if path == '/api/v2/provjera':
        import izvor as IZ
        d = _jl(os.path.join(IZ.mapa(cfg()), 'za_provjeru.json'), {}) or {}
        byid = {x['id']: x for x in katalog()['igraci']}
        return 200, [dict(v, id=int(k), klub_baza=(byid.get(int(k)) or {}).get('klub'), poz=(byid.get(int(k)) or {}).get('poz'),
                          drz=(byid.get(int(k)) or {}).get('drz')) for k, v in sorted(d.items(), key=lambda kv: -kv[1].get('db_ovr', 0))]
    if path == '/api/v2/postavke': return 200, postavke()
    if path == '/api/v2/podaci': return 200, podaci_stanje()
    if path == '/api/v2/verzija': return 200, verzija(g('provjeri') == '1')
    if path == '/api/v2/ping': AA_PING['t'] = time.time(); return 200, {'app': 'squad-updater', 'version': verzija(False)['verzija']}
    if path == '/api/v2/zatvaram': AA_PING['zatvara'] = time.time(); return 200, {'ok': True}
    if path == '/api/v2/izvoz':
        fmt = g('format', 'csv'); data = izvoz(flat, fmt)
        return 200, data, ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if fmt == 'xlsx' else 'text/csv; charset=utf-8'), \
            {'Content-Disposition': 'attachment; filename="players.%s"' % ('xlsx' if fmt == 'xlsx' else 'csv')}
    return None

# ------------------------------------------------------------------ korisnicka formula (klizaci)
_FR = {'kljuc': None}
FLOCK = threading.Lock()

def formula_stanje():
    import model_ea27 as ME
    f = ME.formula(postavke().get('formula'))
    return {'formula': f, 'zadano': ME.ZADANO, 'granice': ME.GRANICE, 'aktivna': ME.formula_aktivna(f)}

def formula_spremi(b):
    import model_ea27 as ME
    d = postavke()
    if b.get('reset'): d.pop('formula', None)
    else:
        f = ME.formula(b.get('formula') or {})
        d['formula'] = {k: v for k, v in f.items() if abs(v - ME.ZADANO[k]) > 1e-9}        # pamti samo promjene
        if not d['formula']: d.pop('formula')
    _jw(POSTAVKE, d)
    return formula_stanje()

def _formula_rastav():
    """Rastav (Shapley) za sve uparene igrace iz baze - racuna se jednom (~10 s), pa klizaci rade odmah."""
    import model_ea27 as ME, objasni as OB, numpy as np
    I = OB._indeks(); kat = katalog()['igraci']
    kljuc = (I['kljuc'], KAT['mtime'])
    with FLOCK:
        if _FR['kljuc'] != kljuc:
            potreban = {x['tm']: x for x in kat if x.get('tm')}
            X, igr = [], []
            for code, pl in I['lige'].items():
                cm = lg = None
                for q in pl:
                    x = potreban.get(q.get('tm_id'))
                    if x is None or not (q.get('value') and q.get('age')): continue
                    if cm is None: cm, lg = ME.strengths(pl)
                    q = dict(q); q['_trend'], q['_peak'] = ME.hist_feats(q['tm_id'], datetime.date.today(), q['value'])
                    X.append(ME.x(q, cm, lg, code)); igr.append((x['id'], x['ime'], x.get('klub'), x.get('liga'), x.get('poz')))
                    potreban.pop(q['tm_id'], None)
            X = np.array(X, float) if X else np.zeros((0, 8))
            osn, phi, _ = ME.shapley(X, OB.referenca()) if len(X) else (np.zeros(0), np.zeros((0, 6)), None)
            _FR.update(kljuc=kljuc, osn=osn, phi=phi, grp=X[:, 2] if len(X) else np.zeros(0), igr=igr)
    return _FR

def formula_pregled(b):
    """Usporedba korisnicke formule sa zadanom na igracima iz baze: najbolji, najveci pomaci, lige, raspodjela."""
    import model_ea27 as ME, numpy as np
    R = _formula_rastav()
    if not R['igr']: return {'n': 0}
    f = ME.formula(b.get('formula') or {}); sk = float(b['skala']) if b.get('skala') is not None else ME.SKALA
    ocj = lambda v: np.clip(np.round([ME.to_game(float(t), sk) for t in v]), 40, 99).astype(int)
    a = ocj(ME.primijeni(R['osn'], R['phi'], R['grp'], ME.ZADANO)); n_ = ocj(ME.primijeni(R['osn'], R['phi'], R['grp'], f))
    d = n_ - a; I = R['igr']
    red = lambda i: {'id': I[i][0], 'ime': I[i][1], 'klub': I[i][2], 'poz': I[i][4], 'prije': int(a[i]), 'sada': int(n_[i])}
    lige = collections.defaultdict(list)
    for i, x in enumerate(I): lige[x[3]].append(i)
    L = sorted(lige.items(), key=lambda kv: -len(kv[1]))[:14]
    return {'n': len(I), 'prosjek': round(float(d.mean()), 2), 'gore': int((d > 0).sum()), 'dolje': int((d < 0).sum()),
            'raspodjela': {str(k): int((np.clip(d, -6, 6) == k).sum()) for k in range(-6, 7)},
            'najbolji': [red(i) for i in np.argsort(-n_, kind='stable')[:12]],
            'gore_top': [red(i) for i in np.argsort(-d, kind='stable')[:6] if d[i] > 0],
            'dolje_top': [red(i) for i in np.argsort(d, kind='stable')[:6] if d[i] < 0],
            'lige': [{'liga': k, 'n': len(v), 'prije': round(float(a[v].mean()), 1), 'sada': round(float(n_[v].mean()), 1)} for k, v in L]}

def post(path, b, start_job, py, job_active):
    if path == '/api/v2/formula': return 200, formula_spremi(b)
    if path == '/api/v2/formula/pregled': return 200, formula_pregled(b)
    if path == '/api/v2/procjena': return 200, procjena(b.get('opseg') or {'tip': 'sve'}, b.get('opcije') or [])
    if path == '/api/v2/posao':
        if job_active(): return 409, {'greska': 'Another job is running. Wait for it or stop it.'}
        ok = posao(b, start_job, py)
        if ok:                                           # zapamti zadnji izbor (forma se sljedeci put sama popuni)
            d = postavke(); d['posao_zadano'] = {'opcije': [o for o in b.get('opcije') or [] if o in OPCIJE], 'od': b.get('od') or 'original',
                                                 'u_igru': bool(b.get('u_igru')), 'skala': b.get('skala')}
            if 'reset_edit' in b: d['edit_reset'] = bool(b['reset_edit'])
            _jw(POSTAVKE, d)
        return 200, {'ok': ok}
    if path == '/api/v2/u_igru':
        if job_active(): return 409, {'greska': 'Another job is running. Wait for it or stop it.'}
        g = postavke().get('igra_cilj'); pr = projekt()
        if not g: return 400, {'greska': 'Choose the game folder in Settings first.'}
        if not pr['izlaz_postoji']: return 400, {'greska': 'There is no new database yet. Run a job first.'}
        if igra_radi(): return 409, {'greska': 'The game is running. Close it, then copy.'}
        _hist_dodaj('kopija', 'Copied into the game', pr['izlaz'], 'Copy into game')      # prije starta: posao zna zavrsiti prije upisa
        ok = start_job('Copy into game', 'posao', None, [('Copy into game', py('spremanje.py') + ['--izlaz=' + pr['izlaz'], '--u-igru=' + g] + _reset_arg(b))])
        if not ok: _hist_makni()
        return 200, {'ok': ok}
    if path == '/api/v2/repr_uredi':
        if job_active(): return 409, {'greska': 'Another job is running. Wait for it or stop it.'}
        import repr_rucno as RR
        pr = projekt()
        if not pr['izlaz_postoji']: return 400, {'greska': 'There is no new database yet. Run an update first.'}
        tid = int(b['id']); c = cfg(); R = RR.ucitaj(c)
        cl = lambda v: sorted({int(i) for i in v or []})
        R[str(tid)] = {'dodaj': cl(b.get('dodaj')), 'makni': cl(b.get('makni')),
                       'brojevi': {str(int(k)): int(v) for k, v in (b.get('brojevi') or {}).items() if 1 <= int(v) <= 99}}
        RR.spremi(c, R)
        _hist_dodaj('repr', 'National team edited: %s' % (b.get('tim') or tid), pr['izlaz'], 'Apply national team edits')
        ok = start_job('Edit national team', 'posao', None, [('Apply national team edits', py('repr_rucno.py') + ['--izlaz=' + pr['izlaz']]),
                                                             ('Update player list', py('katalog.py') + ['--izlaz=' + pr['izlaz']])])
        if not ok: _hist_makni()
        return 200, {'ok': ok}
    if path == '/api/v2/vrati_igru':
        if job_active(): return 409, {'greska': 'Another job is running. Wait for it or stop it.'}
        if igra_radi(): return 409, {'greska': 'The game is running. Close it first.'}
        import spremanje as SP
        d = postavke(); g = d.get('igra_cilj')
        if not g: return 400, {'greska': 'Choose the game folder in Settings first.'}
        sv = SP.save_mapa(d.get('igra_dir'), d.get('save_dir'))
        _hist_dodaj('vracanje', 'Game restored', g, 'Restore the game')
        ok = start_job('Restore the game', 'posao', None, [('Restore the game', py('spremanje.py') + ['--vrati-igru=' + g] + (['--save=' + sv] if sv else []))])
        if not ok: _hist_makni()
        return 200, {'ok': ok}
    if path == '/api/v2/provjera':
        import tm_igrac as TI, izvor as IZ
        f = os.path.join(IZ.mapa(cfg()), 'za_provjeru.json'); d = _jl(f, {}) or {}
        k = str(b['id']); e = d.pop(k, None)
        if e is None: return 404, {'greska': 'This player is no longer on the list.'}
        if b.get('akcija') == 'odobri':
            if e.get('unos'): R = TI.rucne(); R[k] = dict(e['unos'], izvor='rucno'); TI.spremi_rucne(R)
            elif e.get('r'): TI.dodaj(int(k), e['r'], 'rucno')
        else:
            zakljucaj(int(k), True)
        _jw(f, d); KAT.update(mtime=None)
        return 200, {'ok': True, 'ostalo': len(d)}
    if path == '/api/v2/zakljucaj': zakljucaj(b['id'], bool(b.get('da', True))); return 200, {'ok': True}
    if path == '/api/v2/ponisti':
        if job_active(): return 409, {'greska': 'Wait for the running job to finish.'}
        ponisti(b['id']); return 200, {'ok': True}
    if path == '/api/v2/osvjezi_podatke':
        if job_active(): return 409, {'greska': 'Another job is running. Wait for it or stop it.'}
        return 200, {'ok': osvjezi_podatke(start_job, py)}
    if path == '/api/v2/postavke':
        if b.get('igra_dir') and not os.path.isdir(os.path.join(b['igra_dir'], 'Data')): return 400, {'greska': 'That folder has no Data subfolder - choose the PES 2021 folder.'}
        if b.get('sider_ini') and not os.path.isfile(b['sider_ini']): return 400, {'greska': 'sider.ini not found.'}
        d = postavke(); d.update({k: v for k, v in b.items() if k in ('jezik', 'igra_cilj', 'tm_razmak', 'igra_dir', 'sider_ini', 'update_url', 'posao_zadano', 'edit_reset', 'save_dir')}); _jw(POSTAVKE, d)
        if 'igra_dir' in b or 'sider_ini' in b:
            import provjera_faca as PF
            if d.get('sider_ini'): PF.SIDER_INI = d['sider_ini']; PF.SIDER = os.path.dirname(d['sider_ini'])
            if d.get('igra_dir'): PF.GAME = d['igra_dir']
            if cfg()['tip'] == 'igra' and globals().get('RELOAD'): KAT.update(mtime=None); RELOAD()
        return 200, d
    if path == '/api/v2/izlaz':
        import izvor as IZ
        pj = _jl(projekt_put(), {}) or {}; pj['izlaz'] = (b.get('izlaz') or '').strip().strip('"'); _jw(projekt_put(), pj); return 200, projekt()
    if path == '/api/v2/katalog':
        if job_active(): return 409, {'greska': 'Wait for the running job to finish.'}
        pr = projekt()
        start_job('Update player list', 'katalog', py('katalog.py') + (['--izlaz=' + pr['izlaz']] if pr['izlaz_postoji'] else []))
        return 200, {'ok': True}
    if path == '/api/v2/otvori':
        p = b.get('put') or projekt()['izlaz']
        if os.path.isdir(p): os.startfile(p); return 200, {'ok': True}
        return 404, {'greska': 'Folder does not exist yet.'}
    return None
