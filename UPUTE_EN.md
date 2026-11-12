# Squad Updater – quick guide

Squad Updater updates a PES 2021 / Football Life database from Transfermarkt (and EA SPORTS FC for attribute shapes).
It never changes your database: every job writes a full copy with the changed files into a folder you choose.

## Start
1. Unzip the folder anywhere you can write to (e.g. Documents, not Program Files) and run `SquadUpdater.exe`.
   The app opens in its own window. When you close the window the program stops (if a job is still running it
   finishes first; start `SquadUpdater.exe` again to open its window).
   If port 8765 is taken the app picks a free one; if the folder is write-protected it tells you.
2. **Change database** (left): the game database (set the game folder and sider.ini in Settings), a database folder
   (CommonLib, Mod Studio, unpacked), a CPK file, or a PES 2020 Editor CSV.
3. The player list is built once (a few seconds; ~15 s for 200,000 players).

## A job
**New job** → choose *Players to update* (whole database, leagues, clubs/national teams, or the current filter from
the Players page), tick the *Changes*, pick *Start from* (input database or last output) and the output folder, then
**Run job**. The estimate tells you how long it takes; slow steps (injuries, one-by-one search) resume where they stopped.

Everyone outside the chosen players stays byte-for-byte as in the input database. Before anything is saved the new
database is checked (record sizes, unique IDs, every squad player exists); if a check fails, nothing is written.

## Players page
Filter by name, league, club, nationality, national team, position, age, overall, status (no club, on loan, no real
face, not on Transfermarkt, check match, changed…), contract year or change size. Click a player for attributes before
and after, the Transfermarkt match, **Lock player** (future jobs never change him) and **Undo for this player**.
Export the filtered list to CSV or Excel, or use it as the scope of a new job.

## Into the game
Use the output folder as a Sider live CPK root, or set *Copy into the game* in Settings and tick it in a job
(existing files there are backed up first). Add the shown `cpk.root` line to sider.ini once.

**Edit file:** the game keeps Edit mode changes in `EDIT00000000` (FL27: `Documents\SPGAME\Football Life\<id>\save`).
While it exists, its squads override the national teams from the new database, and the game creates a new one from the
current database the first time it starts without one. *Copy into game* can therefore move the old edit file to a
`save_backup_<date>` folder next to it (on by default); the game then builds a fresh one from the new database.
Manual Edit mode changes are not carried over, so make them after updating. The Overview page shows whether the game
has the new database and whether an edit file is in the way.

## Keeping it current
**Settings → Ratings data → Update ratings data** downloads the current EA SPORTS FC ratings and the Transfermarkt squads,
then learns the formula again (about 30–90 minutes the first time, less later; it can be stopped and resumed). If the new
formula looks wrong the previous one is kept. **Check for a new version** needs an update address (Settings → advanced)
that whoever sent you the program provides. Settings shows a dot when the ratings data is older than 60 days.

## Good to know
- Transfermarkt is queried politely (about 2 requests per second). Large first runs take time; later runs use the cache.
- Ratings: overall from market value, age, position, club and league, learned on ~13,000 EA SPORTS FC 27 ratings
  (average error ≈ 1.8). The *Gap for weaker players* slider moves weaker players between EA FC (0) and your database (1).
- **Market value (experimental)** is off by default. It writes the Transfermarkt value, in thousands of euros, into the
  player's MarketValue field. Most databases leave that field empty, so check a few players in a new Master League first.
- **Edit a national team squad:** National teams → choose a team → *Edit squad*. Add players (search by name), remove
  players and change shirt numbers, then *Save to the new database*. Your changes are remembered and applied again after
  every national-team update; *Undo all my changes* restores the calculated squad. A player can be in only one national team.
- **Best starting line-up** (job option): the first eleven of every squad become the best players for the team's formation,
  using the new ratings and position ratings. The 12 substitutes are the backup goalkeeper plus at least 3 defenders,
  3 midfielders and 2 forwards, then the best of the rest; the weakest of each line are left out. Both are ordered goalkeeper to forward. Only the squad order changes.
- **Compare two players:** open a player and type another name into *Compare with…*.
- **History** also lists copies into the game, game restores, squad edits and changes made outside the app.
