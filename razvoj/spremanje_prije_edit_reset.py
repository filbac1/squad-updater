# -*- coding: utf-8 -*-
"""
SPREMANJE U NOVU MAPU: cijela ulazna baza (sve datoteke iz pesdb + PlayerAppearance) u istoj strukturi,
s promijenjenim .bin datotekama, i provjera prije nego se ista zapise.

    pripremi(izlaz, od_originala=True)   -> kopira ulaznu bazu u izlaznu mapu (sirove datoteke, nepromijenjene)
    zapisi(izlaz, {'Player.bin': bytes, ...}) -> provjeri pa zapise promijenjene (WESYS); vraca popis putanja
    citaj_iz(izlaz)                      -> pesdb mapa izlaza (za "krenuti od zadnjeg izlaza")

Ulazna baza se nikad ne mijenja. Ako je izlazna mapa = ulazna, odbija.
"""
import os, sys, json, struct, zlib, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fl27db as D

REL_PESDB = os.path.join('common', 'etc', 'pesdb')
REL_APP = os.path.join('common', 'character0', 'model', 'character', 'appearance')
APP = 'PlayerAppearance.bin'
OZNAKA = 'baza_info.json'          # u izlaznoj mapi: odakle je, kad, kojim poslovima

def _norm(p): return os.path.normcase(os.path.abspath(p))

def _wesys_pack(data):
    comp = zlib.compress(bytes(data), 9)
    return b'\xff\x10\x81WESYS' + struct.pack('<II', len(comp), len(data)) + comp

# ------------------------------------------------------------------ ulazne datoteke
def ulazne(cfg):
    """{relativna_putanja_u_izlazu: ('datoteka', putanja) | ('cpk', cpk_putanja, row)} za sve datoteke baze."""
    import izvor as IZ
    out = {}
    if cfg['tip'] in ('mapa', 'cpk'):
        pes = IZ.pesdb_dir(cfg)
        root = os.path.join(IZ.BAZE, cfg['id']) if cfg['tip'] == 'cpk' else cfg['put']
        rel = os.path.relpath(pes, root)
        rel = REL_PESDB if rel.startswith('..') or rel == '.' else rel
        for f in os.listdir(pes):
            if os.path.isfile(os.path.join(pes, f)): out[os.path.join(rel, f)] = ('datoteka', os.path.join(pes, f))
        a = IZ.appearance_file(cfg)
        if a:
            ra = os.path.relpath(a, root)
            out[ra if not ra.startswith('..') else os.path.join(REL_APP, APP)] = ('datoteka', a)
        return out
    if cfg['tip'] == 'igra':
        PF = D.PF
        for r in D.roots():                                   # livecpk ima prednost (prvi root pobjeduje)
            for sub, only in ((REL_PESDB, None), (REL_APP, APP)):
                d = os.path.join(r, sub)
                if not os.path.isdir(d): continue
                for f in os.listdir(d):
                    if (only is None or f == only) and os.path.isfile(os.path.join(d, f)):
                        out.setdefault(os.path.join(sub, f), ('datoteka', os.path.join(d, f)))
        order = sorted(PF.game_cpks(), key=lambda p: (os.path.basename(os.path.dirname(p)).lower() == 'download', os.path.getmtime(p)), reverse=True)
        for path in order:
            try: c = PF.Cpk(path)
            except Exception: continue
            for row in c.toc:
                dn = (row.get('DirName') or '').replace('\\', '/').strip('/')
                fn = row.get('FileName') or ''
                if dn == 'common/etc/pesdb' or (dn == REL_APP.replace(os.sep, '/') and fn == APP):
                    out.setdefault(os.path.join(*dn.split('/'), fn), ('cpk', path, row))
        return out
    return {}

def _procitaj(src):
    if src[0] == 'datoteka': return open(src[1], 'rb').read()
    return D.PF.Cpk(src[1]).read(src[2])

