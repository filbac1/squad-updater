# -*- coding: utf-8 -*-
"""
Katalog SVIH liga s Transfermarkta (Europa, Amerika, Azija, Afrika; svi rangovi) -> cache\\katalog_liga.json (30 dana).

    python katalog_liga.py            -> skini / osvjezi katalog i ispisi broj liga
"""
import os, re, sys, json, time, html

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tm_overall as T

FILE = os.path.join(HERE, 'cache', 'katalog_liga.json')
KONT = {'europa': 'Europa', 'amerika': 'Amerika', 'asien': 'Azija i Oceanija', 'afrika': 'Afrika'}

def parse(t, kont):
    seg = t[t.find('class="items"'):]
    seg = seg[:seg.find('</tbody>')]
    out, tier = [], ''
    for r in re.split(r'<tr(?: class="(?:odd|even)")?>', seg)[1:]:
        m = re.match(r'\s*<td class="extrarow[^"]*"[^>]*>(.*?)</td>', r, re.S)
        if m: tier = T.clean(m.group(1)); continue
        c = re.search(r'href="/([^/"]+)/startseite/wettbewerb/([A-Z0-9]+)" title="([^"]+)"', r)
        if not c: continue
        land = re.search(r'title="([^"]+)" alt="[^"]+" class="flaggenrahmen"', r)
        z = re.findall(r'<td class="zentriert">([^<]*)</td>', r)
        val = re.search(r'rechts hauptlink">([^<]*)<', r)
        out.append({'kod': c.group(2), 'naziv': html.unescape(c.group(3)), 'drzava': html.unescape(land.group(1)) if land else '',
                    'rang': tier, 'kontinent': kont, 'klubova': int(z[0]) if z and z[0].strip().isdigit() else None,
                    'vrijednost': T.clean(val.group(1)) if val else ''})
    return out

def skini():
    allc = {}
    for slug, kont in KONT.items():
        for page in range(1, 40):
            t = T.get('https://www.transfermarkt.com/wettbewerbe/%s?page=%d' % (slug, page))
            rows = parse(t, kont)
            new = [r for r in rows if r['kod'] not in allc]
            for r in new: allc[r['kod']] = r
            print('  %s, stranica %d: %d liga' % (kont, page, len(new)), flush=True)
            if not new: break
            time.sleep(1.5)
    L = sorted(allc.values(), key=lambda r: (r['kontinent'], r['drzava'], r['rang'], r['naziv']))
    json.dump(L, open(FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    return L

def katalog(osvjezi=False):
    if not osvjezi and os.path.exists(FILE) and time.time() - os.path.getmtime(FILE) < 30 * 86400:
        return json.load(open(FILE, encoding='utf-8'))
    return skini()

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    L = katalog(osvjezi=True)
    print('GOTOVO: %d liga u katalogu -> %s' % (len(L), FILE))
