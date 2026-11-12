# -*- coding: utf-8 -*-
"""Povijest TM vrijednosti (paralelno, 6 niti; nastavlja gdje je stao; cache\\tm_povijest.json).
    python razvoj/povijest_ea27.py          -> igraci upareni s EA FC 27 (kalibracija)
    python razvoj/povijest_ea27.py --sve    -> SVI igraci iz skinutih TM liga (za trend i vrh karijere u predvidanju)"""
import os, sys, json, time, urllib.request, urllib.error, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import tm_overall as T
sys.stdout.reconfigure(encoding='utf-8')
P = os.path.join(HERE, 'cache', 'tm_povijest.json')
H = json.load(open(P, encoding='utf-8')) if os.path.exists(P) else {}
if '--sve' in sys.argv:
    import model_ea27 as ME
    M = []
    for code, f in ME.latest_leagues().items():
        M += json.load(open(f, encoding='utf-8'))['players']
else:
    M = json.load(open(os.path.join(HERE, 'cache', 'ea27_upareni.json'), encoding='utf-8'))
M.sort(key=lambda q: -(q.get('value') or 0))
todo = list(dict.fromkeys(str(q['tm_id']) for q in M if q.get('tm_id') and str(q['tm_id']) not in H))
print('za skinuti: %d' % len(todo), flush=True)
hdr = dict(T.UA, Accept='application/json')
lock = threading.Lock()

def one(k):
    for a in range(4):
        try:
            r = urllib.request.urlopen(urllib.request.Request(
                'https://tmapi-alpha.transfermarkt.technology/player/%s/market-value-history' % k, headers=hdr), timeout=15)
            return k, [(h['marketValue']['determined'], h['marketValue']['value']) for h in json.load(r)['data']['history']]
        except urllib.error.HTTPError as e:
            if e.code == 404: return k, []
            time.sleep(10 * (a + 1))
        except Exception:
            time.sleep(3 * (a + 1))
    return k, None

def save():
    tmp = P + '.tmp'; json.dump(H, open(tmp, 'w', encoding='utf-8')); os.replace(tmp, P)

t0 = time.time(); n = 0
with ThreadPoolExecutor(6) as ex:
    for f in as_completed([ex.submit(one, k) for k in todo]):
        k, h = f.result()
        if h is not None:
            with lock: H[k] = h
        n += 1
        if n % 500 == 0:
            save(); print('  %d/%d (%.0f/min)' % (n, len(todo), n / (time.time() - t0) * 60), flush=True)
save()
print('GOTOVO: %d igraca s poviscu' % len(H), flush=True)
