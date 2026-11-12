# -*- coding: utf-8 -*-
"""
Jezik izlaza: zapis rada, Excel izvjestaji i tekstualni izvjestaji.

Skripte su pisane na hrvatskom; za korisnike s jezikom 'en' (zadano, postavke.json -> "jezik") se sve sto vide
prevodi na engleski ovdje, na jednom mjestu:
    tr(linija)     -> prevedena linija zapisa rada / napomene u izvjestaju (regex pravila + rjecnik)
    x(tekst)       -> tocni prijevod naslova stupaca, listova, 'da'/'ne'
    jezik()        -> 'en' | 'hr'
Pravila su pisana za stvarne poruke skripti (ocjene, ugovori, ozljede, reprezentacije, ciscenje, bez_kluba, katalog,
spremanje, ea27, model); nepoznata linija ostaje kakva jest.
"""
import os, re, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
_C = {'t': 0, 'v': 'en'}

def jezik():
    if time.time() - _C['t'] > 3:
        _C['t'] = time.time()
        try: _C['v'] = json.load(open(os.path.join(HERE, 'postavke.json'), encoding='utf-8')).get('jezik') or 'en'
        except (OSError, ValueError): _C['v'] = 'en'
    return _C['v']

# ------------------------------------------------------------------ tocni prijevodi
EXACT = {
    'Pregled': 'Overview', 'Igraci': 'Players', 'Atributi': 'Attributes', 'Neupareni (TM)': 'Unmatched (TM)', 'Dodaci (EA, reputacija)': 'Extras (EA, reputation)',
    'Podaci (TM)': 'Data (TM)', 'Info': 'Info',
    'Liga': 'League', 'Ocijenjeno': 'Rated', 'Prosj. stari OVR': 'Avg old OVR', 'Prosj. novi OVR': 'Avg new OVR', 'Prosj. promjena': 'Avg change',
    'Pad >= 5': 'Drop >= 5', 'Rast >= 5': 'Rise >= 5', 'Ispravljeni podaci': 'Data fixed', 'TM bez vrijednosti': 'TM without value',
    'Neupareni (klub u bazi)': 'Unmatched (club in database)', 'UKUPNO': 'TOTAL', 'ID u bazi': 'ID in database', 'Igrač': 'Player', 'Klub (TM)': 'Club (TM)',
    'Klub (baza)': 'Club (database)', 'Pozicija': 'Position', 'Godine': 'Age', 'Vrijednost (M EUR)': 'Value (M EUR)', 'Trenutni OVR': 'Current OVR',
    'Ciljni OVR (TM)': 'Target OVR (TM)', 'Novi OVR': 'New OVR', 'Promjena': 'Change', 'EA FC 27': 'EA FC', 'Napomena': 'Note', 'Stari OVR': 'Old OVR',
    'Igrač (TM)': 'Player (TM)', 'Klub je u bazi': 'Club is in database', 'Ciljni OVR': 'Target OVR', 'Promjene': 'Changes',
    'Promjene (EA FC 27, reputacija, ozljede)': 'Changes (EA FC, reputation, injuries, contracts)',
    'da': 'yes', 'ne': 'no',
    'Kalibracija TM -> overall': 'Calibration TM -> overall', 'Datum': 'Date', 'Izvor ocjena': 'Ratings source', 'Igraca u kalibraciji': 'Players in calibration',
    'Prosjecna greska (5-fold)': 'Average error (5-fold)', 'Unutar +-3': 'Within +-3', 'Overall formula': 'Overall formula',
    'tocna PES21 formula (iz PES2020 Editora), provjerena na pesdb.net': 'exact PES21 formula (from PES2020 Editor), checked on pesdb.net',
}
def x(s):
    return EXACT.get(s, s) if jezik() == 'en' else s

