# -*- coding: utf-8 -*-
"""Razvoj: usporedba modela TM (vrijednost, godine, pozicija, klub, liga) -> EA FC 27 overall."""
import os, sys, json, glob, collections
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import tm_overall as T
sys.stdout.reconfigure(encoding='utf-8')

ea = json.load(open(os.path.join(HERE, 'cache', 'ea_fc27.json'), encoding='utf-8'))
P = []
files = {}
for f in glob.glob(os.path.join(HERE, 'cache', 'tm_*_*.json')):
    code, season = os.path.basename(f)[3:-5].rsplit('_', 1)
    if season.isdigit() and int(season) > files.get(code, (0,))[0]: files[code] = (int(season), f)
for code, (s, f) in sorted(files.items()):
    d = json.load(open(f, encoding='utf-8'))
    cm = T.club_strength(d['players']) if hasattr(T, 'club_strength') else None
    L = collections.defaultdict(list)
    for q in d['players']:
        if q['value']: L[q['club']].append(np.log(q['value'] / 1e6))
    cm = {c: float(np.mean(sorted(v)[-14:])) for c, v in L.items()}
    lg = float(np.mean(sorted(cm.values())[-10:])) if cm else 0
    for q in d['players']:
        if q.get('dob') and q.get('value') and q['club'] in cm:
            q['_cm'] = cm[q['club']]; q['_lg'] = lg; q['_code'] = code; P.append(q)
T.match_ea(P, ea)
M = [q for q in P if q.get('ea')]
print('TM igraca %d, uparenih s EA27 %d' % (len(P), len(M)))
json.dump([{k: v for k, v in q.items() if k != 'ea'} | {'ea_ovr': q['ea']['ovr'], 'ea_pos': q['ea']['pos']} for q in M],
          open(os.path.join(HERE, 'cache', 'ea27_upareni.json'), 'w', encoding='utf-8'), ensure_ascii=False)

GRP = T.GRP; GROUPS = T.GROUPS
def f_base(q):
    return T.feats(q, {q['club']: q['_cm']})
def f_ext(q):
    L = np.log(max(q['value'], 5e4) / 1e6); a = q['age']; g = GRP.get(q['pos'], 'CM')
    sp = [max(a - k, 0) for k in (20, 22, 24, 26, 28, 30, 32, 34)]
    return [L, L * L, max(L - np.log(40), 0), a] + sp + [L * s for s in sp] + \
           [1.0 if g == x else 0.0 for x in GROUPS] + [q['_cm'], q['_lg'], L * q['_lg']]
y = np.array([q['ea']['ovr'] for q in M], float)
ages = np.array([q['age'] for q in M])
idx = np.arange(len(y)); np.random.seed(1); np.random.shuffle(idx)
def cv(fit, pred, X):
    out = np.zeros(len(y))
    for k in range(5):
        te = idx[k::5]; tr = np.setdiff1d(idx, te); m = fit(X[tr], y[tr]); out[te] = pred(m, X[te])
    return out
def rep(name, pr):
    e = pr - y
    s = '%-28s MAE %.2f  unutar3 %.0f%%  |' % (name, np.abs(e).mean(), 100 * (np.abs(e) <= 3).mean())
    for lo, hi in ((15, 20), (20, 23), (23, 28), (28, 31), (31, 34), (34, 45)):
        k = (ages >= lo) & (ages < hi)
        s += ' %d-%d: %+.1f/%.1f' % (lo, hi - 1, e[k].mean(), np.abs(e[k]).mean())
    print(s)
for nm, F in (('ridge base', f_base), ('ridge ext', f_ext)):
    X = np.array([F(q) for q in M], float)
    pr = cv(lambda a, b: T.ridge(a, b), lambda m, a: a @ m[0] + m[1], X); rep(nm, pr)
from sklearn.ensemble import HistGradientBoostingRegressor as H
Xg = np.array([[np.log(max(q['value'], 5e4) / 1e6), q['age'], GROUPS.index(GRP.get(q['pos'], 'CM')) + 1 if GRP.get(q['pos']) != 'GK' else 0,
                q['_cm'], q['_lg']] for q in M], float)
for lr in (0.05,):
    mk = lambda a, b: H(max_iter=600, learning_rate=lr, max_leaf_nodes=31, min_samples_leaf=30, l2_regularization=1.0,
                        categorical_features=[2], monotonic_cst=[1, 0, 0, 0, 0], random_state=0).fit(a, b)
    pr = cv(mk, lambda m, a: m.predict(a), Xg); rep('GBM lr%.2f' % lr, pr)
