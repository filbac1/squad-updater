# -*- coding: utf-8 -*-
"""
NAJBOLJA POSTAVA: slaze redoslijed igraca u svakoj momcadi tako da prvih 11 bude najbolja postava za formaciju momcadi.

    python postave.py --izlaz=<nova baza> [--samo=Croatia,Real Madrid CF] [--baza=...]

  Igra uzima prvih 11 igraca iz PlayerAssignment.bin (redni broj 0-10) i stavlja ih na mjesta 0-10 formacije
  (TacticsFormation.bin, prva taktika momcadi). Baze cesto imaju igrace poredane po poziciji (GK, GK, CB...),
  pa bi drugi golman igrao stopera. Ovdje se za svako mjesto u formaciji bira igrac s najvecom ocjenom na toj
  poziciji (iz NOVE baze), uz kaznu za poziciju koju ne igra dobro (B -3, C -15) i +2 na glavnoj poziciji; optimalno (madarska metoda).
  Klupa (mjesta 11-22): najbolji rezervni golman + barem 3 obrane, 3 veznih, 2 napadaca (najbolji), ostatak po ocjeni;
  poredano od golmana do napadaca;
  izvan kadra (23+): najslabiji iz svake linije, isto poredani. Brojevi dresa, kapetan i izvodaci
  prekida ostaju (vezani su uz igraca). Momcadi s manje od 11 igraca ili bez taktike se preskacu.
  Mijenja se SAMO redni broj u PlayerAssignment.bin.
"""
import os, sys, json, struct, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fl27db as D
import overall as O

PF = D.PF
KAZNA = {2: 0, 1: -3, 0: -15}          # ocjena pozicije A / B / C
KLUPA = 12                             # zamjene u kadru za utakmicu (23 = 11 + 12)
MIN_LINIJA = {1: 3, 2: 3, 3: 2}         # najmanje na klupi: obrana / vezni red / napad
LINIJA = [0, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3]   # GK | CB LB RB | DMF CMF LMF RMF AMF | LWF RWF SS CF
GLAVNA = 2                             # prednost igracu na njegovoj glavnoj poziciji (specijalist ispred svestranog)
SLOT_MASK = 0x3f << 10

