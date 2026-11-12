# -*- coding: utf-8 -*-
"""Usporedba: baza / proporcionalno / EA profil za odabrane igrace (iz dva izvjestaja)."""
import sys, openpyxl, re, json, os
sys.stdout.reconfigure(encoding='utf-8')
A, B = sys.argv[1], sys.argv[2]
names = sys.argv[3].split(',')
SH = ['OffAw', 'BallC', 'Drib', 'Tight', 'LowP', 'LoftP', 'Fin', 'Head', 'PlaceK', 'Curl', 'Speed', 'Accel',
      'KickP', 'Jump', 'Phys', 'Bal', 'Stam', 'DefAw', 'BallW', 'Aggr', 'GKAw', 'GKCat', 'GKClr', 'GKRef', 'GKRea']
SHOW = ['Speed', 'Accel', 'Fin', 'OffAw', 'Drib', 'LowP', 'Head', 'Jump', 'Phys', 'Stam', 'DefAw', 'BallW']
def load(f):
    out = {}
    for r in openpyxl.load_workbook(f, read_only=True)['Atributi'].iter_rows(min_row=2, values_only=True):
        old, new = {}, {}
        for k, v in zip(SH, r[5:30]):
            m = re.match(r'(\d+)→(\d+)', str(v))
            old[k], new[k] = (int(m.group(1)), int(m.group(2))) if m else (int(v), int(v))
        out[r[1]] = (r[2], r[3], r[4], old, new)
    return out
a, b = load(A), load(B)
print('%-20s %-4s %-5s  %s' % ('', '', 'OVR', '  '.join('%5s' % k for k in SHOW)))
for n in names:
    if n not in a: print(n, 'nema'); continue
    pos, o1, n1, old, prop = a[n]; _, _, n2, _, ea = b[n]
    print('%-20s %-4s %2d     %s' % (n, pos, o1, '  '.join('%5d' % old[k] for k in SHOW)), ' baza')
    print('%-20s %-4s %2d     %s' % ('', '', n1, '  '.join('%5d' % prop[k] for k in SHOW)), ' proporcionalno')
    print('%-20s %-4s %2d     %s' % ('', '', n2, '  '.join('%5d' % ea[k] for k in SHOW)), ' EA profil')
    print()
