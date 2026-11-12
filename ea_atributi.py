# -*- coding: utf-8 -*-
"""
REALNI ATRIBUTI IZ EA FC 27: preslikavanje 34 detaljna EA atributa -> 25 PES atributa.

- Uci se na igracima koji postoje i u bazi i u EA FC 27 (parovi preko TM imena + datuma rodenja),
  zasebna ridge regresija za svaki PES atribut (GK atributi samo na golmanima, ostali na igracima iz polja).
  Test (5-fold, 11.165 igraca): prosjecno odstupanje 3.0 boda, objasnjeno 58 % razlika.
- U izracunu: profil = w * EA profil + (1-w) * baza (default w = 0.7), pa se skalira TOCNO na ciljni overall.
  Igracima bez EA zapisa ostaje profil iz baze.

    python ea_atributi.py      -> nauci preslikavanje (ea_atributi.json)
"""
import os, sys, json, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
FILE = os.path.join(HERE, 'ea_atributi.json')
TEZINA = 0.7

# svaki PES atribut se racuna SAMO iz EA atributa koji ga stvarno opisuju (inace npr. brzina 'posuduje' od dodavanja)
IZVORI = {
    'Offensive Awareness': ['positioning', 'reactions', 'composure', 'finishing'],
    'Ball Control': ['ballControl', 'dribbling', 'composure'],
    'Dribbling': ['dribbling', 'agility', 'ballControl', 'balance'],
    'Tight Possession': ['dribbling', 'agility', 'ballControl', 'balance', 'composure'],
    'Low Pass': ['shortPassing', 'vision'],
    'Lofted Pass': ['longPassing', 'vision', 'crossing'],
    'Finishing': ['finishing', 'positioning', 'composure', 'shotPower'],
    'Heading': ['headingAccuracy', 'jumping'],
    'Place Kicking': ['freeKickAccuracy', 'penalties', 'curve'],
    'Curl': ['curve', 'freeKickAccuracy', 'crossing'],
    'Speed': ['sprintSpeed'],
    'Acceleration': ['acceleration', 'agility'],
    'Kicking Power': ['shotPower', 'longShots'],
    'Jump': ['jumping'],
    'Physical Contact': ['strength', 'aggression', 'balance'],
    'Balance': ['balance', 'agility'],
    'Stamina': ['stamina'],
    'Defensive Awareness': ['defensiveAwareness', 'interceptions', 'reactions'],
    'Ball Winning': ['standingTackle', 'slidingTackle', 'interceptions'],
    'Aggression': ['aggression'],
    'GK Awareness': ['gkPositioning', 'gkReflexes'],
    'GK Catching': ['gkHandling'],
    'GK Clearing': ['gkHandling', 'gkDiving', 'gkKicking'],
    'GK Reflexes': ['gkReflexes'],
    'GK Reach': ['gkDiving', 'gkPositioning'],
}
_M = None

def model():
    global _M
    if _M is None:
        _M = json.load(open(FILE, encoding='utf-8')) if os.path.exists(FILE) else None
    return _M

def _ridge(X, y, lam=5.0):
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = np.c_[(X - mu) / sd, np.ones(len(X))]
    I = np.eye(Z.shape[1]) * lam; I[-1, -1] = 0
    w = np.linalg.solve(Z.T @ Z + I, Z.T @ y)
    coef = w[:-1] / sd
    return [float(c) for c in coef], float(w[-1] - (coef * mu).sum())

# ------------------------------------------------------------------ EA zapis igraca
_EA = None
def ea_index():
    global _EA
    if _EA is None:
        import model_ea27 as ME
        _EA = collections.defaultdict(list)
        for e in json.load(open(ME.EA, encoding='utf-8')):
            if e.get('women') or not e.get('bd') or not e.get('stats'): continue
            mo, d, y = e['bd'].split()[0].split('/'); _EA['%s-%02d-%02d' % (y, int(mo), int(d))].append(e)
    return _EA

def ea_entry(q):
    """EA FC 27 zapis TM igraca (ime + datum rodenja); None ako nema ili nije jednoznacno."""
    import tm_overall as T
    if not q.get('dob'): return None
    nt = T.norm(q['name'])
    c = [e for e in ea_index().get(q['dob'], []) if nt & (T.norm(e['first']) | T.norm(e['last']) | T.norm(e['common']))]
    return c[0] if len(c) == 1 else None

