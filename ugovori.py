# -*- coding: utf-8 -*-
"""
UGOVORI I POSUDBE s Transfermarkta (brzi JSON API) -> Player.bin: ContractUntil, OwnerClub, LoanUntil.

    python ugovori.py [--osvjezi] [--niti=8] [--limit=500]

Za igrace koje je zadnji izracun uparo (baze\\<id>\\tm_ids.json):
  1. /players (50 igraca po zahtjevu): trenutni klub, ugovor do, reprezentacija, broj na dresu  -> cache\\tm_api_igraci.json
  2. /transfer/history/player/<id>: zakazani "povratak s posudbe" = igrac je trenutno na posudbi
     (vlasnik = klub u koji se vraca, posudba do = datum povratka)                               -> cache\\tm_posudbe.json
Cache vrijedi 7 dana (--osvjezi = skini ponovno). ocjene.py primjenjuje automatski (iskljuci s --bez-ugovora).

TM klub -> klub u bazi: glasanjem preko uparenih igraca (trenutni TM klub igraca vs njegov klub u bazi).
Posudba se upisuje samo ako je i klub-vlasnik u bazi; inace igrac dobije ugovor do kraja posudbe.
Trzisna vrijednost (MarketValue) se NE pise dok se u igri ne provjeri u kojim je jedinicama.
"""
import os, sys, json, time, datetime, threading, collections
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
F_IGR = os.path.join(HERE, 'cache', 'tm_api_igraci.json')
F_POS = os.path.join(HERE, 'cache', 'tm_posudbe.json')
SVJEZE = 7 * 86400

def _load(f):
    try: return json.load(open(f, encoding='utf-8'))
    except (OSError, ValueError): return {}

def _datum(s):
    """'2034-06-30' ili '2027-06-30T00:00:00+02:00' -> 20340630 (0 ako nema)."""
    if not s: return 0
    try: y, m, d = (int(x) for x in s[:10].split('-')); return y * 10000 + m * 100 + d
    except ValueError: return 0

def sazmi(d):
    """API zapis igraca -> mali dict za cache."""
    a = d.get('attributes') or {}
    ca = d.get('clubAssignments') or []
    cur = [c for c in ca if c.get('type') == 'current']
    nt = [c for c in ca if c.get('type') == 'nationalTeam']
    return {'klub': int(cur[0]['clubId']) if cur else None, 'broj': cur[0].get('shirtNumber') if cur else None,
            'ugovor': _datum(a.get('contractUntil')),
            'repr': int(nt[0]['clubId']) if nt else None, 'repr_broj': nt[0].get('shirtNumber') if nt else None,
            't': int(time.time())}

def posudba(h, klub):
    """Iz povijesti transfera: (vlasnik_tm_klub, posudba_do, ugovor_s_vlasnikom) ako je igrac trenutno na posudbi
    u 'klub', inace None. Ugovor s vlasnikom = 'contractUntilDate' zakazanog povratka."""
    if not h: return None
    H = h.get('history') or {}
    danas = datetime.date.today().isoformat()
    for t in sorted((H.get('pending') or []) + (H.get('terminated') or []), key=lambda t: (t.get('details') or {}).get('date') or ''):
        dt = ((t.get('details') or {}).get('date') or '')[:10]
        if not dt or dt <= danas: continue
        if (t.get('typeDetails') or {}).get('type') != 'RETURNED_FROM_PREVIOUS_LOAN': continue
        src = int(t['transferSource']['clubId']); dst = int(t['transferDestination']['clubId'])
        if klub is None or src == klub:
            return dst, _datum(dt), _datum(t['details'].get('contractUntilDate'))
    return None

def skini(tm_ids, osvjezi=False, niti=32, log=print):
    import tm_api as A, napredak as N
    I, Pz = _load(F_IGR), _load(F_POS)
    now = time.time()
    stari = lambda c, k: osvjezi or str(k) not in c or now - c[str(k)].get('t', 0) > SVJEZE
    todo = [t for t in tm_ids if stari(I, t)]
    log('Ugovori: %d igraca, skidam profil za %d...' % (len(tm_ids), len(todo)))
    lock = threading.Lock()
    def batch(ids):
        ds = A.players(ids) or []
        with lock:
            for d in ds: I[str(d['id'])] = sazmi(d)
    chunks = [todo[k:k + 50] for k in range(0, len(todo), 50)]
    with ThreadPoolExecutor(niti) as ex:
        for n, _ in enumerate(ex.map(batch, chunks), 1):
            if n % 4 == 0 or n == len(chunks): N.javi(min(n * 50, len(todo)), len(todo))
            if n % 40 == 0: log('   profili %d/%d' % (min(n * 50, len(todo)), len(todo)))
    json.dump(I, open(F_IGR, 'w', encoding='utf-8'))
    todo = [t for t in tm_ids if str(t) in I and stari(Pz, t)]
    log('Posudbe: skidam povijest transfera za %d igraca...' % len(todo))
    def one(t):
        h = A.get('/transfer/history/player/%s' % t, tries=3)
        try: p = posudba(h, I[str(t)]['klub']) if h else None
        except (KeyError, TypeError, ValueError): p = None
        with lock:
            Pz[str(t)] = {'vlasnik': p[0] if p else None, 'do': p[1] if p else 0, 'ugovor': p[2] if p else 0, 't': int(time.time()), 'ok': bool(h)}
    with ThreadPoolExecutor(niti) as ex:
        for n, _ in enumerate(ex.map(one, todo), 1):
            if n % 100 == 0 or n == len(todo): N.javi(n, len(todo))
            if n % 1000 == 0:
                log('   povijest %d/%d' % (n, len(todo)))
                with lock: json.dump(Pz, open(F_POS, 'w', encoding='utf-8'))
    json.dump(Pz, open(F_POS, 'w', encoding='utf-8'))
    return I, Pz

