# -*- coding: utf-8 -*-
"""
FACE-OVI: (1) popis najpotrebnijih face-ova, (2) boja koze generic igraca iz Transfermarkt fotografije.

    python koza.py --samo-popis -> samo popis najpotrebnijih face-ova (brzo, za sucelje)
    python koza.py              -> skini fotke (cache\\portreti), nauci model, izvjestaj (nista se ne upisuje)
    python koza.py --upisi      -> + novi PlayerAppearance.bin u ocjene_tm\\izlaz (SAMO igraci bez pravog face-a)
    --min-razlika=2             -> boja se mijenja samo ako se procjena razlikuje od baze za barem toliko (default 2)

Model se uci na igracima koji IMAJU pravi face (njima je boju koze postavio facemaker): ton koze s TM fotke
(Haar lice -> obrazi -> medijan Lab) -> SkinColour 1-6. Igraci s pravim face-om se nikad ne mijenjaju.
Izvjestaj izvjestaji\\faceovi_*.txt: igraci bez face-a poredani po TM vrijednosti (+ link na TM fotku).
"""
import os, sys, json, time, struct, zlib, datetime, collections, urllib.request, threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
PDIR = os.path.join(HERE, 'cache', 'portreti'); os.makedirs(PDIR, exist_ok=True)
F_URL = os.path.join(HERE, 'cache', 'tm_portreti.json')
APP_REL = os.path.join('common', 'character0', 'model', 'character', 'appearance', 'PlayerAppearance.bin')
SKIN = (37, 0, 3, 0)          # PlayerAppearance: bajt 37, bitovi 0-2 (iz tablice editora, stupac SkinColour)
TRAIN_MAX = 4000

def urls(tm_ids, log):
    import tm_api as A
    U = json.load(open(F_URL, encoding='utf-8')) if os.path.exists(F_URL) else {}
    need = [t for t in tm_ids if str(t) not in U]
    log('Linkovi fotki: treba %d' % len(need))
    lock = threading.Lock()
    def b(ch):
        for d in A.players(ch) or []:
            with lock: U[str(d['id'])] = d.get('portraitUrl') or ''
    with ThreadPoolExecutor(8) as ex: list(ex.map(b, [need[k:k + 50] for k in range(0, len(need), 50)]))
    json.dump(U, open(F_URL, 'w', encoding='utf-8'))
    return U

def download(U, tm_ids, log):
    import tm_overall as T
    todo = [t for t in tm_ids if U.get(str(t)) and 'default' not in U[str(t)] and not os.path.exists(os.path.join(PDIR, '%s.jpg' % t))]
    log('Fotke: skidam %d' % len(todo))
    def one(t):
        for a in range(3):
            try:
                b = urllib.request.urlopen(urllib.request.Request(U[str(t)], headers=T.UA), timeout=20).read()
                open(os.path.join(PDIR, '%s.jpg' % t), 'wb').write(b); return
            except Exception:
                time.sleep(1 + a)
    with ThreadPoolExecutor(12) as ex:
        for n, _ in enumerate(ex.map(one, todo), 1):
            if n % 1000 == 0: log('   %d/%d' % (n, len(todo)))

