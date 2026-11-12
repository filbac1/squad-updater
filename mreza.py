# -*- coding: utf-8 -*-
"""
Zajednicki HTTP GET s ponovnim koristenjem veza (keep-alive): svaka nit ima svoju requests.Session,
pa se TCP/TLS veza prema Transfermarktu ne otvara iznova za svaki zahtjev.
Greske se dizu kao urllib.error.HTTPError (isti oblik kao prije), da pozivatelji ne trebaju mijenjati obradu.
Ako requests nije instaliran, radi preko urllib-a kao prije.
"""
import io, threading, urllib.request, urllib.error

try:
    import requests
    from requests.adapters import HTTPAdapter
except ImportError:                      # pragma: no cover
    requests = None

_tl = threading.local()

def _sesija():
    s = getattr(_tl, 's', None)
    if s is None:
        s = requests.Session()
        a = HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
        s.mount('https://', a); s.mount('http://', a)
        _tl.s = s
    return s

def dohvati(url, headers=None, timeout=30):
    """GET -> bytes. Status >= 400 -> urllib.error.HTTPError (e.code); mrezne greske -> iznimka kao i prije."""
    if requests is None:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=timeout) as r:
            return r.read()
    r = _sesija().get(url, headers=headers or {}, timeout=timeout)
    if r.status_code >= 400:
        raise urllib.error.HTTPError(url, r.status_code, r.reason or '', r.headers, io.BytesIO(b''))
    return r.content
