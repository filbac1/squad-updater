# -*- coding: utf-8 -*-
"""
Provjera faca po nacionalnostima - SP Football Life 2027

Prolazi po SVIM igracima iz baze igre (Player.bin), odredi im nacionalnost
(i drugu nacionalnost) i provjeri postoji li za njih "prava" faca:
  - u livecpk mapama koje su aktivne u sider.ini (cpk.root), ili
  - u CPK datotekama same igre (Data\\*.cpk, download\\*.cpk).

Koristenje (iz mape SiderAddons\\face_provjera, ili dvoklik na pokreni.bat):
    python provjera_faca.py                    -> svi igraci
    python provjera_faca.py CROATIA SERBIA     -> samo te drzave (engleski naziv, bilo koja velicina slova)
    python provjera_faca.py --liga=england     -> samo igraci iz liga koje sadrze "england"
                                                  (npr. --liga="england 1. liga", --liga="ostali klubovi (croatia)")
    python provjera_faca.py --bez-cpk          -> ne gleda CPK-ove igre, samo livecpk (brze)

Rezultat ide u mapu "izvjestaji" pokraj skripte:
    face_<datum>.txt  - sazetak po drzavama + popis igraca BEZ face po drzavama
    face_<datum>.csv  - svi igraci (otvara se u Excelu)
"""
import os, sys, struct, zlib, glob, csv, collections, datetime, re

HERE = os.path.dirname(os.path.abspath(__file__))
# Kopija iz face_provjera za aplikaciju (Squad Updater). Mapa igre i sider.ini dolaze iz postavke.json
# ("igra_dir", "sider_ini"); bez njih vrijedi raspored ove instalacije (ocjene_tm u SiderAddons u mapi igre).
def _postavke():
    try:
        import json
        return json.load(open(os.path.join(HERE, 'postavke.json'), encoding='utf-8'))
    except Exception:
        return {}
_P = _postavke()
SIDER_INI = _P.get('sider_ini') or os.path.join(os.path.dirname(HERE), 'sider.ini')
SIDER = os.path.dirname(SIDER_INI)
GAME = _P.get('igra_dir') or os.path.dirname(os.path.dirname(HERE))
FACE_DIR = 'Asset/model/character/face/real'

# ----------------------------------------------------------------- CPK citac
def _decrypt(b):
    m = 0x655f; o = bytearray(b)
    for i in range(len(o)):
        o[i] ^= m & 0xff; m = (m * 0x4115) & 0xffffffff
    return bytes(o)

def _utf(b):
    if b[:4] != b'@UTF':
        b = _decrypt(b)
    if b[:4] != b'@UTF':
        raise ValueError('nije @UTF tablica')
    size, = struct.unpack('>I', b[4:8]); t = b[8:8 + size]
    _, rows_off, str_off, data_off, _, ncol, rowlen, nrows = struct.unpack('>HHIIIHHI', t[:24])
    def s(o):
        e = t.index(b'\0', str_off + o); return t[str_off + o:e].decode('utf-8', 'replace')
    fm = {0: '>B', 1: '>b', 2: '>H', 3: '>h', 4: '>I', 5: '>i', 6: '>Q', 7: '>q', 8: '>f'}
    def rd(p, typ):
        if typ in fm:
            f = fm[typ]; n = struct.calcsize(f); return struct.unpack(f, t[p:p + n])[0], p + n
        if typ == 0xA:
            o, = struct.unpack('>I', t[p:p + 4]); return s(o), p + 4
        if typ == 0xB:
            o, l = struct.unpack('>II', t[p:p + 8]); return t[data_off + o:data_off + o + l], p + 8
        raise ValueError('nepoznat tip %x' % typ)
    cols = []; p = 24
    for _ in range(ncol):
        fl = t[p]; no, = struct.unpack('>I', t[p + 1:p + 5]); p += 5
        st, typ, const = fl & 0xf0, fl & 0x0f, None
        if st in (0x30, 0x70):
            const, p = rd(p, typ)
        cols.append((s(no), st, typ, const))
    rows = []
    for r in range(nrows):
        p = rows_off + r * rowlen; row = {}
        for name, st, typ, const in cols:
            if st == 0x50: v, p = rd(p, typ)
            elif st in (0x30, 0x70): v = const
            else: v = None
            row[name] = v
        rows.append(row)
    return rows

