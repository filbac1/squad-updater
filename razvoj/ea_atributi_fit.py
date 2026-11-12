# -*- coding: utf-8 -*-
"""Razvoj: preslikavanje EA FC 27 detaljnih atributa -> 25 PES atributa (ucenje na igracima iz baze)."""
import os, sys, json, collections
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')
import izvor as IZ, ocjene as OC, model_ea27 as ME, fl27db as D, tm_overall as T

IZ.use({'tip': 'igra'}); P, raw, src = IZ.load_players(); P = [p for p in P if p['pos'] != '?']
idx = OC.build_index(P)
EA = json.load(open(ME.EA, encoding='utf-8'))
byd = collections.defaultdict(list)
for e in EA:
    if e['women'] or not e['bd']: continue
    mo, d, y = e['bd'].split()[0].split('/'); byd['%s-%02d-%02d' % (y, int(mo), int(d))].append(e)
def ea_of(q):
    nt = T.norm(q['name'])
    c = [e for e in byd.get(q.get('dob'), []) if nt & (T.norm(e['first']) | T.norm(e['last']) | T.norm(e['common']))]
    return c[0] if len(c) == 1 else None

pairs = []
for code, f in sorted(ME.latest_leagues().items()):
    d = json.load(open(f, encoding='utf-8'))
    for q in d['players']: q['name'] = T.clean(q['name'])
    cmap = OC.map_clubs(d['players'], P, idx)
    cand = []
    for qi, q in enumerate(d['players']):
        for sc, p in OC.match_all(q, idx, cmap):
            if sc >= 1.6: cand.append((sc, qi, p))
    cand.sort(key=lambda x: -x[0]); used_q, used_p = set(), set()
    for sc, qi, p in cand:
        if qi in used_q or p['idx'] in used_p: continue
        used_q.add(qi); used_p.add(p['idx'])
        e = ea_of(d['players'][qi])
        if e and e.get('stats'): pairs.append((p, e, code))
print('parova baza<->EA:', len(pairs))
json.dump([[p['id'], e['id'], c] for p, e, c in pairs], open(os.path.join(HERE, 'cache', 'parovi_baza_ea.json'), 'w'))

KEYS = sorted(k for k in pairs[0][1]['stats'] if k not in ('pac', 'sho', 'pas', 'dri', 'def', 'phy'))
print('EA kljucevi:', len(KEYS))
X = np.array([[e['stats'].get(k, 50) for k in KEYS] for p, e, c in pairs], float)
GKp = np.array([p['pos'] == 'GK' for p, e, c in pairs])
Y = np.array([[p['attr'][a] for a in D.ANAMES] for p, e, c in pairs], float)
idx_ = np.arange(len(Y)); np.random.seed(1); np.random.shuffle(idx_)
def ridge(X, y, lam=5.0):
    mu, sd = X.mean(0), X.std(0) + 1e-9; Z = np.c_[(X - mu) / sd, np.ones(len(X))]
    I = np.eye(Z.shape[1]) * lam; I[-1, -1] = 0
    w = np.linalg.solve(Z.T @ Z + I, Z.T @ y); return mu, sd, w
def pred(m, X):
    mu, sd, w = m; return np.c_[(X - mu) / sd, np.ones(len(X))] @ w
print('%-20s %6s %6s %6s' % ('PES atribut', 'MAE', 'R2', 'baseline'))
res = {}
for j, a in enumerate(D.ANAMES):
    sel = GKp if j >= 20 else ~GKp          # GK atributi uce se samo na golmanima, ostali na igracima iz polja
    Xs, ys = X[sel], Y[sel, j]; ii = np.arange(len(ys)); np.random.shuffle(ii)
    pr = np.zeros(len(ys))
    for k in range(5):
        te = ii[k::5]; tr = np.setdiff1d(ii, te); pr[te] = pred(ridge(Xs[tr], ys[tr]), Xs[te])
    mae = np.abs(pr - ys).mean(); r2 = 1 - ((pr - ys) ** 2).sum() / ((ys - ys.mean()) ** 2).sum()
    res[a] = (mae, r2); print('%-20s %6.2f %6.2f %6.2f' % (a, mae, r2, np.abs(ys - ys.mean()).mean()))
print('prosjek MAE %.2f, R2 %.2f' % (np.mean([v[0] for v in res.values()]), np.mean([v[1] for v in res.values()])))
