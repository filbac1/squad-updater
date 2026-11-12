# minimize total slack + small L1 on weights, then report weights *100
import json,sys,numpy as np
from scipy.optimize import linprog
A=["Offensive Awareness","Ball Control","Dribbling","Tight Possession","Low Pass","Lofted Pass","Finishing","Heading","Place Kicking","Curl","Defensive Awareness","Ball Winning","Aggression","GK Awareness","GK Catching","GK Clearing","GK Reflexes","GK Reach","Speed","Acceleration","Kicking Power","Jump","Physical Contact","Balance","Stamina"]
pos=sys.argv[1]; lam=float(sys.argv[2]) if len(sys.argv)>2 else 0.5
R=[json.loads(l) for l in open('data.jsonl')]; R=[r for r in R if r['pos']==pos]
X=np.array([[float(r[a]) for a in A] for r in R]); y=np.array([r['ovr'] for r in R],float)
keep=X.std(0)>0; A2=[a for a,k in zip(A,keep) if k]; X=X[:,keep]
n,m=X.shape; Xc=np.c_[X,np.ones(n)]; I=np.eye(n)
# w = wp - wn ; vars wp(m) wn(m) c s(n)
Aub=np.r_[np.c_[-X,X,-np.ones(n),-I],np.c_[X,-X,np.ones(n),-I]]; bub=np.r_[-(y-0.5),y+0.5]
cost=np.r_[lam*np.ones(2*m),0,np.ones(n)]
res=linprog(cost,A_ub=Aub,b_ub=bub,bounds=[(0,None)]*(2*m)+[(None,None)]+[(0,None)]*n,method='highs')
w=res.x[:m]-res.x[m:2*m]; c=res.x[2*m]; s=res.x[2*m+1:]
print(pos,n,'violations',(s>1e-6).sum(),'sum slack %.3f'%s.sum(),'c %.3f'%c,'sumw %.4f'%w.sum())
for a,v in sorted(zip(A2,w),key=lambda t:-abs(t[1])):
    if abs(v)>1e-4: print('  %-22s %.4f'%(a,v))
