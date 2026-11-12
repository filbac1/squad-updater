import json,sys,numpy as np
pos=sys.argv[1]; S=sys.argv[2].split(',')
R=[json.loads(l) for l in open('data.jsonl')]; R=[r for r in R if r['pos']==pos]
X=np.array([[r[a] for a in S] for r in R],float); y=np.array([r['ovr'] for r in R],float)
def rm(M):
    Mc=np.c_[M,np.ones(len(M))]; w,*_=np.linalg.lstsq(Mc,y,rcond=None); return np.sqrt(((Mc@w-y)**2).mean()),w
print('lin',rm(X)[0])
res=[]
for T in range(40,100,2):
    for k in (-0.5,-0.3,-0.2,-0.1,0.1,0.2,0.3,0.5,1,2):
        res.append((rm(X+k*np.maximum(X-T,0))[0],T,k))
res.sort(); print(res[:8])
for p in (0.5,0.8,1.2,1.5,2,3):
    print('pow',p,rm(X**p)[0])