# ------------------------------------------------------------------ pravila (regex) - linije zapisa rada i napomene
_R = [
 # --- opcenito / ocjene
 (r'^Brisanje \(ciscenje\.py\): (\d+) igraca bez kluba.*', r'Cleanup: removing \1 free agents (retired / duplicates)'),
 (r'^(\s*)Transfermarkt (\S+), sezona (\d+)\.\.\.', r'\1Transfermarkt \2, season \3...'),
 (r'^Ucitavam bazu: (.*?) \(iz zadnjeg izlaza\)$', r'Loading database: \1 (from last output)'),
 (r'^Ucitavam bazu: (.*)', r'Loading database: \1'),
 (r'^   (\d+) igraca$', r'   \1 players'),
 (r'^Zakljucano: (\d+) igraca \(ne mijenjaju se\)', r'Locked: \1 players (not changed)'),
 (r'^Opseg: (\d+) igraca, lige na Transfermarktu: (.*)', r'Scope: \1 players, Transfermarkt leagues: \2'),
 (r'^Opseg: (\d+) igraca$', r'Scope: \1 players'),
 (r'^Opseg: (\d+) reprezentacija', r'Scope: \1 national teams'),
 (r'^Opseg: (\d+) promjena izvan opsega odbaceno', r'Scope: \1 changes outside the scope discarded'),
 (r'^(\s+)Transfermarkt (\S+): (\d+) igraca \(API\)', r'\1Transfermarkt \2: \3 players (API)'),
 (r'^\s+\(API nije uspio za (\S+): (.*) - koristim stranice\)', r'   (API failed for \1: \2 - using the web pages)'),
 (r'^Sve lige: (\d+) TM liga\. Bez TM koda \(preskaceni\): (.*)', r'All leagues: \1 Transfermarkt leagues. Without a Transfermarkt code (skipped): \2'),
 (r'^Dodatne lige s Transfermarkta: (.*)', r'Extra Transfermarkt leagues: \1'),
 (r'^Uparivanje gotovo: (\d+) igraca s Transfermarkt ID-em', r'Matching done: \1 players with a Transfermarkt ID'),
 (r'^(\s+)\(Transfermarkt usporava - razmak ([\d.]+) s\)', r'\1(Transfermarkt is slowing down - interval \2 s)'),
 (r'^Rucni popis: (\d+) igraca \(ima prednost pred ligama\)', r'Manual list: \1 players (takes priority over leagues)'),
 (r'^Nema liga ni rucnog popisa za izracun.*', r'No leagues or manual list to calculate. Choose leagues first.'),
 (r'^Realni atributi iz EA FC 27: profil = (\d+) % EA \+ (\d+) % baza', r'Realistic attributes from EA FC: profile = \1 % EA + \2 % your database'),
 (r'^\[(\d+)/(\d+)\] Liga (\S+) \((.*)\): (\d+) TM igraca', r'[\1/\2] League \3 (\4): \5 Transfermarkt players'),
 (r'^Upareno globalno: (\d+) igraca iz (\d+) liga', r'Matched across all leagues: \1 players from \2 leagues'),
 (r'^Reputacija uskladjena s novim overallom kod (\d+) igraca', r'Reputation adjusted to the new overall for \1 players'),
 (r'^Otpornost na ozljede \(TM povijest ozljeda\): promijenjeno kod (\d+) igraca', r'Injury resistance (Transfermarkt injury history): changed for \1 players'),
 (r'^Ugovori s Transfermarkta: (\d+) igraca \(posudbi (\d+); (\d+) igraca je na TM-u u drugom klubu - preskoceno\)',
  r'Contracts from Transfermarkt: \1 players (\2 loans; \3 players are at another club on Transfermarkt - skipped)'),
 (r'^Godine u bazi racunaju se na (\S+) \(([\d.,]+) % igraca tocno\)', r'Ages in the database are counted on \1 (\2 % of players match)'),
 (r'^Drzavljanstvo: (\d+) igraca treba puni popis s Transfermarkta\.\.\.', r'Nationality: \1 players need the full list from Transfermarkt...'),
 (r'^Osnovni podaci: promijenjeno kod (\d+) igraca \(godine (\d+), visina (\d+), drzavljanstvo (\d+)\)', r'Player data: changed for \1 players (age \2, height \3, nationality \4)'),
 (r'^Upareno (\d+) igraca, neupareno (\d+)\. Promjena atributa kod (\d+) igraca \(EA profil: (\d+)\)\.',
  r'Matched \1 players, \2 unmatched. Attributes changed for \3 players (EA profile: \4).'),
 (r'^Izvjestaj: (.*)', r'Report: \1'),
 (r'^EA SPORTS FC 27 \((\d+) igraca\)', r'EA SPORTS FC 27 (\1 players)'),
 (r'^Nova baza: (.*)', r'New database: \1'),
 (r'^Novi Player\.bin: (.*?)\s+\(provjeren, (\d+) igraca\)', r'New Player.bin: \1 (checked, \2 players)'),
 (r'^CSV za editor \((\d+) igraca, promijenjeno (\d+)\): (.*)', r'Editor CSV (\1 players, \2 changed): \3'),
 (r'^Za zapis novog Player\.bin pokreni ponovno s --upisi\.', r'Nothing was written to the game folder.'),
 (r'^--upisi radi samo s \.bin bazom.*', r'Writing into the game works only with a .bin database (not with a CSV).'),
 (r'^   drzavljanstva (\d+)/(\d+)', r'   nationalities \1/\2'),
 (r'^   \(preskacem (\S+) - nema podataka\)', r'   (skipping \1 - no data)'),
 # --- ugovori / ozljede
 (r'^Ugovori: (\d+) igraca, skidam profil za (\d+)\.\.\.', r'Contracts: \1 players, downloading profiles for \2...'),
 (r'^   profili (\d+)/(\d+)', r'   profiles \1/\2'),
 (r'^Posudbe: skidam povijest transfera za (\d+) igraca\.\.\.', r'Loans: downloading transfer history for \1 players...'),
 (r'^   povijest (\d+)/(\d+)', r'   history \1/\2'),
 (r'^Gotovo za (\d+) s: (.*)', r'Done in \1 s: \2'),
 (r'^Primjena: .*', r'The contracts are used by the next ratings step.'),
 (r'^Igraca: (\d+), vec skinuto: (\d+), sada: (\d+)', r'Players: \1, already downloaded: \2, now: \3'),
 (r'^\[(\d+)/(\d+)\] (\d+) igraca/min', r'[\1/\2] \3 players/min'),
 (r'^(\s+)osvjezavam (\d+) starijih zapisa \(nova sezona / starije od 30-120 dana\)', r'\1refreshing \2 older records (new season / older than 30-120 days)'),
 (r'^GOTOVO: (\d+) igraca s podacima o ozljedama', r'DONE: \1 players with injury data'),
 # --- reprezentacije
 (r'^Reprezentacija u bazi: (\d+), povezano s TM-om: (\d+)', r'National teams in the database: \1, linked to Transfermarkt: \2'),
 (r'^Promijenjeno reprezentacija: (\d+) \(izvjestaj: (.*)\)', r'National teams changed: \1 (report: \2)'),
 (r'^Upisano u igru: (.*)', r'Written into the game: \1'),
 (r'^\(probni izracun - za upis u igru dodaj --upisi\)', r'(preview only - nothing written into the game)'),
 # --- ciscenje
 (r'^Igraca bez kluba i reprezentacije: (\d+) \(s TM id-em: (\d+)\)', r'Free agents without a national team: \1 (with a Transfermarkt ID: \2)'),
 (r'^TM profil za (\d+) igraca\.\.\.', r'Transfermarkt profile for \1 players...'),
 (r'^Za brisanje: (\d+)(\s+.*)?', r'To remove: \1\2'),
 (r'^Popis: (.*)', r'List: \1'),
 (r'^Brisanje u igri: .*', r'The removal is applied when the new database is written.'),
 (r'^Popis za brisanje obrisan.*', r'Removal list cleared.'),
 # --- bez_kluba
 (r'^Baza: (.*)', r'Database: \1'),
 (r'^Za ovu bazu jos nema izracuna po ligama - trazim sve igrace\.', r'No league calculation for this database yet - searching all players.'),
 (r'^Igraca za trazenje: (\d+), vec obradjeno: (\d+), sada: (\d+)', r'Players to search: \1, already done: \2, now: \3'),
 (r'^   \.\.\. (\d+) obradjeno, (\d+) igraca/min', r'   ... \1 done, \2 players/min'),
 (r'^GOTOVO: nadjeno (\d+) od (\d+)\. Rucni popis sada ima (\d+) igraca\.', r'DONE: found \1 of \2. The manual list now has \3 players.'),
 # --- katalog / faceovi / spremanje
 (r'^Tražim face-ove…', r'Looking for real faces…'),
 (r'^Katalog: (\d+) igrača \(([\d.]+) s\) -> (.*)', r'Player list: \1 players (\2 s) -> \3'),
 (r'^Katalog radi s \.bin bazom.*', r'The player list needs a .bin database (a CSV has no clubs or contracts).'),
 (r'^Popis face-ova: (\d+) igraca bez face-a.*', r'Face list: \1 players without a real face'),
 (r'^Izlazna mapa pripremljena: (\d+) datoteka baze -> (.*)', r'Output folder ready: \1 database files -> \2'),
 (r'^Nastavljam na postojecem izlazu: (.*)', r'Continuing on the existing output: \1'),
 (r'^Spremljeno \(provjereno\): (.*)', r'Saved (checked): \1'),
 (r'^Provjera nove baze NIJE prosla, nista nije spremljeno:', r'The new database FAILED validation, nothing was saved:'),
 (r'^(\s*)Player\.bin: velicina (\d+) nije visekratnik od (\d+)', r'\1Player.bin: size \2 is not a multiple of \3'),
 (r'^(\s*)Player\.bin: (\d+) dupliciranih ID-ova', r'\1Player.bin: \2 duplicate IDs'),
 (r'^(\s*)PlayerAssignment\.bin: (\d+) igraca ne postoji u Player\.bin(.*)', r'\1PlayerAssignment.bin: \2 players do not exist in Player.bin\3'),
 (r'^(\s*)PlayerAssignment\.bin: momcadi s vise od 40 igraca: (.*)', r'\1PlayerAssignment.bin: teams with more than 40 players: \2'),
 (r'^(\s*)PlayerAssignment\.bin: velicina nije visekratnik od 16', r'\1PlayerAssignment.bin: size is not a multiple of 16'),
 (r'^(\s*)PlayerAppearance\.bin: velicina nije visekratnik od 60', r'\1PlayerAppearance.bin: size is not a multiple of 60'),
 (r'^Kopirano u igru \((.*?)\): (.*)', r'Copied into the game (\1): \2'),
 (r'^Nema promijenjenih datoteka za kopiranje\.', r'No changed files to copy.'),
 (r'^Ulaz posla = zadnji izlaz \(snimka: (.*)\)', r'Job input = last output (snapshot: \1)'),
 (r'^Izlazna mapa ne smije biti ista kao ulazna baza: (.*)', r'The output folder must be different from the input database: \1'),
 (r'^Izlazna mapa nije pripremljena: (.*)', r'The output folder is not prepared: \1'),
 (r'^Izlazna mapa jos nema bazu.*', r'The output folder has no database yet - choose "Start from: input database".'),
 (r'^Nema baze u (.*)', r'No database in \1'),
 # --- EA / model / Transfermarkt
 (r'^\[(\d+)/(\d+)\] stranica (\d+): (\d+) igraca', r'[\1/\2] page \3: \4 players'),
 (r'^stranica (\d+): (\d+) igraca', r'page \1: \2 players'),
 (r'^GOTOVO: (\d+) igraca \(EA kaze (.*?)\) -> (.*)', r'DONE: \1 players (EA reports \2) -> \3'),
 (r'^\s+greska \((.*)\), pokusavam ponovno\.\.\.', r'  error (\1), retrying...'),
 (r'^Model nauceni na (\d+) igraca \((\d+) liga; (\d+) s vrijednoscu na (\S+)\)\. Prosjecna greska ([\d.]+), unutar \+-3: (\d+) %, nagib vrha ([\d.-]+)',
  r'Model trained on \1 players (\2 leagues; \3 with value on \4). Average error \5, within +-3: \6 %, top slope \7'),
 (r'^(\s+)! Transfermarkt privremeno blokira \((\d+)\), cekam (\d+) s\.\.\.', r'\1! Transfermarkt is temporarily blocking (\2), waiting \3 s...'),
 (r'^(\s+)! (.*) \((.*)\), pokusavam ponovno\.\.\.', r'\1! \2 (\3), retrying...'),
 (r'^(\s+)povijest vrijednosti: (\d+) novih igraca \(~(\d+) min\)\.\.\.', r'\1value history: \2 new players (~\3 min)...'),
 (r'^(\s+)! povijest (\S+): (.*)', r'\1! history \2: \3'),
 (r'^Ne mogu naci u bazi: (.*)', r'Database files not found: \1'),
 # --- napomene u Excel izvjestajima i opisi promjena
 (r'^godine (\d+) → (\d+) \(TM godine\)', r'age \1 → \2 (TM age)'),
 (r'^godine (\d+) → (\d+)', r'age \1 → \2'),
 (r'^visina (\d+) → (\d+)', r'height \1 → \2'),
 (r'^visina: baza (\d+), TM (\d+) - razlika prevelika, nije mijenjano \(provjeri\)', r'height: database \1, TM \2 - difference too large, not changed (check)'),
 (r'^2\. drzava (.*) → (.*)', r'2nd nationality \1 → \2'),
 (r'^drzava (.*) → (.*)', r'nationality \1 → \2'),
 (r'^reprezentacija (.*), a TM: (.*) - drzavljanstvo nije mijenjano', r'national team \1, but TM says \2 - nationality not changed'),
 (r'^TM prva drzava (.*), baza (.*) - treba puni popis drzavljanstava', r'TM first nationality \1, database \2 - needs the full nationality list'),
 (r'^jaca noga (lijeva|desna) → (lijeva|desna)', lambda m: 'stronger foot %s → %s' % ({'lijeva': 'left', 'desna': 'right'}[m.group(1)], {'lijeva': 'left', 'desna': 'right'}[m.group(2)])),
 (r'^slabija noga (.*)', r'weaker foot \1'),
 (r'^vjestine \+(.*)', r'skills +\1'),
 (r'^reputacija (\d+) → (\d+)', r'reputation \1 → \2'),
 (r'^ozljede (\d+) → (\d+) \(([\d.,]+) dana/sezonu\)', r'injuries \1 → \2 (\3 days/season)'),
 (r'^posudba do (\S+) \(vlasnik (.*?)\), ugovor do (\S+)', r'loan until \1 (owner \2), contract until \3'),
 (r'^ugovor do (\S+)', r'contract until \1'),
 (r'^TM nema trzisnu vrijednost - ocjena nije mijenjana', r'No Transfermarkt market value - rating not changed'),
 (r'^Transfermarkt nema trzisnu vrijednost za ovog igraca\.', r'Transfermarkt has no market value for this player.'),
 (r'^bez kluba - kontekst zadnjeg kluba(?:; liga (\S+) iz cache-a)?', lambda m: 'no club - context of the last club' + ('; league %s from cache' % m.group(1) if m.group(1) else '')),
 (r'^Tra[zž]im face-ove\.\.\.', r'Looking for real faces...'),
 (r'^Linkovi fotki: treba (\d+)', r'Photo links: need \1'),
 (r'^Fotke: skidam (\d+)', r'Photos: downloading \1'),
]
RULES = [(re.compile(p), r) for p, r in _R]

