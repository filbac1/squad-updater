# -*- coding: utf-8 -*-
"""
Overall iz Transfermarkta - formula: trzisna vrijednost + godine (+ pozicija, ugovor, jacina kluba)

1. Skine aktualne sastave lige s transfermarkt.com (vrijednost, datum rodenja, pozicija, ugovor).
2. Skine EA FC ocjene (drop-api.ea.com) - sluze SAMO za kalibraciju formule.
3. Uparuje igrace (datum rodenja + ime), nauci formulu (regresija) i izracuna "TM overall" za SVE igrace lige.

Koristenje:
    python tm_overall.py            -> Premier League (GB1)
    python tm_overall.py GB1 ES1    -> vise liga (TM kodovi: GB1, ES1, IT1, L1, FR1, NL1, PO1, TR1, GR1 ...)
    --osvjezi                       -> ponovno skini podatke (inace koristi cache mlađi od 3 dana)

Izlaz: mapa izvjestaji\\tm_overall_<liga>_<datum>.txt / .csv
"""
import os, sys, re, json, time, html, datetime, unicodedata, collections, urllib.request, csv
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache'); os.makedirs(CACHE, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'}
REFRESH = '--osvjezi' in sys.argv
TODAY = datetime.date.today()
SEASON = TODAY.year if TODAY.month >= 7 else TODAY.year - 1     # TM saison_id

def clean(s):
    return html.unescape(re.sub(r'<.*', '', s, flags=re.S)).strip()

def get(url, tries=4):
    for a in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                raw = r.read()
            try: return raw.decode('utf-8')
            except UnicodeDecodeError: return raw.decode('cp1252', 'replace')
        except Exception as e:
            print('   ! %s (%s), pokusavam ponovno...' % (url, e)); time.sleep(5 * (a + 1))
    raise SystemExit('Ne mogu dohvatiti: ' + url)

def cached(name, fn, max_days=3):
    p = os.path.join(CACHE, name)
    if not REFRESH and os.path.exists(p) and time.time() - os.path.getmtime(p) < max_days * 86400:
        return json.load(open(p, encoding='utf-8'))
    d = fn(); json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False); return d

# ---------------- Transfermarkt ----------------
def tm_league(code):
    t = get('https://www.transfermarkt.com/x/startseite/wettbewerb/%s/saison_id/%d' % (code, SEASON))
    lname = html.unescape(re.search(r'<h1[^>]*>\s*(.*?)\s*</h1>', t, re.S).group(1)).strip()
    clubs = sorted(set(re.findall(r'href="/([^/"]+)/startseite/verein/(\d+)/saison_id/%d"' % SEASON, t)))
    players = []
    for slug, cid in clubs:
        time.sleep(3)
        k = get('https://www.transfermarkt.com/%s/kader/verein/%s/saison_id/%d/plus/1' % (slug, cid, SEASON))
        club = html.unescape(re.search(r'<h1[^>]*>\s*(.*?)\s*</h1>', k, re.S).group(1)).strip()
        seg = k[k.find('class="items"'):]
        n = 0
        for r in re.split(r'<tr class="(?:odd|even)">', seg)[1:]:
            m = re.search(r'<a href="/[^"]+/profil/spieler/(\d+)">\s*(.*?)\s*</a>', r, re.S)
            if not m: continue
            pos = re.search(r'<tr>\s*<td>\s*(.*?)\s*</td>\s*</tr>', r, re.S)
            dob = re.search(r'(\d\d)/(\d\d)/(\d{4}) \((\d+)\)', r)
            val = re.search(r'marktwertverlauf/spieler/\d+">[^\d<]*([\d.,]+)\s*(bn|m|k)', r, re.I)
            con = re.findall(r'<td class="zentriert">(\d\d/\d\d/\d{4}|-)</td>', r)
            nat = re.findall(r'title="([^"]+)" alt="[^"]+" class="flaggenrahmen"', r)
            h = re.search(r'(\d),(\d\d)m', r)
            players.append({
                'tm_id': int(m.group(1)), 'name': clean(m.group(2)), 'club': club,
                'pos': html.unescape(pos.group(1).strip()) if pos else '',
                'dob': '%s-%s-%s' % (dob.group(3), dob.group(2), dob.group(1)) if dob else None,
                'age': int(dob.group(4)) if dob else None,
                'nat': html.unescape(nat[0]) if nat else '',
                'height': int(h.group(1)) * 100 + int(h.group(2)) if h else None,
                'contract': con[-1] if con else '-',
                'value': float(val.group(1).replace(',', '')) * {'bn': 1e9, 'm': 1e6, 'k': 1e3}[val.group(2).lower()] if val else None})
            n += 1
        print('   %-32s %3d igraca' % (club, n))
    return {'league': lname, 'players': players}

