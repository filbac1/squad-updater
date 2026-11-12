# -*- coding: utf-8 -*-
"""
DODATNI PODACI IZ EA FC 27 (uz ocjene i atribute): jaca noga, slabija noga, sporedne pozicije, vjestine.

Pravila su izvedena iz 11.165 igraca koji su i u bazi i u EA (vidi razvoj/):
  jaca noga     - EA (1 = desna, 2 = lijeva) je pouzdana -> ispravlja se kad se ne slaze (~400 igraca)
  slabija noga  - PES ljestvica 1-4 (vecina 2), EA 1-5 zvjezdica: ispravljaju se samo ocite razlike
                  (EA 5 -> barem 3/3; EA 4 -> barem 3; EA 1-2 -> najvise 2). Slabija noga ulazi u overall!
  pozicije      - EA glavna pozicija -> barem A; EA sporedna pozicija s ocjenom C -> B. Registrirana se ne dira.
  vjestine      - EA PlayStyles -> PES vjestine (tablica dolje, provjerena "liftom" na parovima);
                  samo se DODAJU, postojece ostaju; najvise 10 vjestina + 5 COM stilova po igracu
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fl27db as D

POZ = {'ST': 'CF', 'CF': 'SS', 'LW': 'LWF', 'RW': 'RWF', 'CAM': 'AMF', 'CM': 'CMF', 'CDM': 'DMF', 'LM': 'LMF',
       'RM': 'RMF', 'LB': 'LB', 'LWB': 'LB', 'RB': 'RB', 'RWB': 'RB', 'CB': 'CB', 'GK': 'GK'}

# EA PlayStyle -> PES vjestina(e) (naziv stupca u CSV-u editora)
PS = {'Aerial Fortress': ['HeadingSpecial'], 'Aerial': ['HeadingSpecial'], 'Precision Header': ['HeadingSpecial'],
      'Technical': ['DoubleTouch'], 'Trickster': ['FlipFlap'], 'Inventive': ['MarseilleTurn'],
      'Long Ball Pass': ['LongBallExpert'], 'Rapid': ['SpeedingBullet'], 'Intercept': ['Interception'],
      'Whipped Pass': ['PinpointCrossing', 'EarlyCross'], 'Incisive Pass': ['ThroughPassing'], 'Tiki Taka': ['OneTouchPass'],
      'Pinged Pass': ['WeightedPass'], 'Jockey': ['ManMarking'], 'Slide Tackle': ['AcrobaticClear'], 'Block': ['AcrobaticClear'],
      'Long Throw': ['LongThrow'], 'Far Throw': ['GKLongThrow'], 'Dead Ball': ['KnuckleShot'], 'Power Shot': ['LongRangeShot'],
      'Enforcer': ['FirstTimeShot'], 'Acrobatic': ['AcrobaticFinishing'], 'Chip Shot': ['Chipshotcontrol'],
      'Gamechanger': ['OutsideCurler'], 'Trivela': ['OutsideCurler'], 'Press Proven': ['TrackBack'], 'Relentless': ['FightingSpirit']}
COM = {'Trickster', 'MazingRun', 'SpeedingBullet', 'IncisiveRun', 'LongBallExpert', 'EarlyCross', 'LongRanger'}
COL = {n: c for c, (b, s, n) in D.SKILLS.items()}
MAX_SKILLS, MAX_COM = 10, 5

def promjene(p, e):
    """p = igrac iz baze (fl27db/izvor), e = EA zapis. -> (changes dict, opisi promjena)."""
    ch, op = {}, []
    if not e: return ch, op
    # jaca noga
    if e.get('foot') in (1, 2) and p.get('foot') is not None:
        want = 1 if e['foot'] == 2 else 0
        if want != p['foot']:
            ch['_foot'] = want; op.append('jaca noga %s → %s' % ('lijeva' if p['foot'] else 'desna', 'lijeva' if want else 'desna'))
    # slabija noga
    wf, wfu, wfa = e.get('wf'), p.get('wfu'), p['attr'].get('_wfa')
    if wf and wfu and wfa:
        nu, na = wfu, wfa
        if wf == 5: nu, na = max(wfu, 3), max(wfa, 3)
        elif wf == 4: nu, na = max(wfu, 2), max(wfa, 3)
        elif wf <= 2: nu, na = min(wfu, 2), min(wfa, 2)
        if nu != wfu: ch['_wfu'] = nu
        if na != wfa: ch['_wfa'] = na
        if nu != wfu or na != wfa: op.append('slabija noga %d/%d → %d/%d (EA %d★)' % (wfu, wfa, nu, na, wf))
    # pozicije
    pr = p.get('pos_rating') or []
    if pr:
        main = POZ.get(e.get('pos')); alts = {POZ.get(a) for a in e.get('alt') or []} - {None}
        for i, ps in enumerate(D.POS):
            if ps == p['pos']: continue
            new = pr[i]
            if ps == main: new = 2
            elif ps in alts and pr[i] == 0: new = 1
            if new != pr[i]:
                ch['_pos%d' % i] = new; op.append('%s %s → %s' % (ps, 'CBA'[pr[i]], 'CBA'[new]))
    # vjestine (samo dodavanje)
    have = set(p.get('skills') or ())
    n_sk = sum(1 for c in have if D.SKILLS[c][2] not in COM); n_com = sum(1 for c in have if D.SKILLS[c][2] in COM)
    gk = p['pos'] == 'GK'
    add = []
    for lab, typ in e.get('ps') or []:
        for sk in PS.get((lab or '').rstrip('+'), []):
            c = COL.get(sk)
            if c is None or c in have or c in add: continue
            if gk != sk.startswith('GK'): continue
            if sk in COM:
                if n_com >= MAX_COM: continue
                n_com += 1
            else:
                if n_sk >= MAX_SKILLS: continue
                n_sk += 1
            add.append(c)
    for c in add:
        ch['_sk%d' % c] = 1
    if add: op.append('vjestine +' + ', '.join(D.SKILLS[c][2] for c in add))
    return ch, op
