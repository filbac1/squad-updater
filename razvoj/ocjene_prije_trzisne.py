# -*- coding: utf-8 -*-
"""
OCJENE IZ TRANSFERMARKTA -> FL27 baza

1. Odaberes ligu iz baze igre (ili upises TM kod).
2. Program skine sastave s Transfermarkta (vrijednost, godine, pozicija) i izracuna CILJNI overall
   formulom kalibriranom na ocjenama iz same baze (sve lige baze odjednom).
3. Upari TM igrace s igracima u bazi (ime + godine, klub kao potvrda).
4. Atribute svakog uparenog igraca proporcionalno skalira tako da njegov overall (na registriranoj
   poziciji) bude sto blize ciljnom. Profil igraca ostaje isti.
5. Izvjestaj u Excelu; s --upisi i novi Player.bin u mapi izlaz\\ (NE dira igru ni tvoju bazu).

Pokretanje:
    pokreni_ocjene.bat                       -> izbornik liga
    pokreni_ocjene.bat GB1 ES1               -> izravno TM kodovi
    --baza="D:\\neka\\baza"                  -> mapa koja sadrzi Player.bin, Team.bin ... (npr. ModStudio / CommonLib\\common\\etc\\pesdb)
    --upisi                                  -> zapisi izlaz\\common\\etc\\pesdb\\Player.bin
    --kalibriraj                             -> ponovno nauci TM->overall formulu
    --max-promjena=N                         -> ogranici promjenu overalla na +-N (default bez ogranicenja)
    --skala=0.5                              -> ljestvica ispod 82: 0 = cista EA FC 27, 1 = stisnuta kao baza (default 0.5)
    --sve                                    -> sve lige iz baze odjednom (preporuceno uz --csv)
    --samo-rucne / --bez-rucnih              -> samo rucni popis (rucne.json) / ignoriraj rucni popis
    --ea-profil=0.7 / --bez-ea-profila       -> realni atributi iz EA FC 27 (udio EA profila), ili samo proporcionalno
    --bez-ea-dodataka                        -> NE mijenjaj jacu/slabiju nogu, sporedne pozicije, vjestine iz EA
    --bez-ozljeda                            -> NE primjenjuj otpornost na ozljede iz TM povijesti (ozljede.py)
    --bez-ugovora                            -> NE upisuj ugovore i posudbe s TM-a (ugovori.py)
    --bez-brisanja                           -> NE brisi igrace s popisa ciscenje.py (umirovljeni/duplikati)
    --izlaz=<mapa> [--od=izlaz]              -> nova baza u mapi (kopija cijele ulazne baze + novi Player.bin, provjereno);
                                                --od=izlaz: krenuti od zadnjeg izlaza umjesto od originala
    --opseg=<json>                           -> mijenjaju se samo igraci u opsegu (lige / klubovi / igraci), ostalo ostaje isto
    --bez-ocjena                             -> atributi/overall ostaju; primjenjuju se samo podaci, dodaci, ugovori, brisanje
    --bez-reputacije                         -> NE uskladuj reputaciju s novim overallom
    --bez-podataka                           -> NE popravljaj godine / drzavljanstvo / visinu s Transfermarkta
    --stara-kalibracija                      -> stara formula (TM -> ocjene iz baze)
    --baza=<mapa ili .cpk>  --csv-ulaz=<editor.csv>   -> vlastita baza (vidi izvor.py); bez toga baza iz sucelja ili igre
    --dodatne=ALB1,KR2                       -> dodatne TM lige (i kad ih baza nema; nuzno za CSV bez klubova)
    --csv[=putanja]                          -> svjez izvoz cijele baze u CSV formatu PES2020 Editora, s novim
                                                atributima i OverallStats (za import u editor)
"""
import os, sys, re, json, time, datetime, unicodedata, collections, difflib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fl27db as D
import lang as LGX
import overall as O
import tm_overall as T

ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
OPT = dict((a[2:].split('=', 1) + [True])[:2] for a in sys.argv[1:] if a.startswith('--'))
KAL_FILE = os.path.join(HERE, 'kalibracija.json')

# liga iz baze (interni naziv ili "OSTALI:<drzava>") -> TM kod
TM_KOD = {
    'ENGLAND_D1_LEAGUE': 'GB1', 'ENGLAND_D2_LEAGUE': 'GB2', 'SPAIN_D1_LEAGUE': 'ES1', 'SPAIN_D2_LEAGUE': 'ES2',
    'ITALY_D1_LEAGUE': 'IT1', 'ITALY_D2_LEAGUE': 'IT2', 'GERMANY_D1_LEAGUE': 'L1', 'GERMANY_D2_LEAGUE': 'L2',
    'FRANCE_D1_LEAGUE': 'FR1', 'FRANCE_D2_LEAGUE': 'FR2', 'NETHERLANDS_D1_LEAGUE': 'NL1', 'PORTUGAL_D1_LEAGUE': 'PO1',
    'BELGIUM_D1_LEAGUE': 'BE1', 'TURKEY_D1_LEAGUE': 'TR1', 'SCOTLAND_D1_LEAGUE': 'SC1', 'DENMARK_D1_LEAGUE': 'DK1',
    'GREECE_D1_LEAGUE': 'GR1', 'RUSSIA_D1_LEAGUE': 'RU1', 'ARGENTINA_D1_LEAGUE': 'ARG1', 'BRAZIL_D1_LEAGUE': 'BRA1',
    'BRAZIL_D2_LEAGUE': 'BRA2', 'CHILE_D1_LEAGUE': 'CLPD', 'COLOMBIA_D1_LEAGUE': 'COL1', 'CHINA_D1_LEAGUE': 'CSL',
    'JAPAN_D1_LEAGUE': 'JAP1', 'KSA_D1_LEAGUE': 'SA1', 'US_D1_LEAGUE': 'MLS1',
    'CROATIA_D1_LEAGUE': 'KR1', 'AUSTRIA_D1_LEAGUE': 'A1', 'SWITZERLAND_D1_LEAGUE': 'C1', 'POLAND_D1_LEAGUE': 'PL1',
    'CZECH_D1_LEAGUE': 'TS1', 'SERBIA_D1_LEAGUE': 'SER1', 'UKRAINE_D1_LEAGUE': 'UKR1', 'NORWAY_D1_LEAGUE': 'NO1',
    'SWEDEN_D1_LEAGUE': 'SE1', 'MEXICO_D1_LEAGUE': 'MEX1', 'KOREA_D1_LEAGUE': 'RSK1', 'AUSTRALIA_D1_LEAGUE': 'AUS1',
    'ROMANIA_D1_LEAGUE': 'RO1', 'BULGARIA_D1_LEAGUE': 'BU1', 'HUNGARY_D1_LEAGUE': 'UNG1', 'SLOVENIA_D1_LEAGUE': 'SL1',
    'CYPRUS_D1_LEAGUE': 'ZYP1', 'ISRAEL_D1_LEAGUE': 'ISR1', 'SLOVAKIA_D1_LEAGUE': 'SLO1', 'BOSNIA_D1_LEAGUE': 'BOS1',
    'OSTALI:Croatia': 'KR1', 'OSTALI:Austria': 'A1', 'OSTALI:Switzerland': 'C1', 'OSTALI:Poland': 'PL1',
    'OSTALI:Czech Republic': 'TS1', 'OSTALI:Serbia': 'SER1', 'OSTALI:Ukraine': 'UKR1', 'OSTALI:Norway': 'NO1',
    'OSTALI:Sweden': 'SE1', 'OSTALI:Mexico': 'MEX1', 'OSTALI:Korea Republic': 'RSK1', 'OSTALI:Australia': 'AUS1',
    'OSTALI:Romania': 'RO1', 'OSTALI:Bulgaria': 'BU1', 'OSTALI:Hungary': 'UNG1', 'OSTALI:Slovenia': 'SL1',
    'OSTALI:Cyprus': 'ZYP1', 'OSTALI:Israel': 'ISR1', 'OSTALI:Slovakia': 'SLO1', 'OSTALI:Egypt': 'EGY1',
    'OSTALI:Qatar': 'QSL', 'OSTALI:Uae': 'UAE1', 'OSTALI:Germany': 'L1', 'OSTALI:Uruguay': 'URU1',
    'OSTALI:Paraguay': 'PR1C', 'OSTALI:Ecuador': 'EC1N', 'OSTALI:Peru': 'TDeA',
    'OSTALI:Republic Of Korea': 'RSK1', 'OSTALI:Thailand': 'THA1', 'OSTALI:Iran': 'IRN1', 'OSTALI:Malaysia': 'MYS1',
    'OSTALI:United Arab Emirates': 'UAE1', 'OSTALI:Azerbaijan': 'AZ1', 'OSTALI:Singapore': 'SIN1', 'OSTALI:Bolivia': 'BO1A',
    'OSTALI:Jordan': 'JO1L', 'OSTALI:Uzbekistan': 'UZ1', 'OSTALI:Tunisia': 'TUN1', 'OSTALI:Vietnam': 'VIE1',
    'OSTALI:Morocco': 'MAR1', 'OSTALI:Latvia': 'LET1', 'OSTALI:Finland': 'FI1', 'OSTALI:Moldova': 'MO1N',
    'OSTALI:Venezuela': 'VZ1C', 'OSTALI:India': 'IND1', 'OSTALI:Iraq': 'IRQ1', 'OSTALI:Indonesia': 'IN1L',
    'OSTALI:Lithuania': 'LI1', 'OSTALI:Tajikistan': 'TAD1', 'OSTALI:Albania': 'ALB1', 'OSTALI:Bosnia-Herzegovina': 'BOS1',
    'OSTALI:North Macedonia': 'MAZ1', 'OSTALI:Montenegro': 'MNE1', 'OSTALI:Kosovo': 'KO1', 'OSTALI:Georgia': 'GE1N',
    'OSTALI:Kazakhstan': 'KAS1', 'OSTALI:Armenia': 'ARM1', 'OSTALI:Belarus': 'WER1', 'OSTALI:Estonia': 'EST1',
    'OSTALI:Iceland': 'IS1', 'OSTALI:Ireland': 'IR1', 'OSTALI:Northern Ireland': 'NIR1', 'OSTALI:Wales': 'WAL1',
    'OSTALI:Israel': 'ISR1', 'OSTALI:Turkey': 'TR1', 'OSTALI:Greece': 'GR1', 'OSTALI:Denmark': 'DK1',
    'OSTALI:Scotland': 'SC1', 'OSTALI:Netherlands': 'NL1', 'OSTALI:Belgium': 'BE1', 'OSTALI:Portugal': 'PO1',
    'OSTALI:Russia': 'RU1', 'OSTALI:Japan': 'JAP1', 'OSTALI:China Pr': 'CSL', 'OSTALI:Chile': 'CLPD', 'OSTALI:Colombia': 'COL1',
}
_EXTRA = os.path.join(HERE, 'tm_kodovi.json')
if os.path.exists(_EXTRA):
    TM_KOD.update(json.load(open(_EXTRA, encoding='utf-8')))
