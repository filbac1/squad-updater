# -*- coding: utf-8 -*-
"""
REPREZENTACIJE prema zadnjem pozivu na Transfermarktu -> novi PlayerAssignment.bin u ocjene_tm\\izlaz.

    python reprezentacije.py [--upisi] [--osvjezi] [--samo=Croatia,England] [--min=0.5] [--izlaz=<mapa> --od=izlaz] [--opseg=<json>]

  1. reprezentacija u bazi -> TM reprezentacija: glasanjem preko igraca (cache\\tm_api_igraci.json, skida ugovori.py)
  2. TM popis (API /club/<id>/squad, cache\\reprezentacije\\<id>.json, 7 dana) -> igraci u bazi:
     preko uparenih TM id-ova (tm_ids.json + rucni popis), inace ime + godine + drzava
  3. novi sastav = TOCNO zadnji TM poziv (najvise 26; siri popis -> 26 najboljih po overallu, >= 3 golmana).
     Pozvani koji ne postoje u bazi zamjenjuju se igracima iz starog sastava (najbolji overall). Redoslijed kao u
     originalu (po poziciji), prvu postavu igra slaze sama. Brojevi na dresu s TM-a.
  Reprezentacija se preskace ako je u bazi pronadeno manje od --min (default 50 %) pozvanih igraca.
  Bez --upisi: samo izvjestaj (izvjestaji\\reprezentacije_*.txt). Uvijek krece od ORIGINALNOG PlayerAssignment.bin.
"""
import os, sys, json, time, struct, zlib, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fl27db as D
import overall as O

PF = D.PF
CDIR = os.path.join(HERE, 'cache', 'reprezentacije'); os.makedirs(CDIR, exist_ok=True)
OUT = os.path.join(D.IZLAZ, 'common', 'etc', 'pesdb', 'PlayerAssignment.bin')
OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
GK, DEF, MID = {'GK'}, {'CB', 'LB', 'RB'}, {'DMF', 'CMF', 'LMF', 'RMF', 'AMF'}
MAXS = 26
MINS = 23
grp = lambda pos: 0 if pos in GK else 1 if pos in DEF else 2 if pos in MID else 3

def wesys_write(data, path):
    comp = zlib.compress(data, 9)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(b'\xff\x10\x81WESYS' + struct.pack('<II', len(comp), len(data)) + comp)

def tm_squad(cid, osvjezi=False):
    import tm_api as A
    p = os.path.join(CDIR, '%s.json' % cid)
    if not osvjezi and os.path.exists(p) and time.time() - os.path.getmtime(p) < 7 * 86400:
        return json.load(open(p, encoding='utf-8'))
    s = A.get('/club/%s/squad' % cid) or {}
    sq = [x for x in s.get('squad') or [] if x.get('type') in ('nationalTeam', 'current')]
    info = {}
    for d in A.players([x['playerId'] for x in sq]) or []:
        ld = d.get('lifeDates') or {}
        info[d['id']] = {'ime': d.get('name'), 'dob': ld.get('dateOfBirth'), 'god': ld.get('age'),
                         'poz': ((d.get('attributes') or {}).get('position') or {}).get('shortName')}
    out = [{'tm_id': int(x['playerId']), 'broj': x.get('shirtNumber'), 'kapetan': bool(x.get('isCaptain')),
            **info.get(str(x['playerId']), {})} for x in sq]
    json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    return out

