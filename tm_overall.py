# -*- coding: utf-8 -*-
"""
Overall iz Transfermarkta - formula: trzisna vrijednost + godine (+ pozicija, jacina kluba)

1. Skine aktualne sastave lige s transfermarkt.com (vrijednost, datum rodenja, pozicija, ugovor).
2. Skine EA FC ocjene (drop-api.ea.com) - sluze SAMO za kalibraciju formule.
3. Uparuje igrace (datum rodenja + ime), nauci formulu (regresija) i izracuna "TM overall" za SVE igrace lige.
   Formula se uci na TM vrijednostima iz trenutka kad su EA ocjene nastale (KAL_DATUM, iz povijesti
   vrijednosti), a primjenjuje na danasnje vrijednosti - tako vremenski raskorak EA vs TM ne kvari formulu.

Koristenje:
    python tm_overall.py            -> Premier League (GB1)
    python tm_overall.py GB1 ES1    -> vise liga (TM kodovi: GB1, ES1, IT1, L1, FR1, NL1, PO1, TR1, GR1 ...)
    --osvjezi                       -> ponovno skini podatke (inace koristi cache mlađi od 3 dana)
    --kal=GB1,A1,C1                 -> lige na kojima se formula UCI (uz izlazne lige); default KAL_LIGE.
                                       Bitno za lige koje EA nema (npr. KR1 = HNL): formula uci na ligama slicnog ranga.
    --kal=                          -> uci samo na izlaznim ligama

Izlaz: mapa izvjestaji\\tm_overall_<liga>_<datum>.xlsx / .txt
"""
import os, sys, re, json, time, html, datetime, unicodedata, collections, urllib.request, urllib.error, csv
import numpy as np
import mreza as M

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache'); os.makedirs(CACHE, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'}
REFRESH = '--osvjezi' in sys.argv
TODAY = datetime.date.today()
SEASON = TODAY.year if TODAY.month >= 7 else TODAY.year - 1     # TM saison_id
KAL_LIGE = ['GB1', 'A1', 'C1', 'SC1', 'DK1', 'PL1']   # PL + lige ranga slicnog HNL-u koje EA ima
KAL_DATUM = datetime.date(2025, 9, 1)   # izlazak EA FC 26 ocjena; testirano: najbolje poklapanje (greska 1.6 umjesto 2.3)

def clean(s):
    return html.unescape(re.sub(r'<.*', '', s, flags=re.S)).strip()

def get(url, tries=4):
    """GET s ponavljanjem. Kod blokade (HTTP 429/403/503) ceka sve dulje (1, 2, 4... do 15 min), do ~1 h ukupno."""
    a = blok = 0
    while a < tries:
        try:
            raw = M.dohvati(url, UA, 60)
            try: return raw.decode('utf-8')
            except UnicodeDecodeError: return raw.decode('cp1252', 'replace')
        except urllib.error.HTTPError as e:
            if e.code == 404: raise SystemExit('Ne postoji (404): ' + url)
            if e.code in (429, 403, 503) and blok < 8:
                w = min(60 * 2 ** blok, 900); blok += 1
                print('   ! Transfermarkt privremeno blokira (%d), cekam %d s...' % (e.code, w), flush=True)
                time.sleep(w); continue
            print('   ! %s (%s), pokusavam ponovno...' % (url, e)); a += 1; time.sleep(5 * a)
        except Exception as e:
            print('   ! %s (%s), pokusavam ponovno...' % (url, e)); a += 1; time.sleep(5 * a)
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
                'nat': html.unescape(nat[0]) if nat else '', 'nats': [html.unescape(x) for x in dict.fromkeys(nat)],
                'height': int(h.group(1)) * 100 + int(h.group(2)) if h else None,
                'contract': con[-1] if con else '-',
                'value': float(val.group(1).replace(',', '')) * {'bn': 1e9, 'm': 1e6, 'k': 1e3}[val.group(2).lower()] if val else None})
            n += 1
        print('   %-32s %3d igraca' % (club, n))
    return {'league': lname, 'players': players}

