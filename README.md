# Squad Updater

Squad Updater brings a PES 2021 / Football Life database up to date from Transfermarkt, with ratings calibrated on EA SPORTS FC.
It never changes your database: every job writes a full copy with the changed files into a folder you choose.

## What it does
- **Ratings** from market value, age, position, club and league, learned on ~13,000 EA SPORTS FC ratings (average error ≈ 1.8).
- **Your own formula:** sliders for how much value, age, club, league, region and value trend count, plus shifts per line, with a live preview.
- **Why this overall?** Every player shows how his rating is built up from the formula.
- **Player data:** age, nationality, height, contracts and loans, injury resistance, reputation, EA attribute shapes, foot and skills.
- **National teams** from the latest call-ups, **best starting line-ups**, cleanup of retired players and duplicates.
- **Scope:** whole database, chosen leagues, clubs or a filter. Everything outside the scope stays byte-for-byte the same.
- Works with the game database, CommonLib / Mod Studio folders (tested with 211,000 players), CPK files and PES 2020 Editor CSV.

## Download
Get the latest `SquadUpdater-x.y.z.zip` from [Releases](https://github.com/filbac1/squad-updater/releases), unzip it to a folder you can
write to (not Program Files) and run `SquadUpdater.exe`. No Python needed. The app tells you when a new version is out
(Settings → Check for a new version).

See [UPUTE_EN.md](UPUTE_EN.md) for the full guide.

## Running from source
Python 3.13 with `numpy`, `scikit-learn`, `openpyxl` and `requests`:

```
python ui.py                                  # opens the app in your browser
python -m unittest discover -s testovi        # tests
napravi_exe.bat                               # tests + PyInstaller build -> Desktop\SquadUpdater.zip
python objavi_izdanje.py "What is new"        # publish a GitHub release (bump version.py first)
```

Transfermarkt is queried politely (rate-limited, cached). Large first runs take time; later runs reuse the cache.
