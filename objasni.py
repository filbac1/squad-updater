# -*- coding: utf-8 -*-
"""
"Zasto ova ocjena?" - rastav ocjene iz formule (model_ea27) na doprinose ulaza.

Tocne Shapleyjeve vrijednosti po 6 skupina ulaza (64 kombinacije, jedan poziv modela):
  vrijednost, dob, jacina kluba, jacina lige, regija trzista, povijest vrijednosti (trend + vrh karijere).
Pozicija se ne rastavlja (referentni igrac igra istu poziciju).
Referentni igrac: 1 M EUR, 26 godina, prosjecan klub u prosjecnoj ligi, europsko trziste, bez trenda.
Zbroj: referentni + doprinosi = ocjena formule (EA ljestvica), pa ljestvica igre (klizac) -> ocjena.
"""
import os, sys, glob, json, math, itertools, datetime
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SKUPINE = [('value', [0]), ('age', [1]), ('club', [3]), ('league', [4]), ('region', [5]), ('history', [6, 7])]

def _liga_datoteke():
    import model_ea27 as ME
    return ME.latest_leagues()

_IDX = {'kljuc': None}

def _indeks():
    """Jedan prolaz kroz skinute lige: tm_id -> kod lige, igraci po ligi, referentne jacine. Vrijedi dok se datoteke ne promijene."""
    import model_ea27 as ME
    F = _liga_datoteke()
    kljuc = tuple(sorted((c, os.path.getmtime(f)) for c, f in F.items()))
    if _IDX['kljuc'] != kljuc:
        ids, lige, imena, lgs, cms = {}, {}, {}, [], []
        for code, f in F.items():
            try: d = json.load(open(f, encoding='utf-8'))
            except (OSError, ValueError): continue
            pl = d.get('players') or []; lige[code] = pl; imena[code] = d.get('league') or code
            for q in pl:
                if q.get('tm_id'): ids.setdefault(q['tm_id'], code)
            cm, lg = ME.strengths(pl)
            if cm: lgs.append(lg); cms += list(cm.values())
        _IDX.update(kljuc=kljuc, ids=ids, lige=lige, imena=imena,
                    ref={'lg': float(np.median(lgs)) if lgs else 0.0, 'cm': float(np.median(cms)) if cms else -1.0})
    return _IDX

def referenca():
    """Referentni ulazi (bez pozicije): medijan jacine lige i kluba u svim skinutim ligama."""
    return _indeks()['ref']

def nadji(tm_id):
    """-> (kod lige, igrac iz TM liste, popis igraca lige) ili None."""
    I = _indeks(); code = I['ids'].get(tm_id)
    if code is None: return None
    pl = I['lige'][code]
    return code, next(q for q in pl if q.get('tm_id') == tm_id), pl

def rastav(q, cm, lg, code):
    """-> dict: ref, doprinosi {skupina: bodovi}, model (EA ljestvica). Doprinosi se zbrajaju tocno."""
    import model_ea27 as ME
    M = ME.load(); L0 = math.log(M['info'].get('top_v0', ME.TOP_V0)); nagib = M['info'].get('top_nagib', 0.0)
    q = dict(q)
    if '_trend' not in q and q.get('tm_id'):
        q['_trend'], q['_peak'] = ME.hist_feats(q['tm_id'], datetime.date.today(), q['value'])
    xx = ME.x(q, cm, lg, code)
    R = referenca()
    ref = [0.0, 26, xx[2], R['cm'], R['lg'], 0, 0.0, 0.0]
    k = len(SKUPINE); rows = []
    maske = list(itertools.product((0, 1), repeat=k))
    for m in maske:
        r = list(ref)
        for on, (_, idx) in zip(m, SKUPINE):
            if on:
                for i in idx: r[i] = xx[i]
        rows.append(r)
    X = np.array(rows, float); extra = np.maximum(X[:, 0] - L0, 0) * nagib; X[:, 0] = np.minimum(X[:, 0], L0)
    V = dict(zip(maske, M['model'].predict(X) + extra))
    phi = {}
    for j, (ime, _) in enumerate(SKUPINE):
        s = 0.0
        for m in maske:
            if m[j]: continue
            n = sum(m); w = math.factorial(n) * math.factorial(k - n - 1) / math.factorial(k)
            m1 = list(m); m1[j] = 1
            s += w * (V[tuple(m1)] - V[m])
        phi[ime] = round(float(s), 2)
    return {'ref': round(float(V[(0,) * k]), 2), 'doprinosi': phi, 'model': round(float(V[(1,) * k]), 2),
            'ulazi': {'value': q.get('value'), 'age': q.get('age'), 'pos': q.get('pos'), 'club': q.get('club'), 'league': code,
                      'trend': round(float(xx[6]), 3), 'peak': round(float(xx[7]), 3)}}

def objasni(tm_id, skala=None):
    """Cijelo objasnjenje za igraca (tm_id) ili None ako nije u skinutim ligama / nema vrijednost."""
    import model_ea27 as ME
    r = nadji(int(tm_id))
    if not r: return None
    code, q, players = r
    if not (q.get('value') and q.get('age')): return None
    cm, lg = ME.strengths(players)
    out = rastav(q, cm, lg, code)
    out['ulazi']['league_ime'] = _indeks()['imena'].get(code, code)
    sk = ME.SKALA if skala is None else float(skala)
    out['skala'] = sk
    out['igra'] = round(float(ME.to_game(out['model'], sk)), 2)
    out['ocjena'] = int(np.clip(np.round(out['igra']), 40, 99))
    try: out['ea'] = ME.ea_lookup(dict(q, name=q['name'].split('<')[0].strip()))
    except Exception: out['ea'] = None
    return out

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(objasni(int(sys.argv[1])), ensure_ascii=False, indent=1))
