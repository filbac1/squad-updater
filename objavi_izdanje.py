# -*- coding: utf-8 -*-
"""
Objavi novu verziju na GitHubu (Releases) - korisnici je vide u Settings -> Check for a new version.

  1. povecaj VERSION u version.py
  2. napravi_exe.bat  (testovi + PyInstaller -> Desktop\\SquadUpdater.zip)
  3. python objavi_izdanje.py "Sto je novo u jednoj recenici"

Napravi tag vX.Y.Z, izdanje s prilogom SquadUpdater-X.Y.Z.zip i biljeskom. Treba GitHub CLI (gh) i prijavu (gh auth login).
"""
import os, sys, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import version as V

def gh():
    for p in (shutil.which('gh'), r'C:\Program Files\GitHub CLI\gh.exe'):
        if p and os.path.exists(p): return p
    raise SystemExit('GitHub CLI (gh) nije instaliran.')

def main():
    if len(sys.argv) < 2: raise SystemExit(__doc__)
    biljeska = sys.argv[1].strip()
    zip_ = os.path.join(os.path.expanduser('~'), 'Desktop', 'SquadUpdater.zip')
    if not os.path.exists(zip_): raise SystemExit('Nema %s - prvo pokreni napravi_exe.bat.' % zip_)
    if subprocess.run(['git', 'status', '--porcelain'], cwd=HERE, capture_output=True, text=True).stdout.strip():
        raise SystemExit('Ima necommitanih promjena - commitaj ih prije objave.')
    tag = 'v' + V.VERSION
    d = tempfile.mkdtemp(); asset = os.path.join(d, 'SquadUpdater-%s.zip' % V.VERSION); shutil.copy2(zip_, asset)
    subprocess.run(['git', 'push', 'origin', 'HEAD'], cwd=HERE, check=True)
    subprocess.run([gh(), 'release', 'create', tag, asset, '--repo', V.REPO, '--title', 'Squad Updater ' + V.VERSION,
                    '--notes', biljeska, '--target', 'main'], cwd=HERE, check=True)
    print('Objavljeno: https://github.com/%s/releases/tag/%s' % (V.REPO, tag))

if __name__ == '__main__':
    main()
