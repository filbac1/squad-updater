# -*- coding: utf-8 -*-
"""
OCJENE FL27 - lokalno web sucelje (bez AI-ja, samo Python standardna biblioteka + postojece skripte).

    python ui.py          (ili pokreni_ui.bat)  -> otvori http://127.0.0.1:8765

Kartice:
  Lige                 - lige iz baze + TM kodovi (upis koda za novu ligu), izracun -> CSV za PES2020 Editor + Excel
  Pojedinacni igraci   - trazi bilo kojeg igraca na Transfermarktu (ime ili link), overall po formuli,
                         povezi s igracem u bazi i dodaj na rucni popis (ima prednost pred ligama)
  Igraci bez kluba     - skupno trazenje igraca iz baze koji nemaju klub (nastavlja gdje je stao)
  Reprezentacije       - zadnji poziv s Transfermarkta: prijedlog po reprezentaciji, upis u igru, povratak na original
  Ugovori              - ugovori i posudbe s Transfermarkta (istek po godinama, popis posudbi)
  Ciscenje             - umirovljeni i duplikati bez kluba za brisanje, "zadrzi" po igracu
  Face-ovi             - igraci bez pravog face-a po TM vrijednosti, pokrivenost po ligama
  Formula              - nove EA FC ocjene, ponovno ucenje formule, ozljede, izvoz baze
"""
import time, os, sys, json, glob, shutil, threading, subprocess, collections, webbrowser, urllib.parse, datetime, re
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, 'izvjestaji')
DESKTOP = os.path.join(os.path.expanduser('~'), 'Desktop')
EXTRA = os.path.join(HERE, 'tm_kodovi.json')
PORT = 8765
sys.path.insert(0, HERE)
import app_api as AA

def py(script):
    """Naredba za pokretanje skripte (u zapakiranoj aplikaciji: isti .exe s --skripta)."""
    return [script]                      # _spawn doda --skripta u zapakiranoj aplikaciji


# ------------------------------------------------------------------ baza (ucitava se jednom, u pozadini)
STATE = {'lige': None, 'greska': None, 'baza': None}
AA.STATE = STATE
DBLOCK = threading.Lock()

def load_leagues():
    try:
        import ocjene as OC, fl27db as D, model_ea27 as ME, tm_igrac as TI, izvor as IZ
        with DBLOCK:
            IZ.use(IZ.aktivna()); TI._DB = None
            B = TI.baza()
        P = B['P']
        cnt = collections.Counter(OC.db_league_key(p) for p in P if OC.db_league_key(p))
        tmname = {}
        for code, f in ME.latest_leagues().items():
            try: tmname[code] = json.load(open(f, encoding='utf-8')).get('league') or ''
            except Exception: pass
        out = []
        for k, n in cnt.items():
            tm = OC.TM_KOD.get(k, '')
            nm = '%s, ostali klubovi' % k[7:] if k.startswith('OSTALI:') else D.PF.nice_league(k)
            if tmname.get(tm) and not tmname[tm].upper().startswith(tm):
                nm = '%s (%s)' % (tmname[tm], k[7:] if k.startswith('OSTALI:') else nm)
            out.append({'key': k, 'naziv': nm, 'n': n, 'tm': tm})
        out.sort(key=lambda x: (x['key'].startswith('OSTALI:'), -x['n']))
        STATE.update(lige=out, ukupno=len(P), bez_kluba=sum(1 for p in P if not p['club_id']),
                     baza=IZ.opis(IZ.CFG), tip=IZ.CFG['tip'], greska=None)
        import katalog as KT
        if IZ.CFG['tip'] != 'csv' and not os.path.exists(KT.datoteka(IZ.CFG)) and not JOB.get('aktivan'):
            pr = AA.projekt()
            start_job('Build player list', 'katalog', py('katalog.py') + (['--izlaz=' + pr['izlaz']] if pr['izlaz_postoji'] else []))
    except BaseException as e:               # i sys.exit (baza nije nadjena) -> poruka u aplikaciji
        STATE['greska'] = str(e) if isinstance(e, SystemExit) else '%s: %s' % (type(e).__name__, e)

def reload_db():
    STATE.update(lige=None, greska=None, baza=None)
    threading.Thread(target=load_leagues, daemon=True).start()

AA.RELOAD = lambda: reload_db()

