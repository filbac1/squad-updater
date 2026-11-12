# -*- coding: utf-8 -*-
"""
Overall za POJEDINACNE igrace s Transfermarkta (bilo koja liga, i igraci bez kluba).

  trazi(upit)                -> kandidati s TM brze pretrage (ime ili TM link)
  izracun(tm_igrac)          -> ciljni overall (EA ljestvica + ljestvica igre) uz kontekst kluba i lige
  db_kandidati(tm_igrac)     -> igraci iz FL27 baze koji mu odgovaraju (ime + godine)
  Rucni popis (rucne.json)   -> {db_id: {...}}; ocjene.py ga primjenjuje uz lige (rucni unos ima prednost)

Kontekst (jacina kluba i lige) se uzima iz cache-a liga; ako liga nije skinuta, iz momcadi kluba
(1 zahtjev) + procjena lige po vrijednosti; za igrace bez kluba iz zadnjeg kluba.
"""
import os, re, sys, json, time, html, datetime, collections, urllib.parse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tm_overall as T
import model_ea27 as ME

CACHE = os.path.join(HERE, 'cache')
KLUB_DIR = os.path.join(CACHE, 'klubovi'); os.makedirs(KLUB_DIR, exist_ok=True)
def rucne_put():
    import izvor as IZ
    return os.path.join(IZ.mapa(), 'rucne.json')
TM = 'https://www.transfermarkt.com'
SLEEP = 1.5
POZ = {'GK': 'Goalkeeper', 'CB': 'Centre-Back', 'LB': 'Left-Back', 'RB': 'Right-Back', 'DM': 'Defensive Midfield',
       'CM': 'Central Midfield', 'AM': 'Attacking Midfield', 'LW': 'Left Winger', 'RW': 'Right Winger',
       'LM': 'Left Midfield', 'RM': 'Right Midfield', 'CF': 'Centre-Forward', 'SS': 'Second Striker',
       'DF': 'Centre-Back', 'MF': 'Central Midfield', 'FW': 'Centre-Forward'}
MENU = {'GB1', 'ES1', 'IT1', 'L1', 'FR1', 'CL', 'EL', 'UCOL', 'FIWC', 'EM24', 'WM26', 'NL1', 'PO1', 'TR1'}

import threading
_last = [0.0]
_rl = threading.Lock()
def get(url):
    """Web stranica TM-a; najvise jedan zahtjev svakih SLEEP sekundi UKUPNO (i kad radi vise niti)."""
    with _rl:
        w = SLEEP - (time.time() - _last[0])
        if w > 0: time.sleep(w)
        _last[0] = time.time()
    return T.get(url)

def money(s):
    m = re.search(r'€\s*([\d.,]+)\s*(bn|m|k)', s or '', re.I)
    return float(m.group(1).replace(',', '')) * {'bn': 1e9, 'm': 1e6, 'k': 1e3}[m.group(2).lower()] if m else None

# ------------------------------------------------------------------ pretraga
def trazi(upit):
    upit = upit.strip()
    m = re.search(r'/spieler/(\d+)', upit)
    if m: return [profil(int(m.group(1)))]
    t = get(TM + '/schnellsuche/ergebnis/schnellsuche?query=' + urllib.parse.quote(upit))
    i = t.find('Search results for players')
    if i < 0: return []
    seg = t[i:t.find('</tbody>', i)]
    out = []
    for r in re.split(r'<tr class="(?:odd|even)">', seg)[1:]:
        a = re.search(r'href="/[^"]+/profil/spieler/(\d+)">(.*?)</a>', r)
        if not a: continue
        c = re.search(r'title="([^"]*)" href="/([^/"]+)/startseite/verein/(\d+)"', r)
        tds = re.findall(r'<td class="zentriert">(.*?)</td>', r, re.S)
        img = re.search(r'<img src="([^"]+portrait[^"]+)"', r)
        out.append({'tm_id': int(a.group(1)), 'name': T.clean(a.group(2)),
                    'club': (html.unescape(c.group(1)) if c else '').strip('- ') , 'club_slug': c.group(2) if c else '',
                    'club_id': int(c.group(3)) if c else None,
                    'pos': POZ.get(T.clean(tds[0]) if tds else '', 'Central Midfield'),
                    'pos_kratko': T.clean(tds[0]) if tds else '',
                    'age': int(T.clean(tds[2])) if len(tds) > 2 and T.clean(tds[2]).isdigit() else None,
                    'nat': [html.unescape(x) for x in re.findall(r'title="([^"]+)" alt="[^"]+" class="flaggenrahmen"', r)],
                    'value': money(r.split('rechts hauptlink')[-1][:80]) if 'rechts hauptlink' in r else None,
                    'slika': img.group(1) if img else None})
    return out