def formacije(db):
    """team id -> [uloga (indeks u D.POS) za mjesta 0..10] iz prve taktike momcadi."""
    X = db['Tactics.bin']; F = db['TacticsFormation.bin']
    prva = {}
    for i in range(len(X) // 12):
        tac, team = struct.unpack_from('<II', X, i * 12)
        if team not in prva or tac < prva[team]: prva[team] = tac
    uloge = collections.defaultdict(dict)
    for i in range(len(F) // 12):
        tac, uloga = struct.unpack_from('<II', F, i * 12); idx = F[i * 12 + 10]
        if idx <= 10: uloge[tac][idx] = uloga
    out = {}
    for team, tac in prva.items():
        u = uloge.get(tac) or {}
        if len(u) == 11 and all(0 <= u[k] < len(D.POS) for k in range(11)) and u[0] == 0:
            out[team] = [u[k] for k in range(11)]
    return out

def igraci(praw):
    """player id -> (ocjene na svih 13 pozicija, ocjene pozicija A/B/C, registrirana pozicija)."""
    out = {}
    for i in range(len(praw) // D.REC):
        r = praw[i * D.REC:(i + 1) * D.REC]
        pos = D.getf(r, 54, 2, 4)
        if pos > 12: continue
        a = {n: D.getf(r, b, s, 6, 40) for n, b, s in D.ATTR}; a['_wfa'] = D.getf(r, 57, 6, 2, 1)
        ovr = [O.ovr(a, p) for p in D.POS]
        prof = [D.getf(r, b, s, 2) for b, s in D.POS_RATING]
        prof[pos] = 2
        out[struct.unpack_from('<I', r, 8)[0]] = (ovr, prof, pos)
    return out

def postava(ids, uloge, I):
    """ids = igraci momcadi, uloge = 11 uloga formacije -> novi redoslijed (prvih 11 = mjesta formacije)."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    ids = [i for i in ids if i in I]
    if len(ids) < 11: return None
    M = np.array([[I[i][0][u] + KAZNA[I[i][1][u]] + (GLAVNA if I[i][2] == u else 0) for u in uloge] for i in ids], dtype=float)
    rows, cols = linear_sum_assignment(-M)
    start = [None] * 11
    for r_, c_ in zip(rows, cols): start[c_] = ids[r_]
    ost = [i for i in ids if i not in start]
    best = lambda i: max(I[i][0][p] for p in range(13) if I[i][1][p] == 2)
    linija = lambda i: LINIJA[I[i][2]]
    po = {l: sorted([i for i in ost if linija(i) == l], key=lambda i: -best(i)) for l in range(4)}
    # klupa: najbolji rezervni golman + barem MIN_LINIJA iz svake linije (najbolji), ostatak najbolji po ocjeni
    kv = {0: min(1, len(po[0]))}
    mjesta = min(KLUPA - kv[0], sum(len(po[l]) for l in (1, 2, 3)))
    kv.update({l: min(MIN_LINIJA[l], len(po[l])) for l in (1, 2, 3)})
    while sum(kv[l] for l in (1, 2, 3)) > mjesta:            # mala momcad: smanji najvecu kvotu
        l = max((1, 2, 3), key=lambda l: kv[l]); kv[l] -= 1
    while sum(kv[l] for l in (1, 2, 3)) < mjesta:            # sljedece mjesto: najbolji preostali igrac iz bilo koje linije
        l = max((l for l in (1, 2, 3) if kv[l] < len(po[l])), key=lambda l: best(po[l][kv[l]]))
        kv[l] += 1
    red = lambda xs: sorted(xs, key=lambda i: (linija(i), I[i][2], -best(i)))    # od golmana do napadaca
    klupa = red([i for l in range(4) for i in po[l][:kv[l]]])
    van = red([i for l in range(4) for i in po[l][kv[l]:]])                      # najslabiji iz svake linije
    return start + klupa + van

def slozi(araw, praw, db, samo=None, log=print):
    """Vrati (novi PlayerAssignment bajtovi ili None, broj promijenjenih momcadi, opis)."""
    form = formacije(db)
    I = igraci(praw)
    recs = [list(struct.unpack_from('<4I', araw, i * 16)) for i in range(len(araw) // 16)]
    po = collections.defaultdict(list)
    for k, r in enumerate(recs): po[r[2]].append(k)
    T = db['Team.bin']; ime = {struct.unpack_from('<I', T, i * 1532 + 8)[0]: PF.cstr(T[i * 1532 + 368:i * 1532 + 438]) for i in range(len(T) // 1532)}
    n, bez = 0, 0
    for tid, ks in po.items():
        if samo and ime.get(tid, '').lower() not in samo: continue
        if tid not in form: bez += 1; continue
        ks.sort(key=lambda k: (recs[k][3] >> 10) & 0x3f)
        stari = [recs[k][1] for k in ks]
        novi = postava(stari, form[tid], I)
        if not novi or novi == stari or len(novi) != len(stari): continue
        mjesto = {pid: s for s, pid in enumerate(novi)}
        for k in ks: recs[k][3] = (recs[k][3] & ~SLOT_MASK) | (mjesto[recs[k][1]] << 10)
        n += 1
    log('Najbolja postava: slozeno %d momcadi (%d bez taktike u bazi preskoceno)' % (n, bez))
    if not n: return None, 0
    return b''.join(struct.pack('<4I', *r) for r in recs), n

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import izvor as IZ, spremanje as SP
    OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
    cfg = IZ.use(IZ.cfg_from_opts(OPT))
    izl = OPT.get('izlaz')
    if not isinstance(izl, str): raise SystemExit('Treba --izlaz=<nova baza>')
    pes = SP.citaj_iz(izl)
    if not pes: raise SystemExit('Nova baza jos ne postoji: %s' % izl)
    db, _ = D.load_files(('Team.bin', 'Tactics.bin', 'TacticsFormation.bin', 'PlayerAssignment.bin', 'Player.bin'))
    rd = lambda n: PF.wesys(open(os.path.join(pes, n), 'rb').read()) if os.path.isfile(os.path.join(pes, n)) else db[n]
    samo = {s.strip().lower() for s in OPT['samo'].split(',')} if isinstance(OPT.get('samo'), str) else None
    data, n = slozi(rd('PlayerAssignment.bin'), rd('Player.bin'), db, samo, log=lambda s: print(s, flush=True))
    if data is not None:
        SP.zapisi(izl, {'PlayerAssignment.bin': data}, posao={'korak': 'najbolja postava', 'promijenjeno': n}, log=lambda s: print(s, flush=True))

if __name__ == '__main__':
    main()
