# -*- coding: utf-8 -*-
"""
KATALOG IGRACA za pregled i filtere u aplikaciji (radi i za 200.000 igrača).

    python katalog.py [--izlaz=<mapa>]      -> baze\\<id>\\katalog.json

Jedan zapis po igraču: original (ulazna baza) + trenutni izlaz (ako postoji): klub, liga, država, reprezentacija,
pozicija, godine, stari/novi overall, ugovor/posudba (iz .bin), Transfermarkt (id, vrijednost), pravi face,
statusi (ručni popis, za provjeru, za brisanje, zaključan, promijenjen, obrisan u izlazu).
"""
import os, sys, json, glob, struct, time, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fl27db as D
import overall as O

FACE_DIR = 'Asset/model/character/face/real'

def _jl(p, d=None):
    try: return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError): return d

def datoteka(cfg):
    import izvor as IZ
    return os.path.join(IZ.mapa(cfg), 'katalog.json')

def zakljucani(cfg):
    import izvor as IZ
    return set(_jl(os.path.join(IZ.mapa(cfg), 'zakljucani.json'), []))

def lica(cfg):
    """ID-evi igrača koji imaju pravi face u ovoj bazi (livecpk/CPK za igru, mapa ili CPK za ostale)."""
    PF = D.PF
    if cfg['tip'] == 'igra':
        try: return set(PF.face_index(PF.sider_roots(), PF.game_cpks()))
        except Exception: return set()
    ids = set()
    if cfg['tip'] == 'mapa':
        for dp, dn, fn in os.walk(cfg['put']):
            if dp.replace('\\', '/').lower().endswith('face/real'):
                ids |= {int(d) for d in dn if d.isdigit()}; dn[:] = []
    elif cfg['tip'] == 'cpk':
        try:
            for row in PF.Cpk(cfg['put']).toc:
                dn = (row.get('DirName') or '').replace('\\', '/').strip('/')
                if dn.startswith(FACE_DIR + '/'):
                    x = dn[len(FACE_DIR) + 1:].split('/')[0]
                    if x.isdigit(): ids.add(int(x))
        except Exception: pass
    return ids

def _rec_info(r):
    pos = D.getf(r, 54, 2, 4)
    a = {n: D.getf(r, b, s, 6, 40) for n, b, s in D.ATTR}; a['_wfa'] = D.getf(r, 57, 6, 2, 1)
    return {'ovr': O.ovr(a, D.POS[pos]) if pos < 13 else None,
            'ugovor': D.getf(r, 12, 0, 27), 'posudba': D.getf(r, 16, 0, 27), 'vlasnik': D.getf(r, 4, 0, 32),
            'dob': D.getf(r, 51, 0, 6, 15)}

def izgradi(cfg=None, izlaz=None, log=print):
    import izvor as IZ, spremanje as SP
    t0 = time.time()
    cfg = IZ.use(cfg or IZ.aktivna())
    P, raw, _ = IZ.load_players(cfg)
    if raw is None: raise SystemExit('Katalog radi s .bin bazom (CSV baza nema klubove ni ugovore).')
    teams = {p['club_id']: p['club'] for p in P if p['club_id']}
    novi = {}
    pes = SP.citaj_iz(izlaz) if izlaz else None
    if pes:
        nb = D.PF.wesys(open(os.path.join(pes, 'Player.bin'), 'rb').read())
        for i in range(len(nb) // D.REC):
            r = nb[i * D.REC:(i + 1) * D.REC]; novi[struct.unpack_from('<I', r, 8)[0]] = r
    mapa = IZ.mapa(cfg)
    d2t = {}
    for e in _jl(os.path.join(mapa, 'tm_ids.json'), []): d2t[e[0]] = e[1]
    ru = _jl(os.path.join(mapa, 'rucne.json'), {})
    for k, v in ru.items():
        if v.get('tm_id'): d2t.setdefault(int(k), v['tm_id'])
    tmv = {}
    for f in glob.glob(os.path.join(HERE, 'cache', 'tm_*_20*.json')):
        d = _jl(f)
        if isinstance(d, dict):
            for q in d.get('players', []): tmv.setdefault(q['tm_id'], q.get('value'))
    for v in ru.values():
        if v.get('tm_id') and v.get('vrijednost'): tmv.setdefault(v['tm_id'], v['vrijednost'])
    zp = set(int(k) for k in _jl(os.path.join(mapa, 'za_provjeru.json'), {}))
    bv = set(int(k) for k in _jl(os.path.join(mapa, 'bez_vrijednosti.json'), {}))     # nadjen na TM-u, ali bez vrijednosti (umirovljen, amater)
    br = set(int(k) for k in _jl(os.path.join(mapa, 'brisanje.json'), {}))
    zk = zakljucani(cfg)
    log('Tražim face-ove…')
    fc = lica(cfg)
    out = []
    for p in P:
        r0 = raw[p['idx'] * D.REC:(p['idx'] + 1) * D.REC]
        i0 = _rec_info(r0)
        r1 = novi.get(p['id']) if pes else None
        i1 = _rec_info(r1) if r1 is not None else None
        cur = i1 or i0
        t = d2t.get(p['id'])
        st = []
        if not p['club_id']: st.append('bez_kluba')
        if cur['posudba']: st.append('posudba')
        if p['id'] not in fc: st.append('bez_facea')
        if t is None: st.append('bez_vrijednosti' if p['id'] in bv else 'nije_na_tm')
        if p['id'] in zp: st.append('sumnjivo')
        if str(p['id']) in ru: st.append('rucno')
        if p['id'] in br: st.append('za_brisanje')
        if p['id'] in zk: st.append('zakljucan')
        if pes and r1 is None: st.append('obrisan')
        if r1 is not None and r1 != r0: st.append('promijenjen')
        out.append({'id': p['id'], 'ime': p['name'], 'klub': p['club'], 'klub_id': p['club_id'], 'liga': p['league'],
                    'liga_k': p.get('league_code') or (('OSTALI:' + p['country']) if p['club_id'] else ''),
                    'drz': p['nat'], 'repr': p['nt'], 'poz': p['pos'], 'dob': cur['dob'],
                    'ovr0': i0['ovr'], 'ovr': cur['ovr'], 'ug': cur['ugovor'] or None, 'pos_do': cur['posudba'] or None,
                    'vlasnik': teams.get(cur['vlasnik']) if cur['vlasnik'] else None,
                    'tm': t, 'vr': tmv.get(t) if t else None, 'st': st})
    meta = {'vrijeme': time.strftime('%Y-%m-%dT%H:%M:%S'), 'izvor': IZ.opis(cfg), 'izlaz': izlaz if pes else None,
            'igraca': len(out), 'trajanje_s': round(time.time() - t0, 1)}
    f = datoteka(cfg)
    with open(f + '.novo', 'w', encoding='utf-8') as w: json.dump({'meta': meta, 'igraci': out}, w, ensure_ascii=False, separators=(',', ':'))
    os.replace(f + '.novo', f)
    log('Katalog: %d igrača (%.0f s) -> %s' % (len(out), time.time() - t0, f))
    return meta

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import izvor as IZ
    OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
    cfg = IZ.cfg_from_opts(OPT)
    izgradi(cfg, OPT.get('izlaz') if isinstance(OPT.get('izlaz'), str) else None, log=lambda s: print(s, flush=True))