# rijeci unutar linija koje imaju slobodan tekst (ostaju poslije pravila)
WORDS = [
 ('nije nadjen na TM-u', 'not found on Transfermarkt'), ('PROVJERI (nije dodano)', 'CHECK (not added)'),
 ('Transfermarkt nema trzisnu vrijednost za ovog igraca.', 'Transfermarkt has no market value for this player.'),
 (' g., ', ' y, '),
 ('nije skinuta - jacina lige procijenjena', 'not downloaded - league strength estimated'),
 ("'duplikat'", "'duplicate'"), ("'umirovljen'", "'retired'"), ("'legenda (ostaje)'", "'legend (kept)'"),
 ("'bez kluba i na TM-u (ostaje)'", "'free agent on TM too (kept)'"), ("'TM: ima klub koji nije u bazi (ostaje)'", "'TM: has a club that is not in the database (kept)'"),
 ("'sacuvan rucno (ostaje)'", "'kept manually (kept)'"),
 ("'ugovor'", "'contracts'"), ("'posudba_vlasnik_nije_u_bazi'", "'loans_owner_not_in_database'"), ("'posudba'", "'loans'"),
 ("'drugi_klub'", "'other_club_on_tm'"), ("'klubova_mapirano'", "'clubs_mapped'"),
 ('duplikat: isti TM igrac kao', 'duplicate: same Transfermarkt player as'), ('umirovljen (Transfermarkt)', 'retired (Transfermarkt)'),
]