# nove lige: kad igra dobije ligu koje ovdje nema, program pita za TM kod (ili dodaj red ovdje)

# ------------------------------------------------------------------ pomocne
import functools
@functools.lru_cache(maxsize=400000)
def _toks(s):
    s = unicodedata.normalize('NFKD', s or ''); s = ''.join(c for c in s if not unicodedata.combining(c))
    for a, b in (('ø', 'o'), ('Ø', 'O'), ('ß', 'ss'), ('æ', 'ae'), ('ł', 'l'), ('đ', 'd'), ('Đ', 'D'), ('ı', 'i')):
        s = s.replace(a, b)
    return tuple(t for t in re.sub(r'[^a-z ]', ' ', s.lower()).split() if len(t) > 1)

def toks(s):
    return list(_toks(s))               # (kesirano - isti naziv se normalizira stotine tisuca puta)

CLUB_STOP = {'fc', 'cf', 'afc', 'sc', 'ac', 'as', 'ss', 'ssc', 'rc', 'cd', 'ud', 'sd', 'club', 'de', 'la', 'the', 'fk',
             'sk', 'nk', 'hnk', 'gnk', 'calcio', 'sv', 'vfl', 'vfb', 'tsg', 'bk', 'if', 'cp', 'sl', 'ca', 'se', 'ec', 'cr',
             'futebol', 'football', 'united', 'city', 'real', 'sporting', 'atletico', 'club', 'olympique', 'stade'}
def club_sim(a, b):
    ta = [t for t in toks(a) if t not in CLUB_STOP] or toks(a)
    tb = [t for t in toks(b) if t not in CLUB_STOP] or toks(b)
    if not ta or not tb: return 0.0
    j = len(set(ta) & set(tb)) / len(set(ta) | set(tb))
    return max(j, difflib.SequenceMatcher(None, ' '.join(ta), ' '.join(tb)).ratio() * 0.9)

OPS_TM = []
def opseg(P, opt):
    """--opseg=<json>: {"lige": [kljuc lige iz baze], "tm_lige": [TM kod], "klubovi": [id], "igraci": [id]}
    -> skup idx igraca u opsegu (None = cijela baza)."""
    global OPS_TM
    if not isinstance(opt.get('opseg'), str): return None
    o = json.load(open(opt['opseg'], encoding='utf-8'))
    lige, kl, ig = set(o.get('lige') or []), set(o.get('klubovi') or []), set(o.get('igraci') or [])
    OPS_TM = [c.upper() for c in o.get('tm_lige') or []]
    return {p['idx'] for p in P if p['id'] in ig or (p['club_id'] and p['club_id'] in kl) or (db_league_key(p) and db_league_key(p) in lige)}

def brisanje(cfg, P, DOZ=None):
    """idx igraca s popisa ciscenje.py (samo bez kluba i reprezentacije; i samo u opsegu)."""
    import ciscenje as CI
    br = CI.ucitaj(cfg)
    if not br: return set()
    ok_ = {p_['id']: p_ for p_ in P if not p_['club_id'] and not p_['nt']}
    skip = {ok_[i]['idx'] for i in br if i in ok_ and (DOZ is None or ok_[i]['idx'] in DOZ)}
    print('Brisanje (ciscenje.py): %d igraca bez kluba (umirovljeni / duplikati)' % len(skip), flush=True)
    return skip

def db_league_key(p):
    if p['league_code']: return p['league_code']
    if p['club_id']: return 'OSTALI:' + p['country']
    return ''

def tm_fetch(code):
    """Sastav TM lige; pokusa tekucu sezonu, pa prethodnu (lige koje se igraju u kalendarskoj godini)."""
    for season in (T.SEASON, T.SEASON - 1):
        name = 'tm_%s_%d.json' % (code, season)
        p = os.path.join(T.CACHE, name)
        fresh = os.path.exists(p) and 'osvjezi' not in OPT
        if fresh:
            d = json.load(open(p, encoding='utf-8'))
            # prazna sezona (npr. kalendarska liga jos nije pocela) se pamti 2 dana, puna 7 dana
            fresh = time.time() - os.path.getmtime(p) < (2 if not d.get('players') else 7) * 86400
        if fresh:
            pass
        else:
            d = None
            if season == T.SEASON and 'bez-api' not in OPT:          # brzi Transfermarkt API (~1 s po ligi umjesto ~1 min scrapea)
                try:
                    import tm_api as TA
                    d = TA.league(code)
                    if d and d['players']: print('   Transfermarkt %s: %d igraca (API)' % (code, len(d['players'])), flush=True)
                    else: d = None
                except BaseException as e:
                    print('   (API nije uspio za %s: %s - koristim stranice)' % (code, e), flush=True); d = None
            if d is None:
                old = T.SEASON; T.SEASON = season
                try:
                    print('   Transfermarkt %s, sezona %d...' % (code, season))
                    d = T.tm_league(code)
                except SystemExit:
                    d = {'league': code, 'players': []}
                finally:
                    T.SEASON = old
            json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False)     # i prazno (da se ne trazi svaki put)
        if d['players']:
            for q in d['players']: q['name'] = T.clean(q['name']); q['tm_league'] = code
            return d
    return {'league': code, 'players': []}

