import json,sys,itertools,numpy as np
pos=sys.argv[1]; S=sys.argv[2].split(','); rng=range(1,int(sys.argv[3])+1)
R=[json.loads(l) for l in open('data.jsonl')]; R=[r for r in R if r['pos']==pos]
X=np.array([[r[a] for a in S] for r in R],float); y=np.array([r['ovr'] for r in R],float)
best=[]
for w in itertools.product(rng,repeat=len(S)):
    if np.gcd.reduce(w)!=1: continue
    s=X@np.array(w)/sum(w)
    A=np.c_[s,np.ones_like(s)]; c,*_=np.linalg.lstsq(A,y,rcond=None)
    e=np.sqrt(((A@c-y)**2).mean()); best.append((e,w,c))
best.sort(key=lambda t:t[0])
for e,w,c in best[:15]: print('%.4f'%e,w,np.round(c,4))
