import json,sys,numpy as np
pos=sys.argv[1]; S=sys.argv[2].split(',')
R=[json.loads(l) for l in open('data.jsonl')]
R=[r for r in R if r['pos']==pos]
X=np.array([[r[a] for a in S] for r in R],float); y=np.array([r['ovr'] for r in R],float)
Xc=np.c_[X,np.ones(len(X))]
w,*_=np.linalg.lstsq(Xc,y,rcond=None); p=Xc@w
print(len(R),'rmse',np.sqrt(((p-y)**2).mean()),'sumw',w[:-1].sum())
for a,v in zip(S+['c'],w): print('%-22s %.5f  rel %.3f'%(a,v,v/w[0]))
r=y-p
for k in ('age','height','weight','Form','Injury Resistance','Weak Foot Usage','Weak Foot Accuracy'):
    v=np.array([q[k] for q in R],float); print(k,'corr resid %.3f'%np.corrcoef(v,r)[0,1])
idx=np.argsort(-abs(r))[:8]
for i in idx: print(R[i]['url'].split('/')[-1],y[i],round(p[i],2))