def profil(tm_id):
    """Osnovni podaci s profila (za TM link i za zadnji klub igraca bez kluba)."""
    t = get(TM + '/x/profil/spieler/%d' % tm_id)
    hd = t[t.find('data-header'):t.find('data-header') + 9000]
    name = T.clean(re.sub(r'<[^>]+>', ' ', re.search(r'<h1[^>]*>(.*?)</h1>', hd, re.S).group(1))) if '<h1' in hd else str(tm_id)
    name = re.sub(r'^#\d+\s*', '', re.sub(r'\s+', ' ', name)).strip()
    clubs = re.findall(r'href="/([^/"]+)/startseite/verein/(\d+)[^"]*"[^>]*>\s*(?:<[^>]+>\s*)*([^<]*)', hd)
    dob = re.search(r'(\w{3} \d{1,2}, \d{4}) \((\d+)\)', t) or re.search(r'(\d\d/\d\d/\d{4}) \((\d+)\)', t)
    pos = re.search(r'Position:\s*</span>\s*<span[^>]*>\s*([^<]+)', t)
    val = re.search(r'data-header__market-value-wrapper">(.*?)</a>', t, re.S)
    last = re.search(r'Last club:.*?href="/([^/"]+)/startseite/verein/(\d+)', t, re.S)
    img = re.search(r'data-header__profile-image"[^>]*src="([^"]+)"', t)
    hh = re.search(r'Height:\s*</span>\s*<span[^>]*>\s*(\d),(\d\d)\s*m', t)
    nats = re.findall(r'Citizenship:\s*</span>\s*<span[^>]*>(.*?)</span>', t, re.S)
    nats = re.findall(r'title="([^"]+)" alt="[^"]+" class="flaggenrahmen"', nats[0]) if nats else []
    c = clubs[0] if clubs else ('', '0', '')
    return {'tm_id': tm_id, 'name': name, 'club': T.clean(c[2]) or c[0], 'club_slug': c[0], 'club_id': int(c[1]),
            'pos': html.unescape(pos.group(1)).strip().split(' - ')[-1] if pos else 'Central Midfield', 'pos_kratko': '',
            'age': int(dob.group(2)) if dob else None, 'nat': [html.unescape(x) for x in dict.fromkeys(nats)],
            'visina': int(hh.group(1)) * 100 + int(hh.group(2)) if hh else None,
            'value': money(re.sub(r'<[^>]+>', '', val.group(1))) if val else None,
            'zadnji_klub': {'slug': last.group(1), 'id': int(last.group(2))} if last else None,
            'slika': img.group(1) if img else None}

# ------------------------------------------------------------------ kontekst kluba i lige
def klub(slug, cid):
    """Momcad kluba (cache 7 dana): igraci s vrijednostima + kod lige."""
    p = os.path.join(KLUB_DIR, '%s.json' % cid)
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 7 * 86400:
        return json.load(open(p, encoding='utf-8'))
    k = get(TM + '/%s/kader/verein/%s/saison_id/%d/plus/1' % (slug or 'x', cid, T.SEASON))
    name = T.clean(re.search(r'<h1[^>]*>\s*(.*?)\s*</h1>', k, re.S).group(1)) if '<h1' in k else str(cid)
    hd = k[k.find('data-header'):k.find('data-header') + 8000]
    codes = re.findall(r'/startseite/wettbewerb/([A-Z0-9]+)', hd)
    if not codes:
        cnt = collections.Counter(re.findall(r'/startseite/wettbewerb/([A-Z0-9]+)', k))
        codes = [c for c, n in cnt.most_common() if c not in MENU and n >= 2] or [c for c, n in cnt.most_common() if n >= 3]
    vals = [money(x) for x in re.findall(r'marktwertverlauf/spieler/\d+">([^<]*)', k)]
    igr = {}
    seg = k[k.find('class="items"'):]
    for r in re.split(r'<tr class="(?:odd|even)">', seg)[1:]:
        m = re.search(r'/profil/spieler/(\d+)', r)
        if not m: continue
        hh = re.search(r'(\d),(\d\d)\s*m', r)
        nat = re.findall(r'title="([^"]+)" alt="[^"]+" class="flaggenrahmen"', r)
        igr[m.group(1)] = {'visina': int(hh.group(1)) * 100 + int(hh.group(2)) if hh else None,
                           'drzave': [html.unescape(x) for x in dict.fromkeys(nat)]}
    d = {'id': cid, 'ime': name, 'liga': codes[0] if codes else None, 'vrijednosti': [v for v in vals if v], 'igraci': igr}
    json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    return d

def _club_cm(vals):
    L = sorted(np.log(np.array(vals) / 1e6))[-14:] if vals else []
    return float(np.mean(L)) if len(L) else None

