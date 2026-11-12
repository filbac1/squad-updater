# -*- coding: utf-8 -*-
"""
OSVJEZAVANJE PODATAKA O OCJENAMA (formula TM -> overall):  ea27.py (EA ocjene) -> --lige -> --ucenje.

    python osvjezi_podatke.py --lige [--sve]   -> skine TM sastave liga koje formula koristi (starije od 7 dana; --sve = sve)
    python osvjezi_podatke.py --ucenje         -> nauci formulu iz cache\\ea_fc27.json i TM sastava (stara se sprema kao .bak)

Datum ocjena (KAL_DATUM) = danas (SU_KAL_DATUM) - EA ocjene se tijekom sezone mijenjaju, pa se uci na vrijednostima iz tog dana.
"""
import os, sys, json, time, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

def kodovi():
    import model_ea27 as ME, ocjene as OC
    try: lige = list(ME.load()['info']['lige'])
    except Exception: lige = []
    return sorted(set(lige) | set(OC.TM_KOD.values()))

def lige(sve=False):
    import ocjene as OC
    if sve: OC.OPT['osvjezi'] = True
    codes = kodovi()
    print('Transfermarkt leagues to check: %d' % len(codes), flush=True)
    for i, c in enumerate(codes, 1):
        try:
            d = OC.tm_fetch(c)
            print('[%d/%d] League %s (%s): %d players' % (i, len(codes), c, d.get('league'), len(d.get('players', []))), flush=True)
        except BaseException as e:                       # SystemExit iz TM sloja - jedna liga ne smije srusiti sve
            print('[%d/%d] League %s skipped: %s' % (i, len(codes), c, e), flush=True)

def ucenje():
    import model_ea27 as ME
    if os.path.isfile(ME.FILE): shutil.copyfile(ME.FILE, ME.FILE + '.bak')
    m, info = ME.train()
    print('Model nauceni na %d igraca (%d liga; %d s vrijednoscu na %s). Prosjecna greska %.2f, unutar +-3: %.0f %%, nagib vrha %.2f'
          % (info['n'], len(info['lige']), info['n_povijest'], info['kal_datum'], info['greska'], 100 * info['unutar3'], info['top_nagib']), flush=True)
    if info['n'] < 3000 or info['greska'] > 3.0:
        if os.path.isfile(ME.FILE + '.bak'): shutil.copyfile(ME.FILE + '.bak', ME.FILE)
        raise SystemExit('The new formula looks wrong (%d players, error %.2f) - the previous formula was restored.' % (info['n'], info['greska']))

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--lige' in sys.argv: lige('--sve' in sys.argv)
    elif '--ucenje' in sys.argv: ucenje()
    else: print(__doc__)
