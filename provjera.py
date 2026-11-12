# -*- coding: utf-8 -*-
"""
PROVJERA SUSTAVA (regresijski testovi) - pokreni nakon svake promjene koda:

    python provjera.py          (ili pokreni_provjeru.bat)

Ne dira igru ni bazu: sve pise u privremenu mapu.
"""
import os, sys, csv, json, random, tempfile, traceback, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')
REZ = []

def test(naziv):
    def deco(fn):
        t = time.time()
        try:
            msg = fn() or ''
            REZ.append((True, naziv)); print('  OK    %-52s %s (%.1fs)' % (naziv, msg, time.time() - t), flush=True)
        except Exception as e:
            REZ.append((False, naziv)); print('  GRESKA %-51s %s' % (naziv, e), flush=True)
            traceback.print_exc(limit=2)
        return fn
    return deco

import fl27db as D, pes_overall as PO, izvor as IZ

@test('Formula igre = pesdb.net ocjene')
def _():
    n = ok = 0
    for l in open(os.path.join(HERE, 'razvoj', 'pesdb', 'data.jsonl'), encoding='utf-8'):
        r = json.loads(l)
        if r.get('pos') in D.POS and r.get('ovr') and all(r.get(a) is not None for a in D.ANAMES):
            n += 1; ok += PO.overall([r[a] for a in D.ANAMES], r['Weak Foot Accuracy'], D.POS.index(r['pos'])) == r['ovr']
    assert ok / n >= 0.995, '%d/%d' % (ok, n)
    return '%d/%d tocno' % (ok, n)

@test('Vektorska formula = obicna formula')
def _():
    import numpy as np
    rng = np.random.default_rng(1); A = rng.integers(40, 100, (3000, 25))
    for pos in range(13):
        for w in (1, 4):
            v = PO.overall_vec(A, w, pos); s = [PO.overall(a, w, pos) for a in A[:500]]
            assert list(v[:500]) == s, 'pozicija %d' % pos
    return '13 pozicija x 2'

IZ.use({'tip': 'igra'})
P, RAW, SRC = IZ.load_players()

@test('Baza se cita iz ORIGINALA (ne iz ocjene_tm\\izlaz)')
def _():
    db, src = D.PF.load_db(D.roots(), D.PF.game_cpks(), names=('Player.bin',))
    assert 'ocjene_tm' not in src['Player.bin'].lower(), src['Player.bin']
    return os.path.basename(src['Player.bin'])

@test('Player.bin: upis i citanje (atributi, godine, visina, drzave)')
def _():
    p = next(x for x in P if x['pos'] != '?' and x['age'] < 40)
    ch = {p['idx']: {'Speed': 77, 'Finishing': 41, '_age': p['age'] + 1, '_height': 181, '_nat': p['nat_id'], '_nat2': 0}}
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'Player.bin'); D.write_player_bin(RAW, ch, out)
        n = D.PF.wesys(open(out, 'rb').read())
    assert len(n) == len(RAW)
    r = n[p['idx'] * 312:(p['idx'] + 1) * 312]
    amap = {a: (b, s) for a, b, s in D.ATTR}
    assert D.getf(r, *amap['Speed'], 6, 40) == 77 and D.getf(r, *amap['Finishing'], 6, 40) == 41
    assert D.getf(r, 51, 0, 6, 15) == p['age'] + 1 and D.getf(r, 27, 0, 8, 100) == 181
    diff = sum(1 for i in range(0, len(RAW), 312) if RAW[i:i + 312] != n[i:i + 312])
    assert diff == 1, 'promijenjeno %d zapisa' % diff
    return 'samo 1 zapis promijenjen'

@test('CSV izvoz: format PES2020 Editora (281 stupac)')
def _():
    import izvoz_csv as X
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'b.csv'); n = IZ.export_csv(out, {}, {'tip': 'igra', 'id': 'igra'})
        R = list(csv.reader(open(out, encoding='utf-8-sig'), delimiter=';'))
    assert R[0] == X.HEADER and len(R[0]) == 281 and all(len(r) == 281 for r in R[1:200])
    assert open(os.path.join(HERE, 'editor_zaglavlje.txt'), encoding='utf-8-sig').read().strip().split(';') == R[0]
    # OverallStats = formula igre
    bad = sum(1 for r in R[1:3000] if r[13].isdigit() and int(r[13]) < 13 and
              int(r[150]) != PO.overall([int(x) for x in r[27:52]], int(r[53]), int(r[13])))
    assert bad == 0, '%d krivih OverallStats' % bad
    return '%d igraca' % n