_CASC = None
def feat(t):
    """Ton koze s fotke: medijan Lab obraza + cijelog lica (6 brojeva) ili None."""
    import cv2
    global _CASC
    if _CASC is None: _CASC = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml'))
    f = os.path.join(PDIR, '%s.jpg' % t)
    img = cv2.imread(f) if os.path.exists(f) else None
    if img is None: return None
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    fs = _CASC.detectMultiScale(g, 1.1, 5, minSize=(40, 40))
    if not len(fs): return None
    x, y, w, h = max(fs, key=lambda r: r[2] * r[3])
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    ycc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    def reg(x0, x1, y0, y1):
        r = lab[y + int(h * y0):y + int(h * y1), x + int(w * x0):x + int(w * x1)].reshape(-1, 3)
        c = ycc[y + int(h * y0):y + int(h * y1), x + int(w * x0):x + int(w * x1)].reshape(-1, 3)
        m = (c[:, 1] > 128) & (c[:, 1] < 180) & (c[:, 2] > 70) & (c[:, 2] < 135)     # grubo: samo pikseli koze
        r = r[m] if m.sum() > 30 else r
        return np.median(r, axis=0)
    cheeks = np.concatenate([reg(0.15, 0.40, 0.45, 0.70), reg(0.60, 0.85, 0.45, 0.70)]).reshape(2, 3).mean(axis=0)
    whole = reg(0.2, 0.8, 0.2, 0.9)
    return list(cheeks) + list(whole)

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    log = lambda s: print(s, flush=True)
    import izvor as IZ, fl27db as D, izvoz_csv as X
    cfg = IZ.use(IZ.cfg_from_opts(OPT))
    PF = D.PF
    P, _, _ = D.load(); B = {p['id']: p for p in P}
    Praw, A, src = X.load_bins()
    app = {struct.unpack_from('<I', A, i * 60)[0]: i for i in range(len(A) // 60)}
    log('Trazim face-ove...')
    faces = PF.face_index(PF.sider_roots(), PF.game_cpks())
    mapa = IZ.mapa(cfg)
    L = json.load(open(os.path.join(mapa, 'tm_ids.json')))
    d2t = {d: t for d, t, o in L}
    try:
        for k, e in json.load(open(os.path.join(mapa, 'rucne.json'), encoding='utf-8')).items():
            if e.get('tm_id'): d2t.setdefault(int(k), e['tm_id'])
    except (OSError, ValueError): pass
    I = json.load(open(os.path.join(HERE, 'cache', 'tm_api_igraci.json'), encoding='utf-8')) if os.path.exists(os.path.join(HERE, 'cache', 'tm_api_igraci.json')) else {}
    tm = {}
    for f in __import__('glob').glob(os.path.join(HERE, 'cache', 'tm_*_20*.json')):
        try: dd = json.load(open(f, encoding='utf-8'))
        except ValueError: continue
        for q in dd.get('players', []) if isinstance(dd, dict) else []: tm[q['tm_id']] = q
    val = lambda d: (tm.get(d2t.get(d)) or {}).get('value') or 0

    # (1) popis najpotrebnijih face-ova
    bez = [p for p in P if (p['club_id'] or p['nt']) and p['id'] not in faces and not any(x in p['club'] for x in ('Classics', 'ML Default'))]
    bez.sort(key=lambda p: -val(p['id']))
    lg = collections.defaultdict(lambda: [0, 0])
    for p in P:
        if p['club_id']: lg[p['league']][0] += 1; lg[p['league']][1] += p['id'] in faces
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    os.makedirs(os.path.join(HERE, 'izvjestaji'), exist_ok=True)

    U0 = json.load(open(F_URL, encoding='utf-8')) if os.path.exists(F_URL) else {}
    if 'samo-popis' in OPT:                        # brzo: samo popis za sucelje (linkovi fotki za prvih 600)
        top = [d2t[p['id']] for p in bez[:600] if p['id'] in d2t]
        U0 = urls(top, log)
    json.dump({'vrijeme': stamp, 'ukupno_bez': len(bez),
               'lige': [{'liga': k, 'n': v[0], 'face': v[1]} for k, v in sorted(lg.items(), key=lambda x: -x[1][0])],
               'igraci': [{'id': p['id'], 'ime': p['name'], 'klub': p['club'] or ('repr. ' + ', '.join(p['nt'])), 'liga': p['league'],
                           'poz': p['pos'], 'dob': p['age'], 'drzava': p['nat'], 'vrijednost': val(p['id']),
                           'tm_id': d2t.get(p['id']), 'slika': U0.get(str(d2t.get(p['id'])), '') if d2t.get(p['id']) else ''}
                          for p in bez[:600]]},
              open(os.path.join(HERE, 'izvjestaji', 'faceovi_zadnje.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    if 'samo-popis' in OPT:
        log('Popis face-ova: %d igraca bez face-a (izvjestaji/faceovi_zadnje.json)' % len(bez)); return

    # (2) boja koze
    with_face = [p for p in P if p['id'] in faces and p['id'] in d2t and p['id'] in app]
    with_face.sort(key=lambda p: -val(p['id'])); train = with_face[:TRAIN_MAX]
    target = [p for p in bez if p['id'] in d2t and p['id'] in app]
    ids = [d2t[p['id']] for p in train + target]
    U = urls(ids, log); download(U, ids, log)
    log('Racunam ton koze...')
    F = {p['id']: feat(d2t[p['id']]) for p in train + target}      # bez niti: OpenCV Haar u nitima rusi proces
    sk = lambda pid: D.getf(A[app[pid] * 60:(app[pid] + 1) * 60], *SKIN)
    Xtr = np.array([F[p['id']] for p in train if F[p['id']] is not None]); ytr = np.array([sk(p['id']) for p in train if F[p['id']] is not None])
    from sklearn.ensemble import HistGradientBoostingRegressor as HGB
    from sklearn.model_selection import cross_val_predict
    m = HGB(max_iter=300, learning_rate=0.05, max_leaf_nodes=15)
    cv = np.clip(np.round(cross_val_predict(m, Xtr, ytr, cv=5)), 1, 6)
    acc = (cv == ytr).mean(); acc1 = (np.abs(cv - ytr) <= 1).mean()
    log('Model koze: %d igraca s face-om, tocno %.0f %%, +-1 %.0f %%' % (len(ytr), 100 * acc, 100 * acc1))
    m.fit(Xtr, ytr)
    mr = int(OPT['min-razlika']) if isinstance(OPT.get('min-razlika'), str) else 2
    promj = []
    for p in target:
        f_ = F[p['id']]
        if f_ is None: continue
        v = float(m.predict([f_])[0]); nv = int(np.clip(round(v), 1, 6)); cur = sk(p['id'])
        if abs(v - cur) >= mr - 0.25 and nv != cur: promj.append((p, cur, nv, v))
    fr = os.path.join(HERE, 'izvjestaji', 'faceovi_%s.txt' % stamp)
    with open(fr, 'w', encoding='utf-8') as w:
        w.write('FACE-OVI (%s)\n\nPokrivenost po ligama (igraci s pravim face-om):\n' % stamp)
        for k, v in sorted(lg.items(), key=lambda x: -x[1][0]):
            w.write('  %-38s %4d/%4d  %3d %%\n' % (k, v[1], v[0], 100 * v[1] // max(1, v[0])))
        w.write('\nNAJPOTREBNIJI FACE-OVI (bez face-a, po TM vrijednosti; %d igraca):\n' % len(bez))
        for p in bez[:1500]:
            t = d2t.get(p['id'])
            w.write('  %7d  %-28s %-26s %6.1f M  %s\n' % (p['id'], p['name'][:28], (p['club'] or 'repr. ' + ','.join(p['nt']))[:26], val(p['id']) / 1e6,
                    U.get(str(t), '') if t else ''))
        w.write('\nBOJA KOZE (model: tocno %.0f %%, +-1 %.0f %%): promjena kod %d generic igraca (razlika >= %d)\n' % (100 * acc, 100 * acc1, len(promj), mr))
        for p, cur, nv, v in sorted(promj, key=lambda x: -val(x[0]['id'])):
            w.write('  %7d  %-28s %-24s %d -> %d  (%.1f)\n' % (p['id'], p['name'][:28], p['club'][:24], cur, nv, v))
    import lang as LG; LG.prevedi_datoteku(fr)
    log('Bez face-a: %d igraca; boja koze bi se promijenila kod %d. Izvjestaj: %s' % (len(bez), len(promj), fr))
    if 'upisi' in OPT and promj:
        out = bytearray(A)
        for p, cur, nv, v in promj:
            i = app[p['id']]; r = bytearray(out[i * 60:(i + 1) * 60]); D.setf(r, *SKIN[:3], nv); out[i * 60:(i + 1) * 60] = r
        path = os.path.join(D.IZLAZ, APP_REL)
        comp = zlib.compress(bytes(out), 9); os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f: f.write(b'\xff\x10\x81WESYS' + struct.pack('<II', len(comp), len(out)) + comp)
        log('Upisano: %s' % path)

if __name__ == '__main__':
    main()
