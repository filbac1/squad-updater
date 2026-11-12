# -*- coding: utf-8 -*-
"""
Pojedinacno trazenje igraca na Transfermarktu (ime, godine, drzavljanstvo) -> overall istom formulom
-> rucni popis te baze (baze\\<id>\\rucne.json, izvor 'auto').

    python bez_kluba.py                      -> igraci iz baze BEZ KLUBA (~3 s po igracu, nastavlja gdje je stao)
    python bez_kluba.py --neocijenjeni       -> SVI igraci koje zadnji izracun po ligama nije ocijenio
    python bez_kluba.py --reprezentacija     -> samo igraci bez kluba koji su u nekoj reprezentaciji
    python bez_kluba.py --limit=200          -> najvise 200 igraca u ovom pokretanju
    python bez_kluba.py --ponovi             -> ponovno trazi i one koji prosli put nisu nadjeni
    --niti=4 --razmak=0.5                    -> paralelne niti / najmanji razmak izmedu pretraga na TM webu (s)
    --baza=<mapa ili .cpk>  --csv-ulaz=<editor.csv>   -> vlastita baza (kao ocjene.py)
"""
import os, sys, json, struct, time
from difflib import SequenceMatcher as _SM

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import izvor as IZ
import tm_igrac as TI
import napredak as N
import ocjene as OC

OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
PRAVILA = 2         # verzija pravila uparivanja: kad se poveca, ponovno se traze i oni koji prosli put nisu nadjeni
MAX_SKOK = 8        # vise od ovoliko bodova promjene bez potvrde klubom -> 'za provjeru', ne automatski