# ------------------------------------------------------------------ ucenje
def train():
    import izvor as IZ, ocjene as OC, model_ea27 as ME, fl27db as D, tm_overall as T
    IZ.use({'tip': 'igra'}); P, raw, src = IZ.load_players(); P = [p for p in P if p['pos'] != '?']
    idx = OC.build_index(P); pairs = []
    for code, f in sorted(ME.latest_leagues().items()):
        d = json.load(open(f, encoding='utf-8'))
        for q in d['players']: q['name'] = T.clean(q['name'])
        cmap = OC.map_clubs(d['players'], P, idx)
        cand = sorted(((sc, qi, p) for qi, q in enumerate(d['players']) for sc, p in OC.match_all(q, idx, cmap) if sc >= 1.6),
                      key=lambda x: -x[0])
        uq, up = set(), set()
        for sc, qi, p in cand:
            if qi in uq or p['idx'] in up: continue
            uq.add(qi); up.add(p['idx'])
            e = ea_entry(d['players'][qi])
            if e: pairs.append((p, e))
    keys = sorted(k for k in pairs[0][1]['stats'] if k not in ('pac', 'sho', 'pas', 'dri', 'def', 'phy'))
    X = np.array([[e['stats'].get(k, 50) for k in keys] for p, e in pairs], float)
    kidx = {k: i for i, k in enumerate(keys)}
    gk = np.array([p['pos'] == 'GK' for p, e in pairs])
    out = {'kljucevi': keys, 'n': len(pairs), 'atributi': {}}
    for j, a in enumerate(D.ANAMES):
        sel = gk if j >= 20 else ~gk
        y = np.array([p['attr'][a] for p, e in pairs], float)[sel]
        cols = [kidx[k] for k in IZVORI[a]]
        cs, b = _ridge(X[sel][:, cols], y, lam=1.0)
        c = [0.0] * len(keys)
        for i, v in zip(cols, cs): c[i] = v
        fit = X[sel] @ np.array(c) + b
        # regresija stisne raspon prema prosjeku (zvijezde izgube vrhunce) -> vrati raspon kakav je u bazi
        # preslikavanje po percentilima: EA rang -> ista pozicija u raspodjeli tog atributa u bazi (cuva vrhunce zvijezda)
        lv = np.linspace(0, 100, 201)
        out['atributi'][a] = {'coef': c, 'const': b, 'q_p': [float(v) for v in np.percentile(fit, lv)],
                              'q_y': [float(v) for v in np.percentile(y, lv)]}
    json.dump(out, open(FILE, 'w', encoding='utf-8'), indent=0)
    global _M; _M = out
    return out

# ------------------------------------------------------------------ primjena
def profil(e, gk):
    """25 PES atributa iz EA zapisa (dict naziv->vrijednost); samo dio koji vrijedi za tu ulogu."""
    M = model()
    if not M or not e or not e.get('stats'): return None
    x = np.array([e['stats'].get(k, 50) for k in M['kljucevi']], float)
    import fl27db as D
    names = D.ANAMES[20:] if gk else D.ANAMES[:20]
    out = {}
    for a in names:
        m = M['atributi'][a]
        v = float(np.dot(m['coef'], x) + m['const'])
        if 'q_p' in m:
            qp, qy = m['q_p'], m['q_y']
            if v > qp[-1]: v = qy[-1] + (v - qp[-1])            # iznad najboljeg u bazi: nastavi linearno
            elif v < qp[0]: v = qy[0] + (v - qp[0])
            else: v = float(np.interp(v, qp, qy))
        out[a] = v
    return out

def blend(attr, e, gk, w=None):
    """Novi pocetni profil igraca: w * EA profil + (1-w) * baza. Vrati (attr dict, je li EA koristen)."""
    w = TEZINA if w is None else w
    pr = profil(e, gk)
    if not pr or w <= 0: return dict(attr), False
    a = dict(attr)
    for n, v in pr.items():
        a[n] = int(max(40, min(99, round(w * v + (1 - w) * attr[n]))))
    return a, True

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    M = train()
    print('Preslikavanje EA -> PES nauceno na %d igraca (%d EA atributa) -> %s' % (M['n'], len(M['kljucevi']), FILE))