# ------------------------------------------------------------------ uparivanje
def build_index(P):
    idx = collections.defaultdict(list)
    for p in P:
        for t in set(toks(p['name']) + toks(p['shirt'])): idx[t].append(p)
    return idx

def _nat_ok(tp, p):
    """None = ne znamo, True/False = drzavljanstvo TM igraca odgovara bazi."""
    nats = tp.get('nats') or ([tp['nat']] if tp.get('nat') else [])
    if not nats or not p.get('nat_id'): return None
    try:
        import tm_podaci as TP
        ids = {TP.country_id(x) for x in nats}
        return p['nat_id'] in ids or (p.get('nat2_id') or 0) in ids
    except Exception:
        return None

def _exp_age(tp):
    """Godine koje bi igrac trebao imati u bazi: iz TM datuma rodenja na referentni datum baze, inace TM godine."""
    if tp.get('dob'):
        try:
            import tm_podaci as TP
            return TP.age_at(tp['dob'])
        except Exception:
            pass
    return tp.get('age')

def first_ok(tt, p):
    """Je li ime (ne prezime) TM igraca spojivo s bazom: isto ime, jedno pocetak drugog (Alex/Alexander) ili nadimak
    sadrzan u imenu (Tasos/Anastasios). Ako jedna strana nema ime (samo prezime / inicijal) -> spojivo."""
    from difflib import SequenceMatcher as SM
    tf = tt[:-1]
    sur = tt[-1]
    # tokeni baze bez prezimena (i bez prezimena na dresu u drugoj transliteraciji: HAMRALIEV / Khamraliev)
    pf = [t for t in toks(p['name']) + toks(p['shirt']) if t != sur and SM(None, t, sur).ratio() < 0.8]
    if not tf or not pf: return True
    for a in tf:
        for b in pf:
            if a == b or a.startswith(b) or b.startswith(a): return True
            if min(len(a), len(b)) >= 4 and (a in b or b in a): return True
            if SM(None, a, b).ratio() >= 0.75: return True     # Christian/Cristian, Muhammadali/Mukhammadali
    return False

def match_all(tp, idx, club_map):
    """Svi prihvatljivi igraci iz baze za TM igraca: [(slicnost, p)].
    Pravilo: prezime (ili cijelo ime) mora odgovarati. Djelomicno ime (npr. nadimak) samo uz isti klub,
    iste godine i bez proturjecja u visini/drzavljanstvu. Imenjaci s ~10+ cm razlike i drugom drzavom se odbacuju."""
    tt = toks(tp['name'])
    if not tt: return []
    out = []
    ea = _exp_age(tp)
    cands = {p['idx']: p for t in tt for p in idx.get(t, [])}.values()
    for p in cands:
        pt = set(toks(p['name']) + toks(p['shirt']))
        ov = len(set(tt) & pt) / len(set(tt))
        sur = tt[-1] in pt
        name_s = ov + (0.4 if sur else 0)
        same_club = bool(p['club_id'] and club_map.get(tp['club']) == p['club_id'])
        if ea is not None:
            da = abs(p['age'] - ea)
            # cijelo ime + isti klub: baza smije imati krive godine (do 3) - ispravak podataka ih popravi
            if da > (3 if (ov == 1 and sur and same_club) else 1): continue
        h = tp.get('height'); dh = abs(h - p['height']) if h and p.get('height') else None
        nat = _nat_ok(tp, p)
        if name_s >= 0.9 and ov < 1 and not same_club and not first_ok(tt, p):
            name_s = 0.5                                    # samo prezime, drugi klub, drugo ime (Maximilian/Johannes Eggestein)
        if name_s >= 0.9:                                   # jako ime
            if dh is not None and dh >= 10 and nat is False: continue
        elif name_s >= 0.5:                                 # slabo ime (nadimak, jedno od imena)
            if not (same_club and ea == p['age'] and (dh is None or dh <= 4) and nat is not False): continue
        else:
            continue
        sc = name_s + (1.0 if same_club else 0) + (0.2 if ea == p['age'] else 0)
        if dh is not None: sc += 0.2 if dh <= 2 else (-0.3 if dh >= 8 else 0)
        if nat is True: sc += 0.2
        elif nat is False: sc -= 0.3
        out.append((sc, p))
    return out

def match(tp, idx, club_map):
    tt = toks(tp['name'])
    if not tt: return None, 0
    best, bs = None, 0
    cands = {p['idx']: p for t in tt for p in idx.get(t, [])}.values()
    for p in cands:
        if tp.get('age') and abs(p['age'] - tp['age']) > 1: continue
        pt = set(toks(p['name']) + toks(p['shirt']))
        s = len(set(tt) & pt) / len(set(tt))
        if tt[-1] in pt: s += 0.4                       # prezime
        if tp.get('age') == p['age']: s += 0.2
        if p['club_id'] and club_map.get(tp['club']) == p['club_id']: s += 1.0
        if s > bs: best, bs = p, s
    return best, bs

_DBCLUBS = {}
def map_clubs(tm_players, P, idx=None):
    """TM klub -> club_id u bazi: najslicnije ime, pa GLASANJE preko igraca (puno ime + godine) -
    povezuje klubove razlicitih imena (npr. 'Grêmio Foot-Ball Porto Alegrense' = 'Grêmio') i ispravlja krive."""
    key = id(P)
    if key not in _DBCLUBS: _DBCLUBS.clear(); _DBCLUBS[key] = {p['club_id']: p['club'] for p in P if p['club_id']}
    db_clubs = _DBCLUBS[key]
    out = {}
    by = collections.defaultdict(list)
    for q in tm_players: by[q['club']].append(q)
    for c in by:
        sc = sorted(((club_sim(c, n), cid) for cid, n in db_clubs.items()), reverse=True)
        if sc and sc[0][0] >= 0.5: out[c] = sc[0][1]
    if idx is not None:
        for c, qs in by.items():
            v = collections.Counter()
            for q in qs:
                for s_, p in match_all(q, idx, {}):
                    if s_ >= 1.6 and p['club_id']: v[p['club_id']] += 1
            if not v: continue
            cid, n = v.most_common(1)[0]
            if n >= 3 and n >= 0.6 * sum(v.values()) and out.get(c) != cid:
                if c not in out or n >= 5: out[c] = cid
    return out

# ------------------------------------------------------------------ kalibracija TM -> overall iz baze
def club_strength(players):
    L = collections.defaultdict(list)
    for q in players:
        if q['value']: L[q['club']].append(np.log(q['value'] / 1e6))
    return {c: float(np.mean(sorted(v)[-14:])) for c, v in L.items()}

