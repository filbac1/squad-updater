# -*- coding: utf-8 -*-
"""
Overall igraca u FL27/PES21 = TOCNA formula igre (pes_overall.py, iz Ejogc327 editora).
Provjereno na pesdb.net: 1410/1415 tocno (ostalo +-1), na editorovom CSV-u 99.96 %.

Stara linearna procjena (formula_overall.json iz pesdb) vise se ne koristi.
"""
import numpy as np
from fl27db import ANAMES, POS
import pes_overall as PO

def _args(attr, wfa):
    a = [attr[n] for n in ANAMES] if isinstance(attr, dict) else list(attr)
    if wfa is None: wfa = attr.get('_wfa', 2) if isinstance(attr, dict) else 2
    return a, wfa

def ovr(attr, pos, wfa=None):
    a, w = _args(attr, wfa)
    return int(PO.overall(a, w, POS.index(pos)))

def ovr_raw(attr, pos, wfa=None):
    """Glatka (neokrugljena) verzija, za kalibraciju i trazenje skaliranja."""
    a, w = _args(attr, wfa)
    return float(PO.overall_raw(a, w, POS.index(pos)))

def formula():
    # kompatibilnost: nijedna pozicija vise nije "privremena"
    return {p: {} for p in POS}

if __name__ == '__main__':
    import sys, json, os, collections
    sys.stdout.reconfigure(encoding='utf-8')
    data = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'razvoj', 'pesdb', 'data.jsonl')
    ok, n = collections.Counter(), collections.Counter()
    for l in open(data, encoding='utf-8'):
        r = json.loads(l)
        if r.get('pos') in POS and r.get('ovr') and all(r.get(x) is not None for x in ANAMES):
            n[r['pos']] += 1; ok[r['pos']] += ovr(r, r['pos'], r['Weak Foot Accuracy']) == r['ovr']
    for p in POS:
        if n[p]: print('%-4s %d/%d tocno' % (p, ok[p], n[p]))
