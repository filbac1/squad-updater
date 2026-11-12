import json,sys,numpy as np
S="GK Awareness,GK Reach,GK Reflexes,GK Clearing,GK Catching,Jump,Physical Contact,Ball Control".split(',')
R=[json.loads(l) for l in open('data.jsonl')]; R=[r for r in R if r['pos']=='GK']
X=np.array([[r[a] for a in S] for r in R],float); y=np.array([r['ovr'] for r in R],float)
Xc=np.c_[X,np.ones(len(X))]; w,*_=np.linalg.lstsq(Xc,y,rcond=None); p=Xc@w
print(np.round(w,4)); print('y range',y.min(),y.max())
for lo in range(40,100,5):
    m=(p>=lo)&(p<lo+5)
    if m.sum(): print(lo,m.sum(),'mean resid %.3f'%(y[m]-p[m]).mean())
# quadratic in p
for d in (2,3):
    c=np.polyfit(p,y,d); q=np.polyval(c,p); print(d,'rmse',np.sqrt(((q-y)**2).mean()))
