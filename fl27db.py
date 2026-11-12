# -*- coding: utf-8 -*-
"""
Citanje/pisanje FL27 (PES21) baze igraca: atributi, pozicija, godine, klub, liga.

Raspored Player.bin (312 B po igracu) je iz tablice polja Ejogc327 PES2020 Editora,
provjeren na PES21 podacima s pesdb.net. Polje = ((u32 LE na bajtu b) >> pomak) & maska + dodatak.
"""
import os, sys, re, struct, zlib, collections, json

HERE = os.path.dirname(os.path.abspath(__file__))
SIDER = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import provjera_faca as PF          # kopija u ocjene_tm (mapa igre / sider.ini iz postavke.json)          # CPK citac, sider rootovi, load_db, cstr, is_national, nice_league

REC = 312
POS = ['GK', 'CB', 'LB', 'RB', 'DMF', 'CMF', 'LMF', 'RMF', 'AMF', 'LWF', 'RWF', 'SS', 'CF']
ATTR = [  # (naziv, bajt, pomak) - svi 6 bitova, +40
    ('Offensive Awareness', 46, 2), ('Ball Control', 35, 1), ('Dribbling', 44, 0), ('Tight Possession', 52, 0),
    ('Low Pass', 32, 7), ('Lofted Pass', 50, 2), ('Finishing', 49, 4), ('Heading', 36, 0), ('Place Kicking', 31, 2),
    ('Curl', 41, 4), ('Speed', 38, 2), ('Acceleration', 43, 0), ('Kicking Power', 44, 6), ('Jump', 36, 6),
    ('Physical Contact', 48, 6), ('Balance', 47, 0), ('Stamina', 42, 2), ('Defensive Awareness', 34, 3),
    ('Ball Winning', 39, 0), ('Aggression', 48, 0), ('GK Awareness', 40, 6), ('GK Catching', 45, 4),
    ('GK Clearing', 33, 5), ('GK Reflexes', 40, 0), ('GK Reach', 37, 4)]
ANAMES = [a[0] for a in ATTR]
GK_ATTR = ANAMES[20:]
POS_RATING = [(43, 6), (58, 4), (39, 6), (59, 2), (51, 6), (57, 0), (58, 2), (57, 4), (58, 0), (59, 0), (59, 4), (59, 6), (58, 6)]

def getf(r, b, s, w, add=0):
    return ((int.from_bytes(r[b:b + 4], 'little') >> s) & ((1 << w) - 1)) + add

def setf(r, b, s, w, val, add=0):
    """r = bytearray zapisa; upisuje vrijednost u bitovno polje."""
    v = int(val) - add
    if not 0 <= v < (1 << w):
        raise ValueError('vrijednost %s izvan polja' % val)
    x = int.from_bytes(r[b:b + 4], 'little')
    m = ((1 << w) - 1) << s
    x = (x & ~m) | (v << s)
    r[b:b + 4] = x.to_bytes(4, 'little')

BASE = None
IZLAZ = os.path.join(HERE, 'izlaz')

def roots():
    """Sider livecpk rootovi BEZ nasih mapa (stara izlazna mapa i mapa u koju se kopira u igru) - izracun uvijek
    krece od originalne baze igre, nikad od vlastitog rezultata."""
    van = {os.path.normcase(os.path.abspath(IZLAZ))}
    try:
        g = json.load(open(os.path.join(HERE, 'postavke.json'), encoding='utf-8')).get('igra_cilj')
        if g: van.add(os.path.normcase(os.path.abspath(g)))
    except (OSError, ValueError): pass
    return [r for r in PF.sider_roots() if os.path.normcase(os.path.abspath(r)) not in van]
NAMES = ('Player.bin', 'Team.bin', 'PlayerAssignment.bin', 'Country.bin', 'Competition.bin', 'CompetitionEntry.bin')

def set_base(path):
    """Citaj bazu iz mape (npr. ...\\common\\etc\\pesdb ili mapa koja ga sadrzi) umjesto aktivne baze igre."""
    global BASE
    for cand in (path, os.path.join(path, 'common', 'etc', 'pesdb'), os.path.join(path, 'etc', 'pesdb')):
        if os.path.isfile(os.path.join(cand, 'Player.bin')):
            BASE = cand; return cand
    raise SystemExit('U mapi %s nema Player.bin' % path)