def mapa_klubova(parovi, I):
    """parovi = [(db_klub_id, tm_id)] -> {tm_klub_id: db_klub_id} glasanjem (>=3 glasa i >=60 %)."""
    v = collections.defaultdict(collections.Counter)
    for db_club, t in parovi:
        e = I.get(str(t))
        if db_club and e and e.get('klub'): v[e['klub']][db_club] += 1
    out = {}
    for tk, c in v.items():
        db_club, n = c.most_common(1)[0]
        if n >= 3 and n >= 0.6 * sum(c.values()): out[tk] = db_club
    return out

def promjene(parovi_p):
    """parovi_p = [(p, tm_id)] (p = igrac iz fl27db.load) -> ({idx: {'_ugovor','_vlasnik','_posudba'}}, opisi, statistika)."""
    I, Pz = _load(F_IGR), _load(F_POS)
    if not I: return {}, {}, None
    km = mapa_klubova([(p['club_id'], t) for p, t in parovi_p], I)
    ch, op, st = {}, {}, collections.Counter()
    for p, t in parovi_p:
        e = I.get(str(t))
        if not e or not p.get('club_id'): continue
        if km.get(e.get('klub')) != p['club_id']: st['drugi_klub'] += 1; continue     # TM: igrac je u drugom klubu
        c = {}
        ug = e.get('ugovor') or 0
        ps = Pz.get(str(t)) or {}
        if ps.get('vlasnik') and ps.get('do'):
            own = km.get(ps['vlasnik'])
            if own and own != p['club_id']:
                ug = max(ps.get('ugovor') or 0, ps['do'])                      # ugovor s vlasnikom (ne kraj posudbe)
                c.update(_vlasnik=own, _posudba=ps['do']); st['posudba'] += 1
                op[p['idx']] = 'posudba do %s (vlasnik %s), ugovor do %s' % (_fmt(ps['do']), own, _fmt(ug) if ug else '?')
            else:
                ug = ps['do']; st['posudba_vlasnik_nije_u_bazi'] += 1
        if ug and ug >= 20250101:
            c['_ugovor'] = ug; st['ugovor'] += 1
            op.setdefault(p['idx'], 'ugovor do %s' % _fmt(ug))
        if c: ch[p['idx']] = c
    st['klubova_mapirano'] = len(km)
    return ch, op, st

def _fmt(v): return '%02d.%02d.%d.' % (v % 100, v // 100 % 100, v // 10000)

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import izvor as IZ
    OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
    cfg = IZ.use(IZ.cfg_from_opts(OPT))
    src = os.path.join(IZ.mapa(cfg), 'tm_ids.json')
    if not os.path.exists(src): raise SystemExit('Prvo pokreni izracun (ocjene.py) - on zapise koje igrace treba provjeriti.')
    L = sorted(json.load(open(src)), key=lambda x: -x[2])
    S = IZ.opseg_ids(OPT)
    if S is not None: L = [e for e in L if e[0] in S]
    ids = [t for d, t, o in L if t]
    if isinstance(OPT.get('limit'), str): ids = ids[:int(OPT['limit'])]
    t0 = time.time()
    skini(ids, 'osvjezi' in OPT, int(OPT['niti']) if isinstance(OPT.get('niti'), str) else 32, log=lambda s: print(s, flush=True))
    import fl27db as D
    P, _, _ = D.load(); B = {p['id']: p for p in P}
    ch, op, st = promjene([(B[d], t) for d, t, o in L if d in B and t])
    print('Gotovo za %.0f s: %s' % (time.time() - t0, dict(st)))
    print('Primjena: ocjene.py (ili ubaci_u_igru.bat) - automatski, iskljuci s --bez-ugovora.')

if __name__ == '__main__':
    main()
