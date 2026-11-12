# -*- coding: utf-8 -*-
"""
RUCNE IZMJENE SASTAVA REPREZENTACIJA (Sucelje -> Reprezentacije -> Uredi sastav).

    python repr_rucno.py --izlaz=<nova baza> [--baza=...]

  Izmjene se pamte po bazi u baze\\<id>\\reprezentacije_rucno.json:
      {"<team id>": {"dodaj": [player id, ...], "makni": [...], "brojevi": {"<player id>": broj}}}
  i primjenjuju na PlayerAssignment.bin nove baze. Osnovni sastav (prije rucnih izmjena) cuva se u
  <nova baza>\\_rucno\\osnova.json, pa se svaka izmjena moze ponistiti. Ako se sastav u novoj bazi u meduvremenu
  promijenio (npr. novi izracun reprezentacija), osnova se ponovno uzima iz nove baze.
  reprezentacije.py ovo poziva na kraju, pa rucne izmjene ostaju i nakon novog izracuna.
"""
import os, sys, json, struct, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fl27db as D

F = 'reprezentacije_rucno.json'
MAXS, MINS = 26, 23
PF = D.PF

def _jl(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError): return d

def _jw(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + '.novo', 'w', encoding='utf-8') as f: json.dump(o, f, ensure_ascii=False, indent=1)
    os.replace(p + '.novo', p)

def put(cfg):
    import izvor as IZ
    return os.path.join(IZ.mapa(cfg), F)

def ucitaj(cfg): return _jl(put(cfg), {}) or {}

def spremi(cfg, d):
    d = {k: v for k, v in d.items() if v.get('dodaj') or v.get('makni') or v.get('brojevi')}
    _jw(put(cfg), d)

