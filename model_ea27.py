# -*- coding: utf-8 -*-
"""
TM -> overall formula kalibrirana na EA SPORTS FC 27 ocjenama.

Ulazi: TM vrijednost (glavno), godine, pozicija, jacina kluba (ln prosjek top-14 vrijednosti),
jacina lige (prosjek top-10 klubova). Model: gradient boosting s monotonim ogranicenjem
(veca vrijednost nikad ne smije dati manju ocjenu). Ljestvica = EA FC 27.

    python model_ea27.py      -> nauci model iz svih TM liga u cache\\ i cache\\ea_fc27.json
"""
import os, sys, json, glob, pickle, datetime, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tm_overall as T

FILE = os.path.join(HERE, 'model_ea27.pkl')
EA = os.path.join(HERE, 'cache', 'ea_fc27.json')

def grp(pos):
    g = T.GRP.get(pos, 'CB' if pos == 'Defender' else 'CM')
    return 0 if g == 'GK' else T.GROUPS.index(g) + 1

def strengths(players):
    """-> (jacina kluba dict, jacina lige)"""
    L = collections.defaultdict(list)
    for q in players:
        if q.get('value'): L[q['club']].append(np.log(q['value'] / 1e6))
    cm = {c: float(np.mean(sorted(v)[-14:])) for c, v in L.items()}
    lg = float(np.mean(sorted(cm.values())[-10:])) if cm else 0.0
    return cm, lg

# regija lige (TM kod) - trziste vrijednosti se razlikuje (J. Amerika jeftinija, Azija/Australija skuplja).
# 0 = Europa (default, npr. i Albanija), 1 = J. Amerika, 2 = Sj./Srednja Amerika, 3 = Azija + Australija, 4 = Afrika
REGIJA = {}
for _r, _codes in ((1, 'ARG1 ARG2 BRA1 BRA2 BRA3 URU1 COL1 CLPD TDeA PAR1 PR1C EL1S EC1N BO1A VZ1L VZ1C'),
                   (2, 'MLS1 MEX1 USL CRPD'),
                   (3, 'CSL SA1 SA2 JAP1 JAP2 QSL AUS1 RSK1 THA1 IRN1 MYS1 UAE1 SIN1 JOR1 JO1L UZ1 VIE1 KUW1 IRQ1 IN1L PHI1 TJK1 TAD1 IND1'),
                   (4, 'EGY1 TUN1 MAR1 ALG1 RSA1')):
    for _c in _codes.split(): REGIJA[_c] = _r

J_AMERIKA = {'Argentina', 'Brazil', 'Uruguay', 'Paraguay', 'Chile', 'Colombia', 'Peru', 'Ecuador', 'Bolivia', 'Venezuela'}
_KAT = None
def regija(code):
    code = (code or '').strip()
    if code in REGIJA: return REGIJA[code]
    global _KAT
    if _KAT is None:                       # nepoznata liga -> regija iz kataloga liga (kontinent/drzava)
        f = os.path.join(HERE, 'cache', 'katalog_liga.json')
        _KAT = {r['kod']: r for r in json.load(open(f, encoding='utf-8'))} if os.path.exists(f) else {}
    r = _KAT.get(code)
    if not r: return 0
    k = r['kontinent']
    if k == 'Amerika': return 1 if r['drzava'] in J_AMERIKA else 2
    return {'Azija i Oceanija': 3, 'Afrika': 4}.get(k, 0)

def x(q, cm, lg, code=None):
    return [np.log(max(q['value'], 5e4) / 1e6), q['age'], grp(q['pos']), cm.get(q['club'], lg - 1), lg,
            regija(code or q.get('tm_league')), q.get('_trend', 0.0), q.get('_peak', 0.0)]

# ------------------------------------------------------------------ povijest vrijednosti (trend, vrh karijere)
_H = None
def _hist():
    global _H
    if _H is None:
        hp = os.path.join(HERE, 'cache', 'tm_povijest.json')
        try: _H = json.load(open(hp, encoding='utf-8')) if os.path.exists(hp) else {}
        except ValueError: _H = {}
    return _H

