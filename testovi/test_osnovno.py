# -*- coding: utf-8 -*-
"""Brzi testovi bez mreze; pokrece ih napravi_exe.bat prije pakiranja:  python -m unittest discover -s testovi -v"""
import os, sys, json, time, tempfile, unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


class Ozljede(unittest.TestCase):
    def setUp(self):
        import ozljede as OZ
        self.OZ = OZ
        self.now = time.mktime((2026, 11, 12, 12, 0, 0, 0, 0, -1))

    def test_novi_igrac_zastario(self):
        self.assertTrue(self.OZ.zastarjelo(1, {}, {}, self.now))

    def test_svjez_otporan(self):
        t = self.now - 60 * 86400
        self.assertFalse(self.OZ.zastarjelo(1, {'1': 3.0}, {'1': t}, self.now))       # otporan: 120 dana

    def test_sklon_brze_zastari(self):
        t = self.now - 40 * 86400
        self.assertTrue(self.OZ.zastarjelo(1, {'1': 50.0}, {'1': t}, self.now))       # sklon: 30 dana

    def test_nova_sezona(self):
        t = time.mktime((2026, 6, 20, 0, 0, 0, 0, 0, -1))                             # prije 1.7.
        self.assertTrue(self.OZ.zastarjelo(1, {'1': 0.0}, {'1': t}, self.now))

    def test_ocjena(self):
        self.assertEqual([self.OZ.ocjena(d) for d in (0, 10, 11, 45, 46)], [3, 3, 2, 2, 1])


class Jezik(unittest.TestCase):
    def test_pravila_bez_kontrolnih_znakova(self):
        import lang as LG
        for rx, rep in LG.RULES:
            if isinstance(rep, str): self.assertFalse(any(ord(c) < 32 for c in rep), rep)

    def test_prijevod(self):
        import lang as LG
        st = LG.jezik; LG.jezik = lambda: 'en'
        try:
            self.assertEqual(LG.tr('Igraca: 5, vec skinuto: 3, sada: 2'), 'Players: 5, already downloaded: 3, now: 2')
            self.assertEqual(LG.tr('   osvjezavam 4 starijih zapisa (nova sezona / starije od 30-120 dana)'),
                             '   refreshing 4 older records (new season / older than 30-120 days)')
        finally:
            LG.jezik = st


class Napredak(unittest.TestCase):
    def test_eta(self):
        import ui
        ui.JOB['rezultat'] = {}; T = {}
        ui._napredak(10, 110, T); T['t0'] -= 10                     # 10 s za prvih 0 -> 10
        ui._napredak(20, 110, T)
        self.assertEqual(ui.JOB['rezultat']['napredak'], [20, 110])
        self.assertAlmostEqual(ui.JOB['rezultat']['eta'], 90, delta=3)

    def test_dogadaj_samo_u_aplikaciji(self):
        import napredak as N
        self.assertEqual(N.UKLJUCENO, os.environ.get('SU_DOGADAJI') == '1')


class Izvjestaji(unittest.TestCase):
    def test_zadrzavanje(self):
        import app_api as A
        with tempfile.TemporaryDirectory() as d:
            for i in range(15):
                open(os.path.join(d, 'ocjene_SVE_2026-11-%02d_120000.xlsx' % (i + 1)), 'w').close()
            open(os.path.join(d, 'reprezentacije_zadnje.json'), 'w').close()
            r = A.ocisti_izvjestaje(zadrzi=10, mapa=d)
            ost = sorted(os.listdir(d))
            self.assertEqual(r['obrisano'], 5)
            self.assertIn('reprezentacije_zadnje.json', ost)
            self.assertIn('ocjene_SVE_2026-11-15_120000.xlsx', ost)
            self.assertNotIn('ocjene_SVE_2026-11-05_120000.xlsx', ost)


class Paket(unittest.TestCase):
    def test_spec_sadrzi_module_i_podatke(self):
        s = open(os.path.join(HERE, 'SquadUpdater.spec'), encoding='utf-8').read()
        for m in ('mreza', 'napredak'):
            self.assertIn("'%s'" % m, s)
        for f in ('cache/ozljede.json', 'cache/ozljede_t.json', 'cache/tm_nat_ids.json'):
            self.assertIn(f, s); self.assertTrue(os.path.exists(os.path.join(HERE, f)), f)


if __name__ == '__main__':
    unittest.main()
