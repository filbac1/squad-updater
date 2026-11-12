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

# ------------------------------------------------------------------ edit file igre (FL27 / PES 2021)
U_IGRI = 'squad_updater_u_igri.json'      # u mapi igre: kad je i sto zadnje kopirano

def dokumenti():
    """Prava mapa Dokumenti (i kad je preusmjerena na OneDrive)."""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value: return buf.value
    except Exception: pass
    return os.path.join(os.path.expanduser('~'), 'Documents')

def save_mapa(igra_dir=None, rucno=None):
    """Mapa sa save datotekama koju igra stvarno koristi (EDIT00000000, SYSTEM...).
    FL27: <Dokumenti>/SPGAME/Football Life/<SteamID iz sys.ini>/save; obicni PES 2021: KONAMI/.../<id>/save."""
    if rucno and os.path.isdir(rucno): return rucno
    sid = None
    for f in ([os.path.join(igra_dir, 'sys.ini')] if igra_dir else []):
        try:
            for line in open(f, encoding='utf-8', errors='replace'):
                if line.strip().lower().startswith('steamid='): sid = line.split('=', 1)[1].strip()
        except OSError: pass
    doc = dokumenti(); kand = []
    for base in (os.path.join(doc, 'SPGAME', 'Football Life'), os.path.join(doc, 'KONAMI', 'eFootball PES 2021 SEASON UPDATE')):
        if sid: kand.append(os.path.join(base, sid, 'save'))
    for k in kand:
        if os.path.isdir(k): return k
    return None

def edit_stanje(save):
    f = os.path.join(save or '', 'EDIT00000000')
    if not save or not os.path.isfile(f): return {'save': save, 'postoji': False}
    return {'save': save, 'postoji': True, 'vrijeme': datetime.datetime.fromtimestamp(os.path.getmtime(f)).isoformat(timespec='seconds')}

def edit_reset(save, log=print):
    """Edit file nadjacava sastave iz baze -> premjesti ga (i njegove pratece datoteke) u save_backup_<vrijeme>.
    Igra pri sljedecem pokretanju napravi novi edit iz nove baze. Nista se ne brise."""
    if not save or not os.path.isfile(os.path.join(save, 'EDIT00000000')): log('Edit file: nema ga, igra ce napraviti novi.'); return []
    bk = os.path.join(os.path.dirname(save), 'save_backup_' + datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S'))
    os.makedirs(bk, exist_ok=True); out = []
    for f in os.listdir(save):
        if f.upper().startswith('EDIT00000000'):
            shutil.move(os.path.join(save, f), os.path.join(bk, f)); out.append(f)
    log('Edit file premjesten u %s (igra ce napraviti novi iz nove baze).' % bk)
    return out

def u_igri(cilj):
    """Sto je zadnje kopirano u igru (ili None)."""
    try: return json.load(open(os.path.join(cilj, U_IGRI), encoding='utf-8'))
    except (OSError, ValueError, TypeError): return None

def isto_u_igri(izlaz, cilj):
    """Jesu li datoteke koje su poslovi promijenili iste u igri kao u izlazu? {ime: True/False/None}"""
    import hashlib
    info = json.load(open(os.path.join(izlaz, OZNAKA), encoding='utf-8')) if izlaz and os.path.exists(os.path.join(izlaz, OZNAKA)) else {}
    imena = sorted({n for p in info.get('poslovi', []) for n in p.get('datoteke', [])})
    pes = citaj_iz(izlaz); out = {}
    h = lambda f: hashlib.md5(open(f, 'rb').read()).hexdigest() if os.path.isfile(f) else None
    for n in imena:
        src = appearance_u(izlaz) if n == APP else os.path.join(pes or '', n)
        if not src or not os.path.isfile(src): continue
        dst = os.path.join(cilj, os.path.relpath(src, izlaz))
        a, b = h(src), h(dst); out[n] = None if b is None else a == b
    return out

def vrati_igru(cilj, save=None, log=print):
    """Vrati mapu igre na stanje prije ZADNJEG kopiranja: datoteke iz _prije_<vrijeme> natrag, datoteke koje tada
    nisu postojale se uklone (igra opet cita svoje CPK-ove), a ako je tada premjesten edit file, vrati se i on."""
    zad = u_igri(cilj) or {}
    bks = sorted(d for d in os.listdir(cilj) if d.startswith('_prije_') and os.path.isdir(os.path.join(cilj, d))) if os.path.isdir(cilj) else []
    bk = zad.get('backup') if zad.get('backup') in bks else (bks[-1] if bks else None)
    if not bk and not zad: raise SystemExit('Nema zapisa o kopiranju u igru - nema se sto vratiti.')
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S'); out = []
    imena = zad.get('datoteke') or []
    src_bk = os.path.join(cilj, bk) if bk else None
    rel_map = {}
    if src_bk:
        for root, _, fs in os.walk(src_bk):
            for f in fs: rel_map[f] = os.path.relpath(os.path.join(root, f), src_bk)
    for n in sorted(set(imena) | set(rel_map)):
        rel = rel_map.get(n) or (os.path.join(REL_APP, n) if n == APP else os.path.join(REL_PESDB, n))
        dst = os.path.join(cilj, rel)
        if os.path.isfile(dst):                         # trenutno stanje i dalje ostaje sacuvano
            k = os.path.join(cilj, '_vraceno_' + stamp, rel); os.makedirs(os.path.dirname(k), exist_ok=True); shutil.copy2(dst, k)
        if n in rel_map:
            os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(os.path.join(src_bk, rel_map[n]), dst); out.append('%s (vraceno)' % n)
        elif os.path.isfile(dst):
            os.remove(dst); out.append('%s (uklonjeno - igra cita original)' % n)
    if zad.get('edit_reset') and save:
        bdir = sorted(d for d in os.listdir(os.path.dirname(save)) if d.startswith('save_backup_'))
        if bdir:
            b_ = os.path.join(os.path.dirname(save), bdir[-1])
            if os.path.isfile(os.path.join(save, 'EDIT00000000')): edit_reset(save, log=log)
            for f in os.listdir(b_):
                if f.upper().startswith('EDIT00000000') and not os.path.exists(os.path.join(save, f)):
                    shutil.copy2(os.path.join(b_, f), os.path.join(save, f)); out.append(f + ' (vraceno u save)')
    try: os.remove(os.path.join(cilj, U_IGRI))
    except OSError: pass
    log('Igra vracena na stanje prije zadnjeg kopiranja: ' + (', '.join(out) or 'nista'))
    return out

def u_igru(izlaz, cilj, log=print, reset_edit=None):
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
    ed = edit_reset(reset_edit, log=log) if reset_edit else []
    try:
        json.dump({'vrijeme': datetime.datetime.now().isoformat(timespec='seconds'), 'izvor': os.path.abspath(izlaz), 'datoteke': imena,
                   'edit_reset': bool(ed), 'backup': '_prije_' + stamp}, open(os.path.join(cilj, U_IGRI), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    except OSError: pass
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
        u_igru(iz, OPT['u-igru'], log=lg, reset_edit=OPT.get('reset-edit') if isinstance(OPT.get('reset-edit'), str) else None)
    if isinstance(OPT.get('vrati-igru'), str):
        vrati_igru(OPT['vrati-igru'], OPT.get('save') if isinstance(OPT.get('save'), str) else None, log=lg)