@test('CSV predlozak: mijenjaju se samo dopusteni stupci')
def _():
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, 'src.csv'); IZ.export_csv(src, {}, {'tip': 'igra', 'id': 'igra'})
        rows = list(csv.reader(open(src, encoding='utf-8-sig'), delimiter=';'))
        small = os.path.join(td, 'mali.csv')
        with open(small, 'w', encoding='utf-8-sig', newline='') as f:
            csv.writer(f, delimiter=';', lineterminator='\r\n').writerows(rows[:300])
        pid = int(rows[5][0])
        out = os.path.join(td, 'out.csv')
        IZ.export_csv(out, {pid: {'Speed': 90, '_age': 30, '_height': 190}}, {'tip': 'csv', 'csv': small, 'id': 't'})
        A = list(csv.reader(open(small, encoding='utf-8-sig'), delimiter=';')); B = list(csv.reader(open(out, encoding='utf-8-sig'), delimiter=';'))
    cols = {i for a, b in zip(A, B) for i in range(len(a)) if a[i] != b[i]}
    assert cols <= set(range(27, 52)) | {150, 10, 8, 6, 7}, sorted(cols)
    assert B[5][37] == '90' and B[5][10] == '30' and B[5][8] == '190'
    return 'stupci %s' % sorted(cols)

@test('Uparivanje: imenjaci i krive godine (Hedlund, Kuhn)')
def _():
    import ocjene as OC, model_ea27 as ME
    idx = OC.build_index([p for p in P if p['pos'] != '?'])
    out = []
    for code, ime, tm_id in (('SE1', 'Simon Hedlund', 116900), ('L1', 'Nicolas Kühn', None)):
        f = ME.latest_leagues().get(code)
        if not f: out.append('%s: nema cache' % code); continue
        d = json.load(open(f, encoding='utf-8')); cmap = OC.map_clubs(d['players'], P)
        for q in d['players']:
            q['name'] = OC.T.clean(q['name'])
            if q['name'] == ime and (tm_id is None or q['tm_id'] == tm_id):
                m = OC.match_all(q, idx, cmap)
                assert m and max(m, key=lambda x: x[0])[1]['name'] == ime, '%s nije uparen ispravno: %s' % (ime, [(round(s, 2), p['name']) for s, p in m])
                out.append(ime)
    # imenjak iz istog kluba s istim imenom ne smije proci
    fake = {'name': 'Simon Nekitamo', 'club': 'IF Elfsborg', 'age': 33, 'height': 196, 'nat': 'Austria'}
    f = ME.latest_leagues().get('SE1')
    if f:
        d = json.load(open(f, encoding='utf-8')); cmap = OC.map_clubs(d['players'], P)
        assert not [p for s, p in OC.match_all(fake, idx, cmap) if p['name'] == 'Simon Hedlund' and s >= 1.3], 'imenjak prosao'
    return ', '.join(out)

@test('Pojedinacno trazenje: ime mora odgovarati, krive godine uz isti klub')
def _():
    import bez_kluba as BK
    p = {'name': 'Gian Ferrari', 'shirt': 'FERRARI', 'age': 32, 'nat': 'Italy', 'nat_id': None, 'club': 'SS Arezzo'}
    q = {'name': 'Alex Ferrari', 'age': 32, 'nat': ['Italy'], 'club': 'UC Sampdoria', 'value': 250000}
    assert BK.najbolji(p, [q])[0] is None, 'Alex Ferrari prihvacen za Gian Ferrari'
    import tm_podaci as TP
    it = TP.country_id('Italy')
    p = {'name': 'Davide Calabria', 'shirt': 'CALABRIA', 'age': 25, 'nat': 'Italy', 'nat_id': it, 'club': 'Panathinaikos FC'}
    q = {'name': 'Davide Calabria', 'age': 29, 'nat': ['Italy'], 'club': 'Panathinaikos', 'value': 3e6}
    assert BK.najbolji(p, [q])[0] is q, 'Calabria (krive godine u bazi) nije nadjen'
    q2 = {'name': 'Davide Calabria', 'age': 29, 'nat': ['Italy'], 'club': 'Neki Drugi Klub', 'value': 3e6}
    assert BK.najbolji(p, [q2])[0] is q2, 'jedinstveni igrac s istim imenom i drzavom (zastarjele godine) nije prihvacen'
    q3 = dict(q2, club='Treci Klub', age=27)
    assert BK.najbolji(p, [q2, q3])[0] is None, 'dva igraca istog imena: dvosmisleno, a prihvaceno'
    q4 = dict(q2, age=22)
    assert BK.najbolji(p, [q4])[0] is None, 'TM mladi od baze za 3 godine prihvacen'
    return '5/5'

