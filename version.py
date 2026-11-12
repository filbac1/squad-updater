# -*- coding: utf-8 -*-
"""Verzija programa i adresa za provjeru nove verzije."""
VERSION = '1.1.0'
# Zadano: zadnje izdanje na GitHubu (tag vX.Y.Z, prilog SquadUpdater-X.Y.Z.zip).
# Moze i vlastita JSON datoteka (Settings -> update_url):
#   {"version": "1.1.0", "url": "https://example.com/SquadUpdater-1.1.0.zip", "notes": "What changed"}
REPO = 'filbac1/squad-updater'
DEFAULT_UPDATE_URL = 'https://api.github.com/repos/%s/releases/latest' % REPO