_LG = {}
def liga_jacina(code):
    """(jacina lige, je li tocna) iz cache-a liga; inace None."""
    if code in _LG: return _LG[code]
    f = ME.latest_leagues().get(code)
    if f:
        cm, lg = ME.strengths(json.load(open(f, encoding='utf-8'))['players'])
        _LG[code] = (lg, cm); return _LG[code]
    return None

_FA = None
def kontekst_po_vrijednosti(lnv):
    """Prosjecna jacina kluba/lige igraca slicne vrijednosti (iz podataka za ucenje) - zadnja rezerva."""
    global _FA
    if _FA is None:
        M = json.load(open(os.path.join(CACHE, 'ea27_upareni.json'), encoding='utf-8'))
        _FA = np.array([[np.log(max(q['value'], 5e4) / 1e6), q['_cm'], q['_lg']] for q in M])
    k = np.abs(_FA[:, 0] - lnv) < 0.35
    s = _FA[k] if k.sum() > 30 else _FA[np.argsort(np.abs(_FA[:, 0] - lnv))[:60]]
    return float(np.median(s[:, 1])), float(np.median(s[:, 2]))

def izracun(q, skala=None):
    """q = TM igrac (iz trazi/profil). Vrati dict s ciljem i opisom konteksta."""
    q = dict(q)
    if not q.get('value'):
        return dict(q, greska='Transfermarkt nema trzisnu vrijednost za ovog igraca.')
    if not q.get('age'):
        return dict(q, greska='Transfermarkt nema godine za ovog igraca.')
    opis, cm, lg, code = [], None, None, None
    # 1) brzi API: datum rodenja, visina, vrijednost, klub / zadnji klub, kod lige, vrijednosti suigraca
    try:
        import tm_api as TA
        a = TA.info(TA.player(q['tm_id']))
    except Exception:
        a = {}
    if a:
        q['dob'] = a.get('dob') or q.get('dob')
        if a.get('height'): q['visina'] = q['height'] = a['height']
        if a.get('value'): q['value'] = a['value']
        if a.get('age'): q['age'] = a['age']
        cid_api = a.get('club_id') if a.get('club_id') not in (None, 515, 123, 0) else None
        if not cid_api and a.get('last_club_id'):
            cid_api = a['last_club_id']; opis.append('bez kluba - kontekst zadnjeg kluba')
        k = TA.club(cid_api) if cid_api else None
        if k and not k.get('nacionalni'):
            code = k['liga']; cm = _club_cm(k['vrijednosti']); q['klub_ctx'] = k['ime']
            lj = liga_jacina(code) if code else None
            if lj:
                lg = lj[0]; opis.append('liga %s iz cache-a' % code)
            else:
                _, lg = kontekst_po_vrijednosti(cm if cm is not None else np.log(max(q['value'] or 5e4, 5e4) / 1e6))
                opis.append('liga %s nije skinuta - jacina lige procijenjena' % (code or '?'))
    if not q.get('value'):
        return dict(q, greska='Transfermarkt nema trzisnu vrijednost za ovog igraca.')
    if not q.get('age'):
        return dict(q, greska='Transfermarkt nema godine za ovog igraca.')
    lnv = np.log(max(q['value'], 5e4) / 1e6)
    cid, slug = q.get('club_id'), q.get('club_slug')
    if cm is not None:
        cid = None                                         # kontekst je vec iz API-ja
    elif cid in (None, 515, 123, 0) or 'Without Club' in (q.get('club') or '') or 'Retired' in (q.get('club') or ''):
        pr = profil(q['tm_id']) if not q.get('zadnji_klub') else q
        if pr.get('visina') and not q.get('visina'): q['visina'] = pr['visina']
        if pr.get('nat') and not q.get('nat'): q['nat'] = pr['nat']
        if pr.get('zadnji_klub'):
            cid, slug = pr['zadnji_klub']['id'], pr['zadnji_klub']['slug']
            opis.append('bez kluba - kontekst zadnjeg kluba')
        else:
            cid = None
    if cid:
        k = klub(slug, cid)
        code = k['liga']; cm = _club_cm(k['vrijednosti'])
        me = (k.get('igraci') or {}).get(str(q['tm_id']))
        if me:
            q.setdefault('visina', me.get('visina'))
            if me.get('drzave') and not q.get('nat'): q['nat'] = me['drzave']
        q['klub_ctx'] = k['ime']
        lj = liga_jacina(code) if code else None
        if lj:
            lg = lj[0]; opis.append('liga %s iz cache-a' % code)
        else:
            _, lg = kontekst_po_vrijednosti(cm if cm is not None else lnv)
            opis.append('liga %s nije skinuta - jacina lige procijenjena' % (code or '?'))
    if cm is None:
        cm, lg2 = kontekst_po_vrijednosti(lnv); lg = lg if lg is not None else lg2
        opis.append('klub nepoznat - procjena po vrijednosti')
    qq = {'value': q['value'], 'age': q['age'], 'pos': q['pos'], 'club': '_c', 'tm_league': code, 'tm_id': q.get('tm_id')}
    ea = ME.predict(qq, {'_c': cm}, lg, fetch=True)
    sk = ME.SKALA if skala is None else skala
    return dict(q, liga_kod=code, jacina_kluba=round(cm, 2), jacina_lige=round(lg, 2), regija=ME.regija(code),
                ea_pred=round(ea, 2), cilj=int(np.clip(np.round(ME.to_game(ea, sk)), 40, 99)),
                ea_ovr=ME.ea_lookup({'name': q['name'], 'dob': q.get('dob')}) if q.get('dob') else None,
                kontekst='; '.join(opis) or 'klub i liga iz Transfermarkta')

