import json,sys,numpy as np
from scipy.optimize import linprog
A=["Offensive Awareness","Ball Control","Dribbling","Tight Possession","Low Pass","Lofted Pass","Finishing","Heading","Place Kicking","Curl","Defensive Awareness","Ball Winning","Aggression","GK Awareness","GK Catching","GK Clearing","GK Reflexes","GK Reach","Speed","Acceleration","Kicking Power","Jump","Physical Contact","Balance","Stamina"]
pos=sys.argv[1]; A=A+(sys.argv[2].split(",") if len(sys.argv)>2 else [])
R=[json.loads(l) for l in open('data.jsonl')]; R=[r for r in R if r['pos']==pos]
X=np.array([[float(r[a]) for a in A] for r in R]); y=np.array([r['ovr'] for r in R],float)
n,m=X.shape; Xc=np.c_[X,np.ones(n)]; I=np.eye(n)
# vars w(m+1), s(n)>=0 ; y-0.5-s <= Xw <= y+0.5+s  -> minimize sum s
Aub=np.r_[np.c_[-Xc,-I],np.c_[Xc,-I]]; bub=np.r_[-(y-0.5),y+0.5]
cost=np.r_[np.zeros(m+1),np.ones(n)]
res=linprog(cost,A_ub=Aub,b_ub=bub,bounds=[(None,None)]*(m+1)+[(0,None)]*n,method='highs')
s=res.x[m+1:]
bad=np.where(s>1e-6)[0]; print('outliers',len(bad),'of',n)
for i in bad:
    r=R[i]; print(' ',r['url'].split('/')[-1],r['ovr'],'slack %.3f'%s[i],'style',r['style'],'skills',len(r['skills']),'age',r['age'],'sec',r['sec'],'qpos',r.get('qpos'))
