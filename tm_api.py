# -*- coding: utf-8 -*-
"""
Brzi Transfermarkt JSON API (tmapi-alpha.transfermarkt.technology) - ~0.1 s po zahtjevu, podnosi paralelne zahtjeve.
Zamjenjuje spore HTML stranice za profil igraca, klub (kod lige) i vrijednosti suigraca.
Pretrage nema u API-ju - ona ostaje na web stranici (tm_igrac.trazi).
"""
import os, sys, json, time, threading, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tm_overall as T
import mreza as M

B = 'https://tmapi-alpha.transfermarkt.technology'
HDR = dict(T.UA, Accept='application/json')
CDIR = os.path.join(HERE, 'cache', 'klubovi_api'); os.makedirs(CDIR, exist_ok=True)
_lock = threading.Lock()

def get(path, tries=4):
    for a in range(tries):
        try:
            return json.loads(M.dohvati(B + path, HDR, 20)).get('data')
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(min(60, 5 * 2 ** a))
        except Exception:
            time.sleep(2 * (a + 1))
    return None

def player(pid):
    return get('/player/%s' % pid)

def players(ids):
    out = []
    ids = [str(i) for i in ids if i]
    for k in range(0, len(ids), 50):
        out += get('/players?' + '&'.join('ids[]=%s' % i for i in ids[k:k + 50])) or []
    return out

def value(d):
    try: return float(d['marketValueDetails']['current']['value']) or None
    except (KeyError, TypeError, ValueError): return None

def info(d):
    """Sazeti podaci igraca iz API zapisa."""
    if not d: return {}
    a = d.get('attributes') or {}; ld = d.get('lifeDates') or {}
    cur = [c for c in d.get('clubAssignments') or [] if c.get('type') == 'current']
    h = a.get('height')
    return {'tm_id': int(d['id']), 'name': d.get('name'), 'dob': None if ld.get('isDateOfBirthUnknown') else ld.get('dateOfBirth'),
            'age': ld.get('age'), 'height': int(round(float(h) * 100)) if h else None, 'value': value(d),
            'pos_api': (a.get('position') or {}).get('name'), 'foot': (a.get('preferredFoot') or {}).get('name'),
            'club_id': int(cur[0]['clubId']) if cur else None, 'last_club_id': int(d['lastClubId']) if d.get('lastClubId') else None,
            'highest': ((d.get('marketValueDetails') or {}).get('highest') or {}).get('value')}

def club(cid):
    """Klub: ime, kod lige, vrijednosti igraca (cache 7 dana)."""
    p = os.path.join(CDIR, '%s.json' % cid)
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 7 * 86400:
        try: return json.load(open(p, encoding='utf-8'))
        except ValueError: pass
    c = get('/club/%s' % cid)
    if not c: return None
    sq = (get('/club/%s/squad' % cid) or {}).get('squad') or []
    vals = [value(x) for x in players([s['playerId'] for s in sq if s.get('type') == 'current'])]
    d = {'id': int(cid), 'ime': c.get('name'), 'liga': (c.get('baseDetails') or {}).get('primaryCompetitionId'),
         'nacionalni': (c.get('baseDetails') or {}).get('isNationalTeam'), 'vrijednosti': [v for v in vals if v]}
    with _lock:
        json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    return d

# ------------------------------------------------------------------ cijela liga preko API-ja (umjesto sporog scrapea stranica)
_NAT = None
def nat_ime(i):
    """TM nacionalnost-id -> naziv (cache\tm_nat_ids.json, naucen iz skinutih liga)."""
    global _NAT
    if _NAT is None:
        try: _NAT = json.load(open(os.path.join(HERE, 'cache', 'tm_nat_ids.json'), encoding='utf-8'))
        except (OSError, ValueError): _NAT = {}
    return _NAT.get(str(i))

def _datum(s):
    return '%s/%s/%s' % (s[8:10], s[5:7], s[:4]) if s and len(s) >= 10 else '-'

def league(code, niti=8):
    """Isti oblik kao tm_overall.tm_league(code): {'league', 'players': [{tm_id, name, club, pos, dob, age, nat, nats, height, contract, value}]}.
    Vraca None ako API ne zna ligu (tada se koristi stara metoda)."""
    from concurrent.futures import ThreadPoolExecutor
    c = get('/competition/%s' % code)
    if not c: return None
    tb = get('/competition/%s/table' % code)
    clubs = []
    for t in (tb or {}).get('tables') or []:
        for x in t.get('clubs') or []:
            if x.get('clubId') and x['clubId'] not in clubs: clubs.append(x['clubId'])
    if not clubs: return None
    def one(cid):
        ci = get('/club/%s' % cid); sq = get('/club/%s/squad' % cid) or {}
        ids = [s['playerId'] for s in sq.get('squad') or [] if s.get('type') == 'current']
        return (ci or {}).get('name') or '', players(ids)
    out = []
    with ThreadPoolExecutor(niti) as ex:
        for club, ds in ex.map(one, clubs):
            for d in ds:
                a = d.get('attributes') or {}; ld = d.get('lifeDates') or {}; nd = (d.get('nationalityDetails') or {}).get('nationalities') or {}
                h = a.get('height')
                nats = [n for n in (nat_ime(nd.get('nationalityId')), nat_ime(nd.get('secondNationalityId'))) if n]
                out.append({'tm_id': int(d['id']), 'name': d.get('name') or '', 'club': club, 'pos': (a.get('position') or {}).get('name') or (a.get('positionGroupName') or ''),
                            'dob': None if ld.get('isDateOfBirthUnknown') else ld.get('dateOfBirth'), 'age': ld.get('age'),
                            'nat': nats[0] if nats else '', 'nats': nats, 'height': int(round(float(h) * 100)) if h else None,
                            'contract': _datum(a.get('contractUntil')), 'value': value(d)})
    nm = (c.get('name') or code)
    return {'league': nm, 'players': out}
