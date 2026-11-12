# -*- coding: utf-8 -*-
"""
Squad Updater - pokretač (i ulazna točka zapakirane aplikacije).

    SquadUpdater.exe                           -> jedan prozor aplikacije (bez crnog prozora i bez kartica preglednika)
    SquadUpdater.exe --skripta ocjene.py ...   -> korak posla (aplikacija ga sama pokreće istim .exe-om)
    python squad_updater.py [--bez-prozora]    -> isto iz izvornog koda

Što radi pri pokretanju:
  * provjeri da u svojoj mapi smije pisati (inace jasna poruka - npr. mapa u Program Files);
  * ako Squad Updater već radi (port 8765), samo otvori njegov prozor;
  * ako je port 8765 zauzet nekim drugim programom, uzme prvi slobodni (8766...);
  * otvori prozor: Edge ili Chrome u "app" načinu (vlastiti prozor bez adresne trake, vlastiti profil);
    ako ih nema, običan preglednik;
  * kad se prozor zatvori, program se sam ugasi (ako nešto radi u pozadini, čeka da posao završi).
"""
import os, sys, time, json, runpy, socket, threading, subprocess, tempfile, urllib.request

FROZEN = getattr(sys, 'frozen', False)
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
BASE_PORT = 8765

def poruka(tekst, naslov='Squad Updater', greska=True):
    """Prozor s porukom (radi i kad nema konzole)."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, tekst, naslov, 0x10 if greska else 0x40)
    except Exception:
        print(naslov + ': ' + tekst, file=sys.stderr)

def moze_pisati(mapa):
    try:
        with tempfile.NamedTemporaryFile(dir=mapa, prefix='.provjera_', delete=True): pass
        return True
    except OSError:
        return False

def ping(port):
    """True ako na portu radi Squad Updater."""
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/api/v2/ping' % port, timeout=2) as r:
            return json.load(r).get('app') == 'squad-updater'
    except Exception:
        return False

def port_slobodan(port):
    s = socket.socket()
    try:
        s.bind(('127.0.0.1', port)); return True
    except OSError:
        return False
    finally:
        s.close()

def nadji_preglednik():
    pf = [os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), os.environ.get('LocalAppData')]
    for rel in (r'Microsoft\Edge\Application\msedge.exe', r'Google\Chrome\Application\chrome.exe'):
        for b in pf:
            if b and os.path.isfile(os.path.join(b, rel)): return os.path.join(b, rel)
    return None

def profil_mapa():
    b = os.environ.get('LOCALAPPDATA') or HERE
    p = os.path.join(b, 'SquadUpdater', 'browser'); os.makedirs(p, exist_ok=True); return p

def otvori_prozor(url):
    """Vraca subprocess (app prozor) ili None ako je otvoren običan preglednik."""
    exe = nadji_preglednik()
    if exe:
        try:
            return subprocess.Popen([exe, '--app=' + url, '--user-data-dir=' + profil_mapa(), '--no-first-run', '--no-default-browser-check',
                                     '--window-size=1440,920', '--disable-features=Translate,msEdgeSignIn'])
        except OSError:
            pass
    import webbrowser
    webbrowser.open(url)
    return None

def glavni(argv):
    if FROZEN:
        sys.path.insert(0, HERE); os.chdir(HERE)
    else:
        sys.path.insert(0, HERE)
    bez_prozora = '--bez-prozora' in argv or '--bez-preglednika' in argv

    if not moze_pisati(HERE):
        poruka('Squad Updater needs to save its data next to the program, but this folder is write-protected:\n\n%s\n\n'
               'Move the whole SquadUpdater folder to a normal location (for example Documents) and start it again. '
               'Do not put it in Program Files.' % HERE)
        return 1

    # vec pokrenut? -> samo otvori prozor
    if ping(BASE_PORT):
        if not bez_prozora: otvori_prozor('http://127.0.0.1:%d/' % BASE_PORT)
        return 0
    port = BASE_PORT
    while not port_slobodan(port) and port < BASE_PORT + 40: port += 1
    if port >= BASE_PORT + 40:
        poruka('Squad Updater could not find a free network port (8765-8805). Close other programs that use them and try again.')
        return 1

    import ui, app_api as AA
    ui.PORT = port
    try:
        ui.serve(port)
    except OSError as e:
        poruka('Squad Updater could not start its local server on port %d:\n%s' % (port, e)); return 1
    for _ in range(50):
        if ping(port): break
        time.sleep(0.1)
    url = 'http://127.0.0.1:%d/' % port
    start = time.time()
    if bez_prozora:
        while True: time.sleep(3600)
    proc = otvori_prozor(url)
    if proc is not None:                                 # prozor je zatvoren -> oznaci kao zatvaranje
        def cekaj():
            proc.wait(); AA.AA_PING['zatvara'] = time.time()
        threading.Thread(target=cekaj, daemon=True).start()
    # nadzor: ugasi se kad je prozor zatvoren (i nista ne radi u pozadini)
    while True:
        time.sleep(2)
        p = AA.AA_PING; now = time.time()
        if ui.JOB.get('aktivan'): continue
        if p['t'] == 0.0:
            if now - start > 180: break                      # prozor se nikad nije javio
        elif p['zatvara'] > p['t'] and now - p['zatvara'] > 8: break
        elif now - p['t'] > 150: break                       # nema otkucaja (prozor ugasen ili zamrznut)
    return 0

if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--skripta':      # korak posla - bez ikakvog prozora
        if FROZEN:
            sys.path.insert(0, HERE); os.chdir(HERE)
        if sys.stdout is None: sys.stdout = open(os.devnull, 'w', encoding='utf-8')
        if sys.stderr is None: sys.stderr = sys.stdout
        script = os.path.basename(sys.argv[2])
        sys.argv = [script] + sys.argv[3:]
        runpy.run_module(script[:-3] if script.endswith('.py') else script, run_name='__main__', alter_sys=True)
    else:
        if sys.stdout is None or sys.stderr is None:           # zapakirano bez konzole: zapis u datoteku
            try: log = open(os.path.join(HERE, 'launcher.log'), 'a', encoding='utf-8', buffering=1)
            except OSError: log = open(os.devnull, 'w')
            if sys.stdout is None: sys.stdout = log
            if sys.stderr is None: sys.stderr = log
        sys.exit(glavni(sys.argv[1:]))