def _crilayla(c):
    unc_size, hdr_off = struct.unpack('<II', c[8:16])
    out = bytearray(unc_size + 0x100); out[:0x100] = c[0x10 + hdr_off:0x10 + hdr_off + 0x100]
    st = {'pos': len(c) - 0x100 - 1, 'pool': 0, 'left': 0}
    def get(n):
        v = 0; got = 0
        while got < n:
            if st['left'] == 0:
                st['pool'] = c[st['pos']]; st['left'] = 8; st['pos'] -= 1
            take = min(st['left'], n - got)
            v = (v << take) | ((st['pool'] >> (st['left'] - take)) & ((1 << take) - 1))
            st['left'] -= take; got += take
        return v
    end = 0x100 + unc_size; wp = end - 1
    while wp >= 0x100:
        if get(1):
            ref = wp + 3 + get(13); length = 3; lvl = 0; vle = [2, 3, 5, 8]
            while True:
                bits = vle[min(lvl, 3)]; v = get(bits); length += v
                if v != (1 << bits) - 1: break
                lvl += 1
            for _ in range(length):
                out[wp] = out[ref]; wp -= 1; ref -= 1
        else:
            out[wp] = get(8); wp -= 1
    return bytes(out[:end])

class Cpk:
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        h = self.f.read(16)
        if h[:4] != b'CPK ':
            raise ValueError('nije CPK')
        hs, = struct.unpack('<I', h[8:12])
        hdr = _utf(self.f.read(hs))[0]
        toc_off = hdr['TocOffset']; content = hdr['ContentOffset']
        self.f.seek(toc_off); th = self.f.read(16); ts, = struct.unpack('<I', th[8:12])
        self.toc = _utf(self.f.read(ts))
        self.add = min(toc_off, content) if content else toc_off

    def read(self, row):
        self.f.seek(row['FileOffset'] + self.add); d = self.f.read(row['FileSize'])
        if d[:8] == b'CRILAYLA':
            d = _crilayla(d)
        return d

def _norm(p):
    return (p or '').replace('\\', '/').strip('/')

# ----------------------------------------------------------------- baza
def wesys(b):
    if b[3:8] != b'WESYS':
        return b
    cs, us = struct.unpack('<II', b[8:16])
    return zlib.decompress(b[16:16 + cs])

def sider_roots():
    roots = []
    ini = SIDER_INI
    if not os.path.isfile(ini): return roots
    for line in open(ini, encoding='utf-8', errors='replace'):
        line = line.split(';', 1)[0].strip()
        m = re.match(r'cpk\.root\s*=\s*"(.*)"', line)
        if m:
            p = m.group(1)
            roots.append(os.path.normpath(p if os.path.isabs(p) else os.path.join(SIDER, p)))
    return roots

def game_cpks():
    out = []
    for sub in ('Data', 'download'):
        out += sorted(glob.glob(os.path.join(GAME, sub, '*.cpk')))
    return out