def odaberi(vrsta):
    """Windows dijalog za odabir mape/datoteke (server je lokalan, pa se otvara na tvom racunalu)."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
    try:
        if vrsta == 'mapa': p = filedialog.askdirectory(title='Odaberi mapu baze (s Player.bin negdje unutra)')
        elif vrsta == 'folder': p = filedialog.askdirectory(title='Choose a folder')
        elif vrsta == 'ini': p = filedialog.askopenfilename(title='Choose sider.ini', filetypes=[('sider.ini', '*.ini'), ('All', '*.*')])
        elif vrsta == 'cpk': p = filedialog.askopenfilename(title='Odaberi CPK datoteku', filetypes=[('CPK', '*.cpk'), ('Sve', '*.*')])
        else: p = filedialog.askopenfilename(title='Odaberi CSV iz PES2020 Editora', filetypes=[('CSV', '*.csv'), ('Sve', '*.*')])
    finally:
        root.destroy()
    return os.path.normpath(p) if p else ''

def katalog():
    f = os.path.join(HERE, 'cache', 'katalog_liga.json')
    if not os.path.exists(f): return None
    return [r for r in json.load(open(f, encoding='utf-8')) if 'Tier' in (r.get('rang') or '')]

def dodatne_put():
    import izvor as IZ
    return os.path.join(IZ.mapa(IZ.aktivna()), 'dodatne_lige.json')

def dodatne():
    p = dodatne_put()
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else []

IZLAZ_BIN = os.path.join(HERE, 'izlaz', 'common', 'etc', 'pesdb', 'Player.bin')
POV = os.path.join(HERE, 'izlaz_povijest')

def verzije():
    """Player.bin u igri + prethodne verzije + original iz igre."""
    out = []
    if os.path.isfile(IZLAZ_BIN):
        out.append({'id': 'trenutna', 'naziv': 'Trenutno u igri', 'vrijeme': datetime.datetime.fromtimestamp(os.path.getmtime(IZLAZ_BIN)).strftime('%d.%m.%Y. %H:%M')})
    for f in sorted(glob.glob(os.path.join(POV, 'Player_*.bin')), reverse=True):
        out.append({'id': os.path.basename(f), 'naziv': 'Prethodna verzija', 'vrijeme': datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%d.%m.%Y. %H:%M')})
    for f in sorted(glob.glob(os.path.join(HERE, 'backup_original_*', 'common', 'etc', 'pesdb', 'Player.bin'))):
        out.append({'id': 'bk:' + os.path.relpath(f, HERE), 'naziv': 'Original iz igre (prije ocjena)', 'vrijeme': datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%d.%m.%Y. %H:%M')})
    for f in sorted(glob.glob(os.path.join(HERE, 'backup_original_*', 'Player.bin.*'))):
        out.append({'id': 'bk:' + os.path.relpath(f, HERE), 'naziv': 'Spremljena verzija (' + os.path.basename(f).split('.', 2)[-1] + ')', 'vrijeme': datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%d.%m.%Y. %H:%M')})
    return {'verzije': out, 'u_igri': any(os.path.normcase(os.path.abspath(r)) == os.path.normcase(os.path.abspath(os.path.join(HERE, 'izlaz')))
                                          for r in __import__('fl27db').PF.sider_roots())}

def vrati(vid):
    import shutil
    if vid.startswith('bk:'):
        src = os.path.abspath(os.path.join(HERE, vid[3:]))
        if not src.startswith(HERE) or not os.path.isfile(src): raise FileNotFoundError(vid)
    else:
        src = os.path.join(POV, os.path.basename(vid))
        if not os.path.isfile(src): raise FileNotFoundError(vid)
    os.makedirs(POV, exist_ok=True)
    if os.path.isfile(IZLAZ_BIN):
        shutil.copy2(IZLAZ_BIN, os.path.join(POV, 'Player_%s.bin' % datetime.datetime.fromtimestamp(os.path.getmtime(IZLAZ_BIN)).strftime('%Y-%m-%d_%H%M%S')))
    os.makedirs(os.path.dirname(IZLAZ_BIN), exist_ok=True)
    shutil.copyfile(src, IZLAZ_BIN)
    return src

def zp_put():
    import izvor as IZ
    return os.path.join(IZ.mapa(IZ.aktivna()), 'za_provjeru.json')

def za_provjeru():
    p = zp_put()
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}

def db():
    import tm_igrac as TI
    with DBLOCK:
        return TI.baza()

# ------------------------------------------------------------------ pokretanje skripti
JOB = {'proc': None, 'log': collections.deque(maxlen=4000), 'naziv': '', 'tip': '', 'start': None, 'kraj': None,
       'izlaz': None, 'rezultat': {}}
LOCK = threading.Lock()

def _spawn(args):
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1', SU_DOGADAJI='1')
    if not getattr(sys, 'frozen', False) and args and args[0].endswith('.py') and not os.path.isabs(args[0]): args = [os.path.join(HERE, args[0])] + args[1:]
    if getattr(sys, 'frozen', False) and args and args[0].endswith('.py'): args = ['--skripta'] + args
    return subprocess.Popen(([sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, '-u']) + args, cwd=HERE, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                            errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

def start_job(naziv, tip, args, koraci=None):
    """args = jedna naredba; koraci = [(opis, args), ...] - niz naredbi, staje na prvoj gresci."""
    with LOCK:
        if JOB.get('aktivan'):
            return False
        koraci = koraci or [(naziv, args)]
        JOB['log'].clear(); JOB['log'].append('> ' + ' '.join(koraci[0][1]))
        p = _spawn(koraci[0][1])
        JOB.update(proc=p, naziv=naziv, tip=tip, start=datetime.datetime.now().isoformat(timespec='seconds'), kraj=None,
                   izlaz=None, rezultat={'korak': [1, len(koraci), koraci[0][0]]} if len(koraci) > 1 else {}, prekid=False, aktivan=True,
                   koraci=[k[0] for k in koraci])
        threading.Thread(target=_pipeline, args=(p, koraci), daemon=True).start()
        return True

def _pipeline(p, koraci):
    JOB['trajanja'] = {}; t_k = time.time()
    for k, (opis, args) in enumerate(koraci):
        if k:
            if JOB['izlaz'] != 0 or JOB.get('prekid'): break
            JOB['log'].append(''); JOB['log'].append('> ' + ' '.join(args))
            JOB['rezultat'].pop('napredak', None); JOB['rezultat']['korak'] = [k + 1, len(koraci), opis]
            p = _spawn(args); JOB['proc'] = p; JOB['izlaz'] = None
        _reader(p, kraj=k == len(koraci) - 1)
        JOB['trajanja'][opis] = time.time() - t_k; t_k = time.time()
    JOB['kraj'] = datetime.datetime.now().isoformat(timespec='seconds'); JOB['aktivan'] = False
    if JOB.get('tip') == 'podaci' and JOB.get('izlaz') == 0:          # nova formula / EA podaci -> ponovno ucitaj
        try:
            import model_ea27 as ME
            ME._M = None; ME._EA = None
        except Exception: pass
    if JOB.get('tip') == 'posao':
        try: AA.zavrsi_posao(JOB['izlaz'] if not JOB.get('prekid') else -1, JOB.get('trajanja'))
        except Exception: pass

def _napredak(i, n, T):
    """Spremi napredak koraka i procjenu preostalog vremena (iz brzine od prvog javljanja u ovom koraku)."""
    now = time.time(); R = JOB['rezultat']; R['napredak'] = [i, n]
    if T.get('n') != n or i < T.get('i0', 0): T.update(n=n, i0=i, t0=now)          # novi brojac (npr. profili -> povijest)
    di, dt = i - T['i0'], now - T['t0']
    R['eta'] = round(dt / di * (n - i)) if di > 0 and dt > 3 else None

def _reader(p, kraj=True):
    import lang as LG
    T = {}; JOB['rezultat'].pop('eta', None)
    for line in p.stdout:
        line = line.rstrip('\n')
        if line.startswith('@@'):                                       # strukturirani dogadaj (napredak.py)
            try: d = json.loads(line[2:])
            except ValueError: d = {}
            if d.get('n'): _napredak(int(d['n'][0]), int(d['n'][1]), T)
            for k, v in (d.get('rez') or {}).items(): JOB['rezultat'][k] = os.path.basename(str(v))
            T['dog'] = True
            continue
        JOB['log'].append(LG.tr(line))      # uzorci ispod citaju izvornu liniju (stare skripte bez dogadaja)
        m = re.match(r'Izvjestaj: (.+\.xlsx)', line)
        if m: JOB['rezultat']['xlsx'] = os.path.basename(m.group(1).strip())
        m = re.match(r'CSV za editor \(.*\): (.+\.csv)', line)
        if m: JOB['rezultat']['csv'] = os.path.basename(m.group(1).strip())
        m = re.match(r'Izvezeno \d+ igraca -> (.+\.csv)', line)
        if m: JOB['rezultat']['csv'] = os.path.basename(m.group(1).strip())
        if T.get('dog'): continue                                       # skripta salje dogadaje -> tekst se ne parsira
        m = re.match(r'\[(\d+)/(\d+)\]', line) or re.match(r'\s+(?:profili|povijest) (\d+)/(\d+)', line)
        if m: _napredak(int(m.group(1)), int(m.group(2)), T)
    JOB['izlaz'] = p.wait()

# ------------------------------------------------------------------ rezultati
def summary(name):
    from openpyxl import load_workbook
    wb = load_workbook(safe_out(name), read_only=True)
    SN = wb.sheetnames
    rows = list(wb[SN[1]].iter_rows(min_row=2, values_only=True))
    lige = collections.defaultdict(list)
    for r in rows: lige[r[4]].append(r)
    L = []
    for lg, rs in sorted(lige.items(), key=lambda x: -len(x[1])):
        d = [r[10] - r[8] for r in rs]
        L.append({'liga': lg, 'n': len(rs), 'prosjek': round(sum(d) / len(d), 2),
                  'pad5': sum(1 for x in d if x <= -5), 'rast5': sum(1 for x in d if x >= 5)})
    def pl(r): return {'ime': r[1], 'klub': r[2], 'poz': r[5], 'dob': r[6], 'vrijednost': r[7], 'staro': r[8], 'novo': r[10]}
    srt = sorted(rows, key=lambda r: r[10] - r[8])
    nep = sum(1 for _ in wb[[n for n in SN if n.startswith('Unmatched') or n.startswith('Neupareni')][0]].iter_rows(min_row=2)) if any(n.startswith(('Unmatched', 'Neupareni')) for n in SN) else 0
    pod = sum(1 for r in wb[[n for n in SN if n.startswith(('Data (TM)', 'Podaci'))][0]].iter_rows(min_row=2, values_only=True) if r[4]) if any(n.startswith(('Data (TM)', 'Podaci')) for n in SN) else 0
    return {'ukupno': len(rows), 'tocno': sum(1 for r in rows if r[10] == r[9]), 'neupareno': nep, 'podaci': pod, 'lige': L,
            'padovi': [pl(r) for r in srt[:12]], 'rast': [pl(r) for r in srt[::-1][:12]],
            'najbolji': [pl(r) for r in sorted(rows, key=lambda r: -r[10])[:15]]}

def safe_out(name):
    p = os.path.abspath(os.path.join(OUTDIR, os.path.basename(name)))
    if not p.startswith(os.path.abspath(OUTDIR)) or not os.path.isfile(p): raise FileNotFoundError(name)
    return p

def files():
    out = []
    for f in sorted(glob.glob(os.path.join(OUTDIR, '*')), key=os.path.getmtime, reverse=True)[:30]:
        if f.endswith(('.csv', '.xlsx')):
            out.append({'ime': os.path.basename(f), 'mb': round(os.path.getsize(f) / 1e6, 1),
                        'vrijeme': datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%d.%m. %H:%M')})
    return out

def model_info():
    try:
        import model_ea27 as ME
        return ME.load()['info'] | {'skala': ME.SKALA, 'prag': ME.SKALA_PRAG, 'baza_nagib': ME.BAZA_NAGIB}
    except Exception as e:
        return {'nema': str(e)}

def rucni_popis(skala):
    import tm_igrac as TI, model_ea27 as ME
    B = db(); out = []
    for sid, e in TI.rucne().items():
        p = B['by_id'].get(int(sid))
        out.append({'db_id': int(sid), 'db_ime': p['name'] if p else '(nema u bazi)', 'db_klub': (p['club'] or 'bez kluba') if p else '',
                    'poz': p['pos'] if p else '', 'staro': p['ovr'] if p else None,
                    'cilj': int(max(40, min(99, round(ME.to_game(e['ea_pred'], skala))))),
                    'tm_ime': e['tm_ime'], 'tm_id': e['tm_id'], 'klub': e.get('klub'), 'vrijednost': e.get('vrijednost'),
                    'godine': e.get('godine'), 'izvor': e.get('izvor'), 'datum': e.get('datum'), 'kontekst': e.get('kontekst')})
    out.sort(key=lambda x: (x['izvor'] != 'rucno', -(x['cilj'] or 0)))
    return out

# ------------------------------------------------------------------ ugovori, reprezentacije, ciscenje, face-ovi, ozljede
IZLAZ_PA = os.path.join(HERE, 'izlaz', 'common', 'etc', 'pesdb', 'PlayerAssignment.bin')

def _mapa():
    import izvor as IZ
    return IZ.mapa(IZ.aktivna())

def _jl(p, d=None):
    try: return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError): return d

def _vr(p):
    return datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%d.%m.%Y. %H:%M') if os.path.exists(p) else None

def repr_stanje():
    return {'izvjestaj': _jl(os.path.join(OUTDIR, 'reprezentacije_zadnje.json')), 'u_igri': _vr(IZLAZ_PA)}

def repr_original():
    if not os.path.isfile(IZLAZ_PA): return False
    os.makedirs(POV, exist_ok=True)
    shutil.move(IZLAZ_PA, os.path.join(POV, 'PlayerAssignment_%s.bin' % datetime.datetime.fromtimestamp(os.path.getmtime(IZLAZ_PA)).strftime('%Y-%m-%d_%H%M%S')))
    return True

def ugovori_stanje():
    import ugovori as UG
    tm_ids = _jl(os.path.join(_mapa(), 'tm_ids.json'), [])
    if not os.path.exists(UG.F_IGR): return {'nema': True, 'igraca': len(tm_ids)}
    B = db(); by = B['by_id']; byidx = {p['idx']: p for p in B['P']}
    klub = {p['club_id']: p['club'] for p in B['P'] if p['club_id']}
    ch, op, st = UG.promjene([(by[d], t) for d, t, o in tm_ids if d in by and t])
    god = collections.Counter(c['_ugovor'] // 10000 for c in ch.values() if c.get('_ugovor'))
    pos = []
    for i, c in ch.items():
        if '_vlasnik' not in c or i not in byidx: continue
        p = byidx[i]
        pos.append({'ime': p['name'], 'id': p['id'], 'klub': p['club'], 'vlasnik': klub.get(c['_vlasnik'], str(c['_vlasnik'])),
                    'do': c['_posudba'], 'ugovor': c.get('_ugovor'), 'ovr': p['ovr'], 'poz': p['pos']})
    pos.sort(key=lambda x: -x['ovr'])
    return {'stat': dict(st) if st else {}, 'godine': sorted(god.items()), 'posudbe': pos, 'igraca': len(tm_ids),
            'skinuto': _vr(UG.F_IGR), 'posudbe_skinuto': _vr(UG.F_POS)}

def ciscenje_stanje():
    import ciscenje as CI, izvor as IZ
    cfg = IZ.aktivna(); B = db(); by = B['by_id']
    br = CI.ucitaj(cfg)
    out = []
    for k, v in br.items():
        p = by.get(k)
        out.append({'id': k, 'ime': p['name'] if p else '?', 'dob': p['age'] if p else None, 'drzava': p['nat'] if p else '',
                    'ovr': p['ovr'] if p else None, 'poz': p['pos'] if p else '', 'razlog': v})
    out.sort(key=lambda x: x['ime'])
    bk = _jl(os.path.join(_mapa(), 'bez_kluba_trazeno.json'), {})
    return {'popis': out, 'zadrzano': len(CI.zadrzi(cfg)), 'napravljeno': _vr(CI.datoteka(cfg)),
            'bez_vrijednosti': len(_jl(os.path.join(_mapa(), 'bez_vrijednosti.json'), {})),
            'trazeno': len(bk), 'nije_nadjeno': sum(1 for v in bk.values() if v is None)}

def ciscenje_zadrzi(pid):
    import ciscenje as CI, izvor as IZ
    cfg = IZ.aktivna()
    z = CI.zadrzi(cfg); z.add(int(pid)); json.dump(sorted(z), open(CI.zadrzi_put(cfg), 'w'))
    br = CI.ucitaj(cfg); br.pop(int(pid), None)
    json.dump({str(k): v for k, v in sorted(br.items())}, open(CI.datoteka(cfg), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

def ozljede_stanje():
    import ozljede as OZ
    C = OZ.ucitaj(); ids = _jl(os.path.join(_mapa(), 'tm_ids.json'), [])
    have = sum(1 for d, t, o in ids if str(t) in C)
    raz = collections.Counter(OZ.ocjena(v) for v in C.values() if v is not None)
    return {'skinuto': have, 'ukupno': len(ids), 'razdioba': {str(k): raz.get(k, 0) for k in (1, 2, 3)}}

def bez_kluba_stanje():
    d = _jl(os.path.join(_mapa(), 'bez_kluba_trazeno.json'), {})
    return {'obradjeno': len(d), 'nadjeno': sum(1 for v in d.values() if v), 'ukupno': STATE.get('bez_kluba')}

# ------------------------------------------------------------------ HTTP
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype='application/json; charset=utf-8', extra=None):
        if not isinstance(body, (bytes, bytearray)):
            body = (json.dumps(body, ensure_ascii=False, default=str) if 'json' in ctype else body).encode('utf-8')
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    def body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}')

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        g = lambda k, d=None: q.get(k, [d])[0]
        try:
            if u.path in ('/', '/app'):
                return self.send(200, open(os.path.join(HERE, 'app.html'), encoding='utf-8').read(), 'text/html; charset=utf-8')
            if u.path in ('/ikona.png', '/favicon.ico'):
                return self.send(200, open(os.path.join(HERE, 'ikona_256.png'), 'rb').read(), 'image/png')
            if u.path == '/classic':
                return self.send(200, open(os.path.join(HERE, 'ui.html'), encoding='utf-8').read(), 'text/html; charset=utf-8')
            r = AA.get(u.path, q)
            if r is not None: return self.send(*r)
            if u.path == '/api/lige':
                return self.send(200, {k: STATE.get(k) for k in ('lige', 'greska', 'baza', 'bez_kluba', 'ukupno', 'tip')} | {'dodatne': dodatne()})
            if u.path == '/api/baza':
                import izvor as IZ
                c = IZ.aktivna(); return self.send(200, c | {'opis': IZ.opis(c)})
            if u.path == '/api/provjera':
                d = za_provjeru()
                return self.send(200, [dict(v, db_id=int(k)) for k, v in sorted(d.items(), key=lambda x: -x[1].get('db_ovr', 0))])
            if u.path == '/api/verzije':
                return self.send(200, verzije())
            if u.path == '/api/katalog':
                return self.send(200, {'lige': katalog()})
            if u.path == '/api/status':
                p = JOB['proc']
                return self.send(200, {'radi': bool(JOB.get('aktivan')), 'naziv': JOB['naziv'], 'tip': JOB['tip'],
                                       'start': JOB['start'], 'kraj': JOB['kraj'], 'izlaz': JOB['izlaz'],
                                       'rezultat': JOB['rezultat'], 'koraci': JOB.get('koraci', []), 'log': list(JOB['log'])[-400:]})
            if u.path == '/api/datoteke': return self.send(200, files())
            if u.path == '/api/repr': return self.send(200, repr_stanje())
            if u.path == '/api/ugovori': return self.send(200, ugovori_stanje())
            if u.path == '/api/ciscenje': return self.send(200, ciscenje_stanje())
            if u.path == '/api/faceovi': return self.send(200, _jl(os.path.join(OUTDIR, 'faceovi_zadnje.json')) or {'nema': True})
            if u.path == '/api/ozljede': return self.send(200, ozljede_stanje())
            if u.path == '/api/model': return self.send(200, model_info())
            if u.path == '/api/sazetak': return self.send(200, summary(g('f')))
            if u.path == '/api/tm_trazi':
                import tm_igrac as TI
                return self.send(200, TI.trazi(g('q', ''))[:15])
            if u.path == '/api/db_trazi':
                import tm_igrac as TI
                db(); return self.send(200, TI.db_trazi(g('q', '')))
            if u.path == '/api/rucne':
                return self.send(200, {'popis': rucni_popis(float(g('skala', 0.5))), 'bez_kluba': bez_kluba_stanje()})
            if u.path == '/preuzmi':
                p = safe_out(g('f'))
                return self.send(200, open(p, 'rb').read(), 'application/octet-stream',
                                 {'Content-Disposition': 'attachment; filename="%s"' % os.path.basename(p)})
            self.send(404, {'greska': 'Nepoznata adresa.'})
        except FileNotFoundError:
            self.send(404, {'greska': 'Datoteka ne postoji.'})
        except SystemExit as e:
            self.send(400, {'greska': str(e)})
        except Exception as e:
            self.send(500, {'greska': '%s: %s' % (type(e).__name__, e)})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            b = self.body()
            r = AA.post(u.path, b, start_job, py, lambda: bool(JOB.get('aktivan')))
            if r is not None: return self.send(*r)
            if u.path == '/api/baza':
                import izvor as IZ
                c = {'tip': b.get('tip', 'igra')}
                if c['tip'] in ('mapa', 'cpk'):
                    c['put'] = (b.get('put') or '').strip().strip('"')
                    if not c['put'] or not os.path.exists(c['put']): return self.send(400, {'greska': 'Putanja ne postoji: %s' % c['put']})
                    if c['tip'] == 'mapa' and not IZ._find(c['put'], 'Player.bin'):
                        return self.send(400, {'greska': 'U toj mapi (ni u podmapama) nema Player.bin.'})
                    if c['tip'] == 'cpk' and not c['put'].lower().endswith('.cpk'):
                        return self.send(400, {'greska': 'Odaberi .cpk datoteku.'})
                if b.get('csv'):
                    c['csv'] = b['csv'].strip().strip('"')
                    if not os.path.isfile(c['csv']): return self.send(400, {'greska': 'CSV ne postoji: %s' % c['csv']})
                    try: IZ.read_csv(c['csv'])
                    except SystemExit as e: return self.send(400, {'greska': str(e)})
                if c['tip'] == 'csv' and not c.get('csv'): return self.send(400, {'greska': 'Odaberi CSV datoteku.'})
                c = IZ.postavi_aktivnu(c); reload_db(); AA.KAT.update(mtime=None)
                return self.send(200, c | {'opis': IZ.opis(c)})
            if u.path == '/api/provjera':
                import tm_igrac as TI
                d = za_provjeru(); k = str(b['db_id']); e = d.pop(k, None)
                if e is None: return self.send(404, {'greska': 'Nema tog igraca na popisu za provjeru.'})
                if b.get('akcija') == 'dodaj':
                    if e.get('unos'):
                        R = TI.rucne(); R[k] = dict(e['unos'], izvor='rucno'); TI.spremi_rucne(R)
                    else:
                        TI.dodaj(int(k), e['r'], 'rucno')
                json.dump(d, open(zp_put(), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                return self.send(200, {'ok': True})
            if u.path == '/api/vrati':
                p = JOB['proc']
                if JOB.get('aktivan'): return self.send(409, {'greska': 'Pričekaj da trenutni zadatak završi.'})
                src = vrati(b['id']); return self.send(200, {'ok': True, 'iz': os.path.basename(src)})
            if u.path == '/api/ciscenje/zadrzi':
                ciscenje_zadrzi(b['id']); return self.send(200, {'ok': True})
            if u.path == '/api/repr/original':
                if JOB.get('aktivan'): return self.send(409, {'greska': 'Pričekaj da trenutni zadatak završi.'})
                return self.send(200, {'ok': repr_original()})
            if u.path == '/api/odaberi':
                return self.send(200, {'put': odaberi(b.get('vrsta', 'mapa'))})
            if u.path == '/api/dodatne':
                kod = sorted({k.strip().upper() for k in b.get('kodovi', []) if k.strip()})
                json.dump(kod, open(dodatne_put(), 'w', encoding='utf-8'))
                return self.send(200, {'ok': True, 'dodatne': kod})
            if u.path == '/api/pokreni':
                args = ['ocjene.py']
                if b.get('samo_rucne'): args.append('--samo-rucne')
                elif b.get('sve'): args.append('--sve')
                else:
                    kod = sorted({k.strip().upper() for k in b.get('kodovi', []) + dodatne() if k.strip()})
                    if not kod: return self.send(400, {'greska': 'Odaberi barem jednu ligu (iz baze ili s Transfermarkta).'})
                    args += kod
                args += ['--csv', '--skala=%.2f' % float(b.get('skala', 0.5))]
                if b.get('osvjezi'): args.append('--osvjezi')
                if b.get('bez_rucnih'): args.append('--bez-rucnih')
                if b.get('bez_podataka'): args.append('--bez-podataka')
                if b.get('bez_ea'): args.append('--bez-ea-profila')
                if b.get('bez_dod'): args.append('--bez-ea-dodataka')
                if b.get('bez_ozljeda'): args.append('--bez-ozljeda')
                if b.get('bez_ugovora'): args.append('--bez-ugovora')
                if b.get('bez_brisanja'): args.append('--bez-brisanja')
                if b.get('upisi'): args.append('--upisi')
                if b.get('maxpromjena'): args.append('--max-promjena=%d' % int(b['maxpromjena']))
                naziv = 'Ocjene: ' + ('samo ručni popis' if b.get('samo_rucne') else 'sve lige' if b.get('sve') else '%d lige' % len(b.get('kodovi', [])))
                koraci = [('Ocjene', args)]
                if not b.get('bez_ugovora') and not b.get('samo_rucne'): koraci.insert(0, ('Ugovori i posudbe', ['ugovori.py']))
                if b.get('upisi') and b.get('repr'): koraci.append(('Reprezentacije', ['reprezentacije.py', '--upisi']))
                if len(koraci) > 1: naziv += ' + ' + ', '.join(k[0].lower() for k in koraci if k[0] != 'Ocjene')
                ok = start_job(naziv, 'ocjene', args, koraci)
                return self.send(200 if ok else 409, {'ok': ok, 'greska': None if ok else 'Već nešto radi — pričekaj ili zaustavi.'})
            if u.path == '/api/zadatak':
                t = b.get('tip')
                if t == 'ea27':
                    part = os.path.join(HERE, 'cache', 'ea_fc27.json.part')
                    if os.path.exists(part): os.remove(part)
                    ok = start_job('Skidanje EA FC ocjena', t, ['ea27.py'])
                elif t == 'model': ok = start_job('Učenje formule', t, ['model_ea27.py'])
                elif t == 'izvoz': ok = start_job('Izvoz baze u CSV', t, ['izvoz_csv.py'])
                elif t == 'katalog': ok = start_job('Skidanje kataloga liga', t, ['katalog_liga.py'])
                elif t == 'ozljede': ok = start_job('Skidanje povijesti ozljeda', t, ['ozljede.py'])
                elif t == 'ugovori': ok = start_job('Skidanje ugovora i posudbi', t, ['ugovori.py'] + (['--osvjezi'] if b.get('osvjezi') else []))
                elif t == 'repr': ok = start_job('Prijedlog reprezentacija', t, ['reprezentacije.py'] + (['--osvjezi'] if b.get('osvjezi') else []))
                elif t == 'repr_upisi': ok = start_job('Reprezentacije u igru', t, ['reprezentacije.py', '--upisi'])
                elif t == 'ciscenje': ok = start_job('Popis za čišćenje', t, ['ciscenje.py'])
                elif t == 'faceovi': ok = start_job('Popis face-ova', t, ['koza.py', '--samo-popis'])
                elif t == 'bezkluba':
                    args = ['bez_kluba.py']
                    if b.get('reprezentacija'): args.append('--reprezentacija')
                    if b.get('ponovi'): args.append('--ponovi')
                    if b.get('limit'): args.append('--limit=%d' % int(b['limit']))
                    if b.get('neocijenjeni'): args.append('--neocijenjeni')
                    ok = start_job('Traženje igrača bez kluba', t, args)
                else:
                    return self.send(400, {'greska': 'Nepoznat zadatak.'})
                return self.send(200 if ok else 409, {'ok': ok, 'greska': None if ok else 'Već nešto radi — pričekaj ili zaustavi.'})
            if u.path == '/api/stop':
                p = JOB['proc']
                JOB['prekid'] = True
                if p and p.poll() is None: p.terminate()
                return self.send(200, {'ok': True})
            if u.path == '/api/tm_izracun':
                import tm_igrac as TI
                r = TI.izracun(b['igrac'], float(b.get('skala', 0.5)))
                db(); r['db'] = TI.db_kandidati(r)
                return self.send(200, r)
            if u.path == '/api/rucne/dodaj':
                import tm_igrac as TI
                e = TI.dodaj(int(b['db_id']), b['r'], 'rucno')
                return self.send(200, {'ok': True, 'unos': e})
            if u.path == '/api/rucne/makni':
                import tm_igrac as TI
                d = TI.rucne()
                ids = [str(x) for x in b.get('db_ids', [])]
                if b.get('izvor'): ids = [k for k, v in d.items() if v.get('izvor') == b['izvor']]
                for k in ids: d.pop(k, None)
                TI.spremi_rucne(d)
                return self.send(200, {'ok': True, 'maknuto': len(ids)})
            if u.path == '/api/kod':
                key, tm = b['key'], (b.get('tm') or '').strip().upper()
                d = json.load(open(EXTRA, encoding='utf-8')) if os.path.exists(EXTRA) else {}
                if tm: d[key] = tm
                else: d.pop(key, None)
                json.dump(d, open(EXTRA, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
                for l in STATE['lige'] or []:
                    if l['key'] == key: l['tm'] = tm
                return self.send(200, {'ok': True})
            if u.path == '/api/desktop':
                p = safe_out(b['f']); dst = os.path.join(DESKTOP, os.path.basename(p))
                shutil.copy2(p, dst)
                return self.send(200, {'ok': True, 'put': dst})
            if u.path == '/api/mapa':
                os.startfile(OUTDIR); return self.send(200, {'ok': True})
            self.send(404, {'greska': 'Nepoznata adresa.'})
        except FileNotFoundError:
            self.send(404, {'greska': 'Datoteka ne postoji.'})
        except SystemExit as e:
            self.send(400, {'greska': str(e)})
        except Exception as e:
            self.send(500, {'greska': '%s: %s' % (type(e).__name__, e)})

def serve(port=None):
    """Pokreni poslužitelj u pozadinskoj niti (za launcher). Vraca ThreadingHTTPServer."""
    os.makedirs(OUTDIR, exist_ok=True)
    threading.Thread(target=load_leagues, daemon=True).start()
    threading.Thread(target=_zagrij, daemon=True).start()
    srv = ThreadingHTTPServer(('127.0.0.1', port or PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

def _zagrij():
    """U pozadini ucitaj formulu i indeks liga, da prvi 'Zasto ova ocjena?' ne ceka ~4 s."""
    try:
        import objasni as OB, model_ea27 as ME
        ME.load(); OB._indeks()
    except Exception: pass

def main():
    """Razvojno pokretanje: python ui.py (otvara običan preglednik). Zapakirana aplikacija koristi squad_updater.py."""
    os.makedirs(OUTDIR, exist_ok=True)
    threading.Thread(target=load_leagues, daemon=True).start()
    threading.Thread(target=_zagrij, daemon=True).start()
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), H)
    url = 'http://127.0.0.1:%d' % PORT
    print('Squad Updater runs at %s  (close this window to stop)' % url)
    if '--bez-preglednika' not in sys.argv: webbrowser.open(url)
    srv.serve_forever()

if __name__ == '__main__':
    main()
