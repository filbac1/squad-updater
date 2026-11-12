import json,sys,numpy as np
from scipy.optimize import linprog
A=["Offensive Awareness","Ball Control","Dribbling","Tight Possession","Low Pass","Lofted Pass","Finishing","Heading","Place Kicking","Curl","Defensive Awareness","Ball Winning","Aggression","GK Awareness","GK Catching","GK Clearing","GK Reflexes","GK Reach","Speed","Acceleration","Kicking Power","Jump","Physical Contact","Balance","Stamina"]
pos=sys.argv[1]; mode=sys.argv[2] if len(sys.argv)>2 else 'round'
extra=sys.argv[3].split(',') if len(sys.argv)>3 else []
R=[json.loads(l) for l in open('data.jsonl')]; R=[r for r in R if r['pos']==pos]
F=A+extra
X=np.array([[float(r[a]) for a in F] for r in R]); y=np.array([r['ovr'] for r in R],float)
n,m=X.shape
lo,hi=(y-0.5,y+0.5) if mode=='round' else (y,y+1)
# vars: w(m), c, t ; maximize t
Xc=np.c_[X,np.ones(n)]
Aub=np.r_[np.c_[-Xc,np.ones(n)], np.c_[Xc,np.ones(n)]]
bub=np.r_[-lo,hi]
cost=np.zeros(m+2); cost[-1]=-1
res=linprog(cost,A_ub=Aub,b_ub=bub,bounds=[(None,None)]*(m+1)+[(None,0.5)],method='highs')
print(pos,mode,n,'margin t=',res.x[-1])
w=res.x
for a,v in sorted(zip(F+['c'],w[:-1]),key=lambda t:-abs(t[1])):
    if abs(v)>1e-3: print('  %-22s %.5f'%(a,v))
