# -*- coding: utf-8 -*-
"""
Popravak OSNOVNIH PODATAKA igraca s Transfermarkta (uz ocjene): godine, drzavljanstvo (glavno + drugo), visina.

Pravila (dogovoreno 10.11.2026.):
  godine    - iz TM DATUMA RODENJA, na referentni datum baze (FL27: 1.1.2027.; odredi se automatski)
  visina    - TM visina u cm (150-210), ako je razlika 1-8 cm; veca razlika se samo prijavi (i TM grijesi)
  drzavljanstvo:
    * ako je glavna drzava iz baze medu TM drzavljanstvima -> glavna ostaje, drugo = drugo TM drzavljanstvo (ako postoji)
    * inace, ako je igrac u REPREZENTACIJI u bazi: glavna = ta reprezentacija ako je medu TM drzavljanstvima,
      a ako nije - ne diraj (u izvjestaju oznaceno)
    * inace glavna = prvo TM drzavljanstvo, drugo = drugo TM drzavljanstvo
    * drzave kojih nema u PES-u (Martinique, Guadeloupe...) se preskacu; ako TM ima samo jedno drzavljanstvo,
      drugo iz baze ostaje
"""
import os, re, sys, json, unicodedata, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fl27db as D

ALIAS = {'United States': 'Usa', 'Korea, South': 'Republic Of Korea', 'Korea, North': 'Korea Dpr', 'Türkiye': 'Turkey',
         'Bosnia-Herzegovina': 'Bosnia And Herzegovina', 'DR Congo': 'Congo Dr', 'The Gambia': 'Gambia',
         'Cape Verde': 'Cabo Verde', 'Central African Republic': 'Central African Rep.', 'St. Lucia': 'Saint Lucia',
         'Southern Sudan': 'South Sudan', 'St. Kitts & Nevis': 'Saint Kitts And Nevis',
         'St. Vincent & Grenadinen': 'St Vincent & Grenadines', 'Cote d\'Ivoire': "Côte D'Ivoire",
         'Chinese Taipei (Taiwan)': 'Chinese Taipei', 'Curacao': 'Curaçao', 'Macedonia': 'North Macedonia',
         'Ireland': 'Ireland', 'Czech Republic': 'Czech Republic', 'Czechia': 'Czech Republic'}

def _n(s):
    return re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower())

_C = None
def drzave():
    """(norm naziv -> id, id -> naziv) iz Country.bin (aktivna baza ili mapa)."""
    global _C
    if _C is None:
        data = None
        if D.BASE and os.path.isfile(os.path.join(D.BASE, 'Country.bin')):
            data = D.PF.wesys(open(os.path.join(D.BASE, 'Country.bin'), 'rb').read())
        cm = D.countries_map(data)
        _C = ({_n(v): k for k, v in cm.items()}, cm)
    return _C

def country_id(tm_name):
    idx, _ = drzave()
    return idx.get(_n(ALIAS.get(tm_name, tm_name)))

REF = datetime.date(2027, 1, 1)      # datum na koji baza racuna godine (ocjene.py ga odredi iz podataka)
MAX_VISINA = 8

def age_at(dob, ref=None):
    ref = ref or REF
    d = datetime.date.fromisoformat(dob) if isinstance(dob, str) else dob
    return ref.year - d.year - ((ref.month, ref.day) < (d.month, d.day))

def odredi_ref(parovi):
    """parovi = [(dob 'YYYY-MM-DD', godine u bazi)] -> 1.1. one godine na koju se baza najbolje slaze."""
    global REF
    best = None
    for y in range(2023, 2031):
        for m in (1, 7):
            R = datetime.date(y, m, 1)
            ok = sum(1 for d, a in parovi if age_at(d, R) == a)
            if best is None or ok > best[0]: best = (ok, R)
    if best and parovi: REF = best[1]
    return REF, (best[0] / len(parovi) if parovi else 0)

def popravci(p, q, nats=None):
    """p = igrac iz baze, q = TM igrac. nats = puni popis TM drzavljanstava (ako je poznat).
    Vrati (changes dict s _age/_height/_nat/_nat2, lista opisa promjena, napomena)."""
    ch, op, nap = {}, [], ''
    # godine
    if q.get('dob') and p.get('age'):
        try: a = age_at(q['dob'])
        except ValueError: a = None
        if a and 15 <= a <= 50 and a != p['age']:
            ch['_age'] = a; op.append('godine %d → %d' % (p['age'], a))
    elif q.get('age') and p.get('age') and 15 <= q['age'] <= 50 and abs(q['age'] - p['age']) >= 2:
        # nema datuma rodenja (pojedinacno trazenje): samo ocite greske, TM danasnje godine
        ch['_age'] = q['age']; op.append('godine %d → %d (TM godine)' % (p['age'], q['age']))
    # visina
    h = q.get('height')
    if h and 150 <= h <= 210 and p.get('height') and h != p['height']:
        if abs(h - p['height']) <= MAX_VISINA:
            ch['_height'] = h; op.append('visina %d → %d' % (p['height'], h))
        else:
            nap = 'visina: baza %d, TM %d - razlika prevelika, nije mijenjano (provjeri)' % (p['height'], h)
    # drzavljanstvo
    tm = nats or q.get('nats') or ([q['nat']] if q.get('nat') else [])
    if isinstance(tm, str): tm = [tm]
    ids = [c for c in (country_id(x) for x in tm) if c]
    ids = list(dict.fromkeys(ids))
    _, cm = drzave()
    if ids:
        cur, cur2 = p.get('nat_id'), p.get('nat2_id') or 0
        prim = cur
        if cur in ids:
            prim = cur
        else:
            nt = [country_id(x) or next((k for k, v in cm.items() if v == x), None) for x in (p.get('nt') or [])]
            nt = [x for x in nt if x]
            if nt:
                hit = [x for x in nt if x in ids]
                if hit: prim = hit[0]
                else: nap = 'reprezentacija %s, a TM: %s - drzavljanstvo nije mijenjano' % (p['nt'][0], ', '.join(tm))
            elif nats is None and not q.get('nats') and len(tm) == 1:
                nap = 'TM prva drzava %s, baza %s - treba puni popis drzavljanstava' % (tm[0], p.get('nat'))
                prim = None
            elif nap.startswith('visina'):
                prim = None                     # i visina i drzava ne odgovaraju - vjerojatno drugi igrac, ne diraj
            else:
                prim = ids[0]
        if prim and not nap.startswith(('reprezentacija', 'TM prva')):
            sec = next((x for x in ids if x != prim), None)
            if prim != cur:
                ch['_nat'] = prim; op.append('drzava %s → %s' % (cm.get(cur, cur), cm.get(prim, prim)))
            if sec is not None and sec != cur2:
                ch['_nat2'] = sec; op.append('2. drzava %s → %s' % (cm.get(cur2, '-') if cur2 else '-', cm.get(sec, sec)))
            elif sec is None and prim != cur and cur2 == prim:
                ch['_nat2'] = 0; op.append('2. drzava %s → -' % cm.get(cur2, cur2))
    return ch, op, nap