def hist_feats(tm_id, date, value_now=None, fetch=False):
    """(trend, vrh): trend = ln(vrijednost na datum) - ln(vrijednost godinu ranije); vrh = ln(najveca do datuma) - ln(sada).
    Bez povijesti -> (0, 0). fetch=True: dohvati povijest preko API-ja ako je nema u cache-u."""
    H = _hist(); h = H.get(str(tm_id))
    if h is None and fetch and tm_id:
        try:
            import tm_api as TA
            d = TA.get('/player/%s/market-value-history' % tm_id)
            h = [(x['marketValue']['determined'], x['marketValue']['value']) for x in (d or {}).get('history', [])]
            H[str(tm_id)] = h
        except Exception:
            h = None
    if not h: return 0.0, 0.0
    v = value_now or T.value_at(h, date)
    if not v: return 0.0, 0.0
    v1 = T.value_at(h, date - datetime.timedelta(days=365)) or v
    pk = max([val or 0 for dt, val in h if datetime.date.fromisoformat(dt) <= date] + [v])
    L = np.log(max(v, 5e4) / 1e6)
    return float(L - np.log(max(v1, 5e4) / 1e6)), float(np.log(max(pk, 5e4) / 1e6) - L)

def latest_leagues():
    files = {}
    for f in glob.glob(os.path.join(HERE, 'cache', 'tm_*_*.json')):
        code, season = os.path.basename(f)[3:-5].rsplit('_', 1)
        if os.path.getsize(f) < 2000: continue          # prazna sezona (zapamcen prazan rezultat)
        if season.isdigit() and int(season) > files.get(code, (0,))[0]: files[code] = (int(season), f)
    return {c: f for c, (s, f) in files.items()}

TOP_V0 = 60.0          # M EUR; iznad toga linearni nastavak
import datetime
KAL_DATUM = datetime.date(2026, 9, 15)   # izlazak EA FC 27 ocjena
if os.environ.get('SU_KAL_DATUM'):            # osvjezavanje podataka (osvjezi_podatke.py): ocjene vrijede od danas
    KAL_DATUM = datetime.date.fromisoformat(os.environ['SU_KAL_DATUM'])

# Ljestvica: FL27 baza je ispod ~82 puno stisnutija od EA (izmjereno na 10.854 igraca: nagib 0.57 ispod praga 82,
# npr. EA 60 -> baza ~70). skala 0 = cista EA ljestvica, 1 = kao baza, 0.5 = pola puta (dogovoreno 10.11.2026.)
SKALA_PRAG = 82.0
BAZA_NAGIB = 0.569
SKALA = 0.5

def to_game(ea_val, skala=SKALA):
    if ea_val is None or ea_val >= SKALA_PRAG: return ea_val
    nagib = 1.0 - skala * (1.0 - BAZA_NAGIB)
    return SKALA_PRAG - (SKALA_PRAG - ea_val) * nagib

def _model():
    from sklearn.ensemble import HistGradientBoostingRegressor as H
    return H(max_iter=600, learning_rate=0.03, max_leaf_nodes=31, min_samples_leaf=30, l2_regularization=1.0,
             categorical_features=[2, 5], monotonic_cst=[1, 0, 0, 0, 0, 0, 0, 0], random_state=0)

def train():
    ea = json.load(open(EA, encoding='utf-8'))
    P, lig = [], []
    for code, f in sorted(latest_leagues().items()):
        d = json.load(open(f, encoding='utf-8'))
        cm, lg = strengths(d['players'])
        n0 = len(P)
        for q in d['players']:
            if q.get('dob') and q.get('value') and q.get('age') and q['club'] in cm:
                q['_x'] = x(q, cm, lg, code); P.append(q)
        lig.append(code)
    T.match_ea(P, ea)
    M = [q for q in P if q.get('ea')]
    # EA ocjene su nastale ~15.9.2026. -> uci na TM vrijednosti iz tog trenutka (gdje je povijest poznata);
    # predvidanje kasnije ide na danasnje vrijednosti. (test: greska 1.62 -> 1.54 na igracima s poviscu)
    H = {}
    hp = os.path.join(HERE, 'cache', 'tm_povijest.json')
    if os.path.exists(hp):
        try: H = json.load(open(hp, encoding='utf-8'))
        except ValueError: H = {}
    n_hist = 0
    for q in M:
        h = H.get(str(q.get('tm_id')))
        v = T.value_at(h, KAL_DATUM) if h else None
        if v:
            q['_x'] = [np.log(max(v, 5e4) / 1e6)] + q['_x'][1:]; n_hist += 1
        if h:
            q['_x'][6], q['_x'][7] = hist_feats(q.get('tm_id'), KAL_DATUM, v or None)
    X = np.array([q['_x'] for q in M], float); y = np.array([q['ea']['ovr'] for q in M], float)
    idx = np.arange(len(y)); np.random.seed(1); np.random.shuffle(idx); pr = np.zeros(len(y))
    for k in range(5):
        te = idx[k::5]; tr = np.setdiff1d(idx, te); pr[te] = _model().fit(X[tr], y[tr]).predict(X[te])
    m = _model().fit(X, y)
    # vrh ljestvice: stablo ne zna ekstrapolirati iznad najvecih vrijednosti -> linearni nastavak u ln(vrijednosti)
    L0 = np.log(TOP_V0); k = X[:, 0] > L0
    Xc = X[k].copy(); Xc[:, 0] = L0; dx = X[k, 0] - L0
    slope = float(((y[k] - m.predict(Xc)) * dx).sum() / (dx * dx).sum()) if k.sum() > 20 else 0.0
    info = {'top_v0': TOP_V0, 'top_nagib': slope, 'n_povijest': n_hist, 'kal_datum': KAL_DATUM.isoformat(), 'n': int(len(y)), 'greska': float(np.abs(pr - y).mean()), 'unutar3': float((np.abs(pr - y) <= 3).mean()),
            'datum': datetime.date.today().isoformat(), 'lige': lig, 'ea': 'EA SPORTS FC 27 (%d igraca)' % len(ea)}
    pickle.dump({'model': m, 'info': info}, open(FILE, 'wb'))
    return m, info

