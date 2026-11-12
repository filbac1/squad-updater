# -*- coding: utf-8 -*-
"""
CISCENJE IGRACA BEZ KLUBA: umirovljeni (prema Transfermarktu) i duplikati -> popis za brisanje iz Player.bin.

    python ciscenje.py            -> izvjestaj + baze\\<id>\\brisanje.json (popis)
    python ciscenje.py --isprazni -> obrisi popis (nista se ne brise iz igre)

Brisanje u igri radi ocjene.py --upisi (ubaci_u_igru.bat) dok postoji brisanje.json (iskljuci s --bez-brisanja).
Brisu se SAMO igraci bez kluba i bez reprezentacije, i to:
  - UMIROVLJENI: TM profil kaze "Retired" (klub 123);
  - DUPLIKATI: isti TM igrac kao neki igrac iz baze koji ima klub/reprezentaciju (npr. stari zapis istog igraca).
Nikad se ne brisu legende: igraci istog imena kao netko u Classics / ML Default momcadima, i sami ti timovi.
Igraci koje TM uopce ne nade samo se navode u izvjestaju (mogu biti izmisljeni / regeni).
"""
import os, sys, json, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
LEG = ('Classics', 'ML Default')
RETIRED, WITHOUT = 123, 515

def datoteka(cfg):
    import izvor as IZ
    return os.path.join(IZ.mapa(cfg), 'brisanje.json')

def zadrzi_put(cfg):
    import izvor as IZ
    return os.path.join(IZ.mapa(cfg), 'zadrzi.json')

def zadrzi(cfg):
    """Igraci koje je korisnik rucno sacuvao - nikad se ne predlazu za brisanje."""
    try: return set(json.load(open(zadrzi_put(cfg), encoding='utf-8')))
    except (OSError, ValueError): return set()

def ucitaj(cfg):
    try: return {int(k): v for k, v in json.load(open(datoteka(cfg), encoding='utf-8')).items()}
    except (OSError, ValueError): return {}

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import izvor as IZ, fl27db as D, ugovori as UG, tm_api as A
    cfg = IZ.use(IZ.cfg_from_opts(OPT))
    f = datoteka(cfg)
    if 'isprazni' in OPT:
        if os.path.exists(f): os.remove(f)
        print('Popis za brisanje obrisan - sljedeci upis u igru vraca sve igrace.'); return
    P, _, _ = D.load(); B = {p['id']: p for p in P}
    legend_names = {p['name'].lower() for p in P if any(x in p['club'] for x in LEG)}
    mapa = IZ.mapa(cfg)
    # TM id svakog igraca iz baze: izracun po ligama + rucni popis + pojedinacno trazenje
    d2t = {}
    for d, t, o in json.load(open(os.path.join(mapa, 'tm_ids.json'))): d2t[d] = t
    for fn in ('rucne.json', 'bez_kluba_trazeno.json', 'bez_vrijednosti.json'):
        try: J = json.load(open(os.path.join(mapa, fn), encoding='utf-8'))
        except (OSError, ValueError): continue
        for k, v in J.items():
            t = v.get('tm_id') if isinstance(v, dict) else v
            if isinstance(t, int): d2t.setdefault(int(k), t)
    S = IZ.opseg_ids(OPT, P)
    slobodni = [p for p in P if not p['club_id'] and not p['nt'] and (S is None or p['id'] in S)]
    print('Igraca bez kluba i reprezentacije: %d (s TM id-em: %d)' % (len(slobodni), sum(1 for p in slobodni if p['id'] in d2t)), flush=True)
    I = UG._load(UG.F_IGR)
    need = [d2t[p['id']] for p in slobodni if p['id'] in d2t and str(d2t[p['id']]) not in I]
    if need:
        print('TM profil za %d igraca...' % len(need), flush=True)
        for k in range(0, len(need), 50):
            for d in A.players(need[k:k + 50]) or []: I[str(d['id'])] = UG.sazmi(d)
        json.dump(I, open(UG.F_IGR, 'w', encoding='utf-8'))
    po_tm = collections.defaultdict(list)
    for d, t in d2t.items():
        if d in B: po_tm[t].append(B[d])
    out, nema, stat = {}, [], collections.Counter()
    Z = zadrzi(cfg)
    for p in slobodni:
        if p['id'] in Z: stat['sacuvan rucno (ostaje)'] += 1; continue
        if p['name'].lower() in legend_names: stat['legenda (ostaje)'] += 1; continue
        t = d2t.get(p['id'])
        if t is None: nema.append(p); continue
        drugi = [q for q in po_tm[t] if q['id'] != p['id'] and (q['club_id'] or q['nt'])
                 and ({q['nat_id'], q.get('nat2_id')} & {p['nat_id'], p.get('nat2_id')}) - {0, None}   # ista drzava
                 and abs(q['age'] - p['age']) <= 2]                                             # i godine (imenjaci!)
        if drugi:
            q = drugi[0]
            out[p['id']] = 'duplikat: isti TM igrac kao %s (%s, id %d)' % (q['name'], q['club'] or 'reprezentacija', q['id'])
            stat['duplikat'] += 1; continue
        e = I.get(str(t)) or {}
        if e.get('klub') == RETIRED:
            out[p['id']] = 'umirovljen (Transfermarkt)'; stat['umirovljen'] += 1
        elif e.get('klub') == WITHOUT: stat['bez kluba i na TM-u (ostaje)'] += 1
        else: stat['TM: ima klub koji nije u bazi (ostaje)'] += 1
    if S is not None:                  # opseg: zadrzi stare stavke izvan opsega
        for k, v in ucitaj(cfg).items():
            if k not in S: out.setdefault(k, v)
    json.dump({str(k): v for k, v in sorted(out.items())}, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    fr = os.path.join(HERE, 'izvjestaji', 'ciscenje_%s.txt' % stamp)
    with open(fr, 'w', encoding='utf-8') as w:
        w.write('CISCENJE IGRACA BEZ KLUBA (%s)\n%s\n\nZA BRISANJE (%d):\n' % (stamp, dict(stat), len(out)))
        for k, v in sorted(out.items(), key=lambda x: B[x[0]]['name']):
            w.write('  %7d  %-30s %3d g.  %-18s %s\n' % (k, B[k]['name'], B[k]['age'], B[k]['nat'], v))
        w.write('\nNISU NADJENI NA TM-u ili jos nisu trazeni (%d, ostaju):\n' % len(nema))
        for p in sorted(nema, key=lambda p: p['name']):
            w.write('  %7d  %-30s %3d g.  %s\n' % (p['id'], p['name'], p['age'], p['nat']))
    import lang as LG; LG.prevedi_datoteku(fr)
    print('Za brisanje: %d  %s' % (len(out), dict(stat)))
    print('Popis: %s\nIzvjestaj: %s' % (f, fr))
    print('Brisanje u igri: ocjene.py --upisi / ubaci_u_igru.bat (iskljuci s --bez-brisanja; vrati sve: ciscenje.py --isprazni)')

if __name__ == '__main__':
    main()