# ------------------------------------------------------------------ priprema / zapis
def pripremi(izlaz, cfg, od_originala=True, log=print):
    """Izlazna mapa dobiva cijelu ulaznu bazu. od_originala=False i mapa vec ima bazu -> ostaje (nadogradnja)."""
    import izvor as IZ
    if cfg['tip'] in ('mapa',) and _norm(izlaz) == _norm(cfg['put']):
        raise SystemExit('Izlazna mapa ne smije biti ista kao ulazna baza: %s' % izlaz)
    os.makedirs(izlaz, exist_ok=True)
    if not od_originala and citaj_iz(izlaz):
        log('Nastavljam na postojecem izlazu: %s' % izlaz); return citaj_iz(izlaz)
    src = ulazne(cfg); n = 0
    for rel, s in src.items():
        dst = os.path.join(izlaz, rel); os.makedirs(os.path.dirname(dst), exist_ok=True)
        if s[0] == 'datoteka': shutil.copyfile(s[1], dst)
        else: open(dst, 'wb').write(_procitaj(s))
        n += 1
    json.dump({'izvor': IZ.opis(cfg), 'id': cfg['id'], 'pripremljeno': datetime.datetime.now().isoformat(timespec='seconds'),
               'poslovi': []}, open(os.path.join(izlaz, OZNAKA), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log('Izlazna mapa pripremljena: %d datoteka baze -> %s' % (n, izlaz))
    return citaj_iz(izlaz)

def citaj_iz(izlaz):
    """pesdb mapa unutar izlazne mape (ili None)."""
    if not izlaz or not os.path.isdir(izlaz): return None
    for dp, dn, fn in os.walk(izlaz):
        if 'Player.bin' in fn: return dp
    return None

def appearance_u(izlaz):
    for dp, dn, fn in os.walk(izlaz):
        if APP in fn: return os.path.join(dp, APP)
    return None

def provjeri(files):
    """files = {ime: decompressed bytes} -> popis gresaka (prazno = u redu)."""
    g = []
    P = files.get('Player.bin')
    if P is not None:
        if len(P) % D.REC: g.append('Player.bin: velicina %d nije visekratnik od %d' % (len(P), D.REC))
        ids = [struct.unpack_from('<I', P, i * D.REC + 8)[0] for i in range(len(P) // D.REC)]
        if len(ids) != len(set(ids)): g.append('Player.bin: %d dupliciranih ID-ova' % (len(ids) - len(set(ids))))
        idset = set(ids)
    A = files.get('PlayerAssignment.bin')
    if A is not None:
        if len(A) % 16: g.append('PlayerAssignment.bin: velicina nije visekratnik od 16')
        elif P is not None:
            miss = {struct.unpack_from('<I', A, i * 16 + 4)[0] for i in range(len(A) // 16)} - idset
            if miss: g.append('PlayerAssignment.bin: %d igraca ne postoji u Player.bin (npr. %s)' % (len(miss), sorted(miss)[:5]))
            per = {}
            for i in range(len(A) // 16):
                _, pid, tid, _ = struct.unpack_from('<4I', A, i * 16); per[tid] = per.get(tid, 0) + 1
            big = [t for t, n in per.items() if n > 40]
            if big: g.append('PlayerAssignment.bin: momcadi s vise od 40 igraca: %s' % big[:5])
    AP = files.get(APP)
    if AP is not None and len(AP) % 60: g.append('PlayerAppearance.bin: velicina nije visekratnik od 60')
    return g

def zapisi(izlaz, nove, posao=None, log=print):
    """nove = {'Player.bin': decompressed bytes, 'PlayerAssignment.bin': ..., 'PlayerAppearance.bin': ...}.
    Provjerava zajedno s datotekama koje su vec u izlazu; ako nesto ne valja, NE zapisuje nista."""
    pes = citaj_iz(izlaz)
    if not pes: raise SystemExit('Izlazna mapa nije pripremljena: %s' % izlaz)
    sve = {}
    for n in ('Player.bin', 'PlayerAssignment.bin'):
        sve[n] = nove[n] if n in nove else (D.PF.wesys(open(os.path.join(pes, n), 'rb').read()) if os.path.isfile(os.path.join(pes, n)) else None)
    ap = appearance_u(izlaz)
    if APP in nove: sve[APP] = nove[APP]
    g = provjeri({k: v for k, v in sve.items() if v is not None})
    if g: raise SystemExit('Provjera nove baze NIJE prosla, nista nije spremljeno:\n  ' + '\n  '.join(g))
    out = []
    for n, data in nove.items():
        dst = (ap or os.path.join(izlaz, REL_APP, APP)) if n == APP else os.path.join(pes, n)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + '.novo'
        open(tmp, 'wb').write(_wesys_pack(data)); os.replace(tmp, dst); out.append(dst)
    if posao:
        f = os.path.join(izlaz, OZNAKA)
        info = json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {'poslovi': []}
        info.setdefault('poslovi', []).append(dict(posao, vrijeme=datetime.datetime.now().isoformat(timespec='seconds'),
                                                   datoteke=sorted(nove)))
        json.dump(info, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log('Spremljeno (provjereno): ' + ', '.join(os.path.relpath(p, izlaz) for p in out))
    return out


# ------------------------------------------------------------------ snimka ulaza, kopija u igru (naredbeni redak)
def snimka(izlaz, cilj):
    """Kopija baze iz izlazne mape u cilj (ulaz posla kad se krece od zadnjeg izlaza)."""
    pes = citaj_iz(izlaz)
    if not pes: raise SystemExit('Izlazna mapa jos nema bazu - odaberi "krenuti od originala".')
    if os.path.isdir(cilj): shutil.rmtree(cilj)
    shutil.copytree(izlaz, cilj, ignore=shutil.ignore_patterns(OZNAKA, '*.novo'))
    return cilj

def u_igru(izlaz, cilj, log=print):
    """Kopira datoteke koje su poslovi promijenili (baza_info.json) u mapu igre (npr. vlastiti livecpk root).
    Postojece datoteke u cilju se prvo spreme u cilj/_prije_<vrijeme>/."""
    info = json.load(open(os.path.join(izlaz, OZNAKA), encoding='utf-8')) if os.path.exists(os.path.join(izlaz, OZNAKA)) else {}
    imena = sorted({n for p in info.get('poslovi', []) for n in p.get('datoteke', [])})
    if not imena: log('Nema promijenjenih datoteka za kopiranje.'); return []
    pes = citaj_iz(izlaz); stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S'); out = []
    for n in imena:
        src = appearance_u(izlaz) if n == APP else os.path.join(pes, n)
        rel = os.path.relpath(src, izlaz)
        dst = os.path.join(cilj, rel)
        if os.path.isfile(dst):
            bk = os.path.join(cilj, '_prije_' + stamp, rel); os.makedirs(os.path.dirname(bk), exist_ok=True); shutil.copy2(dst, bk)
        os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst); out.append(dst)
    log('Kopirano u igru (%s): %s' % (cilj, ', '.join(imena)))
    return out

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import izvor as IZ
    OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
    cfg = IZ.use(IZ.cfg_from_opts(OPT)); iz = OPT.get('izlaz')
    lg = lambda s: print(s, flush=True)
    if 'pripremi' in OPT:
        if OPT.get('od') == 'izlaz':
            cilj = os.path.join(IZ.mapa(cfg), 'ulaz_posla'); snimka(iz, cilj); lg('Ulaz posla = zadnji izlaz (snimka: %s)' % cilj)
        else:
            pripremi(iz, cfg, od_originala=True, log=lg)
    if isinstance(OPT.get('u-igru'), str):
        u_igru(iz, OPT['u-igru'], log=lg)
