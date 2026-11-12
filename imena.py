# -*- coding: utf-8 -*-
"""
IMENA S DIJAKRITIKOM s Transfermarkta i EA FC 27 (Galesic -> Galešić, HRGOVIC -> HRGOVIĆ).

    python imena.py --izlaz=<nova baza> [--baza=...]

  Za svakog igraca uparenog s TM-om (tm_ids.json, rucni popis, pojedinacno trazenje) usporeduje se ime iz baze s TM
  imenom (i imenom iz EA FC 27 - TM neka imena pise bez dijakritike; isti datum rodenja + zajednicka rijec) RIJEC PO RIJEC: rijec iz baze bez dijakritike (npr. 'Galesic') zamjenjuje se TM rijecju samo ako je ona ista
  rijec s dijakritikom ('Galešić'). Skracena ili drukcija imena (M. Ali Shaker, Salva/Salvador) se ne diraju.
  Mijenjaju se sva cetiri polja imena u Player.bin (ime, ime na dresu, ime na dresu reprezentacije, ime za
  komentar/japansko), uz ocuvanje velikih slova (dres: GALEŠIĆ).
  Iznimke: baze\\<id>\\imena_rucno.json {"170801": "Marin Šotiček"} - imaju prednost (TM i EA ga pisu Soticek). Izvjestaj: izvjestaji\\imena_zadnje.json.
"""
import os, sys, re, json, glob, struct, unicodedata, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fl27db as D

PF = D.PF
POLJA = (68, 129, 190, 251)          # 61 bajt svako (UTF-8, zavrsava nulom)
DULJINA = 61
RUCNO = 'imena_rucno.json'           # iznimke: {"id igraca": "Ime s kvacicama"} (npr. TM i EA pisu Soticek)
POSEBNA = {'đ': 'd', 'Đ': 'D', 'ð': 'd', 'Ð': 'D', 'ø': 'o', 'Ø': 'O', 'ł': 'l', 'Ł': 'L', 'ß': 'ss', 'æ': 'ae', 'Æ': 'AE',
           'ı': 'i', 'þ': 'th', 'Þ': 'Th', 'œ': 'oe', 'Œ': 'OE', 'ħ': 'h', 'Ħ': 'H'}

def bez(s):
    """Tekst bez dijakritike: 'Galešić' -> 'Galesic', 'Ødegaard' -> 'Odegaard'."""
    s = ''.join(POSEBNA.get(c, c) for c in s)
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

def ima_dijakritiku(s): return bez(s) != s

def popravi(ime, tm_ime):
    """Ime iz baze -> ime s dijakritikom s TM-a (rijec po rijec), ili isto ime ako nema sto popraviti."""
    tm = {}
    for t in re.split(r"[\s\-\.']+", tm_ime or ''):
        if t and ima_dijakritiku(t): tm.setdefault(bez(t).lower(), t)
    if not tm: return ime
    dijelovi = re.split(r"([\s\-\.']+)", ime)
    out = []
    for d in dijelovi:
        t = tm.get(d.lower()) if d and not ima_dijakritiku(d) and len(d) >= 2 else None
        if t: d = t.upper() if d.isupper() else (t.lower() if d.islower() else t[0].upper() + t[1:])
        out.append(d)
    return ''.join(out)

def ea_imena(dob):
    """tm_id -> ime iz EA FC (TM neka imena pise bez dijakritike: Galesic; EA: Galešić). Par: isti datum rodenja i
    zajednicka rijec u imenu, i to jedini takav EA igrac."""
    try: EA = json.load(open(os.path.join(HERE, 'cache', 'ea_fc27.json'), encoding='utf-8'))
    except (OSError, ValueError): return {}
    po = {}
    for e in EA:
        if e.get('women') or not e.get('bd'): continue
        try: mo, d, y = e['bd'].split()[0].split('/')
        except ValueError: continue
        po.setdefault('%s-%02d-%02d' % (y, int(mo), int(d)), []).append(e)
    rijeci = lambda s: {bez(t).lower() for t in re.split(r"[\s\-\.']+", s or '') if len(t) >= 3}
    out = {}
    for t, (ime, d) in dob.items():
        r = rijeci(ime)
        c = [e for e in po.get(d, []) if r & rijeci(' '.join(filter(None, (e.get('first'), e.get('last'), e.get('common')))))]
        if len(c) == 1: out[t] = ' '.join(filter(None, (c[0].get('first'), c[0].get('last'), c[0].get('common'))))
    return out