_M = None
def load():
    global _M
    if _M is None:
        _M = pickle.load(open(FILE, 'rb')) if os.path.exists(FILE) else dict(zip(('model', 'info'), train()))
    return _M

def predict(q, cm, lg, fetch=False):
    if not (q.get('value') and q.get('age')): return None
    if '_trend' not in q and q.get('tm_id'):
        q = dict(q); q['_trend'], q['_peak'] = hist_feats(q['tm_id'], datetime.date.today(), q['value'], fetch=fetch)
    M = load(); xx = x(q, cm, lg); L0 = np.log(M['info'].get('top_v0', TOP_V0)); extra = 0.0
    if xx[0] > L0:
        extra = (xx[0] - L0) * M['info'].get('top_nagib', 0.0); xx[0] = L0
    return float(M['model'].predict(np.array([xx], float))[0]) + extra

def predict_many(qs, cm, lg, fetch=False):
    """Kao predict(), ali za cijelu listu odjednom (jedan poziv modela umjesto jednog po igracu - ~50x brze)."""
    M = load(); L0 = np.log(M['info'].get('top_v0', TOP_V0)); nagib = M['info'].get('top_nagib', 0.0)
    rows, idx, extra = [], [], []
    today = datetime.date.today()
    for i, q in enumerate(qs):
        if not (q.get('value') and q.get('age')): continue
        if '_trend' not in q and q.get('tm_id'):
            q = dict(q); q['_trend'], q['_peak'] = hist_feats(q['tm_id'], today, q['value'], fetch=fetch)
        xx = x(q, cm, lg); e = 0.0
        if xx[0] > L0: e = (xx[0] - L0) * nagib; xx[0] = L0
        rows.append(xx); idx.append(i); extra.append(e)
    out = [None] * len(qs)
    if rows:
        pr = M['model'].predict(np.array(rows, float))
        for i, v, e in zip(idx, pr, extra): out[i] = float(v) + e
    return out

_EA = None
def ea_lookup(q):
    """EA FC 27 ocjena TM igraca (ime + datum rodenja) ili None."""
    global _EA
    if _EA is None:
        _EA = collections.defaultdict(list)
        for e in json.load(open(EA, encoding='utf-8')):
            if e['women'] or not e['bd']: continue
            mo, d, y = e['bd'].split()[0].split('/'); _EA['%s-%02d-%02d' % (y, int(mo), int(d))].append(e)
    nt = T.norm(q['name'])
    c = [e for e in _EA.get(q.get('dob'), []) if nt & (T.norm(e['first']) | T.norm(e['last']) | T.norm(e['common']))]
    return c[0]['ovr'] if c else None

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    m, info = train()
    print('Model nauceni na %d igraca (%d liga; %d s vrijednoscu na %s). Prosjecna greska %.2f, unutar +-3: %.0f %%, nagib vrha %.2f'
          % (info['n'], len(info['lige']), info['n_povijest'], info['kal_datum'], info['greska'], 100 * info['unutar3'], info['top_nagib']))