def reprezentativci():
    import fl27db as D
    if IZ.CFG['tip'] == 'csv': return set()
    if D.BASE:
        f = os.path.join(D.BASE, 'PlayerAssignment.bin')
        d = D.PF.wesys(open(f, 'rb').read()) if os.path.isfile(f) else b''
    else:
        d = D.load_files(('PlayerAssignment.bin',))[0]['PlayerAssignment.bin']
    s = set()
    for i in range(len(d) // 16):
        _, pid, tid, _ = struct.unpack_from('<4I', d, i * 16); s.add(pid)
    return s

def nat_ok(p, q):
    """True/False/None: odgovara li drzavljanstvo s TM-a (bilo koje od njegovih) bazi."""
    import tm_podaci as TP
    if not q.get('nat') or not p.get('nat_id'): return None
    ids = {TP.country_id(x) for x in q['nat']}
    ids.discard(None)
    if not ids: return None
    return p['nat_id'] in ids or (p.get('nat2_id') or 0) in ids

def ime_ok(pl, ql):
    """Ako i baza i TM imaju ime + prezime, ime mora odgovarati (ili inicijal: 'J. Smith' = 'John Smith')."""
    if len(pl) < 2 or len(ql) < 2: return True
    first = ql[0]
    return first in pl or any(len(t) == 1 and first.startswith(t) for t in pl) or any(t.startswith(first) or first.startswith(t) for t in pl[:-1] if len(t) >= 3)

def tok_eq(a, b):
    """Isti token, ili ista rijec u drugoj transliteraciji (Karrar/Kerrar, Salim/Salem): >= 5 slova, razlika <= 1 slovo."""
    if a == b: return True
    if min(len(a), len(b)) < 5 or abs(len(a) - len(b)) > 1: return False
    return _SM(None, a, b).ratio() >= 0.8

def u(t, S): return any(tok_eq(t, x) for x in S)

def najbolji(p, cands):
    """Najbolji TM kandidat za igraca iz baze (nema kluba za potvrdu, pa strogo):
    - ime: TM prezime u imenu iz baze, ILI cijelo ime iz baze (>= 2 rijeci) sadrzano u duljem TM imenu
      (Evan Eghosa = Evan Eghosa Aisowieren); rijeci se usporeduju i uz jedno slovo razlike (Karrar/Kerrar)
    - ako oba imaju ime, i ime mora odgovarati (ime_ok)
    - godine: baza racuna na 1.1.2027.; razlika baza-TM 0 ili 1 (-1 uz istu/nepoznatu drzavu).
      Zapisi igraca bez kluba cesto su stari 2-3 godine -> uz CIJELO ime i ISTU drzavu dopusteno i TM do 3 godine stariji.
    - dva podjednako dobra razlicita kandidata -> nitko (imenjaci)"""
    pl = OC.toks(p['name'])
    tt = set(pl + OC.toks(p['shirt']))
    exact = [q for q in cands if len(pl) >= 2 and set(OC.toks(q['name'])) == set(pl) and nat_ok(p, q) is True]
    if len(exact) == 1 and exact[0].get('age') and p['age'] and -1 <= exact[0]['age'] - p['age'] <= 15:
        return exact[0], 1.9
    sc = []
    cijelo_q = lambda q: len(pl) >= 2 and all(u(t, set(OC.toks(q['name']))) for t in pl)
    # imenjak je svatko s istim imenom i drzavom cije godine nisu iskljucene (zapisi u bazi znaju kasniti i 4-6 godina)
    moguc = lambda q: not (q.get('age') and p['age']) or -6 <= p['age'] - q['age'] <= 1
    imenjaci = [q for q in cands if cijelo_q(q) and nat_ok(p, q) is True and moguc(q)]   # isto ime, drzava i moguce godine
    for q in cands:
        ql = OC.toks(q['name'])
        qt = set(ql)
        if not qt: continue
        ov = sum(1 for t in qt if u(t, tt)) / len(qt)
        sur = u(ql[-1], tt)
        cijelo = len(pl) >= 2 and all(u(t, qt) for t in pl)          # cijelo ime iz baze je u TM imenu
        if not (sur or ov == 1 or cijelo): continue
        if not ime_ok(pl, ql) and not cijelo: continue
        s = max(ov, 0.9 if cijelo else 0) + (0.3 if (sur or cijelo) else 0)
        n = nat_ok(p, q)
        same_club = bool(p.get('club') and q.get('club') and OC.club_sim(p['club'], q['club']) >= 0.5)
        d = (p['age'] - q['age']) if (q.get('age') and p['age']) else None
        puno = ov == 1 or cijelo
        if d is not None:
            if d in (0, 1): s += 0.3
            elif d == -1 and n is not False: pass
            elif -3 <= d <= -2 and puno and n is True: s -= 0.05                         # stari zapis u bazi
            elif ov == 1 and sur and n is True and same_club and abs(d) <= 15: s -= 0.1  # krive godine u bazi
            else: continue
        else: s -= 0.2                                                                 # TM ne zna godine
        if same_club: s += 0.5
        if n is True: s += 0.5
        elif n is False:
            if not (ov == 1 and d in (0, 1)): continue
            s -= 0.4
        if q.get('value'): s += 0.1
        tocno = (d is not None and -1 <= d <= 1) or same_club
        if len(imenjaci) > 1 and not tocno: continue        # vise imenjaka: zaostale godine nisu dovoljan dokaz
        sc.append((s, q))
    sc.sort(key=lambda x: -x[0])
    if not sc or sc[0][0] < 1.3: return None, (sc[0][0] if sc else 0)
    if len(sc) > 1 and sc[1][1].get('tm_id') != sc[0][1].get('tm_id') and sc[0][0] - sc[1][0] < 0.15:
        return None, sc[0][0]                                                            # imenjaci - ne pogadaj
    return sc[0][1], sc[0][0]

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    cfg = IZ.use(IZ.cfg_from_opts(OPT))
    DONE = os.path.join(IZ.mapa(cfg), 'bez_kluba_trazeno.json')
    print('Baza: %s' % IZ.opis(cfg), flush=True)
    B = TI.baza()
    if 'neocijenjeni' in OPT:
        f = os.path.join(IZ.mapa(cfg), 'ocijenjeni.json')
        rated = set(json.load(open(f))) if os.path.exists(f) else set()
        if not rated: print('Za ovu bazu jos nema izracuna po ligama - trazim sve igrace.', flush=True)
        P = [p for p in B['P'] if p['id'] not in rated]
    else:
        P = [p for p in B['P'] if not p['club_id']]
    # legende / lazni timovi (Classics, ML Default) - umirovljeni, TM nema trzisnu vrijednost
    P = [p for p in P if not any(x in (p.get('club') or '') for x in ('Classics', 'ML Default'))]
    if 'reprezentacija' in OPT:
        R = reprezentativci(); P = [p for p in P if p['id'] in R]
    ru = TI.rucne()
    done = json.load(open(DONE, encoding='utf-8')) if os.path.exists(DONE) else {}
    S = IZ.opseg_ids(OPT, B['P'])
    if S is not None: P = [p for p in P if p['id'] in S]; print('Opseg: %d igraca' % len(P), flush=True)
    VF = os.path.join(IZ.mapa(cfg), 'bez_kluba_pravila.json')
    stara = (json.load(open(VF)) if os.path.exists(VF) else {}).get('verzija', 1) < PRAVILA
    if stara and any(v is None for v in done.values()):
        print('Pravila uparivanja su poboljsana - ponovno trazim i igrace koji prosli put nisu nadjeni.', flush=True)
    ponovi = 'ponovi' in OPT or stara
    todo = [p for p in P if str(p['id']) not in ru and (str(p['id']) not in done or (ponovi and not done[str(p['id'])]))]
    todo.sort(key=lambda p: -p['ovr'])                     # najbolji prvi
    lim = int(OPT['limit']) if 'limit' in OPT else len(todo)
    print('Igraca za trazenje: %d, vec obradjeno: %d, sada: %d' % (len(P), len(P) - len(todo), min(lim, len(todo))), flush=True)
    ZP = os.path.join(IZ.mapa(cfg), 'za_provjeru.json')
    zp = json.load(open(ZP, encoding='utf-8')) if os.path.exists(ZP) else {}
    BV = os.path.join(IZ.mapa(cfg), 'bez_vrijednosti.json')        # nadjen na TM-u, ali bez vrijednosti (umirovljeni...)
    bv = json.load(open(BV, encoding='utf-8')) if os.path.exists(BV) else {}
    import threading
    from concurrent.futures import ThreadPoolExecutor
    lock = threading.Lock()
    st = {'nadjeno': 0, 'n': 0}
    TI.SLEEP = float(OPT.get('razmak', 0.3)) if isinstance(OPT.get('razmak'), str) else 0.3   # najvise ~2 pretrage/s prema TM-u
    TI.baza(); ME_ = __import__('model_ea27'); ME_.load()                                    # ucitaj jednom, prije niti

    def obradi(item):
        i, p = item
        try:
            cands = TI.trazi(p['name'])
            if not cands and p['shirt'] and p['shirt'].lower() != p['name'].lower():
                cands = TI.trazi(p['shirt'])
            q, s_ = najbolji(p, cands)
            if q is None:
                return i, p, None, 'nije nadjen na TM-u', None
            r = TI.izracun(q)
            if 'greska' in r:                           # npr. umirovljen: nema vrijednost, ali TM id se pamti (ciscenje.py)
                return i, p, None, r['greska'], q.get('tm_id')
            klub_ok = bool(p.get('club') and q.get('club') and OC.club_sim(p['club'], q['club']) >= 0.5)
            return i, p, q, r, klub_ok
        except SystemExit as e:
            return i, p, None, 'greska: %s' % e, None
        except Exception as e:
            return i, p, None, 'greska: %s: %s' % (type(e).__name__, e), None

    def zapisi(i, p, q, r, klub_ok):
        N.javi(i, lim)
        if q is None:
            done[str(p['id'])] = None
            if isinstance(klub_ok, int) and not isinstance(klub_ok, bool): bv[str(p['id'])] = klub_ok
            print('[%d/%d] %-26s %s' % (i, lim, p['name'], r), flush=True); return
        if abs(r['cilj'] - p['ovr']) > MAX_SKOK and not klub_ok:
            # velika promjena bez potvrde klubom -> mozda imenjak: ne dodaj, stavi na popis za provjeru
            zp[str(p['id'])] = {'db_ime': p['name'], 'db_ovr': p['ovr'], 'db_godine': p['age'], 'db_drzava': p['nat'],
                                'tm_id': r['tm_id'], 'tm_ime': r['name'], 'klub': r.get('club'), 'godine': r['age'],
                                'vrijednost': r['value'], 'cilj': r['cilj'], 'r': {k: r[k] for k in ('tm_id', 'name', 'club', 'value', 'age', 'pos', 'liga_kod', 'ea_pred', 'kontekst') if k in r} | {'visina': r.get('visina'), 'nat': r.get('nat')}}
            done[str(p['id'])] = 'provjera'
            print('[%d/%d] %-26s -> %s (%s) | %d -> %d  PROVJERI (nije dodano)' % (i, lim, p['name'], r['name'], r.get('club'), p['ovr'], r['cilj']), flush=True)
        else:
            TI.dodaj(p['id'], r, izvor='auto'); done[str(p['id'])] = q['tm_id']; st['nadjeno'] += 1
            print('[%d/%d] %-26s -> %s (%s, %s g., %.2f M) | %d -> %d' % (i, lim, p['name'], r['name'], r.get('club'),
                  r['age'], r['value'] / 1e6, p['ovr'], r['cilj']), flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(int(OPT.get('niti', 6)) if isinstance(OPT.get('niti'), str) else 6) as ex:
        for i, p, q, r, ko in ex.map(obradi, enumerate(todo[:lim], 1)):
            with lock:
                zapisi(i, p, q, r, ko); st['n'] += 1
                if st['n'] % 25 == 0:
                    json.dump(done, open(DONE, 'w', encoding='utf-8')); json.dump(zp, open(ZP, 'w', encoding='utf-8'), ensure_ascii=False)
                    json.dump(bv, open(BV, 'w', encoding='utf-8'))
                    print('   ... %d obradjeno, %.0f igraca/min' % (st['n'], st['n'] / (time.time() - t0) * 60), flush=True)
    nadjeno = st['nadjeno']
    json.dump(done, open(DONE, 'w', encoding='utf-8')); json.dump(zp, open(ZP, 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(bv, open(BV, 'w', encoding='utf-8'))
    if len(todo) <= lim: json.dump({'verzija': PRAVILA}, open(VF, 'w'))        # sve ponovljeno novim pravilima
    print('GOTOVO: nadjeno %d od %d. Rucni popis sada ima %d igraca.' % (nadjeno, min(lim, len(todo)), len(TI.rucne())), flush=True)

if __name__ == '__main__':
    main()