def _recs(raw): return [list(struct.unpack_from('<4I', raw, i * 16)) for i in range(len(raw) // 16)]

def trenutni(izl):
    """PlayerAssignment iz nove baze (ili None)."""
    import spremanje as SP
    pes = SP.citaj_iz(izl)
    f = os.path.join(pes or '', 'PlayerAssignment.bin')
    return PF.wesys(open(f, 'rb').read()) if pes and os.path.isfile(f) else None

def kontekst():
    db, _ = D.load_files(D.NAMES)
    countries = D.countries_map(db['Country.bin'])
    teams, national = {}, set()
    T = db['Team.bin']
    for i in range(len(T) // 1532):
        r = T[i * 1532:(i + 1) * 1532]; tid = struct.unpack_from('<I', r, 8)[0]
        teams[tid] = PF.cstr(r[368:438])
        if PF.is_national(r, countries): national.add(tid)
    return db, countries, teams, national

def _broj(r): return (r[3] & 0xff) + 1
def _slot(r): return (r[3] >> 10) & 0x3f

def primijeni(izl, cfg, log=print):
    """Primijeni sve rucne izmjene na novu bazu. Vraca broj promijenjenih reprezentacija."""
    import spremanje as SP, reprezentacije as REP, overall as O
    R = ucitaj(cfg)
    fo = os.path.join(izl, '_rucno', 'osnova.json'); OS = _jl(fo, {}) or {}
    if not R and not OS: return 0
    raw = trenutni(izl)
    if raw is None: log('Rucne izmjene reprezentacija: nova baza jos nema PlayerAssignment.bin - preskoceno'); return 0
    db, countries, teams, national = kontekst()
    P, _, _ = D.load(); B = {p['id']: p for p in P}
    pes = SP.citaj_iz(izl)
    try:
        praw = PF.wesys(open(os.path.join(pes, 'Player.bin'), 'rb').read())
        pl = {struct.unpack_from('<I', praw, i * D.REC + 8)[0] for i in range(len(praw) // D.REC)}
    except OSError: pl = set(B)
    ovr = REP.live_ovr(izl) or {p['id']: O.ovr(p['attr'], p['pos']) for p in P if p['pos'] != '?'}
    recs = _recs(raw)
    novi, upoz, info = {}, [], {}
    for tk in sorted(set(R) | set(OS), key=lambda k: teams.get(int(k), '')):
        tid = int(tk)
        if tid not in national: continue
        cur = sorted([r for r in recs if r[2] == tid], key=_slot)
        o = OS.get(tk)
        # osnova vrijedi samo dok je sastav u novoj bazi onaj koji smo MI zapisali; inace (novi izracun) -> nova osnova
        if not o or sorted(r[1] for r in cur) != sorted(o.get('zapisano') or []) or any(p_ not in pl for p_, n_ in o['sastav']):
            o = {'sastav': [[r[1], _broj(r)] for r in cur]}
        e = R.get(tk) or {}
        ids = [p_ for p_, n_ in o['sastav'] if p_ in pl]
        makni = set(e.get('makni') or [])
        ids = [i for i in ids if i not in makni]
        for i in e.get('dodaj') or []:
            if i in ids or i not in pl or i not in B: continue
            drugi = {r[2] for r in recs if r[1] == i and r[2] in national and r[2] != tid}
            if drugi:
                upoz.append('%s: %s je vec u reprezentaciji %s - nije dodan' % (teams[tid], B[i]['name'], ', '.join(teams[t] for t in drugi))); continue
            if len(ids) >= MAXS:
                upoz.append('%s: vec %d igraca - %s nije dodan' % (teams[tid], MAXS, B[i]['name'])); continue
            ids.append(i)
        if not e:                                # izmjene ponistene -> osnovni sastav
            pass
        order = sorted(ids, key=lambda i: (D.POS.index(B[i]['pos']) if i in B and B[i]['pos'] in D.POS else 99, -ovr.get(i, 0)))
        brojevi = {int(k): int(v) for k, v in (e.get('brojevi') or {}).items()}
        osn = dict((p_, n_) for p_, n_ in o['sastav'])
        used, num = set(), {}
        for src in (brojevi, osn):
            for i in order:
                n = src.get(i)
                if i not in num and n and 1 <= n <= 99 and n not in used: num[i] = n; used.add(n)
        for i in order:
            if i not in num:
                n = next(k for k in range(1, 100) if k not in used); num[i] = n; used.add(n)
        lst = [(i, s, num[i]) for s, i in enumerate(order)]
        sada = [(r[1], _broj(r)) for r in cur]
        if sorted(sada) != sorted((i, num[i]) for i in order): novi[tid] = lst
        if e: OS[tk] = dict(o, zapisano=sorted(order))
        else: OS.pop(tk, None)
        info[tid] = {'osnova': [p_ for p_, n_ in o['sastav']], 'order': order, 'num': num, 'e': e}
    for u in upoz: log('UPOZORENJE ' + u)
    if novi:
        nove = {'PlayerAssignment.bin': b''.join(struct.pack('<4I', *r) for r in REP.novi_zapisi(recs, novi))}
        dodani = {t: [(i, s_, n_) for i, s_, n_ in l if i not in info[t]['osnova']] for t, l in novi.items()}
        pl_ = REP.drzavljanstva(izl, {t: l for t, l in dodani.items() if l}, teams, countries, spoji=True) if any(dodani.values()) else None
        if pl_ is not None: nove['Player.bin'] = pl_
        # ako je nova baza imala slozene najbolje postave, slozi i uredene reprezentacije (inace bi bile po pozicijama)
        info_ = _jl(os.path.join(izl, SP.OZNAKA), {}) or {}
        if any(p_.get('korak') == 'najbolja postava' for p_ in info_.get('poslovi', [])):
            import postave as PO
            db2, _ = D.load_files(('Tactics.bin', 'TacticsFormation.bin'))
            db2.update(db)
            pr_ = nove.get('Player.bin') or PF.wesys(open(os.path.join(pes, 'Player.bin'), 'rb').read())
            a_, _n = PO.slozi(nove['PlayerAssignment.bin'], pr_, db2, samo={teams[t].lower() for t in novi}, log=log)
            if a_ is not None: nove['PlayerAssignment.bin'] = a_
        SP.zapisi(izl, nove, posao={'korak': 'rucne izmjene reprezentacija', 'promijenjeno': len(novi)}, log=log)
    _jw(fo, OS)
    izvjestaj(info, teams, B, ovr, db)
    log('Rucne izmjene reprezentacija: %d reprezentacija promijenjeno u novoj bazi' % len(novi))
    return len(novi)

def izvjestaj(info, teams, B, ovr, db):
    """Osvjezi izvjestaji/reprezentacije_zadnje.json za uredene reprezentacije (sastav, ulaze/izlaze prema ORIGINALU)."""
    if not info: return
    import reprezentacije as REP
    f = os.path.join(HERE, 'izvjestaji', 'reprezentacije_zadnje.json')
    J = _jl(f, None) or {'vrijeme': datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S'), 'timovi': []}
    orig = _recs(db['PlayerAssignment.bin'])
    pj = lambda i: {'id': i, 'ime': B[i]['name'], 'poz': B[i]['pos'], 'ovr': ovr.get(i), 'klub': B[i]['club'] or 'bez kluba'}
    byid = {t.get('id'): t for t in J['timovi']}
    for tid, x in info.items():
        old_ids = [r[1] for r in orig if r[2] == tid]
        order, num, e = x['order'], x['num'], x['e']
        t = byid.get(tid) or {'tim': teams[tid], 'id': tid, 'pozvanih': 0, 'u_bazi': 0, 'nema': []}
        if 'status_tm' not in t: t['status_tm'] = t.get('status')
        usli = [pj(i) for i in order if i not in old_ids and i in B]
        izasli = [pj(i) for i in old_ids if i not in order and i in B]
        t.update({'ulaze': usli, 'izlaze': izasli, 'sastav': [dict(pj(i), broj=num[i], linija=REP.grp(B[i]['pos'])) for i in order if i in B],
                  'rucno': {'dodano': [i for i in order if i not in x['osnova']], 'maknuto': [i for i in x['osnova'] if i not in order]} if e else None})
        t['status'] = ('promijenjeno' if (usli or izasli) else 'isto') if (e or t['status_tm'] in ('promijenjeno', 'isto')) else t['status_tm']
        if tid not in byid: J['timovi'].append(t); byid[tid] = t
    J['timovi'].sort(key=lambda t: t['tim'])
    _jw(f, J)

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import izvor as IZ
    OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
    cfg = IZ.use(IZ.cfg_from_opts(OPT))
    if not isinstance(OPT.get('izlaz'), str): raise SystemExit('Treba --izlaz=<nova baza>')
    primijeni(OPT['izlaz'], cfg, log=lambda s: print(s, flush=True))
