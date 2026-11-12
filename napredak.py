# -*- coding: utf-8 -*-
"""
Strukturirani dogadaji za aplikaciju: skripta ispise redak  @@{"n": [i, n]}  koji ui._reader procita kao JSON
(ne ulazi u zapis rada i ne ovisi o tekstu poruke ni o prijevodu).
Ispisuje se samo kad skriptu pokrece aplikacija (SU_DOGADAJI=1); rucno pokretanje u konzoli ostaje cisto.

    import napredak as N
    N.javi(i, ukupno)            # napredak koraka (traka + preostalo vrijeme)
    N.rezultat(xlsx='a.xlsx')    # datoteke koje je korak napravio
"""
import os, sys, json

UKLJUCENO = os.environ.get('SU_DOGADAJI') == '1'
PREFIKS = '@@'

def _posalji(d):
    if UKLJUCENO:
        sys.stdout.write(PREFIKS + json.dumps(d, ensure_ascii=False) + '\n'); sys.stdout.flush()

def javi(i, n):
    _posalji({'n': [int(i), int(n)]})

def rezultat(**kw):
    _posalji({'rez': kw})