# ---------------- EA FC (kalibracija) ----------------
def ea_all():
    out, off = [], 0
    while True:
        d = json.loads(get('https://drop-api.ea.com/rating/ea-sports-fc?locale=en&limit=100&offset=%d' % off))
        out += [{'first': e['firstName'], 'last': e['lastName'], 'common': e['commonName'], 'bd': e['birthdate'],
                 'ovr': e['overallRating'], 'women': (e.get('gender') or {}).get('id') == 1,
                 'team': (e.get('team') or {}).get('label'), 'pos': (e.get('position') or {}).get('shortLabel')}
                for e in d['items']]
        off += len(d['items'])
        if not d['items'] or off >= d['totalItems']: return out
        time.sleep(0.5)

def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    for a, b in (('ø', 'o'), ('Ø', 'O'), ('ß', 'ss'), ('æ', 'ae'), ('ł', 'l'), ('đ', 'd'), ('Đ', 'D')):
        s = s.replace(a, b)
    return set(re.sub(r'[^a-z ]', ' ', s.lower()).split())

def match_ea(players, ea):
    byd = collections.defaultdict(list)
    for e in ea:
        if e['women']: continue
        m, d, y = e['bd'].split()[0].split('/'); byd['%s-%02d-%02d' % (y, int(m), int(d))].append(e)
    for p in players:
        nt = norm(p['name'])
        c = [e for e in byd.get(p['dob'], []) if nt & (norm(e['first']) | norm(e['last']) | norm(e['common']))]
        p['ea'] = c[0] if c else None

# ---------------- formula ----------------
GRP = {'Goalkeeper': 'GK', 'Centre-Back': 'CB', 'Left-Back': 'FB', 'Right-Back': 'FB', 'Defensive Midfield': 'DM',
       'Central Midfield': 'CM', 'Attacking Midfield': 'AM', 'Left Winger': 'W', 'Right Winger': 'W',
       'Left Midfield': 'W', 'Right Midfield': 'W', 'Centre-Forward': 'CF', 'Second Striker': 'CF'}
PES = {'Goalkeeper': 'GK', 'Centre-Back': 'CB', 'Left-Back': 'LB', 'Right-Back': 'RB', 'Defensive Midfield': 'DMF',
       'Central Midfield': 'CMF', 'Attacking Midfield': 'AMF', 'Left Winger': 'LWF', 'Right Winger': 'RWF',
       'Left Midfield': 'LMF', 'Right Midfield': 'RMF', 'Centre-Forward': 'CF', 'Second Striker': 'SS'}
GROUPS = ['CB', 'FB', 'DM', 'CM', 'AM', 'W', 'CF']            # GK = referenca (0)
NAMES = ['ln(vrijednost / 1M EUR)', 'ln(vrijednost) iznad 40M (bonus za zvijezde)', 'godine', 'godine iznad 24', 'godine iznad 28', 'godine iznad 31',
         'ln(vrij.) x godine iznad 28', 'ln(vrij.) x godine ispod 24', 'godina ugovora (max 4)'] + \
        ['pozicija ' + g for g in GROUPS] + ['jacina kluba (ln prosjek top14 vrij.)']

def contract_years(p):
    try:
        d, m, y = map(int, p['contract'].split('/')); return min(max(0.0, (datetime.date(y, m, d) - TODAY).days / 365.25), 4.0)
    except Exception:
        return 1.0

def feats(p, clubm):
    L = np.log(max(p['value'] or 5e4, 5e4) / 1e6); a = p['age'] or 25; g = GRP.get(p['pos'], 'CM')
    return [L, max(L - np.log(40), 0), a, max(a - 24, 0), max(a - 28, 0), max(a - 31, 0), L * max(a - 28, 0), L * max(24 - a, 0), contract_years(p)] + \
           [1.0 if g == x else 0.0 for x in GROUPS] + [clubm[p['club']]]

def ridge(X, y, lam=1.0):
    X = np.asarray(X, float); mu = X.mean(0); sd = X.std(0) + 1e-9
    Z = np.c_[(X - mu) / sd, np.ones(len(X))]; I = np.eye(Z.shape[1]) * lam; I[-1, -1] = 0
    w = np.linalg.solve(Z.T @ Z + I, Z.T @ y)
    coef = w[:-1] / sd; const = w[-1] - (coef * mu).sum()            # natrag u "sirove" jedinice
    return coef, const