def load_files(names):
    """(db, src) za zadane datoteke baze: iz odabrane mape (BASE) ili iz aktivne baze igre. Datoteke koje fale -> b''."""
    if BASE:
        db = {n: PF.wesys(open(os.path.join(BASE, n), 'rb').read()) if os.path.isfile(os.path.join(BASE, n)) else b'' for n in names}
        return db, {n: os.path.join(BASE, n) for n in names}
    return PF.load_db(roots(), PF.game_cpks(), names=tuple(names))

def countries_map(data=None):
    """id drzave -> naziv (iz Country.bin; ako nije zadan, iz aktivne baze igre)."""
    if data is None:
        try:
            db, _ = load_files(('Country.bin',)); data = db['Country.bin']
        except BaseException:
            return {}
    out = {}
    for i in range(len(data) // 1420):
        r = data[i * 1420:(i + 1) * 1420]
        out[(int.from_bytes(r[:8], 'little') >> 10) & 511] = PF.cstr(r[288:358]).title()
    return out

def load():
    """Vrati (players, raw_player_bin, izvor). players = lista dictova s atributima."""
    db, src = load_files(NAMES)   # vlastita mapa: datoteke koje fale (npr. Team.bin) -> prazno, igraci onda nemaju klub
    countries = {}
    d = db['Country.bin']
    for i in range(len(d) // 1420):
        r = d[i * 1420:(i + 1) * 1420]
        countries[(int.from_bytes(r[:8], 'little') >> 10) & 511] = PF.cstr(r[288:358]).title()
    teams, national, tcountry = {}, set(), {}
    d = db['Team.bin']
    for i in range(len(d) // 1532):
        r = d[i * 1532:(i + 1) * 1532]
        tid = struct.unpack_from('<I', r, 8)[0]
        teams[tid] = PF.cstr(r[368:438])
        if PF.is_national(r, countries): national.add(tid)
        tcountry[tid] = countries.get((int.from_bytes(r[70:74], 'little') >> 2) & 511, '?')
    comps = {}
    d = db['Competition.bin']
    for i in range(len(d) // 36):
        r = d[i * 36:(i + 1) * 36]; comps[r[5]] = PF.cstr(r[8:36])
    league = {}
    d = db['CompetitionEntry.bin']
    for i in range(len(d) // 12):
        tid, _, c = struct.unpack_from('<III', d, i * 12)
        n = comps.get(c & 0xff, '')
        if re.search(r'_D\d_LEAGUE$', n): league[tid] = n
    assign = collections.defaultdict(list)
    d = db['PlayerAssignment.bin']
    for i in range(len(d) // 16):
        _, pid, tid, _ = struct.unpack_from('<4I', d, i * 16); assign[pid].append(tid)
    raw = db['Player.bin']
    players = []
    for i in range(len(raw) // REC):
        r = raw[i * REC:(i + 1) * REC]
        pid = struct.unpack_from('<I', r, 8)[0]
        nat = int.from_bytes(r[28:36], 'little')
        clubs = [t for t in assign.get(pid, []) if t not in national]
        club = clubs[0] if clubs else None
        players.append({
            'idx': i, 'id': pid, 'name': PF.cstr(r[68:129]), 'shirt': PF.cstr(r[129:190]),
            'nat': countries.get((nat >> 9) & 511, '?'),
            'club_id': club, 'club': teams.get(club, '') if club else '',
            'league_code': league.get(club, '') if club else '',
            'league': PF.nice_league(league[club]) if club in league else ('Ostali klubovi (%s)' % tcountry.get(club, '?') if club else 'Bez kluba'),
            'country': tcountry.get(club, '') if club else '',
            'pos': POS[getf(r, 54, 2, 4)] if getf(r, 54, 2, 4) < 13 else '?',
            'pos_rating': [getf(r, b, s, 2) for b, s in POS_RATING],
            'age': getf(r, 51, 0, 6, 15), 'height': getf(r, 27, 0, 8, 100), 'weight': getf(r, 32, 0, 7, 30),
            'attr': {n: getf(r, b, s, 6, 40) for n, b, s in ATTR},
        })
        players[-1]['attr']['_wfa'] = getf(r, 57, 6, 2, 1)     # Weak Foot Accuracy (ulazi u overall)
        players[-1].update(foot=getf(r, 64, 2, 1), wfu=getf(r, 56, 6, 2, 1), rep=getf(r, 56, 3, 3, 1), inj=getf(r, 57, 2, 2, 1),
                           skills={c for c, (b, s, n) in SKILLS.items() if (r[b] >> s) & 1})
        players[-1].update(nat_id=(nat >> 9) & 511, nat2_id=nat & 511, nat2=countries.get(nat & 511, '') if nat & 511 else '',
                           nt=[tcountry.get(t, '?') for t in assign.get(pid, []) if t in national])
    return players, raw, src['Player.bin']

# posebna polja (osim atributa) koja smiju u changes: TM/EA podaci o igracu
SPEC = {'_age': (51, 0, 6, 15), '_height': (27, 0, 8, 100), '_nat': (29, 1, 9, 0), '_nat2': (28, 0, 9, 0),
        '_foot': (64, 2, 1, 0), '_wfu': (56, 6, 2, 1), '_wfa': (57, 6, 2, 1), '_rep': (56, 3, 3, 1), '_inj': (57, 2, 2, 1),
        # ugovori (ugovori.py): datumi yyyymmdd, vlasnik = ID kluba u bazi (u32)
        '_ugovor': (12, 0, 27, 0), '_posudba': (16, 0, 27, 0), '_vlasnik': (4, 0, 32, 0),
        # MarketValue (24 bita) - EKSPERIMENTALNO, jedinica nije potvrdena u igri (pise se u tisucama eura)
        '_vrijednost': (20, 0, 24, 0)}
for _i, (_b, _s) in enumerate(POS_RATING): SPEC['_pos%d' % _i] = (_b, _s, 2, 0)
# vjestine (stupci 58-105 u CSV-u editora): (bajt, bit) iz tablice editora
_T0 = json.load(open(os.path.join(HERE, 'editor_tablice.json')))['t0']
_HDR = open(os.path.join(HERE, 'editor_zaglavlje.txt'), encoding='utf-8-sig').read().strip().split(';')
SKILLS = {c: (_T0[c][0], _T0[c][1], _HDR[c]) for c in range(58, 106)}
for _c, (_b, _s, _n) in SKILLS.items(): SPEC['_sk%d' % _c] = (_b, _s, 1, 0)

def apply_changes(rec, ch):
    """rec = bytearray 312 B; ch = {atribut ili _age/_height/_nat/_nat2: vrijednost}."""
    amap = {n: (b, s) for n, b, s in ATTR}
    for n, v in ch.items():
        if n in amap:
            b, s = amap[n]; setf(rec, b, s, 6, max(40, min(99, int(v))), 40)
        elif n in SPEC:
            b, s, w, add = SPEC[n]; setf(rec, b, s, w, int(v), add)
    return rec

def write_player_bin(raw, changes, path, skip=()):
    """changes = {idx: {naziv_atributa: nova_vrijednost}}; skip = idx igraca koji se BRISU. Zapisuje WESYS Player.bin."""
    out = bytearray(raw)
    amap = {n: (b, s) for n, b, s in ATTR}
    for idx, ch in changes.items():
        rec = apply_changes(bytearray(out[idx * REC:(idx + 1) * REC]), ch)
        out[idx * REC:(idx + 1) * REC] = rec
    if skip:
        out = b''.join(out[i * REC:(i + 1) * REC] for i in range(len(out) // REC) if i not in skip)
    data = bytes(out)
    if path is None: return data                     # samo bajtovi (spremanje.py zapisuje i provjerava)
    comp = zlib.compress(data, 9)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(b'\xff\x10\x81WESYS' + struct.pack('<II', len(comp), len(data)) + comp)
    return path
