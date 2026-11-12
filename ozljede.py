# -*- coding: utf-8 -*-
"""
OTPORNOST NA OZLJEDE iz Transfermarkt povijesti ozljeda.

  prosjek propustenih dana po sezoni u zadnje 3 sezone:  <= 10 -> 3 (otporan)   <= 45 -> 2   > 45 -> 1 (sklon ozljedama)
  (PES "Injury Resistance" 1-3; 3 = najbolje)

Skida /verletzungen/spieler/<id> za igrace koje je zadnji izracun ocijenio (baze\\<id>\\tm_ids.json), najbolji prvi,
paralelno uz zajednicko ogranicenje brzine prema TM webu. Nastavlja gdje je stao (cache\\ozljede.json).
ocjene.py ove podatke primjenjuje automatski (iskljuci s --bez-ozljeda).

    python ozljede.py [--limit=2000] [--niti=3] [--osvjezi]

Osvjezavanje: igrac se ponovno provjerava kad pocne nova sezona (1.7.), nakon 30 dana ako je sklon ozljedama
(> 10 dana/sezonu), inace nakon 120 dana (vrijeme zadnje provjere: cache\\ozljede_t.json).
"""
import os, re, sys, json, time, datetime, threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
FILE = os.path.join(HERE, 'cache', 'ozljede.json')
PRAG = (10, 45)

def sezone(n=3, danas=None):
    d = danas or datetime.date.today(); y = d.year if d.month >= 7 else d.year - 1
    return ['%02d/%02d' % ((y - k) % 100, (y - k + 1) % 100) for k in range(n)]

def parse(t):
    seg = t[t.find('class="items"'):]; seg = seg[:seg.find('</table>', seg.find('<tbody'))]
    out = []
    for r in re.split(r'<tr class="(?:odd|even)">', seg)[1:]:
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)]
        if len(cells) < 5: continue
        m = re.search(r'(\d+)\s*days', ' '.join(cells))
        if m: out.append((cells[0], int(m.group(1))))
    return out

def dani_po_sezoni(rows, danas=None):
    sz = sezone(3, danas)
    tot = sum(d for s, d in rows if s in sz)
    # tekuca sezona je tek pocela -> racunaj kao pola sezone
    return tot / 2.5

def ocjena(dani):
    return 3 if dani <= PRAG[0] else 2 if dani <= PRAG[1] else 1

def ucitaj():
    try: return json.load(open(FILE, encoding='utf-8'))
    except (OSError, ValueError): return {}

# ------------------------------------------------------------------ kada ponovno provjeriti (osvjezavanje)
FILE_T = os.path.join(HERE, 'cache', 'ozljede_t.json')     # tm_id -> unix vrijeme zadnje provjere
SVJEZE_SKLON = 30 * 86400      # skloni ozljedama (> 10 dana/sezonu) mijenjaju se brze
SVJEZE = 120 * 86400           # ostali

def ucitaj_t():
    try: return json.load(open(FILE_T, encoding='utf-8'))
    except (OSError, ValueError): return {}

def _pocetak_sezone(now):
    d = datetime.date.fromtimestamp(now); y = d.year if d.month >= 7 else d.year - 1
    return time.mktime(datetime.date(y, 7, 1).timetuple())

def zastarjelo(tid, C, T, now=None):
    """True ako igraca treba (ponovno) provjeriti: nema ga, nova sezona od zadnje provjere,
    ili je provjera starija od 30 dana (sklon ozljedama) / 120 dana (ostali).
    Stari zapisi bez vremena racunaju se kao provjereni kad je cache zadnji put spremljen."""
    k = str(tid)
    if k not in C: return True
    now = now or time.time()
    t = T.get(k)
    if t is None:
        try: t = os.path.getmtime(FILE)
        except OSError: return True
    if t < _pocetak_sezone(now): return True
    return now - t > (SVJEZE_SKLON if (C[k] or 0) > PRAG[0] else SVJEZE)

def _spremi(o, f):
    with open(f + '.novo', 'w', encoding='utf-8') as w: json.dump(o, w)
    os.replace(f + '.novo', f)

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import izvor as IZ, tm_igrac as TI, napredak as N
    OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
    cfg = IZ.use(IZ.cfg_from_opts(OPT))
    src = os.path.join(IZ.mapa(cfg), 'tm_ids.json')
    if not os.path.exists(src): raise SystemExit('Prvo pokreni izracun (ocjene.py) - on zapise koje igrace treba provjeriti.')
    L = sorted(json.load(open(src)), key=lambda x: -x[2])
    S = IZ.opseg_ids(OPT)
    if S is not None: L = [e for e in L if e[0] in S]
    C = ucitaj(); T = ucitaj_t(); lock = threading.Lock(); now = time.time()
    if OPT.get('osvjezi'): todo = [t for d, t, o in L]
    else: todo = [t for d, t, o in L if zastarjelo(t, C, T, now)]
    novih = sum(1 for t in todo if str(t) not in C)
    lim = int(OPT['limit']) if isinstance(OPT.get('limit'), str) else len(todo)
    todo = todo[:lim]
    print('Igraca: %d, vec skinuto: %d, sada: %d' % (len(L), len(L) - novih, len(todo)), flush=True)
    if len(todo) > novih: print('   osvjezavam %d starijih zapisa (nova sezona / starije od 30-120 dana)' % (len(todo) - novih), flush=True)
    TI.SLEEP = 0.25                      # ~4 stranice u sekundi (izmjereno: 8 niti / 0,2 s bez ijedne greske); usporava se samo ako TM pocne odbijati
    t0 = time.time(); n = [0]; losi = [0]
    def one(tid):
        try:
            rows = parse(TI.get('https://www.transfermarkt.com/x/verletzungen/spieler/%s' % tid))
            return tid, round(dani_po_sezoni(rows), 1)
        except BaseException as e:
            losi[0] += 1
            return tid, None
    with ThreadPoolExecutor(int(OPT.get('niti', 8)) if isinstance(OPT.get('niti'), str) else 8) as ex:
        for tid, d in ex.map(one, todo):
            with lock:
                if d is not None: C[str(tid)] = d; T[str(tid)] = int(time.time())
                n[0] += 1
                if n[0] % 10 == 0 or n[0] == len(todo): N.javi(n[0], len(todo))
                if n[0] % 50 == 0:
                    if losi[0] > 5:                               # vise od 10 % gresaka u zadnjih 50 -> uspori i pricekaj
                        TI.SLEEP = min(1.0, TI.SLEEP * 2); time.sleep(20); print('   (Transfermarkt usporava - razmak %.2f s)' % TI.SLEEP, flush=True)
                    losi[0] = 0
                    _spremi(C, FILE); _spremi(T, FILE_T)
                    print('[%d/%d] %.0f igraca/min' % (n[0], len(todo), n[0] / (time.time() - t0) * 60), flush=True)
    _spremi(C, FILE); _spremi(T, FILE_T)
    print('GOTOVO: %d igraca s podacima o ozljedama' % len(C), flush=True)

if __name__ == '__main__':
    main()