def live_ovr(izl=None):
    """Overall svakog igraca iz Player.bin koji je trenutno u igri (izlaz, ako postoji)."""
    import spremanje as SP
    f = os.path.join(SP.citaj_iz(izl) or '', 'Player.bin') if izl else os.path.join(D.IZLAZ, 'common', 'etc', 'pesdb', 'Player.bin')
    if not os.path.exists(f): return {}
    raw = PF.wesys(open(f, 'rb').read()); out = {}
    for i in range(len(raw) // D.REC):
        r = raw[i * D.REC:(i + 1) * D.REC]; pos = D.getf(r, 54, 2, 4)
        if pos > 12: continue
        a = {n: D.getf(r, b, s, 6, 40) for n, b, s in D.ATTR}; a['_wfa'] = D.getf(r, 57, 6, 2, 1)
        out[struct.unpack_from('<I', r, 8)[0]] = O.ovr(a, D.POS[pos])
    return out

def drzavljanstva(izl, novi, teams, countries):
    """Igrac u reprezentaciji mora imati njezinu drzavu kao PRVO drzavljanstvo (igra prikazuje prvo).
    Npr. Naderi (Njemacka / Ceska) pozvan za Cesku -> Ceska / Njemacka. Ako tu drzavu uopce nema, prva postaje ona,
    a dosadasnja prva ide na drugo mjesto. Vraca nove bajtove Player.bin iz izlaza ili None (nista za promijeniti)."""
    import spremanje as SP
    pes = SP.citaj_iz(izl)
    f = os.path.join(pes or '', 'Player.bin')
    if not os.path.isfile(f): return None
    cid = {v.lower(): k for k, v in countries.items()}
    tko = {}
    for tid, lst in novi.items():
        c = cid.get(teams[tid].lower())
        if c is not None:
            for i, s_, n_ in lst: tko[i] = c
    raw = bytearray(PF.wesys(open(f, 'rb').read())); n = 0; prim = []; promj = []
    for k in range(len(raw) // D.REC):
        r = raw[k * D.REC:(k + 1) * D.REC]
        c = tko.get(struct.unpack_from('<I', r, 8)[0])
        if c is None: continue
        n1, n2 = D.getf(r, 29, 1, 9), D.getf(r, 28, 0, 9)
        if n1 == c: continue
        rec = D.apply_changes(bytearray(r), {'_nat': c, '_nat2': n1})
        raw[k * D.REC:(k + 1) * D.REC] = rec; n += 1
        prim.append('%s: %s -> %s' % (PF.cstr(r[68:129]), countries.get(n1, n1), countries.get(c, c)))
        promj.append({'id': struct.unpack_from('<I', r, 8)[0], 'ime': PF.cstr(r[68:129]), 'prije': countries.get(n1, str(n1)),
                      'sada': countries.get(c, str(c)), 'druga': countries.get(n1, str(n1))})
    os.makedirs(os.path.join(HERE, 'izvjestaji'), exist_ok=True)
    json.dump({'vrijeme': datetime.datetime.now().isoformat(timespec='seconds'), 'igraci': promj},
              open(os.path.join(HERE, 'izvjestaji', 'drzavljanstva_zadnje.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print('Drzavljanstvo prema reprezentaciji: promijenjeno kod %d igraca%s' % (n, (' (' + '; '.join(prim[:12]) + (' ...' if n > 12 else '') + ')') if n else ''), flush=True)
    return bytes(raw) if n else None

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import izvor as IZ, ocjene as OC, tm_podaci as TP, ugovori as UG
    cfg = IZ.use(IZ.cfg_from_opts(OPT))
    cfg, IZL = IZ.izlaz_iz_opts(OPT, cfg)
    db, src = D.load_files(D.NAMES)
    P, _, _ = D.load(); B = {p['id']: p for p in P}
    countries = D.countries_map(db['Country.bin'])
    teams, national = {}, set()
    T = db['Team.bin']
    for i in range(len(T) // 1532):
        r = T[i * 1532:(i + 1) * 1532]; tid = struct.unpack_from('<I', r, 8)[0]
        teams[tid] = PF.cstr(r[368:438])
        if PF.is_national(r, countries): national.add(tid)
    A = bytearray(db['PlayerAssignment.bin'])
    recs = [list(struct.unpack_from('<4I', A, i * 16)) for i in range(len(A) // 16)]
    squads = collections.defaultdict(list)
    for k, (a, pid, tid, x) in enumerate(recs):
        if tid in national: squads[tid].append(k)
    inNT = collections.defaultdict(set)
    for a, pid, tid, x in recs:
        if tid in national: inNT[pid].add(tid)

    # TM id <-> baza
    d2t = {d: t for d, t, o in json.load(open(os.path.join(IZ.mapa(cfg), 'tm_ids.json')))}
    try:
        for sid, e in json.load(open(os.path.join(IZ.mapa(cfg), 'rucne.json'), encoding='utf-8')).items():
            if e.get('tm_id'): d2t.setdefault(int(sid), e['tm_id'])
    except (OSError, ValueError): pass
    import ciscenje as CI
    brisani = set(CI.ucitaj(cfg))
    t2d = {t: d for d, t in d2t.items() if d not in brisani}
    I = UG._load(UG.F_IGR)
    ovr = live_ovr(IZL) or {p['id']: O.ovr(p['attr'], p['pos']) for p in P if p['pos'] != '?'}

    # 1. reprezentacija u bazi -> TM id (glasanje)
    votes = collections.defaultdict(collections.Counter)
    for tid, ks in squads.items():
        for k in ks:
            e = I.get(str(d2t.get(recs[k][1])))
            if e and e.get('repr'): votes[tid][e['repr']] += 1
    samo = {s.strip().lower() for s in OPT['samo'].split(',')} if isinstance(OPT.get('samo'), str) else None
    if isinstance(OPT.get('opseg'), str):        # opseg posla: samo reprezentacije navedene medu klubovima
        ok_ = set(json.load(open(OPT['opseg'], encoding='utf-8')).get('klubovi') or [])
        samo = {teams[t].lower() for t in ok_ if t in national} or {'__nijedna__'}
        print('Opseg: %d reprezentacija' % (len(samo) if '__nijedna__' not in samo else 0), flush=True)
    minf = float(OPT['min']) if isinstance(OPT.get('min'), str) else 0.5
    nt_map = {}
    for tid, c in votes.items():
        if samo and teams[tid].lower() not in samo: continue
        cid, n = c.most_common(1)[0]
        if n >= 3 and n >= 0.6 * sum(c.values()): nt_map[tid] = cid
    print('Reprezentacija u bazi: %d, povezano s TM-om: %d' % (len(squads), len(nt_map)), flush=True)

    by_nat = collections.defaultdict(list)
    for p in P: by_nat[p['nat_id']].append(p); by_nat[p.get('nat2_id')].append(p)
    rep, novi, RJ = [], {}, []
    for n_, (tid, cid) in enumerate(sorted(nt_map.items(), key=lambda x: teams[x[0]]), 1):
        sq = tm_squad(cid, 'osvjezi' in OPT)
        if not sq:
            rep.append('%-22s TM popis prazan - preskoceno' % teams[tid])
            RJ.append({'tim': teams[tid], 'id': tid, 'status': 'prazno', 'pozvanih': 0, 'u_bazi': 0}); continue
        old = [recs[k] for k in squads[tid]]
        old_ids = [r[1] for r in old]
        cnt = TP.country_id(teams[tid]) if hasattr(TP, 'country_id') else None
        found, miss = [], []
        for q in sq:
            pid = t2d.get(q['tm_id'])
            if pid is None and q.get('ime'):         # nije uparen: ime + godine + drzava
                tt = OC.toks(q['ime']); ea = TP.age_at(q['dob']) if q.get('dob') else q.get('god')
                c = [p for p in (by_nat.get(cnt) or P if cnt else []) if tt and tt[-1] in set(OC.toks(p['name']) + OC.toks(p['shirt']))
                     and OC.first_ok(tt, p) and (ea is None or abs(p['age'] - ea) <= 1)]
                if len(c) == 1: pid = c[0]['id']
            if pid in B and pid not in [f[0] for f in found]:
                other = inNT[pid] - {tid}
                if other and any(o not in nt_map for o in other):
                    miss.append('%s (u bazi za drugu reprezentaciju)' % q.get('ime')); continue
                found.append((pid, q))
            else:
                miss.append(q.get('ime') or str(q['tm_id']))
        if len(found) < minf * len(sq):
            rep.append('%-22s pronadeno %d/%d pozvanih - premalo, preskoceno' % (teams[tid], len(found), len(sq)))
            RJ.append({'tim': teams[tid], 'id': tid, 'status': 'premalo', 'pozvanih': len(sq), 'u_bazi': len(found), 'nema': miss}); continue
        # sastav = TOCNO zadnji TM poziv; najvise MAXS (sve reprezentacije u FL27 imaju 26)
        target = max(min(MAXS, len(sq)), MINS)          # u utakmicu ide 23 igraca - nikad manje (dopuna iz starog sastava)
        ids = [f[0] for f in found]
        if len(ids) > target:                        # siri popis (27-48): najboljih 26, barem 3 golmana
            gk = sorted([i for i in ids if B[i]['pos'] == 'GK'], key=lambda i: -ovr.get(i, 0))
            ost = sorted([i for i in ids if B[i]['pos'] != 'GK'], key=lambda i: -ovr.get(i, 0))
            ngk = min(len(gk), max(3, round(target * len(gk) / len(ids))))
            ids = gk[:ngk] + ost[:target - ngk]
        # dopuna iz starog sastava SAMO za pozvane koji ne postoje u bazi
        fill = sorted([i for i in old_ids if i not in ids and i in B], key=lambda i: -ovr.get(i, 0))
        while sum(B[i]['pos'] == 'GK' for i in ids) < 3 and any(B[i]['pos'] == 'GK' for i in fill):
            g = next(i for i in fill if B[i]['pos'] == 'GK'); ids.append(g); fill.remove(g)
        while len(ids) < target and fill: ids.append(fill.pop(0))
        while len(ids) > MAXS:                       # dopunjeni golman preko 26: makni najslabijeg ne-golmana
            ids.remove(min([i for i in ids if B[i]['pos'] != 'GK'], key=lambda i: ovr.get(i, 0)))
        # redoslijed u sastavu = kao u originalnoj bazi: po poziciji (GK, CB, LB, RB, DMF ... CF), pa po overallu.
        # (to NIJE prva postava - postavu igra slaze sama; u originalu su npr. prva tri mjesta uvijek golmani)
        order = sorted(ids, key=lambda i: (D.POS.index(B[i]['pos']) if B[i]['pos'] in D.POS else 99, -ovr.get(i, 0)))
        # brojevi: TM, pa stari, pa prvi slobodni
        tmn = {pid: q.get('broj') for pid, q in found}
        oldn = {r[1]: (r[3] & 0xff) + 1 for r in old}
        used, num = set(), {}
        for src_ in (tmn, oldn):
            for i in order:
                n = src_.get(i)
                if i not in num and n and 1 <= n <= 99 and n not in used: num[i] = n; used.add(n)
        for i in order:
            if i not in num:
                n = next(k for k in range(1, 100) if k not in used); num[i] = n; used.add(n)
        novi[tid] = [(i, s, num[i]) for s, i in enumerate(order)]
        izasli = [B[i]['name'] for i in old_ids if i not in order and i in B]
        usli = [B[i]['name'] for i in order if i not in old_ids]
        rep.append('%-22s %2d pozvanih, u bazi %2d | sastav %d | ulaze: %s | izlaze: %s%s' % (
            teams[tid], len(sq), len(found), len(order), ', '.join(usli) or '-', ', '.join(izasli) or '-',
            (' | nema u bazi: ' + ', '.join(miss)) if miss else ''))
        pj = lambda i: {'id': i, 'ime': B[i]['name'], 'poz': B[i]['pos'], 'ovr': ovr.get(i), 'klub': B[i]['club'] or 'bez kluba'}
        RJ.append({'tim': teams[tid], 'id': tid, 'status': 'promijenjeno' if (usli or izasli) else 'isto', 'pozvanih': len(sq), 'u_bazi': len(found),
                   'ulaze': [pj(i) for i in order if i not in old_ids], 'izlaze': [pj(i) for i in old_ids if i not in order and i in B],
                   'sastav': [dict(pj(i), broj=num[i], linija=grp(B[i]['pos'])) for i in order], 'nema': miss})

    # 3. novi PlayerAssignment: stari zapisi promijenjenih reprezentacija van, novi unutra (ID-evi zapisa se ponovno koriste)
    # ID zapisa se cuvaju: igrac koji ostaje u reprezentaciji zadrzava SVOJ zapis (na njega upucuje SpecialPlayerAssignment.bin),
    # novi igraci dobivaju slobodne ID-eve iste reprezentacije (od igraca koji su izasli), a tek onda nove
    keep = [r for r in recs if r[2] not in novi]
    nxt = max(r[0] for r in recs) + 1
    for tid, lst in novi.items():
        stari = {r[1]: r for r in recs if r[2] == tid}
        ostaju = {i for i, s_, n_ in lst}
        slobodni_ = sorted(r[0] for pid_, r in stari.items() if pid_ not in ostaju)
        for i, slot, n in lst:
            if i in stari:
                rid = stari[i][0]; vis = stari[i][3] >> 16 << 16          # visi bitovi (rijetke oznake) ostaju
            else:
                rid = slobodni_.pop(0) if slobodni_ else nxt
                if rid == nxt: nxt += 1
                vis = 0
            keep.append([rid, i, tid, vis | (slot << 10) | (n - 1)])
    keep.sort(key=lambda r: r[0])
    data = b''.join(struct.pack('<4I', *r) for r in keep)
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    os.makedirs(os.path.join(HERE, 'izvjestaji'), exist_ok=True)
    fr = os.path.join(HERE, 'izvjestaji', 'reprezentacije_%s.txt' % stamp)
    open(fr, 'w', encoding='utf-8').write('REPREZENTACIJE prema Transfermarktu (%s)\nPromijenjeno: %d\n\n%s\n' % (stamp, len(novi), '\n'.join(rep)))
    for t_ in squads:
        if t_ not in nt_map and (not samo or teams[t_].lower() in samo):
            RJ.append({'tim': teams[t_], 'id': t_, 'status': 'nepovezano', 'pozvanih': 0, 'u_bazi': 0})
    json.dump({'vrijeme': stamp, 'upisano': 'upisi' in OPT, 'timovi': sorted(RJ, key=lambda x: x['tim'])},
              open(os.path.join(HERE, 'izvjestaji', 'reprezentacije_zadnje.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    import lang as LG; LG.prevedi_datoteku(fr)
    print('Promijenjeno reprezentacija: %d (izvjestaj: %s)' % (len(novi), fr))
    if IZL:
        import spremanje as SP
        nove = {'PlayerAssignment.bin': data}
        pl = drzavljanstva(IZL, novi, teams, countries)
        if pl is not None: nove['Player.bin'] = pl
        SP.zapisi(IZL, nove, posao={'korak': 'reprezentacije', 'promijenjeno': len(novi)}, log=lambda s: print(s, flush=True))
    if 'upisi' in OPT:
        wesys_write(data, OUT); print('Upisano u igru:', OUT)
    else:
        print('(probni izracun - za upis u igru dodaj --upisi)')

if __name__ == '__main__':
    main()