def kalibriraj(P, idx):
    codes = sorted({TM_KOD[k] for k in {db_league_key(p) for p in P} if k in TM_KOD})
    print('\nKALIBRACIJA na ocjenama iz baze, lige: %s' % ', '.join(codes))
    X, y, info = [], [], []
    for code in codes:
        d = tm_fetch(code)
        if not d['players']: print('   (preskacem %s - nema podataka)' % code); continue
        cm = club_strength(d['players']); cmap = map_clubs(d['players'], P)
        n = 0
        for q in d['players']:
            if not (q['value'] and q['age']): continue
            p, s = match(q, idx, cmap)
            if p is None or s < 1.3 or p['pos'] == '?': continue
            X.append(T.feats(q, cm)); y.append(O.ovr_raw(p['attr'], p['pos'])); n += 1
        info.append((code, d['league'], n)); print('   %-5s %-32s upareno %d' % (code, d['league'], n))
    X = np.array(X, float); y = np.array(y, float)
    i = np.arange(len(y)); np.random.seed(1); np.random.shuffle(i); cv = np.zeros(len(y))
    for k in range(5):
        te = i[k::5]; tr = np.setdiff1d(i, te); c, b = T.ridge(X[tr], y[tr]); cv[te] = X[te] @ c + b
    coef, const = T.ridge(X, y)
    K = {'coef': [float(x) for x in coef], 'const': float(const), 'n': int(len(y)),
         'greska': float(np.abs(cv - y).mean()), 'unutar3': float((np.abs(cv - y) <= 3).mean()),
         'lige': info, 'datum': datetime.date.today().isoformat(), 'baza': OPT.get('baza', 'aktivna baza igre')}
    json.dump(K, open(KAL_FILE, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('   gotovo: %d igraca, prosjecna greska %.2f overalla\n' % (K['n'], K['greska']))
    return K

# ------------------------------------------------------------------ skaliranje atributa
K_GRID = np.arange(0.55, 1.6, 0.0025)
DK_GRID = np.arange(-0.06, 0.0601, 0.005)

ATLETSKI = ('Speed', 'Acceleration', 'Jump', 'Physical Contact', 'Stamina', 'Balance', 'Aggression')

def scale_to(p, target, fixed=()):
    """Kao _scale_to; 'fixed' atributi (npr. atletski iz EA profila) se ne mijenjaju - ako tako cilj nije
    dostizan, skalira se sve."""
    r = _scale_to(p, target, fixed)
    if fixed and O.ovr(r, p['pos']) != target:
        r = _scale_to(p, target, ())
    return r

def _scale_to(p, target, fixed=()):
    """Proporcionalno pomnozi atribute (k) tako da overall na poziciji bude TOCNO cilj (tocna formula igre).
    Vektorski (numpy) - cijela mreza faktora odjednom."""
    import pes_overall as PO, itertools
    pos = p['pos']; pi = D.POS.index(pos); wfa = p['attr'].get('_wfa', 2)
    names = [n for n in (D.ANAMES if pos == 'GK' else D.ANAMES[:20]) if n not in fixed]
    a0 = dict(p['attr'])
    v0 = np.array([a0[n] for n in D.ANAMES], np.int64)
    ci = np.array([D.ANAMES.index(n) for n in names])
    def to_dict(row):
        a = dict(a0)
        for i, n in enumerate(D.ANAMES): a[n] = int(row[i])
        return a
    # 1. korak: jedan faktor k za sve atribute; najblizi k = 1.0 koji daje cilj
    M = np.tile(v0, (len(K_GRID), 1))
    M[:, ci] = np.clip(np.round(v0[ci] * K_GRID[:, None]), 40, 99)
    ov = PO.overall_vec(M, wfa, pi)
    d = np.abs(ov - target); dk = np.abs(K_GRID - 1)
    j = np.lexsort((dk, d))[0]
    d0 = abs(int(PO.overall_vec(v0[None, :], wfa, pi)[0]) - target)
    best = to_dict(M[j]) if (d[j], dk[j]) < (d0, 0.0) else dict(a0)
    if min(d[j], d0) == 0: return best
    # 2. korak: formula skace u koracima (i prosjek svih atributa ulazi u nju), pa jedan faktor ponekad preskoci
    # cilj -> zasebni faktori za atribute koji nose overall na poziciji (k1) i za ostale (k1+dk), sto manji |dk|
    w = PO.W[pi] + ([.5, .48, .48, .48, .5] if pi == 0 else [0] * 5)
    mi = np.array([i for i in ci if w[i] > 0]); ri = np.array([i for i in ci if w[i] <= 0], dtype=np.int64)
    found, fkey = None, None
    for dkk in sorted(DK_GRID, key=abs):
        if fkey is not None and abs(dkk) > fkey[0]: break
        M = np.tile(v0, (len(K_GRID), 1))
        M[:, mi] = np.clip(np.round(v0[mi] * K_GRID[:, None]), 40, 99)
        if len(ri): M[:, ri] = np.clip(np.round(v0[ri] * (K_GRID[:, None] + dkk)), 40, 99)
        hit = np.where(PO.overall_vec(M, wfa, pi) == target)[0]
        if len(hit):
            h = hit[np.argmin(np.abs(K_GRID[hit] - 1))]
            key = (abs(dkk), abs(K_GRID[h] - 1))
            if fkey is None or key < fkey: found, fkey = to_dict(M[h]), key
    if found: return found
    # 3. korak (rijetko): dotjeraj +-1..4 na jednom ili dva atributa
    names = [n for n in (D.ANAMES if pos == 'GK' else D.ANAMES[:20]) if n not in fixed]
    def tryset(changes):
        a = dict(best)
        for n, d in changes:
            v = a[n] + d
            if not 40 <= v <= 99: return None
            a[n] = v
        return a if O.ovr(a, pos) == target else None
    for total in (1, 2, 3, 4):                       # najmanja ukupna promjena prvo
        cand = []
        for n in names:                              # jedan atribut +-total
            for d in (total, -total):
                a = tryset([(n, d)])
                if a: cand.append(a)
        if total >= 2:                               # dva atributa
            for n1, n2 in itertools.combinations(names, 2):
                for d1 in range(1, total):
                    d2 = total - d1
                    for s1, s2 in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                        a = tryset([(n1, s1 * d1), (n2, s2 * d2)])
                        if a: cand.append(a)
        if cand:
            # najmanje odstupanje od proporcionalnog profila: preferiraj promjene u smjeru cilja
            sgn = 1 if target > O.ovr(a0, pos) else -1
            return max(cand, key=lambda a: sum(sgn * (a[n] - best[n]) for n in names))
    return best

# ------------------------------------------------------------------ main
def choose_leagues(P):
    cnt = collections.Counter(db_league_key(p) for p in P if db_league_key(p))
    keys = sorted(cnt, key=lambda k: (k.startswith('OSTALI:'), k))
    print('\nLIGE U BAZI:')
    for i, k in enumerate(keys, 1):
        nm = D.PF.nice_league(k) if not k.startswith('OSTALI:') else 'Ostali klubovi (%s)' % k[7:]
        print('  %3d) %-36s %4d igraca   TM: %s' % (i, nm, cnt[k], TM_KOD.get(k, '?')))
    s = input('\nUpisi broj(eve) lige ili TM kod(ove), odvojeno razmakom: ').split()
    out = []
    for x in s:
        if x.isdigit() and 1 <= int(x) <= len(keys):
            k = keys[int(x) - 1]
            if k in TM_KOD: out.append(TM_KOD[k])
            else: out.append(input('TM kod za %s (npr. KR1): ' % k).strip().upper())
        elif x: out.append(x.upper())
    return out

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import izvor as IZ
    cfg = IZ.use(IZ.cfg_from_opts(OPT))
    cfg, IZL = IZ.izlaz_iz_opts(OPT, cfg)
    print('Ucitavam bazu: %s%s' % (IZ.opis(cfg), ' (iz zadnjeg izlaza)' if cfg.get('citaj') else ''))
    P, raw, src = IZ.load_players(cfg)
    P = [p for p in P if p['pos'] != '?']
    print('   %d igraca' % len(P))
    idx = build_index(P)
    P_by_idx = {p['idx']: p for p in P}
    DOZ = opseg(P, OPT)                  # None = cijela baza; inace skup idx igraca koje se smije mijenjati
    import katalog as KAT
    ZK = KAT.zakljucani(cfg)             # zakljucani igraci: nikad se ne mijenjaju
    if ZK:
        DOZ = (DOZ if DOZ is not None else {p['idx'] for p in P}) - {p['idx'] for p in P if p['id'] in ZK}
        print('Zakljucano: %d igraca (ne mijenjaju se)' % len(ZK), flush=True)
    LEG = {p['idx'] for p in P if any(t in (p.get('club') or '') for t in ('Classics', 'ML Default'))}
    if LEG:                              # legende (Classic / ML Default timovi): umirovljeni, TM vrijednost ih ne opisuje
        DOZ = (DOZ if DOZ is not None else {p['idx'] for p in P}) - LEG
        print('Legende (Classic / ML Default): %d igraca se ne mijenja' % len(LEG), flush=True)
    if DOZ is not None:
        keys = collections.Counter(db_league_key(p) for p in P if p['idx'] in DOZ and db_league_key(p))
        codes = sorted({TM_KOD[k] for k in keys if k in TM_KOD} | set(OPS_TM))
        print('Opseg: %d igraca, lige na Transfermarktu: %s' % (len(DOZ), ', '.join(codes) or '-'), flush=True)
    elif 'sve' in OPT:                     # sve lige iz baze koje imaju TM kod
        keys = collections.Counter(db_league_key(p) for p in P if db_league_key(p))
        codes = sorted({TM_KOD[k] for k in keys if k in TM_KOD})
        miss = sorted((k, n) for k, n in keys.items() if k not in TM_KOD)
        print('Sve lige: %d TM liga. Bez TM koda (preskaceni): %s' % (len(codes), ', '.join('%s (%d)' % m for m in miss) or '-'))
        dod = os.path.join(IZ.mapa(cfg), 'dodatne_lige.json')
        if os.path.exists(dod):
            extra = [c for c in json.load(open(dod, encoding='utf-8')) if c not in codes]
            if extra: print('Dodatne lige s Transfermarkta: %s' % ', '.join(extra)); codes += extra
    elif 'samo-rucne' in OPT:
        codes = []
    else:
        codes = [a.upper() for a in ARGS] or ([] if 'dodatne' in OPT or not sys.stdin.isatty() else choose_leagues(P))
    RU = {}
    if 'bez-rucnih' not in OPT:
        import tm_igrac as TI
        RU = TI.rucne()
        if DOZ is not None:
            ids_ = {P_by_idx[i]['id'] for i in DOZ}; RU = {k: v for k, v in RU.items() if int(k) in ids_}
        if RU: print('Rucni popis: %d igraca (ima prednost pred ligama)' % len(RU))
    if isinstance(OPT.get('dodatne'), str):
        codes += [c.strip().upper() for c in OPT['dodatne'].split(',') if c.strip() and c.strip().upper() not in codes]
    if not codes and not RU:
        print('Nema liga ni rucnog popisa za izracun. Odaberi lige (za CSV bez klubova: lige s Transfermarkta).'); return
    stara = 'stara-kalibracija' in OPT          # stara: TM -> ocjene iz same baze; nova (default): TM -> EA FC 27
    if stara:
        K = json.load(open(KAL_FILE, encoding='utf-8')) if os.path.exists(KAL_FILE) and 'kalibriraj' not in OPT else kalibriraj(P, idx)
        coef, const = np.array(K['coef']), K['const']
        K['opis'] = 'TM -> ocjene iz baze igre (linearna)'
    else:
        import model_ea27 as ME
        if 'kalibriraj' in OPT: ME._M = dict(zip(('model', 'info'), ME.train()))
        I = ME.load()['info']
        skala = float(OPT['skala']) if 'skala' in OPT else ME.SKALA
        K = {'datum': I['datum'], 'baza': I['ea'], 'n': I['n'], 'greska': I['greska'], 'unutar3': I['unutar3'], 'lige': [],
             'opis': 'TM (market value, age, position, club, league) -> EA FC, gradient boosting; %d TM leagues; scale %.2f (0=EA, 1=your database) below %d' % (len(I['lige']), skala, ME.SKALA_PRAG)}
    maxd = float(OPT['max-promjena']) if 'max-promjena' in OPT else None
    import ea_atributi as EAP, ea_dodatno as EAD
    EADOD = 'bez-ea-dodataka' not in OPT
    EAW = 0.0 if 'bez-ea-profila' in OPT or not EAP.model() else float(OPT.get('ea-profil', EAP.TEZINA) if isinstance(OPT.get('ea-profil'), str) else EAP.TEZINA)
    if EAW > 0: print('Realni atributi iz EA FC 27: profil = %.0f %% EA + %.0f %% baza' % (100 * EAW, 100 * (1 - EAW)), flush=True)

    rows, unmatched, changes = [], [], {}
    # 1. prolaz: parovi iz SVIH liga, pa globalno najbolji par prvi (inace liga koja dode ranije "pojede" igraca
    #    iz kasnije lige samo po prezimenu - npr. Pedro Gomes iz Bugarske uzme Joaa Gomesa iz Aston Ville)
    LD, allpairs = [], []
    for li, code in enumerate(codes, 1):
        d = tm_fetch(code)
        print('[%d/%d] Liga %s (%s): %d TM igraca' % (li, len(codes), code, d['league'], len(d['players'])), flush=True)
        cm = club_strength(d['players']); cmap = map_clubs(d['players'], P, idx)
        cm2 = lg2 = None
        if not stara: cm2, lg2 = ME.strengths(d['players'])
        for qi, q in enumerate(d['players']):
            for sc, p in match_all(q, idx, cmap):
                if sc >= 1.3 and str(p['id']) not in RU: allpairs.append((sc, li - 1, qi, p))
        LD.append((code, d, cm, cmap, cm2, lg2))
    allpairs.sort(key=lambda x: -x[0])
    GOT, used = collections.defaultdict(dict), set()
    for sc, k, qi, p in allpairs:
        if qi in GOT[k] or p['idx'] in used: continue
        GOT[k][qi] = p; used.add(p['idx'])
    print('Upareno globalno: %d igraca iz %d liga' % (len(used), len(LD)), flush=True)
    if 'samo-uparivanje' in OPT:         # treba samo popis TM id-eva (ugovori / ozljede / ciscenje), bez izracuna ocjena
        novi = {}
        for k_, (code_, d_, *_r) in enumerate(LD):
            for qi_, p_ in GOT[k_].items():
                q_ = d_['players'][qi_]
                if q_.get('tm_id') and str(p_['id']) not in RU: novi[p_['id']] = [p_['id'], q_['tm_id'], O.ovr(p_['attr'], p_['pos'])]
        byid_ = {p_['id']: p_ for p_ in P}
        for sid_, e_ in RU.items():
            p_ = byid_.get(int(sid_))
            if p_ is not None and e_.get('tm_id'): novi[p_['id']] = [p_['id'], e_['tm_id'], O.ovr(p_['attr'], p_['pos'])]
        tf_ = os.path.join(IZ.mapa(cfg), 'tm_ids.json')
        if not ('sve' in OPT and DOZ is None) and os.path.exists(tf_):
            try:
                for e_ in json.load(open(tf_)): novi.setdefault(e_[0], e_)
            except ValueError: pass
        json.dump(list(novi.values()), open(tf_, 'w'))
        print('Uparivanje gotovo: %d igraca s Transfermarkt ID-em' % len(novi), flush=True); return
    for li, (code, d, cm, cmap, cm2, lg2) in enumerate(LD):
        tgts = {}
        PRED = None if stara else ME.predict_many(d['players'], cm2, lg2)
        for qi, q in enumerate(d['players']):
            if stara: tgt = float(np.array(T.feats(q, cm)) @ coef + const) if q['value'] and q['age'] else None
            else: tgt = ME.to_game(PRED[qi], skala)
            q['_ea'] = None if stara else ME.ea_lookup(q)
            tgts[qi] = tgt
        got = GOT[li]
        for qi, q in enumerate(d['players']):
            tgt = tgts[qi]; p = got.get(qi)
            if p is not None and str(p['id']) in RU: continue          # rucni unos ima prednost
            if p is None:
                q['_ub'] = q['club'] in cmap
                unmatched.append((d['league'], q, tgt)); continue
            if tgt is None:                                   # TM nema vrijednost: ocjena ostaje, podaci da
                cur = O.ovr(p['attr'], p['pos'])
                rows.append({'league': d['league'], 'tm': q, 'p': p, 'cur': cur, 'tgt': cur, 'new': cur,
                             'attr_new': dict(p['attr']), 'note': 'TM nema trzisnu vrijednost - ocjena nije mijenjana'})
                continue
            cur = O.ovr(p['attr'], p['pos'])
            t = int(np.clip(np.round(tgt), 40, 99))
            if maxd is not None: t = int(np.clip(t, cur - maxd, cur + maxd))
            prov = O.formula()[p['pos']].get('privremeno') and 'privremene' not in OPT
            ea_used = False
            e_ea = EAP.ea_entry(q) if (EAW > 0 or EADOD) else None
            dch, dop = EAD.promjene(p, e_ea) if (EADOD and e_ea) else ({}, [])
            pe = dict(p, attr=dict(p['attr'], _wfa=dch['_wfa'])) if '_wfa' in dch else p     # slabija noga ulazi u overall
            if EAW > 0:                                   # realni profil iz EA FC 27 (mjesavina s bazom)
                base, ea_used = EAP.blend(pe['attr'], e_ea, p['pos'] == 'GK', EAW)
            if ea_used:
                new = scale_to(dict(p, attr=base), t, () if p['pos'] == 'GK' else ATLETSKI)
            else:
                new = scale_to(pe, t) if (t != cur or pe is not p) and not prov else dict(p['attr'])
            nv = O.ovr(new, p['pos'])
            ch = {n: v for n, v in new.items() if v != p['attr'].get(n)}
            ch.update({k: v for k, v in dch.items() if k != '_wfa'})
            if ch: changes[p['idx']] = ch
            rows.append({'league': d['league'], 'tm': q, 'p': p, 'cur': cur, 'tgt': t, 'new': nv, 'attr_new': new, 'ea_profil': ea_used, 'ea_dod': dop,
                         'note': 'nije mijenjan - formula za %s jos privremena' % p['pos'] if prov else ''})

    # rucni popis (pojedinacni igraci s Transfermarkta, ukljucujuci igrace bez kluba)
    by_id = {p['id']: p for p in P}
    for sid, e in RU.items():
        p = by_id.get(int(sid))
        if p is None or p['idx'] in used: continue
        used.add(p['idx'])
        tgt = ME.to_game(e['ea_pred'], skala) if not stara else e['ea_pred']
        cur = O.ovr(p['attr'], p['pos'])
        t = int(np.clip(np.round(tgt), 40, 99))
        if maxd is not None: t = int(np.clip(t, cur - maxd, cur + maxd))
        new = scale_to(p, t) if t != cur else dict(p['attr'])
        nv = O.ovr(new, p['pos'])
        if new != p['attr']: changes[p['idx']] = {n: v for n, v in new.items() if v != p['attr'][n]}
        q = {'name': e['tm_ime'], 'club': e.get('klub') or '', 'value': e.get('vrijednost'), '_ea': None,
             'age': e.get('godine'), 'height': e.get('visina'), 'nats': e.get('drzave'), 'tm_id': e.get('tm_id')}
        rows.append({'league': ('Manual list (%s)' if LGX.en() else 'Rucno (%s)') % e.get('izvor', 'rucno'), 'tm': q, 'p': p, 'cur': cur, 'tgt': t, 'new': nv,
                     'attr_new': new, 'note': e.get('kontekst') or ''})

    # reputacija: pomak za onoliko koliko je novi overall pomaknuo OCEKIVANU reputaciju (raspodjela iz same baze)
    if 'bez-reputacije' not in OPT and rows and rows[0]['p'].get('rep') is not None:
        by = collections.defaultdict(list)
        for p_ in P:
            if p_.get('rep'): by[O.ovr(p_['attr'], p_['pos'])].append(p_['rep'])
        exp = {}
        for o in range(40, 100):
            near = [v for k in range(o - 2, o + 3) for v in by.get(k, [])]
            if len(near) >= 20: exp[o] = float(np.mean(near))
        ks = sorted(exp)
        E = lambda o: exp.get(o, exp[ks[0]] if o < ks[0] else exp[ks[-1]])
        nrep = 0
        for r in rows:
            p_ = r['p']
            if r['new'] == r['cur'] or not p_.get('rep'): continue
            nr = int(np.clip(round(p_['rep'] + E(r['new']) - E(r['cur'])), 1, 8))
            if nr != p_['rep']:
                changes.setdefault(p_['idx'], {})['_rep'] = nr; r['rep_new'] = nr; nrep += 1
                r['ea_dod'] = (r.get('ea_dod') or []) + ['reputacija %d → %d' % (p_['rep'], nr)]
        print('Reputacija uskladjena s novim overallom kod %d igraca' % nrep, flush=True)

    # otpornost na ozljede (cache\ozljede.json, skida ozljede.py) + popis igraca za ozljede.py
    # puni izracun (--sve bez opsega) zamjenjuje popis; djelomicni (lige / opseg) ga samo nadopunjuje
    tf = os.path.join(IZ.mapa(cfg), 'tm_ids.json')
    novi = {r['p']['id']: [r['p']['id'], r['tm'].get('tm_id'), r['new']] for r in rows if r['tm'].get('tm_id')}
    if not ('sve' in OPT and DOZ is None) and os.path.exists(tf):
        try:
            for e in json.load(open(tf)): novi.setdefault(e[0], e)
        except ValueError: pass
    json.dump(list(novi.values()), open(tf, 'w'))
    if 'bez-ozljeda' not in OPT and rows and rows[0]['p'].get('inj') is not None:
        import ozljede as OZ
        CZ = OZ.ucitaj(); ninj = 0
        for r in rows:
            dd = CZ.get(str(r['tm'].get('tm_id')))
            if dd is None: continue
            nv_ = OZ.ocjena(dd)
            if nv_ != r['p']['inj']:
                changes.setdefault(r['p']['idx'], {})['_inj'] = nv_; ninj += 1
                r['ea_dod'] = (r.get('ea_dod') or []) + ['ozljede %d → %d (%.0f dana/sezonu)' % (r['p']['inj'], nv_, dd)]
        if CZ: print('Otpornost na ozljede (TM povijest ozljeda): promijenjeno kod %d igraca' % ninj, flush=True)

    # ugovori i posudbe (cache	m_api_igraci.json + tm_posudbe.json, skida ugovori.py; iskljuci s --bez-ugovora)
    if 'bez-ugovora' not in OPT and IZ.CFG['tip'] != 'csv':
        import ugovori as UG
        uch, uop, ust = UG.promjene([(r['p'], r['tm']['tm_id']) for r in rows if r['tm'].get('tm_id')])
        if ust is not None:
            byidx = {r['p']['idx']: r for r in rows}
            for i_, c_ in uch.items():
                changes.setdefault(i_, {}).update(c_)
                byidx[i_]['ea_dod'] = (byidx[i_].get('ea_dod') or []) + [uop[i_]]
            print('Ugovori s Transfermarkta: %d igraca (posudbi %d; %d igraca je na TM-u u drugom klubu - preskoceno)'
                  % (ust['ugovor'], ust['posudba'], ust['drugi_klub']), flush=True)

    # osnovni podaci s Transfermarkta: godine, drzavljanstvo, visina (iskljuci s --bez-podataka)
    podaci = []
    if 'bez-podataka' not in OPT:
        import tm_podaci as TP
        ref, ok = TP.odredi_ref([(r['tm']['dob'], r['p']['age']) for r in rows if r['tm'].get('dob') and r['p'].get('age')])
        print('Godine u bazi racunaju se na %s (%.1f %% igraca tocno)' % (ref.strftime('%d.%m.%Y.'), 100 * ok), flush=True)
        need = []
        for r in rows:
            ch, op, nap = TP.popravci(r['p'], r['tm'])
            r['_pod'] = (ch, op, nap)
            if nap.startswith('TM prva drzava'): need.append(r)
        if need:
            print('Drzavljanstvo: %d igraca treba puni popis s Transfermarkta...' % len(need), flush=True)
            full = nats_lookup([r['tm'] for r in need])
            for r in need:
                n = full.get(str(r['tm'].get('tm_id')))
                if n: r['_pod'] = TP.popravci(r['p'], r['tm'], nats=n)
        for r in rows:
            ch, op, nap = r.get('_pod', ({}, [], ''))
            if ch:
                c = changes.setdefault(r['p']['idx'], {}); c.update(ch)
            if op or nap: podaci.append((r, op, nap))
        print('Osnovni podaci: promijenjeno kod %d igraca (godine %d, visina %d, drzavljanstvo %d)' % (
            sum(1 for _, op, _ in podaci if op), sum(1 for _, op, _ in podaci if any(o.startswith('godine') for o in op)),
            sum(1 for _, op, _ in podaci if any(o.startswith('visina') for o in op)),
            sum(1 for _, op, _ in podaci if any('drzava' in o for o in op))), flush=True)

    if 'bez-ocjena' in OPT:              # samo podaci / dodaci, atributi (overall) ostaju
        changes = {i: {k: v for k, v in c.items() if k not in D.ANAMES} for i, c in changes.items()}
        changes = {i: c for i, c in changes.items() if c}
    if DOZ is not None:                  # izvan opsega se nista ne mijenja (bajt-po-bajt kao ulaz)
        n0 = len(changes)
        changes = {i: c for i, c in changes.items() if i in DOZ}
        rows = [r for r in rows if r['p']['idx'] in DOZ]
        podaci = [x for x in podaci if x[0]['p']['idx'] in DOZ]
        if n0 != len(changes): print('Opseg: %d promjena izvan opsega odbaceno' % (n0 - len(changes)), flush=True)
    skip = brisanje(cfg, P, DOZ) if 'bez-brisanja' not in OPT and raw is not None else set()

    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    outdir = os.path.join(HERE, 'izvjestaji'); os.makedirs(outdir, exist_ok=True)
    tag = 'SVE' if 'sve' in OPT else ('_'.join(codes) if len(codes) <= 6 else '%d_liga' % len(codes)) if codes else 'RUCNO'
    if cfg['id'] != 'igra': tag = cfg['id'] + '_' + tag
    # popis igraca koje su lige pokrile (za 'Svi neocijenjeni'): puni izracun ga prepisuje, djelomicni samo dodaje
    of = os.path.join(IZ.mapa(cfg), 'ocijenjeni.json')
    ids = {r['p']['id'] for r in rows}
    if ('sve' not in OPT or DOZ is not None) and os.path.exists(of):
        try: ids |= set(json.load(open(of)))
        except ValueError: pass
    json.dump(sorted(ids), open(of, 'w'))
    xl = os.path.join(outdir, 'ocjene_%s_%s.xlsx' % (tag, stamp))
    write_xlsx(xl, rows, unmatched, K, podaci)
    print('\nUpareno %d igraca, neupareno %d. Promjena atributa kod %d igraca (EA profil: %d).' % (len(rows), len(unmatched), len(changes), sum(1 for r in rows if r.get('ea_profil'))))
    print('Izvjestaj: %s' % xl)
    if IZL:
        import spremanje as SP
        data = D.write_player_bin(raw, changes, None, skip)
        SP.zapisi(IZL, {'Player.bin': data}, posao={'korak': 'ocjene', 'opseg': OPT.get('opseg') and json.load(open(OPT['opseg'], encoding='utf-8')),
                                                   'promijenjeno': len(changes), 'obrisano': len(skip), 'izvjestaj': os.path.basename(xl)},
                  log=lambda s: print(s, flush=True))
        print('Nova baza: %s' % IZL, flush=True)
    if 'upisi' in OPT and raw is None:
        print('--upisi radi samo s .bin bazom (ne s CSV-om).')
    elif 'upisi' in OPT:
        out = os.path.join(HERE, 'izlaz', 'common', 'etc', 'pesdb', 'Player.bin')
        if os.path.isfile(out):                       # prethodna verzija -> izlaz_povijest (zadnjih 10)
            import shutil, glob as _g
            hd = os.path.join(HERE, 'izlaz_povijest'); os.makedirs(hd, exist_ok=True)
            shutil.copy2(out, os.path.join(hd, 'Player_%s.bin' % datetime.datetime.fromtimestamp(os.path.getmtime(out)).strftime('%Y-%m-%d_%H%M%S')))
            for old in sorted(_g.glob(os.path.join(hd, 'Player_*.bin')))[:-10]: os.remove(old)
            print('Prethodni Player.bin spremljen u izlaz_povijest\\')
        D.write_player_bin(raw, changes, out, skip)
        # provjera: novi Player.bin se cita natrag i usporeduje s ocekivanim promjenama
        chk = D.PF.wesys(open(out, 'rb').read())
        assert len(chk) == len(raw) - len(skip) * D.REC, 'krivi Player.bin (velicina)'
        print('Novi Player.bin: %s  (provjeren, %d igraca)' % (out, len(chk) // D.REC))
        sr = [r for r in D.PF.sider_roots() if os.path.normcase(os.path.abspath(r)) == os.path.normcase(os.path.abspath(os.path.join(HERE, 'izlaz')))]
        print('Igra ga ucitava preko sider.ini (cpk.root = ".\\ocjene_tm\\izlaz").' if sr else
              '(Igra ga NE koristi dok u sider.ini ne dodas cpk.root = ".\\ocjene_tm\\izlaz" kao PRVI cpk.root.)')
    elif not IZL:
        print('Za zapis novog Player.bin pokreni ponovno s --upisi.')
    if 'csv' in OPT:
        out = OPT['csv'] if isinstance(OPT['csv'], str) else os.path.join(outdir, 'baza_nove_ocjene_%s_%s.csv' % (tag, stamp))
        n = IZ.export_csv(out, {P_by_idx[i]['id']: ch for i, ch in changes.items()}, cfg)
        print('CSV za editor (%d igraca, promijenjeno %d): %s' % (n, len(changes), out))

def nats_lookup(qs):
    """Puni popis drzavljanstava za TM igrace (preko TM pretrage po imenu; cache trajno)."""
    import tm_igrac as TI
    p = os.path.join(T.CACHE, 'tm_drzavljanstva.json')
    C = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    todo = [q for q in qs if q.get('tm_id') and str(q['tm_id']) not in C]
    for i, q in enumerate(todo, 1):
        try:
            for h in TI.trazi(q['name']):
                if h.get('nat'): C.setdefault(str(h['tm_id']), h['nat'])
            C.setdefault(str(q['tm_id']), None)
        except BaseException as e:
            print('   ! %s: %s' % (q['name'], e), flush=True)
        if i % 25 == 0:
            json.dump(C, open(p, 'w', encoding='utf-8'), ensure_ascii=False); print('   drzavljanstva %d/%d' % (i, len(todo)), flush=True)
    json.dump(C, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    return C

def write_xlsx(path, rows, unmatched, K, podaci=()):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.utils import get_column_letter
    import lang as LG
    X = LG.x
    F = Font(name='Arial', size=10); FB = Font(name='Arial', size=10, bold=True, color='FFFFFF')
    HF = PatternFill('solid', fgColor='1F3864')
    def header(ws, cols, widths):
        ws.append([X(c) for c in cols])
        for c in ws[1]: c.font = FB; c.fill = HF; c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.row_dimensions[1].height = 30
        for i, w in enumerate(widths, 1): ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = 'C2'
    wb = Workbook()
    # ---- Pregled (prvi list): po ligama
    wv = wb.active; wv.title = X('Pregled')
    header(wv, ['Liga', 'Ocijenjeno', 'Prosj. stari OVR', 'Prosj. novi OVR', 'Prosj. promjena', 'Pad >= 5', 'Rast >= 5',
                'Ispravljeni podaci', 'TM bez vrijednosti', 'Neupareni (klub u bazi)'], [26, 11, 11, 11, 11, 9, 9, 12, 12, 14])
    pod_ids = {r['p']['id'] for r, op, nap in podaci if op}
    nep = collections.Counter(lg for lg, q, t in unmatched if q.get('_ub'))
    byl = collections.defaultdict(list)
    for r in rows: byl[r['league']].append(r)
    for lg, rs in sorted(byl.items(), key=lambda x: -len(x[1])):
        d = [r['new'] - r['cur'] for r in rs]
        wv.append([lg, len(rs), round(sum(r['cur'] for r in rs) / len(rs), 1), round(sum(r['new'] for r in rs) / len(rs), 1),
                   round(sum(d) / len(d), 2), sum(1 for x in d if x <= -5), sum(1 for x in d if x >= 5),
                   sum(1 for r in rs if r['p']['id'] in pod_ids), sum(1 for r in rs if 'nema trzisnu' in (r.get('note') or '')), nep.get(lg, 0)])
    n = len(rows); d = [r['new'] - r['cur'] for r in rows] or [0]
    wv.append([X('UKUPNO'), n, None, None, round(sum(d) / max(1, len(d)), 2), sum(1 for x in d if x <= -5), sum(1 for x in d if x >= 5),
               len(pod_ids), sum(1 for r in rows if 'nema trzisnu' in (r.get('note') or '')), sum(nep.values())])
    for row in wv.iter_rows(min_row=2):
        for c in row: c.font = F
    for c in wv[wv.max_row]: c.font = Font(name='Arial', size=10, bold=True)
    wv.auto_filter.ref = 'A1:J%d' % (wv.max_row - 1)
    S = len(rows) <= 3000                  # veliki izvjestaji: bez stila po celiji (30 s -> 5 s)
    ws = wb.create_sheet(X('Igraci'))
    header(ws, ['ID u bazi', 'Igrač', 'Klub (TM)', 'Klub (baza)', 'Liga', 'Pozicija', 'Godine', 'Vrijednost (M EUR)',
                'Trenutni OVR', 'Ciljni OVR (TM)', 'Novi OVR', 'Promjena', 'EA FC 27', 'Napomena'],
           [10, 26, 22, 22, 18, 9, 8, 11, 10, 10, 10, 10, 9, 40])
    rows.sort(key=lambda r: (r['league'], r['tm']['club'], -r['tgt']))
    for i, r in enumerate(rows, start=2):
        q, p = r['tm'], r['p']
        ws.append([p['id'], p['name'], q['club'], p['club'], r['league'], p['pos'], p['age'],
                   round(q['value'] / 1e6, 2) if q['value'] else None, r['cur'], r['tgt'], r['new'], '=K%d-I%d' % (i, i), q.get('_ea'), LG.tr(r['note'])])
    n = len(rows) + 1
    for row in (ws.iter_rows(min_row=2, max_row=n) if S else ()):
        for c in row: c.font = F
        for c in row[5:13]: c.alignment = Alignment(horizontal='center')
        row[9].font = Font(name='Arial', size=10, bold=True)
    ws.auto_filter.ref = 'A1:N%d' % n
    ws.conditional_formatting.add('L2:L%d' % n, ColorScaleRule(start_type='num', start_value=-8, start_color='F8696B',
        mid_type='num', mid_value=0, mid_color='FFFFFF', end_type='num', end_value=8, end_color='63BE7B'))
    # atributi staro -> novo
    wa = wb.create_sheet(X('Atributi'))
    short = ['OffAw', 'BallC', 'Drib', 'Tight', 'LowP', 'LoftP', 'Fin', 'Head', 'PlaceK', 'Curl', 'Speed', 'Accel',
             'KickP', 'Jump', 'Phys', 'Bal', 'Stam', 'DefAw', 'BallW', 'Aggr', 'GKAw', 'GKCat', 'GKClr', 'GKRef', 'GKRea']
    header(wa, ['ID u bazi', 'Igrač', 'Pozicija', 'Stari OVR', 'Novi OVR'] + short, [10, 26, 9, 9, 9] + [7] * 25)
    for r in rows:
        p = r['p']
        wa.append([p['id'], p['name'], p['pos'], r['cur'], r['new']] +
                  ['%d→%d' % (p['attr'][a], r['attr_new'][a]) if p['attr'][a] != r['attr_new'][a] else p['attr'][a] for a in D.ANAMES])
    for row in (wa.iter_rows(min_row=2) if S else ()):
        for c in row: c.font = F
        for c in row[2:]: c.alignment = Alignment(horizontal='center')
    wu = wb.create_sheet(X('Neupareni (TM)'))
    header(wu, ['Liga', 'Igrač (TM)', 'Klub (TM)', 'Klub je u bazi', 'Pozicija', 'Godine', 'Vrijednost (M EUR)', 'Ciljni OVR'], [18, 26, 24, 12, 18, 8, 11, 10])
    for lg, q, t in sorted(unmatched, key=lambda x: (not x[1].get('_ub'), x[0], x[1]['club'])):
        wu.append([lg, q['name'], q['club'], X('da') if q.get('_ub') else X('ne'), q['pos'], q['age'], round(q['value'] / 1e6, 2) if q['value'] else None,
                   int(np.clip(np.round(t), 40, 99)) if t is not None else None])
    wu.auto_filter.ref = 'A1:H%d' % (len(unmatched) + 1)
    for row in (wu.iter_rows(min_row=2) if S else ()):
        for c in row: c.font = F
    dod = [r for r in rows if r.get('ea_dod')]
    if dod:
        wd = wb.create_sheet(X('Dodaci (EA, reputacija)'))
        header(wd, ['ID u bazi', 'Igrač', 'Klub (baza)', 'Liga', 'Pozicija', 'Promjene (EA FC 27, reputacija, ozljede)'], [10, 26, 22, 18, 9, 90])
        for r in sorted(dod, key=lambda r: (r['league'], r['p']['club'])):
            wd.append([r['p']['id'], r['p']['name'], r['p']['club'], r['league'], r['p']['pos'], '; '.join(LG.tr(t) for t in r['ea_dod'])])
        for row in (wd.iter_rows(min_row=2) if S else ()):
            for c in row: c.font = F
        wd.auto_filter.ref = 'A1:F%d' % (len(dod) + 1)
    if podaci:
        wp = wb.create_sheet(X('Podaci (TM)'))
        header(wp, ['ID u bazi', 'Igrač', 'Klub (baza)', 'Liga', 'Promjene', 'Napomena'], [10, 26, 22, 18, 60, 60])
        for r, op, nap in sorted(podaci, key=lambda x: (x[0]['league'], x[0]['p']['club'])):
            wp.append([r['p']['id'], r['p']['name'], r['p']['club'], r['league'], '; '.join(LG.tr(t) for t in op), LG.tr(nap)])
        for row in (wp.iter_rows(min_row=2) if S else ()):
            for c in row: c.font = F
        wp.auto_filter.ref = 'A1:F%d' % (len(podaci) + 1)
    wi = wb.create_sheet(X('Info'))
    for line in [('Kalibracija TM -> overall', K.get('opis', '')), ('Datum', K['datum']), ('Izvor ocjena', K['baza']), ('Igraca u kalibraciji', K['n']),
                 ('Prosjecna greska (5-fold)', round(K['greska'], 2)), ('Unutar +-3', '%.0f %%' % (100 * K['unutar3'])),
                 ('Overall formula', 'tocna PES21 formula (iz PES2020 Editora), provjerena na pesdb.net')] + \
                [('Liga ' + c, '%s: %d' % (l, n)) for c, l, n in K['lige']]:
        wi.append([X(str(line[0])), X(line[1]) if isinstance(line[1], str) else line[1]])
    wi.column_dimensions['A'].width = 28; wi.column_dimensions['B'].width = 70
    for row in wi.iter_rows():
        for c in row: c.font = F
    wb.save(path)

if __name__ == '__main__':
    main()