@test('Pojedinacno trazenje (pravila 2): zastarjele godine, dulje TM ime, transliteracija, imenjaci')
def _():
    import bez_kluba as BK, tm_podaci as TP
    pp = lambda n, a, c: {'name': n, 'shirt': n.split()[-1].upper(), 'age': a, 'nat': c, 'nat_id': TP.country_id(c), 'club': ''}
    tq = lambda n, a, c, cl='', v=None: {'name': n, 'age': a, 'nat': [c], 'club': cl, 'value': v, 'tm_id': hash((n, a)) & 0xffffff}
    # baza zaostaje 2 godine + TM ima srednje ime (iz stvarnog uzorka)
    p = pp('Elías Ómarsson', 29, 'Iceland')
    a, b = tq('Elías Már Ómarsson', 31, 'Iceland', 'Víkingur', 5e5), tq('Orri Sigurdur Ómarsson', 31, 'Iceland', 'Valur', 1.5e5)
    assert BK.najbolji(p, [b, a])[0] is a, 'Elías Már Ómarsson nije nadjen'
    p = pp('Evan Eghosa', 19, 'Austria')
    q = tq('Evan Eghosa Aisowieren', 21, 'Austria', 'SV Ried', 4e5)
    assert BK.najbolji(p, [q])[0] is q, 'dulje TM ime (Aisowieren) nije nadjeno'
    p = pp('Karrar Amer', 27, 'Iraq'); q = tq('Kerrar Amer', 28, 'Iraq', 'Al-Karma', 4.5e5)
    assert BK.najbolji(p, [q])[0] is q, 'transliteracija Karrar/Kerrar nije prihvacena'
    # imenjaci s istim imenom i drzavom: dva podjednako dobra -> nitko
    p = pp('Marc Domenech', 24, 'Spain')
    assert BK.najbolji(p, [tq('Marc Domènech', 19, 'Spain', 'Atlético B', 1e6), tq('Marc Doménech', 24, 'Spain', 'FC Andorra', 7e5),
                           tq('Marc Domenech', 24, 'Spain', 'Manresa')])[0] is None, 'imenjaci iste dobi - dvosmisleno, a prihvaceno'
    # TM zapis bez godina ne smije se izjednaciti s pravim kandidatom
    p = pp('Antoine Gauthier', 21, 'France'); q = tq('Antoine Gauthier', 22, 'France', 'Le Puy', 3e5)
    assert BK.najbolji(p, [q, tq('Antoine Gauthier', None, 'France', 'Unknown')])[0] is q, 'Gauthier odbijen zbog TM zapisa bez godina'
    # druga drzava i velika razlika u godinama i dalje ne prolaze
    p = pp('Dan Casey', 27, 'Ireland')
    assert BK.najbolji(p, [tq('Dan Casey', 33, 'Scotland', 'X', 1e5)])[0] is None, 'druga drzava + 6 godina prihvaceno'
    return '6/6'

@test('Aplikacija: procjena posla sa svim opcijama (i trazenjem igraca)')
def _():
    import app_api as A
    E = A.procjena({'tip': 'sve'}, list(A.OPCIJE))
    assert E['minute'] > 0 and any('Transfermarkt' in k['n'] for k in E['koraci']), E
    return '%d koraka, %.0f min' % (len(E['koraci']), E['minute'])

@test('Pakiranje: aplikacija ima sve datoteke potrebne za izracun (bez ea27_upareni.json)')
def _():
    import re, tm_igrac as TI, numpy as np
    spec = open(os.path.join(HERE, 'SquadUpdater.spec'), encoding='utf-8').read()
    for f in ('ea27_kontekst.json', 'model_ea27.pkl', 'cache/ea_fc27.json'):
        assert "'%s'" % f in spec, f + ' se ne pakira'
    TI._FA = None; cm, lg = TI.kontekst_po_vrijednosti(np.log(2.0))
    assert 0 < cm < 5 and 0 < lg < 5, (cm, lg)
    return 'kontekst %.2f / %.2f' % (cm, lg)

