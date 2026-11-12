# -*- coding: utf-8 -*-
"""
TOCNA PES20/21 overall formula (iz Ejogc327 PES2020 Editora, isti izracun kao stupac OverallStats).
Atributi u PES redoslijedu (fl27db.ANAMES, 25 komada, stvarne vrijednosti 40-99),
weak_foot_acc 1-4, pos = indeks registrirane pozicije (0 GK ... 12 CF).
Provjereno: 99.96 % tocno na editorovom CSV-u.
"""
TAB = [31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 56, 59, 62, 65, 67, 70, 73, 75,
       77, 79, 82, 83, 85, 87, 89, 90, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113]
W = [[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, .11, .11, 0, 0, 0, 0, 0],
     [0, 0, 0, 0, 0, 0, 0, .22, 0, 0, .1, 0, 0, .19, .19, 0, .09, .25, .17, .08],
     [.06, .09, .09, .05, 0, .14, 0, 0, 0, 0, .16, .14, 0, .11, .08, .04, .14, .14, .08, .05],
     [.06, .09, .09, .05, 0, .14, 0, 0, 0, 0, .16, .14, 0, .11, .08, .04, .14, .14, .08, .05],
     [.07, .18, .1, .05, .18, .19, 0, 0, 0, .12, .03, .03, 0, .05, .09, .04, .14, .07, .03, .01],
     [.05, .23, .16, .08, .23, .21, 0, 0, 0, 0, .04, .06, 0, 0, .03, .02, .17, .03, 0, 0],
     [.07, .15, .17, .08, .07, .12, 0, 0, 0, .04, .24, .21, 0, 0, 0, 0, .13, 0, 0, 0],
     [.07, .15, .17, .08, .07, .12, 0, 0, 0, .04, .24, .21, 0, 0, 0, 0, .13, 0, 0, 0],
     [.14, .23, .17, .07, .21, .14, .17, 0, 0, 0, .05, .07, 0, 0, .02, .03, .03, 0, 0, 0],
     [.17, .19, .15, .07, .05, .09, .11, 0, 0, 0, .15, .15, .05, 0, .02, .04, .06, 0, 0, 0],
     [.17, .19, .15, .07, .05, .09, .11, 0, 0, 0, .15, .15, .05, 0, .02, .04, .06, 0, 0, 0],
     [.15, .19, .13, .06, .09, .09, .14, 0, 0, 0, .09, .21, .06, 0, .02, .05, .04, 0, 0, 0],
     [.31, .23, .09, .05, 0, 0, .36, .03, 0, 0, .05, .05, .03, .03, .08, .02, 0, 0, 0, 0]]
GKW = (.5, .48)
WF = [0, .23, .56, .56, .23, .23, .56, .56, .37, .47, .47, .37, .38]
BONUS = [[0, 3, 5, 8], [0, 2, 4, 8], [0, 2, 4, 9], [0, 2, 4, 9], [0, 3, 5, 9], [0, 3, 5, 8], [0, 3, 5, 8],
         [0, 3, 5, 8], [0, 3, 5, 8], [0, 2, 4, 10], [0, 2, 4, 10], [0, 3, 5, 9], [0, 3, 5, 8]]

def overall(attrs, weak_foot_acc, pos, reg_pos=None, pos_rating=2):
    """attrs = lista 25 vrijednosti (PES redoslijed). Ako pos != reg_pos, racuna ocjenu na sporednoj poziciji
    s pos_rating (0=C, 1=B, 2=A)."""
    a = [int(x) for x in attrs]; g = a[20:25]
    if reg_pos is None: reg_pos = pos
    num = 0.0
    if pos == 0:
        num += ((g[0] + g[4]) // 2 - 25) * GKW[0] + ((g[1] + g[2] + g[3]) // 3 - 25) * GKW[1]
    num2 = float((g[0] + g[4]) // 2 + (g[1] + g[2] + g[3]) // 3)
    for i in range(20):
        num += (a[i] - 25) * W[pos][i]; num2 += a[i]
    num += (int(weak_foot_acc) - 1) * WF[pos] + 0.5
    if reg_pos != pos:
        return max(40, int(num) + BONUS[pos][pos_rating])
    n3 = int(num) + BONUS[pos][3]
    if pos == 0: return n3
    n4 = max(40, int(num2 / 22.0 + 0.5))
    return int(n3 * 0.6 + TAB[min(n4, 99) - 40] * 0.4 + 0.5)

def overall_raw(attrs, weak_foot_acc, pos):
    """Neokrugljena (glatka) verzija za trazenje skaliranja."""
    a = [float(x) for x in attrs]; g = a[20:25]
    num = 0.0
    if pos == 0:
        num += ((g[0] + g[4]) / 2 - 25) * GKW[0] + ((g[1] + g[2] + g[3]) / 3 - 25) * GKW[1]
    num2 = (g[0] + g[4]) / 2 + (g[1] + g[2] + g[3]) / 3
    for i in range(20):
        num += (a[i] - 25) * W[pos][i]; num2 += a[i]
    num += (weak_foot_acc - 1) * WF[pos] + BONUS[pos][3]
    if pos == 0: return num
    n4 = max(40.0, min(99.0, num2 / 22.0)); lo = int(n4); fr = n4 - lo
    t = TAB[lo - 40] + (TAB[min(lo + 1, 99) - 40] - TAB[lo - 40]) * fr
    return num * 0.6 + t * 0.4

def overall_vec(A, weak_foot_acc, pos):
    """Vektorska verzija overall(): A = numpy matrica (n x 25) cijelih brojeva, isti rezultat kao overall()."""
    import numpy as np
    A = np.asarray(A, dtype=np.int64); g = A[:, 20:25]
    gk1 = (g[:, 0] + g[:, 4]) // 2; gk2 = (g[:, 1] + g[:, 2] + g[:, 3]) // 3
    num = np.zeros(len(A))
    if pos == 0:                                   # isti redoslijed zbrajanja kao editor (float!)
        num = num + ((gk1 - 25) * GKW[0] + (gk2 - 25) * GKW[1])
    for i in range(20):
        num = num + (A[:, i] - 25) * W[pos][i]
    num2 = gk1 + gk2 + A[:, :20].sum(1)
    num = num + (int(weak_foot_acc) - 1) * WF[pos]
    num = num + 0.5
    n3 = np.floor(num).astype(np.int64) + BONUS[pos][3]
    if pos == 0: return n3
    n4 = np.clip(np.floor(num2 / 22.0 + 0.5).astype(np.int64), 40, 99)
    tab = np.array(TAB)[n4 - 40]
    return np.floor(n3 * 0.6 + tab * 0.4 + 0.5).astype(np.int64)