def tm_history(players):
    """Povijest trzisne vrijednosti (TM API). Stare tocke se ne mijenjaju, pa je cache trajan."""
    p = os.path.join(CACHE, 'tm_povijest.json')
    H = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    todo = [q for q in players if str(q['tm_id']) not in H]
    if todo: print('   povijest vrijednosti: %d novih igraca (~%d min)...' % (len(todo), len(todo) // 80 + 1))
    hdr = dict(UA, Accept='application/json')
    for i, q in enumerate(todo):
        k = str(q['tm_id'])
        for a in range(3):
            try:
                r = M.dohvati('https://tmapi-alpha.transfermarkt.technology/player/%s/market-value-history' % k, hdr, 30)
                H[k] = [(h['marketValue']['determined'], h['marketValue']['value']) for h in json.loads(r)['data']['history']]
                break
            except Exception as e:
                print('   ! povijest %s: %s' % (k, e)); time.sleep(5 * (a + 1))
        if i % 50 == 49: json.dump(H, open(p, 'w', encoding='utf-8'))
        time.sleep(0.7)
    if todo: json.dump(H, open(p, 'w', encoding='utf-8'))
    return H

def value_at(hist, date):
    b = [v for d, v in sorted(hist) if v and datetime.date.fromisoformat(d) <= date]
    return b[-1] if b else None

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
         'ln(vrij.) x godine iznad 28', 'ln(vrij.) x godine ispod 24'] + \
        ['pozicija ' + g for g in GROUPS] + ['jacina kluba (ln prosjek top14 vrij.)']

def contract_years(p):
    try:
        d, m, y = map(int, p['contract'].split('/')); return min(max(0.0, (datetime.date(y, m, d) - TODAY).days / 365.25), 4.0)
    except Exception:
        return 1.0

def feats(p, clubm, value=None, age=None):
    L = np.log(max(value or p['value'] or 5e4, 5e4) / 1e6); a = age or p['age'] or 25; g = GRP.get(p['pos'], 'CM')
    return [L, max(L - np.log(40), 0), a, max(a - 24, 0), max(a - 28, 0), max(a - 31, 0), L * max(a - 28, 0), L * max(24 - a, 0)] + \
           [1.0 if g == x else 0.0 for x in GROUPS] + [clubm[p['club']]]

def ridge(X, y, lam=1.0):
    X = np.asarray(X, float); mu = X.mean(0); sd = X.std(0) + 1e-9
    Z = np.c_[(X - mu) / sd, np.ones(len(X))]; I = np.eye(Z.shape[1]) * lam; I[-1, -1] = 0
    w = np.linalg.solve(Z.T @ Z + I, Z.T @ y)
    coef = w[:-1] / sd; const = w[-1] - (coef * mu).sum()            # natrag u "sirove" jedinice
    return coef, const

def write_xlsx(path, order, lnames, coef, const, err, ntrain, clubm, errout, kal):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.utils import get_column_letter
    F = Font(name='Arial', size=10); FB = Font(name='Arial', size=10, bold=True, color='FFFFFF')
    HF = PatternFill('solid', fgColor='1F3864'); thin = Side(style='thin', color='BFBFBF')
    wb = Workbook(); ws = wb.active; ws.title = 'Igraci'
    ws.append(['TM ID', 'Igrač', 'Klub', 'Liga', 'Pozicija (PES)', 'Godine', 'Datum rođenja', 'Nacionalnost',
               'Vrijednost (M EUR)', 'Ugovor do', 'TM overall', 'EA FC overall', 'Razlika TM-EA'])
    for i, p in enumerate(order, start=2):
        ws.append([p['tm_id'], p['name'], p['club'], p['league'], PES.get(p['pos'], p['pos']), p['age'], p['dob'], p['nat'],
                   round(p['value'] / 1e6, 2) if p['value'] else None, p['contract'], p['tm_ovr'],
                   p['ea']['ovr'] if p['ea'] else None, '=IF(L%d="","",K%d-L%d)' % (i, i, i)])
    n = len(order) + 1
    for row in ws.iter_rows(min_row=1, max_row=n):
        for c in row:
            c.font = F; c.border = Border(bottom=thin)
    for c in ws[1]:
        c.font = FB; c.fill = HF; c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[1].height = 30
    for r in range(2, n + 1):
        ws.cell(r, 9).number_format = '0.00'
        for cc in (1, 5, 6, 7, 10, 11, 12, 13): ws.cell(r, cc).alignment = Alignment(horizontal='center')
        ws.cell(r, 11).font = Font(name='Arial', size=10, bold=True)
    for i, w in enumerate([9, 28, 24, 15, 9, 8, 12, 18, 11, 12, 9, 9, 10], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'C2'; ws.auto_filter.ref = 'A1:M%d' % n
    ws.conditional_formatting.add('K2:K%d' % n, ColorScaleRule(start_type='num', start_value=55, start_color='F8696B',
        mid_type='num', mid_value=75, mid_color='FFEB84', end_type='num', end_value=90, end_color='63BE7B'))
    ws.conditional_formatting.add('M2:M%d' % n, ColorScaleRule(start_type='num', start_value=-6, start_color='F8696B',
        mid_type='num', mid_value=0, mid_color='FFFFFF', end_type='num', end_value=6, end_color='5B9BD5'))

    fs = wb.create_sheet('Formula')
    rows = [('TM overall - formula (%s, TM sezona %d/%d)' % (', '.join(lnames), SEASON, SEASON + 1), None),
            ('Kalibrirano na %d igraca uparenih s EA FC ocjenama, TM vrijednost na dan %s.' % (ntrain, KAL_DATUM.strftime('%d.%m.%Y.')), None),
            ('Tocnost (5-fold): prosjecna greska %.2f, unutar +-2: %.0f %%, unutar +-3: %.0f %%'
             % (np.abs(err).mean(), 100 * (np.abs(err) <= 2).mean(), 100 * (np.abs(err) <= 3).mean()), None),
            ('Kalibracijske lige: %s. Greska na igracima ovih liga s EA ocjenom (%d): %.2f'
             % (', '.join(kal), len(errout), np.abs(errout).mean() if len(errout) else float('nan')), None),
            ('Clan formule', 'Koeficijent'), ('Konstanta', float(const))] + [(nm, float(c)) for nm, c in zip(NAMES, coef)] + \
           [('Pozicija GK = 0; rezultat se zaokruzuje i ogranicava na 40-99. Ljestvica je EA FC (ne PES).', None)]
    for r in rows: fs.append(list(r))
    for row in fs.iter_rows():
        for c in row: c.font = F
    fs['A1'].font = Font(name='Arial', size=12, bold=True)
    for c in fs[5]: c.font = FB; c.fill = HF
    for r in range(6, 7 + len(coef)):
        fs.cell(r, 2).number_format = '+0.000;-0.000;0'; fs.cell(r, 2).font = Font(name='Arial', size=10, color='0000FF')
    fs.column_dimensions['A'].width = 52; fs.column_dimensions['B'].width = 13
    vals = [1, 3, 10, 30, 60, 100]; cm = float(np.median(list(clubm.values())))
    st = fs.max_row + 1
    fs.cell(st, 1, 'Primjeri (CM, prosjecan klub lige)').font = Font(name='Arial', size=10, bold=True)
    fs.cell(st + 1, 1, 'Godine / vrijednost')
    for j, v in enumerate(vals): fs.cell(st + 1, 2 + j, '%gM' % v)
    for c in fs[st + 1]: c.font = FB; c.fill = HF
    for i, age in enumerate((18, 21, 24, 27, 30, 33, 36)):
        fs.cell(st + 2 + i, 1, age).alignment = Alignment(horizontal='left')
        for j, v in enumerate(vals):
            q = {'value': v * 1e6, 'age': age, 'pos': 'Central Midfield', 'club': '_'}
            fs.cell(st + 2 + i, 2 + j, int(np.round(np.array(feats(q, dict(clubm, _=cm))) @ coef + const)))
        for c in fs[st + 2 + i]: c.font = F
    for j in range(3, 8): fs.column_dimensions[get_column_letter(j)].width = 8
    wb.save(path)


def main():
    codes = [a.upper() for a in sys.argv[1:] if not a.startswith('--')] or ['GB1']
    kal = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--kal=')), None)
    kal = KAL_LIGE if kal is None else [k.strip().upper() for k in kal.split(',') if k.strip()]
    print('EA FC ocjene (kalibracija)...')
    ea = cached('ea_fc.json', ea_all)
    print('   %d igraca' % len(ea))
    allp, lnames = [], []
    pool, outp = [], []
    for code in codes + [k for k in kal if k not in codes]:
        print('Transfermarkt %s, sezona %d/%d%s...' % (code, SEASON, SEASON + 1, '' if code in codes else ' (samo kalibracija)'))
        d = cached('tm_%s_%d.json' % (code, SEASON), lambda: tm_league(code))
        for p in d['players']: p['league'] = d['league']; p['name'] = clean(p['name']); p['out'] = code in codes
        pool += d['players']
        if code in codes: outp += d['players']; lnames.append(d['league'])
    allp = pool
    match_ea(allp, ea)

    clubL = collections.defaultdict(list)
    for p in allp:
        if p['value']: clubL[p['club']].append(np.log(p['value'] / 1e6))
    clubm = {c: float(np.mean(sorted(v)[-14:])) for c, v in clubL.items()}

    cand = [p for p in allp if p['ea'] and p['value'] and p['age'] and p['dob']]
    H = tm_history(cand)
    train = []
    for p in cand:
        v = value_at(H.get(str(p['tm_id']), []), KAL_DATUM)
        if v:
            p['_kv'] = v; p['_ka'] = (KAL_DATUM - datetime.date.fromisoformat(p['dob'])).days / 365.25; train.append(p)
    X = [feats(p, clubm, p['_kv'], p['_ka']) for p in train]; y = np.array([p['ea']['ovr'] for p in train], float)
    # 5-fold provjera tocnosti
    idx = np.arange(len(train)); np.random.seed(1); np.random.shuffle(idx); cv = np.zeros(len(train))
    for k in range(5):
        te = idx[k::5]; tr = np.setdiff1d(idx, te); c, b = ridge([X[i] for i in tr], y[tr])
        cv[te] = np.array([X[i] for i in te]) @ c + b
    err = cv - y
    coef, const = ridge(X, y)
    errout = np.array([e for e, p in zip(err, train) if p['out']])
    allp = outp
    for p in allp:
        p['tm_ovr'] = int(np.clip(np.round(np.array(feats(p, clubm)) @ coef + const), 40, 99))

    outdir = os.path.join(HERE, 'izvjestaji'); os.makedirs(outdir, exist_ok=True)
    stamp = '%s_%s' % ('_'.join(codes), datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S'))
    order = sorted(allp, key=lambda p: (p['league'], p['club'], -p['tm_ovr']))
    write_xlsx(os.path.join(outdir, 'tm_overall_%s.xlsx' % stamp), order, lnames, coef, const, err, len(train), {c: clubm[c] for c in {p['club'] for p in allp}}, errout, kal)

    with open(os.path.join(outdir, 'tm_overall_%s.txt' % stamp), 'w', encoding='utf-8-sig') as f:
        f.write('TM OVERALL - %s   (%s)\n' % (', '.join(lnames), datetime.datetime.now().strftime('%d.%m.%Y. %H:%M')))
        f.write('Transfermarkt sezona %d/%d, igraca: %d. Kalibrirano na %d igraca uparenih s EA FC ocjenama (TM vrijednost na dan %s).\n'
                % (SEASON, SEASON + 1, len(allp), len(train), KAL_DATUM.strftime('%d.%m.%Y.')))
        f.write('Tocnost (5-fold, na igracima koje formula nije vidjela): prosjecna greska %.2f, RMSE %.2f, '
                'unutar +-2: %.0f %%, unutar +-3: %.0f %%\n\n'
                % (np.abs(err).mean(), np.sqrt((err ** 2).mean()), 100 * (np.abs(err) <= 2).mean(), 100 * (np.abs(err) <= 3).mean()))
        f.write('Kalibracijske lige: %s. Na igracima izlaznih liga s EA ocjenom (%d): prosjecna greska %.2f\n\n'
                % (', '.join(sorted(set(codes) | set(kal))), len(errout), np.abs(errout).mean() if len(errout) else float('nan')))
        f.write('FORMULA:  OVR = %.2f' % const)
        for n, c in zip(NAMES, coef): f.write('\n   %+8.3f x %s' % (c, n))
        f.write('\n   (pozicija GK = 0; rezultat zaokruzen i ogranicen na 40-99)\n')
        f.write('\nPrimjeri (CM, prosjecan klub lige):\n      vrijednost:')
        vals = [1, 3, 10, 30, 60, 100]
        f.write(''.join('%7s' % ('%gM' % v) for v in vals) + '\n')
        cm = float(np.median([clubm[c] for c in {p['club'] for p in allp}]))
        for age in (18, 21, 24, 27, 30, 33, 36):
            row = []
            for v in vals:
                q = {'value': v * 1e6, 'age': age, 'pos': 'Central Midfield', 'club': '_'}
                row.append(int(np.round(np.array(feats(q, dict(clubm, _=cm))) @ coef + const)))
            f.write('   %2d godina:   ' % age + ''.join('%7d' % x for x in row) + '\n')
        cur = None
        for p in order:
            if p['club'] != cur:
                cur = p['club']; f.write('\n%s\n' % cur.upper())
                f.write('   %-28s %-4s %4s %9s %11s %4s %4s\n' % ('Igrac', 'Poz', 'God', 'Vrij(M)', 'Ugovor', 'TM', 'EA'))
            f.write('   %-28s %-4s %4s %9s %11s %4d %4s\n' % (p['name'][:28], PES.get(p['pos'], '?'), p['age'] or '?',
                    '%.1f' % (p['value'] / 1e6) if p['value'] else '-', p['contract'], p['tm_ovr'], p['ea']['ovr'] if p['ea'] else '-'))
    print('\nGotovo. Tocnost: prosjecna greska %.2f overalla (izlazne lige: %.2f na %d igraca s EA ocjenom). Izvjestaj u: %s'
          % (np.abs(err).mean(), np.abs(errout).mean() if len(errout) else float('nan'), len(errout), outdir))
    print('   tm_overall_%s.xlsx / .txt' % stamp)

if __name__ == '__main__':
    main()
