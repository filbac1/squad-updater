# Ocjene FL27 – upute

Sustav računa **overall svakog igrača iz Transfermarkta** (tržišna vrijednost, godine, pozicija, jačina kluba i lige),
proporcionalno skalira atribute tako da overall u igri bude točno taj, i usput **popravlja godine, državljanstvo i visinu**.
Radi bez AI-ja: samo Python i ove skripte.

## Brzo

| Što želim | Kako |
|---|---|
| Sve kroz sučelje | dvoklik `pokreni_ui.bat` → otvori se http://127.0.0.1:8765 |
| Reprezentacije, ugovori, čišćenje, face-ovi | u sučelju, istoimene kartice (svaka ima i gumb za pokretanje) |
| Nove ocjene za cijelu bazu **i odmah u igru** | dvoklik `ubaci_u_igru.bat` (≈ 4 min) |
| Samo CSV za PES2020 Editor (igra se ne dira) | dvoklik `pokreni_sve.bat` → `izvjestaji\baza_nove_ocjene_SVE_*.csv` |
| Provjeriti da sve radi nakon promjena | dvoklik `pokreni_provjeru.bat` (10 testova, ne dira igru) |

## Kako dolazi u igru

- Novi `Player.bin` se piše u `ocjene_tm\izlaz\common\etc\pesdb\Player.bin`.
- `sider.ini` ga učitava jer je **prvi** `cpk.root = ".\ocjene_tm\izlaz"`.
- Svaki novi upis sprema prethodni u `ocjene_tm\izlaz_povijest\` (zadnjih 10). U sučelju (kartica *Formula → Baza u igri*) se
  bilo koja verzija, ili original, vraća jednim klikom.
- Original iz igre: `ocjene_tm\backup_original_2026-11-10\` (+ `SiderAddons\sider.ini.backup_2026-11-10_prije_ocjena`).
- **Isključiti nove ocjene:** obriši/zakomentiraj (`;`) redak `cpk.root = ".\ocjene_tm\izlaz"` u `sider.ini`.
- Izračun **uvijek kreće od originalne baze** (mapa `izlaz` se pri čitanju preskače), pa se ništa ne "nakuplja".
- Postojeći Master League save čuva stare igrače; nove ocjene se vide u novim utakmicama / novom ML-u.
- **Edit file nadjačava sastave:** FL27 sprema u `Dokumenti\SPGAME\Football Life\2027\save\EDIT00000000` (NE u KONAMI mapu).
  Dok postoji, reprezentacije iz baze se ne vide; bez njega igra pri pokretanju napravi novi iz trenutne baze.
  *Kopiraj u igru* zato (zadano) premješta stari edit u `save_backup_<datum>`. Ručne Edit izmjene raditi NAKON ažuriranja.
- Legende (Classic / ML Default timovi) se nikad ne mijenjaju; reprezentativci dobivaju državu reprezentacije kao prvo državljanstvo.

## Tok za cijelu bazu

1. **Lige** – u sučelju *Lige → Označi sve* (+ po želji *Lige s Transfermarkta*), *Izračunaj* (s kvačicom *Ubaci u igru*).
2. **Ostali igrači** – *Pojedinačno traženje → Svi neocijenjeni igrači* (≈ 3 s po igraču, nastavlja gdje je stao).
   Nađeni idu na **ručni popis** (ima prednost pred ligama).
3. Ponovi korak 1 – sad su uključeni i igrači s ručnog popisa.

Legende (Classics/ML Default) se preskaču – TM nema njihovu vrijednost.

**Sigurnost pojedinačnog traženja** (nema kluba za potvrdu, pa su pravila stroga):
- prezime **i** ime moraju odgovarati (ili inicijal), godine dosljedne s 1.1.2027.;
- igrači bez kluba u bazi često imaju zastarjele godine (npr. Martial 19 umjesto 30) – prihvaćaju se samo ako na TM-u postoji
  **točno jedan** igrač s potpuno istim imenom i državom;
- ako bi se ocjena bez potvrde klubom promijenila **više od 8**, igrač ide na popis **„Za provjeru“** (kartica *Pojedinačno
  traženje*) – tamo ga jednim klikom dodaš ili odbaciš.

## Formula

- **Overall u igri**: točna PES21 formula (iz PES2020 Editora; 99,6 % točno na pesdb.net, 100 % na editorovom OverallStats).
- **TM → overall**: gradient boosting naučen na **EA SPORTS FC 27** ocjenama (≈13.000 igrača, 46 liga).
  Ulazi: vrijednost (glavno), godine, pozicija, jačina kluba, jačina lige, regija. Prosječna greška ≈ 1,8; nema pristranosti po dobi.
  Uči se na TM vrijednosti s datuma izlaska EA ocjena (15.9.2026.) gdje je povijest poznata.
- **Ljestvica** (`--skala`, default 0,5): ispod 82 razlika prema slabijima je pola puta između EA FC i sadašnje baze
  (0 = kao EA, 1 = kao baza). Od 82 naviše uvijek kao EA.
- Lige koje formula nikad nije vidjela (npr. Albanija) dobiju procjenu preko jačine kluba/lige i regije (greška ≈ 2).

## Popravak podataka (uključen po defaultu, `--bez-podataka` isključuje)

- **Godine** – iz TM datuma rođenja, na datum na koji baza računa godine (FL27: 1.1.2027., određuje se automatski).
- **Visina** – ako je razlika do 8 cm; veće se samo prijave u izvještaju (i TM griješi).
- **Državljanstvo** (glavno + drugo) – igrač u reprezentaciji zadržava tu državu kao glavnu; države kojih nema u PES-u se preskaču.
- Sve promjene: Excel izvještaj, list **„Podaci (TM)“**.

## Ugovori, reprezentacije, čišćenje, face-ovi (od 11.11.2026.)

| Modul | Što radi | Isključi |
|---|---|---|
| `ugovori.py` | Ugovor do (ContractUntil), posudba (OwnerClub + LoanUntil) s TM API-ja; ugovor s matičnim klubom za posuđene. ≈5 min, cache 7 dana | `--bez-ugovora` |
| `reprezentacije.py --upisi` | Sastav = **točno zadnji TM poziv** (najviše 26; širi popis → 26 najboljih, ≥3 golmana), brojevi s TM-a, postava zadržava formaciju. Piše `izlaz\common\etc\pesdb\PlayerAssignment.bin`. Preskače reprezentacije gdje je u bazi < 50 % pozvanih | obriši tu datoteku |
| `ciscenje.py` | Popis za brisanje igrača **bez kluba**: umirovljeni (TM) i duplikati (isti TM igrač, ista država, ±2 god.). Legende se ne diraju. `--isprazni` vraća sve | `--bez-brisanja` |
| `koza.py` | Popis najpotrebnijih face-ova (po TM vrijednosti, s linkom na TM fotku) → `izvjestaji\faceovi_*.txt`. Boja kože iz TM fotke je testirana i **NE preporučuje se** (`--upisi`): postojeće boje generic igrača su već dobre, a jedna fotka je preneprecizna (svjetlo/sjene) | – |

Tržišna vrijednost (MarketValue) je **eksperimentalna opcija, zadano isključena** (`--trzisna-vrijednost`): TM vrijednost u tisućama eura.
U FL27 bazi je polje gotovo svugdje 0, pa prvo u novom Master Leagueu provjeri nekoliko igrača.

**Ručno uređivanje reprezentacija:** sučelje → *Reprezentacije* → *Uredi sastav* (dodaj/makni igrača, broj dresa).
Izmjene se pamte u `baze\<id>
eprezentacije_rucno.json` i ponovno primjenjuju nakon svakog izračuna reprezentacija
(`repr_rucno.py`); osnovni sastav je u `<nova baza>\_rucno\osnova.json`, pa *Poništi sve moje izmjene* vraća izračunati sastav.

**Najbolja postava** (opcija posla, `postave.py`): prvih 11 u svakoj momčadi = najbolji igrači za formaciju momčadi (TacticsFormation.bin),
prema novim ocjenama i ocjeni pozicije (B −3, C −15, glavna pozicija +2). Klupa (12): rezervni golman + barem 3 obrane, 3 veznih i 2 napadača,
ostatak najbolji po ocjeni; izvan kadra najslabiji iz svake linije. Klupa i izvan kadra poredani od golmana do napadača. Mijenja se samo redni broj u PlayerAssignment.bin.

**Usporedba igrača:** u prozoru igrača upiši drugo ime u *Usporedi s…*. **Povijest** pokazuje i kopiranja u igru,
vraćanja, uređivanja reprezentacija i izmjene napravljene izvan aplikacije.
`ubaci_u_igru.bat` sad redom pokreće: ugovori → ocjene (s ozljedama, ugovorima i brisanjem) → reprezentacije.
U sučelju isto: kartica *Lige*, kvačice *Ozljede / Ugovori / Obriši* i *Ubaci u igru* → *I reprezentacije* (jedan zadatak u koracima).
Redoslijed igrača u reprezentaciji = po poziciji kao u originalu (GK, CB, …); **prvu postavu igra slaže sama** (u originalnoj bazi su prva tri mjesta uvijek golmani).

## Vlastita baza

U sučelju *Promijeni bazu*: aktivna baza igre / mapa s bazom (CommonLib, ModStudio…) / CPK / samo CSV iz editora,
i neobavezno **tvoj CSV kao predložak** (izlaz = tvoj CSV s promijenjenim samo atributima, overallom i podacima).
Naredbeni redak: `--baza="D:\mapa ili datoteka.cpk"`, `--csv-ulaz="D:\baza.csv"`, `--dodatne=ALB1,KR2`.
Svaka baza ima svoj ručni popis i postavke u `baze\<id>\`.

## Nova liga u bazi (npr. Albanija)

Sučelje → *Lige* → u stupcu *TM kod* počni tipkati ime lige i odaberi (npr. `ALB1`). Ili u *Lige s Transfermarkta* označi ligu.

## Održavanje

| Kada | Što |
|---|---|
| Prijelazni rok / nove vrijednosti | `ubaci_u_igru.bat` s `--osvjezi` (ponovno skida Transfermarkt; inače cache 7 dana) |
| Nova EA FC igra (FC 28) | Sučelje → *Formula* → *Skini EA ocjene*, zatim *Nauči formulu* (u `model_ea27.py` promijeni `KAL_DATUM` na datum izlaska novih ocjena) |
| Nakon izmjena koda | `pokreni_provjeru.bat` |

## Datoteke

| Datoteka | Uloga |
|---|---|
| `ocjene.py` | glavni izračun (lige, ručni popis, skaliranje, podaci, izvještaj, CSV, Player.bin) |
| `pes_overall.py` | točna formula overalla igre |
| `model_ea27.py`, `model_ea27.pkl` | formula TM → overall (EA FC 27) |
| `tm_igrac.py`, `bez_kluba.py` | pojedinačni igrači s Transfermarkta, skupno traženje |
| `tm_podaci.py` | pravila za godine / državljanstvo / visinu |
| `izvor.py` | izvori baze (igra, mapa, CPK, CSV) i izlazni CSV |
| `izvoz_csv.py`, `fl27db.py` | čitanje/pisanje Player.bin i PlayerAppearance, CSV za editor |
| `katalog_liga.py`, `ea27.py` | katalog svih TM liga, EA FC ocjene |
| `ui.py`, `ui.html` | lokalno sučelje |
| `provjera.py` | testovi |
| `cache\` | Transfermarkt i EA podaci (može se obrisati – ponovno se skine) |