def main():
    codes = [a.upper() for a in sys.argv[1:] if not a.startswith('--')] or ['GB1']
    print('EA FC ocjene (kalibracija)...')
    ea = cached('ea_fc.json', ea_all)
    print('   %d igraca' % len(ea))
    allp, lnames = [], []
    for code in codes:
        print('Transfermarkt %s, sezona %d/%d...' % (code, SEASON, SEASON + 1))
        d = cached('tm_%s_%d.json' % (code, SEASON), lambda: tm_league(code))
        for p in d['players']: p['league'] = d['league']; p['name'] = clean(p['name'])
        allp += d['players']; lnames.append(d['league'])
    match_ea(allp, ea)

    clubL = collections.defaultdict(list)
    for p in allp:
        if p['value']: clubL[p['club']].append(np.log(p['value'] / 1e6))
    clubm = {c: float(np.mean(sorted(v)[-14:])) for c, v in clubL.items()}

    train = [p for p in allp if p['ea'] and p['value'] and p['age']]
    X = [feats(p, clubm) for p in train]; y = np.array([p['ea']['ovr'] for p in train], float)
    # 5-fold provjera tocnosti
    idx = np.arange(len(train)); np.random.seed(1); np.random.shuffle(idx); cv = np.zeros(len(train))
    for k in range(5):
        te = idx[k::5]; tr = np.setdiff1d(idx, te); c, b = ridge([X[i] for i in tr], y[tr])
        cv[te] = np.array([X[i] for i in te]) @ c + b
    err = cv - y
    coef, const = ridge(X, y)
    for p in allp:
        p['tm_ovr'] = int(np.clip(np.round(np.array(feats(p, clubm)) @ coef + const), 40, 99))

    outdir = os.path.join(HERE, 'izvjestaji'); os.makedirs(outdir, exist_ok=True)
    stamp = '%s_%s' % ('_'.join(codes), datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S'))
    order = sorted(allp, key=lambda p: (p['league'], p['club'], -p['tm_ovr']))
    with open(os.path.join(outdir, 'tm_overall_%s.csv' % stamp), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['TM ID', 'Igrac', 'Klub', 'Liga', 'Pozicija (PES)', 'Godine', 'Datum rodenja', 'Nacionalnost',
                    'Vrijednost (M EUR)', 'Ugovor do', 'TM overall', 'EA FC overall', 'Razlika TM-EA'])
        for p in order:
            e = p['ea']['ovr'] if p['ea'] else ''
            w.writerow([p['tm_id'], p['name'], p['club'], p['league'], PES.get(p['pos'], p['pos']), p['age'], p['dob'], p['nat'],
                        ('%.2f' % (p['value'] / 1e6)).replace('.', ',') if p['value'] else '', p['contract'], p['tm_ovr'],
                        e, (p['tm_ovr'] - e) if e != '' else ''])

    with open(os.path.join(outdir, 'tm_overall_%s.txt' % stamp), 'w', encoding='utf-8-sig') as f:
        f.write('TM OVERALL - %s   (%s)\n' % (', '.join(lnames), datetime.datetime.now().strftime('%d.%m.%Y. %H:%M')))
        f.write('Transfermarkt sezona %d/%d, igraca: %d. Kalibrirano na %d igraca uparenih s EA FC ocjenama.\n'
                % (SEASON, SEASON + 1, len(allp), len(train)))
        f.write('Tocnost (5-fold, na igracima koje formula nije vidjela): prosjecna greska %.2f, RMSE %.2f, '
                'unutar +-2: %.0f %%, unutar +-3: %.0f %%\n\n'
                % (np.abs(err).mean(), np.sqrt((err ** 2).mean()), 100 * (np.abs(err) <= 2).mean(), 100 * (np.abs(err) <= 3).mean()))
        f.write('FORMULA:  OVR = %.2f' % const)
        for n, c in zip(NAMES, coef): f.write('\n   %+8.3f x %s' % (c, n))
        f.write('\n   (pozicija GK = 0; rezultat zaokruzen i ogranicen na 40-99)\n')
        f.write('\nPrimjeri (CM, ugovor 3 god., prosjecan klub lige):\n      vrijednost:')
        vals = [1, 3, 10, 30, 60, 100]
        f.write(''.join('%7s' % ('%gM' % v) for v in vals) + '\n')
        cm = float(np.median(list(clubm.values())))
        for age in (18, 21, 24, 27, 30, 33, 36):
            row = []
            for v in vals:
                q = {'value': v * 1e6, 'age': age, 'pos': 'Central Midfield', 'contract': '30/06/%d' % (TODAY.year + 3), 'club': '_'}
                row.append(int(np.round(np.array(feats(q, dict(clubm, _=cm))) @ coef + const)))
            f.write('   %2d godina:   ' % age + ''.join('%7d' % x for x in row) + '\n')
        cur = None
        for p in order:
            if p['club'] != cur:
                cur = p['club']; f.write('\n%s\n' % cur.upper())
                f.write('   %-28s %-4s %4s %9s %11s %4s %4s\n' % ('Igrac', 'Poz', 'God', 'Vrij(M)', 'Ugovor', 'TM', 'EA'))
            f.write('   %-28s %-4s %4s %9s %11s %4d %4s\n' % (p['name'][:28], PES.get(p['pos'], '?'), p['age'] or '?',
                    '%.1f' % (p['value'] / 1e6) if p['value'] else '-', p['contract'], p['tm_ovr'], p['ea']['ovr'] if p['ea'] else '-'))
    print('\nGotovo. Tocnost: prosjecna greska %.2f overalla. Izvjestaj u: %s' % (np.abs(err).mean(), outdir))
    print('   tm_overall_%s.txt / .csv' % stamp)

if __name__ == '__main__':
    main()