@test('Najbolja postava: formacija iz TacticsFormation, golman na mjestu 0, rezervni golman prvi na klupi')
def _():
    import postave as PO, struct
    db, _ = D.load_files(('Team.bin', 'Tactics.bin', 'TacticsFormation.bin', 'Player.bin', 'PlayerAssignment.bin'))
    F = PO.formacije(db); assert len(F) > 700, len(F)
    T = db['Team.bin']; rm = next(struct.unpack_from('<I', T, i * 1532 + 8)[0] for i in range(len(T) // 1532) if D.PF.cstr(T[i * 1532 + 368:i * 1532 + 438]) == 'Real Madrid CF')
    assert [D.POS[u] for u in F[rm]] == ['GK', 'CB', 'CB', 'RB', 'LB', 'DMF', 'CMF', 'CMF', 'RWF', 'LWF', 'CF'], F[rm]
    I = PO.igraci(db['Player.bin']); A = db['PlayerAssignment.bin']
    ids = [struct.unpack_from('<4I', A, i * 16)[1] for i in range(len(A) // 16) if struct.unpack_from('<4I', A, i * 16)[2] == rm]
    n = PO.postava(ids, F[rm], I)
    assert sorted(n) == sorted(ids) and I[n[0]][2] == 0 and I[n[11]][2] == 0, 'golmani nisu na mjestu 0 / prvi na klupi'
    assert sum(I[i][2] == 0 for i in n[:11]) == 1, 'vise golmana u postavi'
    L = [PO.LINIJA[I[i][2]] for i in n]
    assert L[11:23] == sorted(L[11:23]) and L[23:] == sorted(L[23:]), 'klupa / izvan kadra nisu od golmana do napadaca'
    assert L[11:23].count(0) == 1, 'na klupi nije tocno jedan golman'
    best = lambda i: max(I[i][0][p] for p in range(13) if I[i][1][p] == 2)
    for l in range(1, 4):
        k = [best(i) for i, x in zip(n[11:23], L[11:23]) if x == l]; v = [best(i) for i, x in zip(n[23:], L[23:]) if x == l]
        assert not k or not v or min(k) >= max(v), 'izvan kadra je jaci igrac nego na klupi (linija %d)' % l
    data, k = PO.slozi(A, db['Player.bin'], db, samo={'real madrid cf'}, log=lambda s: None)
    assert k == 1 and len(data) == len(A), k
    return '4-3-3 Real Madrid, %d igraca' % len(ids)

@test('Imena s dijakritikom: rijec po rijec, velika slova, skracena imena se ne diraju')
def _():
    import imena as IM
    ok = [('Niko Galesic', 'Niko Galešić', 'Niko Galešić'), ('GALESIC', 'Niko Galešić', 'GALEŠIĆ'),
          ('Simun Hrgovic', 'Simun Hrgovic Šimun Hrgović', 'Šimun Hrgović'), ('Martin Odegaard', 'Martin Ødegaard', 'Martin Ødegaard'),
          ('Kerim Alici', 'Kerim Alıcı', 'Kerim Alıcı'), ('M. Ali Shaker', 'Mohammed Ali Shakir', 'M. Ali Shaker'),
          ('Salvador Ferrer', 'Salva Ferrer', 'Salvador Ferrer'), ('Luka Modrić', 'Luka Modric', 'Luka Modrić'),
          ('Duje Caleta-Car', 'Duje Ćaleta-Car', 'Duje Ćaleta-Car')]
    for a, src, b in ok:
        assert IM.popravi(a, src) == b, (a, src, IM.popravi(a, src))
    return '%d/%d' % (len(ok), len(ok))

@test('Uparivanje po ligama: samo prezime iz drugog kluba ne smije proci')
def _():
    import ocjene as OC
    t = OC.toks
    ok = [('Cristian Martinez', 'Christian Martínez', 'MARTINEZ'),
          ('Mukhammadkodir Khamraliev', 'M. Khamraliev', 'HAMRALIEV'), ("Georges-Kevin N'Koudou", "Georges N'Koudou", 'NKOUDOU'),
          ('Danilo', 'Danilo Santos', 'DANILO')]
    bad = [('Johannes Eggestein', 'Maximilian Eggestein', 'EGGESTEIN'), ('Pedro Gomes', 'João Gomes', 'JOÃO GOMES'),
           ('Igor Jesus', 'Geovane Jesus', 'GEOVANE')]
    for a, b, s in ok: assert OC.first_ok(t(a), {'name': b, 'shirt': s}), '%s / %s odbijen' % (a, b)
    for a, b, s in bad: assert not OC.first_ok(t(a), {'name': b, 'shirt': s}), '%s / %s prihvacen' % (a, b)
    return '%d/%d' % (len(ok) + len(bad), len(ok) + len(bad))

@test('Ugovori: posudba iz TM povijesti transfera, polja u Player.bin')
def _():
    import ugovori as UG, fl27db as D, datetime
    god = datetime.date.today().year + 1
    h = {'history': {'terminated': [], 'pending': [
        {'details': {'date': '%d-06-30T00:00:00+02:00' % god, 'contractUntilDate': '%d-06-30T00:00:00+02:00' % (god + 3)},
         'typeDetails': {'type': 'RETURNED_FROM_PREVIOUS_LOAN'}, 'transferSource': {'clubId': '430'}, 'transferDestination': {'clubId': '148'}},
        {'details': {'date': None}, 'typeDetails': {'type': 'STANDARD'}, 'transferSource': {'clubId': '1'}, 'transferDestination': {'clubId': '2'}}]}}
    r = UG.posudba(h, 430)
    assert r == (148, god * 10000 + 630, (god + 3) * 10000 + 630), r
    assert UG.posudba(h, 999) is None, 'posudba u krivom klubu'
    rec = bytearray(D.REC)
    D.apply_changes(rec, {'_ugovor': 20300630, '_posudba': 20270630, '_vlasnik': 173})
    assert (D.getf(rec, 12, 0, 27), D.getf(rec, 16, 0, 27), D.getf(rec, 4, 0, 32)) == (20300630, 20270630, 173)
    return 'Draguşin-tip posudbe, 3 polja'

@test('Spremanje: provjera nove baze i opseg posla')
def _():
    import spremanje as SP, ocjene as OC, fl27db as D, struct, json, tempfile
    rec = lambda pid: bytes(8) + struct.pack('<I', pid) + bytes(D.REC - 12)
    P = rec(1) + rec(2)
    A_ok = struct.pack('<4I', 1, 1, 100, 0) + struct.pack('<4I', 2, 2, 100, 0)
    A_bad = A_ok + struct.pack('<4I', 3, 99, 100, 0)
    assert SP.provjeri({'Player.bin': P, 'PlayerAssignment.bin': A_ok}) == []
    assert SP.provjeri({'Player.bin': P, 'PlayerAssignment.bin': A_bad}), 'igrac koji ne postoji prosao provjeru'
    assert SP.provjeri({'Player.bin': P + rec(2)}), 'duplicirani ID prosao provjeru'
    assert SP.provjeri({'Player.bin': P[:-1]}), 'kriva velicina prosla provjeru'
    pl = [{'idx': 0, 'id': 1, 'club_id': 10, 'league_code': 'X_D1_LEAGUE', 'country': ''},
          {'idx': 1, 'id': 2, 'club_id': 20, 'league_code': 'Y_D1_LEAGUE', 'country': ''},
          {'idx': 2, 'id': 3, 'club_id': None, 'league_code': '', 'country': ''}]
    f = os.path.join(tempfile.gettempdir(), 'opseg_test.json')
    json.dump({'lige': ['X_D1_LEAGUE'], 'igraci': [3]}, open(f, 'w'))
    assert OC.opseg(pl, {'opseg': f}) == {0, 2}
    assert OC.opseg(pl, {}) is None
    return '4 provjere baze, opseg lige+igraci'

@test('EA profil: atletski atributi iz EA, cilj tocno pogoden')
def _():
    import ea_atributi as EAP, ocjene as OC, overall as O
    assert EAP.model(), 'ea_atributi.json ne postoji'
    p = next(x for x in P if x['name'] == 'Erling Haaland')
    e = next(x for x in json.load(open(os.path.join(HERE, 'cache', 'ea_fc27.json'), encoding='utf-8')) if x['last'] == 'Haaland' and x['first'] == 'Erling')
    base, used = EAP.blend(p['attr'], e, False)
    assert used and base['Jump'] > p['attr']['Jump'] + 3, 'Haaland skok iz EA nije veci (%d -> %d)' % (p['attr']['Jump'], base['Jump'])
    new = OC.scale_to(dict(p, attr=base), 91, OC.ATLETSKI)
    assert O.ovr(new, p['pos']) == 91 and new['Jump'] == base['Jump'], 'cilj ili atletski atribut'
    return 'skok %d -> %d, OVR 91' % (p['attr']['Jump'], new['Jump'])

@test('EA dodaci: noga, slabija noga, pozicije, vjestine (Player.bin + CSV)')
def _():
    p = next(x for x in P if x['pos'] == 'CB' and not x['foot'] and 84 not in x['skills'] and x['pos_rating'][3] == 0)
    ch = {p['idx']: {'_foot': 1, '_wfu': 3, '_pos3': 2, '_sk84': 1}}
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'Player.bin'); D.write_player_bin(RAW, ch, out)
        n = D.PF.wesys(open(out, 'rb').read())
        r = n[p['idx'] * 312:(p['idx'] + 1) * 312]
        assert D.getf(r, 64, 2, 1) == 1 and D.getf(r, 56, 6, 2, 1) == 3 and D.getf(r, *D.POS_RATING[3], 2) == 2
        b, s, nm = D.SKILLS[84]; assert (r[b] >> s) & 1 == 1, nm
        # CSV predlozak
        src = os.path.join(td, 'src.csv'); IZ.export_csv(src, {}, {'tip': 'igra', 'id': 'igra'})
        rows = list(csv.reader(open(src, encoding='utf-8-sig'), delimiter=';'))
        i = next(k for k, x in enumerate(rows) if x[0] == str(p['id']))
        small = os.path.join(td, 'm.csv')
        with open(small, 'w', encoding='utf-8-sig', newline='') as f: csv.writer(f, delimiter=';', lineterminator='\r\n').writerows([rows[0], rows[i]])
        out2 = os.path.join(td, 'o.csv'); IZ.export_csv(out2, {p['id']: {'_foot': 1, '_wfu': 3, '_pos3': 2, '_sk84': 1}}, {'tip': 'csv', 'csv': small, 'id': 't'})
        B = list(csv.reader(open(out2, encoding='utf-8-sig'), delimiter=';'))[1]
    assert B[11] == 'True' and B[52] == '3' and B[17] == '2' and B[84] == 'True', (B[11], B[52], B[17], B[84])
    return '%s: noga, WF, RB=A, %s' % (p['name'], nm)

@test('Godine u bazi: referentni datum 1.1.2027.')
def _():
    import tm_podaci as TP, datetime
    assert TP.age_at('2008-02-22', datetime.date(2027, 1, 1)) == 18 and TP.age_at('2008-01-01', datetime.date(2027, 1, 1)) == 19
    return 'ok'

@test('Drzave: TM nazivi -> PES')
def _():
    import tm_podaci as TP
    for n in ('United States', 'Korea, South', 'Türkiye', 'Bosnia-Herzegovina', 'DR Congo', "Cote d'Ivoire", 'Croatia', 'England'):
        assert TP.country_id(n), n
    return '8/8'

@test('Formula TM -> overall (model) se ucitava i predvida')
def _():
    import model_ea27 as ME
    I = ME.load()['info']
    cm = {'Bayern': 4.0}
    a = ME.predict({'value': 100e6, 'age': 24, 'pos': 'Attacking Midfield', 'club': 'Bayern', 'tm_league': 'L1'}, cm, 3.0)
    b = ME.predict({'value': 1e6, 'age': 24, 'pos': 'Attacking Midfield', 'club': 'Bayern', 'tm_league': 'L1'}, cm, 3.0)
    assert 84 <= a <= 92 and b < a, (a, b)
    assert I['greska'] < 2.0
    return 'greska %.2f, 100M -> %.1f' % (I['greska'], a)

ok = sum(1 for r in REZ if r[0])
print('\n%d/%d testova proslo.' % (ok, len(REZ)))
sys.exit(0 if ok == len(REZ) else 1)