def tr(s):
    """Prevedi jednu liniju (ili napomenu). Na hrvatskom ('hr') vraca nepromijenjeno."""
    if not isinstance(s, str) or jezik() != 'en' or not s: return s
    for rx, rep in RULES:
        if rx.search(s):
            s = rx.sub(rep, s, count=1); break
    for a, b in WORDS:
        if a in s: s = s.replace(a, b)
    return s

def tr_text(t):
    """Vise linija (tekstualni izvjestaji)."""
    if jezik() != 'en': return t
    return '\n'.join(tr(l) for l in t.split('\n'))

def en():
    return jezik() == 'en'

# ------------------------------------------------------------------ tekstualni izvjestaji (datoteke)
FILE_WORDS = [
 ('CISCENJE IGRACA BEZ KLUBA', 'CLEANUP OF PLAYERS WITHOUT A CLUB'), ('ZA BRISANJE', 'TO REMOVE'),
 ('NISU NADJENI NA TM-u ili jos nisu trazeni', 'NOT FOUND ON TRANSFERMARKT OR NOT SEARCHED YET'), ('ostaju)', 'kept)'),
 ('REPREZENTACIJE prema Transfermarktu', 'NATIONAL TEAMS from Transfermarkt'), ('Promijenjeno:', 'Changed:'),
 (' pozvanih, u bazi ', ' called up, in database '), ('| sastav ', '| squad '), ('| ulaze: ', '| in: '), ('| izlaze: ', '| out: '),
 ('| nema u bazi: ', '| not in database: '), ('pronadeno ', 'found '), (' pozvanih - premalo, preskoceno', ' called up - too few, skipped'),
 ('TM popis prazan - preskoceno', 'Transfermarkt squad empty - skipped'), ('(u bazi za drugu reprezentaciju)', '(in the database for another national team)'),
 ('FACE-OVI', 'REAL FACES'), ('Pokrivenost po ligama (igraci s pravim face-om)', 'Coverage by league (players with a real face)'),
 ('NAJPOTREBNIJI FACE-OVI (bez face-a, po TM vrijednosti;', 'MOST NEEDED FACES (no real face, by Transfermarkt value;'), (' igraca):', ' players):'),
 ('BOJA KOZE', 'SKIN COLOUR'), ('promjena kod', 'changes for'), ('generic igraca', 'generic players'), ('razlika >=', 'difference >='),
]

def prevedi_datoteku(path):
    """Prevedi tekstualni izvjestaj na mjestu (za 'en'); na 'hr' ne radi nista."""
    if jezik() != 'en' or not os.path.isfile(path): return
    t = open(path, encoding='utf-8').read()
    t = tr_text(t)
    for a, b in FILE_WORDS: t = t.replace(a, b)
    open(path, 'w', encoding='utf-8').write(t)
