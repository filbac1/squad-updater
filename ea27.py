# -*- coding: utf-8 -*-
"""
Skida EA SPORTS FC 27 ocjene sa sluzbene EA stranice (www.ea.com/games/ea-sports-fc/ratings?page=N).
drop-api.ea.com i dalje vraca FC 26, zato citamo podatke ugradene u stranicu.
Spremanje: cache\\ea_fc27.json (isti oblik kao ea_fc.json). Nastavlja gdje je stao.

    python ea27.py
"""
import os, re, sys, json, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'cache', 'ea_fc27.json')
PART = OUT + '.part'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
URL = 'https://www.ea.com/games/ea-sports-fc/ratings?page=%d'

def get(url):
    for a in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            print('  greska (%s), pokusavam ponovno...' % e, flush=True); time.sleep(10 * (a + 1))
    return ''

def items(html):
    """Izvuci JSON objekte igraca ({"id":..,"rank":..,"overallRating":..}) iz stranice."""
    t = html.replace('\\"', '"')
    dec = json.JSONDecoder(); out = []
    for m in re.finditer(r'\{"id":\d+,"rank":\d+,"overallRating"', t):
        try:
            o, _ = dec.raw_decode(t, m.start())
        except ValueError:
            continue
        out.append(o)
    return out

def conv(e):
    return {'id': e['id'], 'first': e.get('firstName'), 'last': e.get('lastName'), 'common': e.get('commonName'),
            'bd': e.get('birthdate') or '', 'ovr': e['overallRating'],
            'women': (e.get('gender') or {}).get('id') == 1,
            'team': (e.get('team') or {}).get('label'), 'league': e.get('leagueName'),
            'pos': (e.get('position') or {}).get('shortLabel'),
            # detalji (za realne atribute u PES-u)
            'stats': {k: (v.get('value') if isinstance(v, dict) else v) for k, v in (e.get('stats') or {}).items()},
            'alt': [a.get('shortLabel') for a in e.get('alternatePositions') or []],
            'ps': [(a.get('label'), (a.get('type') or {}).get('id')) for a in e.get('playerAbilities') or []],
            'sm': e.get('skillMoves'), 'wf': e.get('weakFootAbility'), 'foot': e.get('preferredFoot'),
            'nat': (e.get('nationality') or {}).get('label')}

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    from concurrent.futures import ThreadPoolExecutor
    data = json.load(open(PART, encoding='utf-8')) if os.path.exists(PART) else {'pages': {}, 'total': None}
    if any(v and 'stats' not in v[0] for v in data['pages'].values()):
        data = {'pages': {}, 'total': None}          # stari format bez detalja -> ispocetka
    def fetch(page):
        t = get(URL % page)
        m = re.search(r'"totalItems":(\d+)', t)
        return page, (int(m.group(1)) if m else None), [conv(e) for e in items(t)]
    if '1' not in data['pages']:
        _, data['total'], data['pages']['1'] = fetch(1)
    total = data['total'] or 20000
    todo = [p for p in range(1, (total + 99) // 100 + 1) if str(p) not in data['pages']]
    with ThreadPoolExecutor(4) as ex:
        for n_, (page, tot, it) in enumerate(ex.map(fetch, todo), 1):
            data['pages'][str(page)] = it
            print('[%d/%d] stranica %d: %d igraca' % (n_, len(todo), page, len(it)), flush=True)
            if page % 20 == 0: json.dump(data, open(PART, 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(data, open(PART, 'w', encoding='utf-8'), ensure_ascii=False)
    seen, allp = set(), []
    for k in sorted(data['pages'], key=int):
        for e in data['pages'][k]:
            if e['id'] not in seen: seen.add(e['id']); allp.append(e)
    json.dump(allp, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    import datetime
    open(os.path.join(HERE, 'cache', 'ea_datum.txt'), 'w').write(datetime.date.today().isoformat())      # datum ocjena (mtime datoteke u paketu nije pouzdan)
    print('GOTOVO: %d igraca (EA kaze %s) -> %s' % (len(allp), data['total'], OUT))

if __name__ == '__main__':
    main()