def load_db(roots, cpks, names=('Player.bin', 'Team.bin', 'PlayerAssignment.bin', 'Country.bin',
                                'Competition.bin', 'CompetitionEntry.bin')):
    db, src = {}, {}
    # 1) livecpk ima prednost (prvi root u sider.ini pobjeduje)
    for r in roots:
        for n in names:
            p = os.path.join(r, 'common', 'etc', 'pesdb', n)
            if n not in db and os.path.isfile(p):
                db[n] = open(p, 'rb').read(); src[n] = p
    # 2) CPK igre: download ima prednost pred Data, noviji pred starijim
    if len(db) < len(names):
        order = sorted(cpks, key=lambda p: (os.path.basename(os.path.dirname(p)).lower() == 'download',
                                            os.path.getmtime(p)), reverse=True)
        for path in order:
            try:
                c = Cpk(path)
            except Exception:
                continue
            for row in c.toc:
                n = row.get('FileName')
                if n in names and n not in db and _norm(row.get('DirName')) == 'common/etc/pesdb':
                    db[n] = c.read(row); src[n] = path
            if len(db) == len(names):
                break
    miss = [n for n in names if n not in db]
    if miss:
        sys.exit('Database files not found (%s). Open Settings and set the game folder and sider.ini, or use "Change database" to open a database folder or CPK.' % ', '.join(miss))
    return {k: wesys(v) for k, v in db.items()}, src

def cstr(b):
    return b.split(b'\0')[0].decode('utf-8', 'replace').strip()

def nice_league(name):
    # ENGLAND_D1_LEAGUE -> England 1. liga
    return name.replace('_LEAGUE', '').replace('_', ' ').title().replace(' D1', ' 1. liga').replace(' D2', ' 2. liga')

def is_national(team_rec, countries):
    """reprezentacija = oznaka u Team.bin (bajt 1315 bit 6) ILI ime momcadi = ime drzave
    (neke repke, npr. Haiti, Belarus, San Marino, UAE, nemaju oznaku)"""
    if (team_rec[1315] >> 6) & 1:
        return True
    names = getattr(is_national, '_names', None)
    if names is None or is_national._src is not countries:
        is_national._names = names = {v.lower() for v in countries.values()}
        is_national._src = countries
    return cstr(team_rec[368:438]).lower() in names