# ------------------------------------------------------------------ FL27 baza
_DB = None
def baza():
    global _DB
    if _DB is None:
        import ocjene as OC, izvor as IZ
        P, raw, src = IZ.load_players(IZ.CFG or IZ.aktivna())
        P = [p for p in P if p['pos'] != '?']
        import overall as O
        for p in P: p['ovr'] = O.ovr(p['attr'], p['pos'])
        _DB = {'P': P, 'idx': OC.build_index(P), 'by_id': {p['id']: p for p in P}}
    return _DB

def db_kandidati(q, n=6):
    import ocjene as OC
    B = baza(); tt = OC.toks(q['name'])
    if not tt: return []
    cands = {p['idx']: p for t in tt for p in B['idx'].get(t, [])}.values()
    out = []
    for p in cands:
        pt = set(OC.toks(p['name']) + OC.toks(p['shirt']))
        s = len(set(tt) & pt) / len(set(tt)) + (0.4 if tt[-1] in pt else 0)
        if q.get('age') and p['age']:
            d = abs(p['age'] - q['age'])
            s += 0.3 if d == 0 else 0.15 if d == 1 else -0.3 if d > 2 else 0
        if q.get('nat') and p['nat'] and p['nat'].lower() in [x.lower() for x in q['nat']]: s += 0.2
        out.append((s, p))
    out.sort(key=lambda x: -x[0])
    good = [db_opis(p, s) for s, p in out[:n] if s >= 1.0]
    return good or [db_opis(p, s) for s, p in out[:3] if s >= 0.7]

def db_opis(p, s=None):
    return {'id': p['id'], 'ime': p['name'], 'klub': p['club'] or ('bez kluba'), 'liga': p['league'], 'poz': p['pos'],
            'dob': p['age'], 'nat': p['nat'], 'ovr': p['ovr'], 'slicnost': round(s, 2) if s is not None else None}

def db_trazi(upit, n=12):
    import ocjene as OC
    B = baza(); tt = OC.toks(upit)
    if not tt: return []
    sets = [{p['idx'] for p in B['idx'].get(t, [])} for t in tt]
    ids = set.intersection(*sets) if sets else set()
    P = [p for p in B['P'] if p['idx'] in ids]
    P.sort(key=lambda p: -p['ovr'])
    return [db_opis(p) for p in P[:n]]

# ------------------------------------------------------------------ rucni popis
def rucne():
    p = rucne_put()
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}

def spremi_rucne(d):
    p = rucne_put(); tmp = p + '.tmp'
    json.dump(d, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, p)

_wl = threading.Lock()
def dodaj(db_id, r, izvor='rucno'):
    with _wl:
        return _dodaj(db_id, r, izvor)

def _dodaj(db_id, r, izvor):
    d = rucne()
    d[str(db_id)] = {'tm_id': r['tm_id'], 'tm_ime': r['name'], 'klub': r.get('club'), 'vrijednost': r['value'],
                     'godine': r['age'], 'pozicija': r['pos'], 'liga_kod': r.get('liga_kod'), 'ea_pred': r['ea_pred'],
                     'kontekst': r.get('kontekst'), 'izvor': izvor, 'datum': datetime.date.today().isoformat(),
                     'visina': r.get('visina'), 'drzave': r.get('nat') or []}
    spremi_rucne(d)
    return d[str(db_id)]

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for q in trazi(' '.join(sys.argv[1:]) or 'Karim Benzema')[:3]:
        r = izracun(q)
        print(r['name'], r.get('club'), r.get('age'), r.get('value'), '->', r.get('cilj'), '(EA %.1f)' % r['ea_pred'] if 'ea_pred' in r else r.get('greska'), '|', r.get('kontekst'))