def tm_imena(mapa):
    """tm_id -> izvor pravopisa: TM ime (lige, rucni popis, reprezentacije) + ime iz EA FC kad je par siguran."""
    I, dob = {}, {}
    for f in glob.glob(os.path.join(HERE, 'cache', 'tm_*_20*.json')):
        try:
            for q in json.load(open(f, encoding='utf-8')).get('players') or []:
                if q.get('tm_id') and q.get('name'):
                    I[int(q['tm_id'])] = q['name']
                    if q.get('dob'): dob[int(q['tm_id'])] = (q['name'], q['dob'])
        except (OSError, ValueError, AttributeError): pass
    for f in glob.glob(os.path.join(HERE, 'cache', 'reprezentacije', '*.json')):
        try:
            for q in json.load(open(f, encoding='utf-8')) or []:
                if q.get('tm_id') and q.get('ime'): I.setdefault(int(q['tm_id']), q['ime'])
        except (OSError, ValueError, TypeError): pass
    try:
        for e in json.load(open(os.path.join(mapa, 'rucne.json'), encoding='utf-8')).values():
            if e.get('tm_id') and e.get('tm_ime'): I.setdefault(int(e['tm_id']), e['tm_ime'])
    except (OSError, ValueError): pass
    for t, n in ea_imena(dob).items(): I[t] = (I.get(t, '') + ' ' + n).strip()
    return I

def parovi(mapa):
    """id igraca u bazi -> TM id (izracun po ligama + rucni popis + pojedinacno trazenje)."""
    d2t = {}
    try:
        for d, t, o in json.load(open(os.path.join(mapa, 'tm_ids.json'))): d2t[d] = t
    except (OSError, ValueError): pass
    for fn in ('rucne.json', 'bez_kluba_trazeno.json'):
        try: J = json.load(open(os.path.join(mapa, fn), encoding='utf-8'))
        except (OSError, ValueError): continue
        for k, v in J.items():
            t = v.get('tm_id') if isinstance(v, dict) else v
            if isinstance(t, int) and not isinstance(t, bool): d2t.setdefault(int(k), t)
    return d2t

def primijeni(praw, mapa, log=print):
    """Vrati (novi Player.bin ili None, popis promjena)."""
    d2t, TI = parovi(mapa), tm_imena(mapa)
    try: RU = {int(k): v for k, v in json.load(open(os.path.join(mapa, RUCNO), encoding='utf-8')).items()}
    except (OSError, ValueError): RU = {}
    raw = bytearray(praw); promj = []
    for i in range(len(raw) // D.REC):
        o = i * D.REC
        pid = struct.unpack_from('<I', raw, o + 8)[0]
        tm = RU.get(pid) or TI.get(d2t.get(pid))
        if not tm or not ima_dijakritiku(tm): continue
        stara = [PF.cstr(raw[o + p:o + p + DULJINA]) for p in POLJA]
        # prednost: rucna iznimka, pa pravopis koji baza vec ima u imenu, pa TM / EA
        izvor = tm if pid in RU else stara[0] + ' ' + stara[3] + ' ' + tm
        nova = [popravi(s, izvor) for s in stara]
        if nova == stara or any(len(n.encode('utf-8')) >= DULJINA for n in nova): continue
        for p, n in zip(POLJA, nova):
            raw[o + p:o + p + DULJINA] = n.encode('utf-8').ljust(DULJINA, b'\0')
        promj.append({'id': pid, 'prije': stara[0], 'sada': nova[0], 'dres': nova[1], 'tm': tm})
    log('Imena s dijakritikom (Transfermarkt, EA FC): popravljeno %d igraca%s' % (len(promj), (' (npr. ' + ', '.join('%s -> %s' % (x['prije'], x['sada']) for x in promj[:6]) + ')') if promj else ''))
    try:
        os.makedirs(os.path.join(HERE, 'izvjestaji'), exist_ok=True)
        json.dump({'vrijeme': datetime.datetime.now().isoformat(timespec='seconds'), 'igraci': promj},
                  open(os.path.join(HERE, 'izvjestaji', 'imena_zadnje.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    except OSError: pass
    return (bytes(raw) if promj else None), promj

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import izvor as IZ, spremanje as SP
    OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
    cfg = IZ.use(IZ.cfg_from_opts(OPT))
    izl = OPT.get('izlaz')
    if not isinstance(izl, str): raise SystemExit('Treba --izlaz=<nova baza>')
    pes = SP.citaj_iz(izl)
    if not pes: raise SystemExit('Nova baza jos ne postoji: %s' % izl)
    praw = PF.wesys(open(os.path.join(pes, 'Player.bin'), 'rb').read())
    data, promj = primijeni(praw, IZ.mapa(cfg), log=lambda s: print(s, flush=True))
    if data is not None:
        SP.zapisi(izl, {'Player.bin': data}, posao={'korak': 'imena s dijakritikom', 'promijenjeno': len(promj)}, log=lambda s: print(s, flush=True))

if __name__ == '__main__':
    main()
