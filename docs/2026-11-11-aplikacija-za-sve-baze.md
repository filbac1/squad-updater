# Aplikacija za bilo koju bazu – dizajn (11.11.2026.)

## Zašto
Ocjene/podaci s Transfermarkta trenutno rade za jednu instalaciju (FL27 + Sider + `ocjene_tm\izlaz`).
Cilj: aplikaciju zapakirati i poslati drugim moderima. Svatko ubaci **svoju** bazu (i ModStudio s ~200.000 igrača),
odabere **što** želi promijeniti i **na kome**, pričeka, spremi rezultat u **novu mapu**, a sve podatke može filtrirati.

## Tok korisnika
1. Otvori bazu: aktivna baza igre, mapa (CommonLib/ModStudio/raspakirano), CPK ili CSV iz PES2020 Editora.
2. Novi posao = jedna ploča:
   - **Na kome (opseg):** cijela baza / odabrane lige / klubovi ili reprezentacije / trenutni filter iz pregleda.
     Sve izvan opsega ostaje bajt-po-bajt isto.
   - **Što (promjene):** ocjene s TM-a, popravak godina/države/visine, EA atributi, noga/WF/pozicije/vještine,
     reputacija, ozljede, ugovori i posudbe, reprezentacije (zadnji poziv), čišćenje (umirovljeni/duplikati),
     pojedinačno traženje igrača bez kluba. Uz svaku: jedna rečenica + procjena trajanja.
   - **Krenuti od:** originalne baze ili zadnjeg izlaza (korisnik bira).
   - **Spremiti u:** nova mapa (ulazna baza u istoj strukturi, sve datoteke, promijenjene zamijenjene) +
     neobavezno „kopiraj i u igru“ ako je korisnik u postavkama sam zadao lokaciju (sider root). sider.ini se ne dira;
     aplikacija pokaže redak koji treba dodati.
3. Obrada u koracima, s napretkom, prekidom i nastavkom.
4. **Pregled i filteri** (poslužitelj filtrira, po stranicama – mora raditi za 200.000 igrača): ime, liga, klub, država,
   reprezentacija, pozicija, godine, ocjena; statusi bez kluba, posudba, ugovor ističe, bez facea, nije nađen na TM-u,
   sumnjiv par, promijenjen u zadnjem poslu, Δ ocjene. Klik na igrača: atributi prije/poslije, TM podaci, zašto je uparen,
   poništi za igrača, zaključaj igrača. Filter → „Use as scope for new job“. Izvoz u Excel/CSV.
5. Povijest poslova: ponovi posao jednim klikom (npr. „Albanija opet“).

## Odluke korisnika
- Radni prostor (baza lijevo, posao/pregled desno), ne čarobnjak.
- Izlaz = inicijalna baza ažurirana novim .bin datotekama u novoj mapi. CSV ulaz → CSV izlaz.
- Krenuti od originala ili od zadnjeg izlaza – bira korisnik.
- „Ubaci u igru“ ostaje kao opcija samo ako korisnik sam zada lokaciju.
- Sučelje na engleskom.
- Distribucija: zapakirano i poslano.

## Moje odluke (provjeri)
- Pakiranje: PyInstaller, mapa s `.exe`, bez instalacije Pythona; formula (model) i EA podaci idu uz aplikaciju,
  TM podaci se skidaju svakom korisniku. Korisnički podaci u `%LOCALAPPDATA%\FLRatings` (ne u mapi programa).
- Hrvatski ostaje kao drugi jezik (postavke).
- CPK ulaz → izlaz je raspakirana mapa (bez ponovnog pakiranja u CPK u prvoj verziji).
- Prije spremanja provjera cijele nove baze (veličine zapisa, ID-ovi, svi igrači iz PlayerAssignmenta postoje); ako ne prođe, ne sprema.
- Postojeći `ui.html` ostaje dok nova aplikacija (`app.html`) ne dostigne isto.

## Anti-ciljevi
Pokvarena baza / rušenje igre; tihe krive promjene (uvijek popis sumnjivih parova); iznenađujuće dugo trajanje bez procjene;
pregaženi ručni rad (ručni popis i zaključani igrači uvijek imaju prednost).

## Faze
1. **Jezgra:** opseg (lige/klubovi/ID-ovi), izlazna mapa s cijelom bazom, „krenuti od“ (original/zadnji izlaz), provjera prije spremanja.
2. **Pregled s filterima** (katalog igrača po projektu, filtriranje i stranice na poslužitelju, detalj igrača, izvoz).
3. **Novo sučelje** (radni prostor, engleski + hrvatski, povijest poslova, postavke s lokacijom igre).
4. **Opće putanje:** bez pretpostavki o Sideru/FL27 (lokacija igre iz postavki), korisnički podaci izvan programa.
5. **Veličina:** test na velikoj bazi (ModStudio), brzina učitavanja i izvještaja.
6. **Pakiranje** (PyInstaller) i test na čistom računalu.

## Stanje (11.11.2026., sve faze napravljene)
1. Jezgra: `spremanje.py` (izlazna mapa = cijela baza + promijenjeno, provjera prije zapisa, `baza_info.json`), `--izlaz`, `--od=izlaz|<snimka>`,
   `--opseg` u ocjene/reprezentacije/ugovori/ozljede/ciscenje/bez_kluba, zakljucani igraci (`zakljucani.json`), `--bez-ocjena`.
2. Pregled: `katalog.py` -> `baze\<id>\katalog.json`; filteri/stranice/izvoz/detalj/zakljucaj/ponisti u `app_api.py`.
3. Aplikacija: `app.html` (Squad Updater, EN + HR), `/classic` = staro sucelje. Posao = koraci (priprema, trazenje, uparivanje,
   ugovori, ozljede, ciscenje, zapis, reprezentacije, katalog, kopija u igru), povijest `poslovi.json`, postavke `postavke.json`.
4. Putanje: `provjera_faca.py` kopiran u ocjene_tm, mapa igre i sider.ini iz postavki.
5. Velika baza (211.160 igraca): ucitavanje 5 s, katalog 13 s, filter < 0,1 s, CSV izvoz 0,7 s, posao za ligu 22 s.
6. Pakiranje: `SquadUpdater.spec`, `squad_updater.py` (--skripta), `napravi_exe.bat` -> Desktop\SquadUpdater.zip (84 MB). Testirano od nule.

Otvoreno: poruke u zapisu rada i Excel izvjestaji su jos na hrvatskom; MarketValue se ne pise; CPK izlaz je mapa.