def parse_db(db):
    # Country.bin: zapis 1420 B, ID = bitovi 10..18, engleski naziv na 288
    countries = {}
    d = db['Country.bin']
    for i in range(len(d) // 1420):
        r = d[i * 1420:(i + 1) * 1420]
        cid = (int.from_bytes(r[:8], 'little') >> 10) & 511
        countries[cid] = cstr(r[288:358]).title()
    # Team.bin: zapis 1532 B, ID na 8, engleski naziv na 368, reprezentacija = bajt 1315 bit 6
    teams, national, tcountry = {}, set(), {}
    d = db['Team.bin']
    for i in range(len(d) // 1532):
        r = d[i * 1532:(i + 1) * 1532]
        tid = struct.unpack_from('<I', r, 8)[0]
        teams[tid] = cstr(r[368:438])
        if is_national(r, countries):
            national.add(tid)
        tcountry[tid] = countries.get((int.from_bytes(r[70:74], 'little') >> 2) & 511, '?')
    # Liga kluba: Competition.bin (zapis 36 B, ID = bajt 5, naziv na 8) + CompetitionEntry.bin (12 B: momcad, -, natjecanje)
    comps = {}
    d = db['Competition.bin']
    for i in range(len(d) // 36):
        r = d[i * 36:(i + 1) * 36]
        comps[r[5]] = cstr(r[8:36])
    league = {}
    d = db['CompetitionEntry.bin']
    for i in range(len(d) // 12):
        tid, _, c = struct.unpack_from('<III', d, i * 12)
        n = comps.get(c & 0xff, '')
        if re.search(r'_D\d_LEAGUE$', n):
            league[tid] = nice_league(n)
    def team_league(tid):
        return league.get(tid) or 'Ostali klubovi (%s)' % tcountry.get(tid, '?')
    # PlayerAssignment.bin: zapis 16 B (id, igrac, momcad, ...)
    assign = collections.defaultdict(list)
    d = db['PlayerAssignment.bin']
    for i in range(len(d) // 16):
        _, pid, tid, _ = struct.unpack_from('<4I', d, i * 16)
        assign[pid].append(tid)
    # Player.bin: zapis 312 B, ID na 8, ime na 68; na 28: bitovi 9..17 nacionalnost, 0..8 druga
    players = []
    d = db['Player.bin']
    for i in range(len(d) // 312):
        r = d[i * 312:(i + 1) * 312]
        pid = struct.unpack_from('<I', r, 8)[0]
        nat = int.from_bytes(r[28:36], 'little')
        n1, n2 = (nat >> 9) & 511, nat & 511
        club_ids = [t for t in assign.get(pid, []) if t not in national]
        players.append({
            'league': ', '.join(sorted({team_league(t) for t in club_ids})) or 'Bez kluba',
            'id': pid, 'name': cstr(r[68:129]),
            'nat': countries.get(n1, 'Nepoznato (%d)' % n1),
            'nat2': countries.get(n2, '') if n2 else '',
            'clubs': [teams.get(t, str(t)) for t in assign.get(pid, []) if t not in national],
            'nteams': [teams.get(t, str(t)) for t in assign.get(pid, []) if t in national],
        })
    return players

# ----------------------------------------------------------------- face
def face_index(roots, cpks):
    """vraca {player_id: izvor} - prvi pronadeni izvor (livecpk ima prednost)"""
    faces = {}
    for r in roots:
        base = os.path.join(r, *FACE_DIR.split('/'))
        if not os.path.isdir(base):
            continue
        label = os.path.relpath(r, os.path.join(SIDER, 'livecpk'))
        for d in os.listdir(base):
            if d.isdigit() and int(d) not in faces and \
               os.path.isfile(os.path.join(base, d, '#Win', 'face.fpk')):
                faces[int(d)] = 'livecpk\\' + label
    for path in cpks:
        try:
            c = Cpk(path)
        except Exception as e:
            print('  ! preskacem %s (%s)' % (os.path.basename(path), e))
            continue
        label = os.path.basename(path)
        for row in c.toc:
            dn = _norm(row.get('DirName'))
            if dn.startswith(FACE_DIR + '/') and row.get('FileName') == 'face.fpk':
                pid = dn[len(FACE_DIR) + 1:].split('/')[0]
                if pid.isdigit() and int(pid) not in faces:
                    faces[int(pid)] = label
    return faces

# ----------------------------------------------------------------- main
def main():
    args = sys.argv[1:]
    use_cpk = '--bez-cpk' not in args
    only = {a.upper() for a in args if not a.startswith('--')}
    lig = [a.split('=', 1)[1].lower() for a in args if a.lower().startswith('--liga=')]

    roots = sider_roots()
    cpks = game_cpks()
    print('Aktivne livecpk mape (sider.ini):')
    for r in roots: print('   ', r)
    print('Citam bazu igraca...')
    db, src = load_db(roots, cpks)
    print('   baza iz:', src['Player.bin'])
    players = parse_db(db)
    print('   igraca u bazi:', len(players))
    print('Trazim face%s...' % ('' if use_cpk else ' (samo livecpk)'))
    faces = face_index(roots, cpks if use_cpk else [])
    print('   pronadeno face:', len(faces))

    if only:
        players = [p for p in players if p['nat'].upper() in only or (p['nat2'] and p['nat2'].upper() in only)]
        print('   filtrirano na:', ', '.join(sorted(only)), '->', len(players), 'igraca')
    if lig:
        players = [p for p in players if any(l in p['league'].lower() for l in lig)]
        print('   filtrirano na ligu:', ', '.join(lig), '->', len(players), 'igraca')

    for p in players:
        p['face'] = faces.get(p['id'], '')

    outdir = os.path.join(HERE, 'izvjestaji'); os.makedirs(outdir, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    if only or lig:
        stamp += '_' + '_'.join(re.sub(r'\W+', '', c.title()) for c in sorted(only) + lig)[:60]
    k = lambda s: s.lower()

    with open(os.path.join(outdir, 'face_%s.csv' % stamp), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['ID', 'Igrac', 'Nacionalnost', 'Druga nacionalnost', 'Klub', 'Liga', 'Reprezentacija', 'Ima facu', 'Izvor face'])
        for p in sorted(players, key=lambda p: (k(p['nat']), k(p['name']))):
            w.writerow([p['id'], p['name'], p['nat'], p['nat2'], ', '.join(p['clubs']), p['league'], ', '.join(p['nteams']),
                        'DA' if p['face'] else 'NE', p['face']])

    by = collections.defaultdict(list); by2 = collections.defaultdict(list)
    for p in players:
        by[p['nat']].append(p)
        if p['nat2']: by2[p['nat2']].append(p)
    allc = sorted(set(by) | set(by2), key=k)
    if only:
        allc = [c for c in allc if c.upper() in only]

    with open(os.path.join(outdir, 'face_%s.txt' % stamp), 'w', encoding='utf-8-sig') as f:
        tot = len(players); hf = sum(1 for p in players if p['face'])
        f.write('PROVJERA FACA PO NACIONALNOSTIMA  (%s)\n' % datetime.datetime.now().strftime('%d.%m.%Y. %H:%M'))
        f.write('Baza: %s\n' % src['Player.bin'])
        f.write('Ukupno igraca: %d   s facom: %d   bez face: %d   (%.1f %% pokriveno)\n\n' % (tot, hf, tot - hf, 100.0 * hf / max(tot, 1)))
        f.write('=== SAZETAK (po prvoj nacionalnosti) ===\n')
        f.write('%-32s %7s %7s %7s %7s\n' % ('Drzava', 'Igraca', 'S facom', 'Bez', '%'))
        for c in sorted(by, key=lambda c: (-len(by[c]), k(c))):
            if only and c.upper() not in only: continue
            n = len(by[c]); h = sum(1 for p in by[c] if p['face'])
            f.write('%-32s %7d %7d %7d %6.0f%%\n' % (c[:32], n, h, n - h, 100.0 * h / n))
        byl = collections.defaultdict(list)
        for p in players: byl[p['league']].append(p)
        f.write('\n\n=== SAZETAK PO LIGAMA ===\n')
        f.write('%-40s %7s %7s %7s %7s\n' % ('Liga', 'Igraca', 'S facom', 'Bez', '%'))
        main_l = sorted([l for l in byl if not l.startswith(('Ostali', 'Bez'))], key=k)
        rest_l = sorted([l for l in byl if l.startswith('Ostali')], key=lambda l: (-len(byl[l]), k(l)))
        for l in main_l + rest_l + [l for l in byl if l == 'Bez kluba']:
            n = len(byl[l]); h = sum(1 for p in byl[l] if p['face'])
            f.write('%-40s %7d %7d %7d %6.0f%%\n' % (l[:40], n, h, n - h, 100.0 * h / n))
        f.write('\n\n=== IGRACI BEZ FACE ===\n')
        for c in allc:
            m1 = sorted([p for p in by.get(c, []) if not p['face']], key=lambda p: k(p['name']))
            m2 = sorted([p for p in by2.get(c, []) if not p['face']], key=lambda p: k(p['name']))
            if not m1 and not m2: continue
            f.write('\n%s  (bez face: %d%s)\n' % (c, len(m1), ', + %d s drugom nacionalnoscu' % len(m2) if m2 else ''))
            for p in m1:
                f.write('   %7d  %-30s %-28s %s\n' % (p['id'], p['name'], ', '.join(p['clubs']) or '-', p['league']))
            if m2:
                f.write('   -- druga nacionalnost --\n')
                for p in m2:
                    f.write('   %7d  %-30s %-28s %s  (%s)\n' % (p['id'], p['name'], ', '.join(p['clubs']) or '-', p['league'], p['nat']))

    print('\nGotovo. Izvjestaj:', outdir)
    print('   face_%s.txt  i  face_%s.csv' % (stamp, stamp))

if __name__ == '__main__':
    main()
