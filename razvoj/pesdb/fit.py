import json,sys,numpy as np
A=["Offensive Awareness","Ball Control","Dribbling","Tight Possession","Low Pass","Lofted Pass","Finishing","Heading","Place Kicking","Curl","Defensive Awareness","Ball Winning","Aggression","GK Awareness","GK Catching","GK Clearing","GK Reflexes","GK Reach","Speed","Acceleration","Kicking Power","Jump","Physical Contact","Balance","Stamina"]
pos=sys.argv[1]
R=[json.loads(l) for l in open('data.jsonl')]
R=[r for r in R if r['pos']==pos]
X=np.array([[r[a] for a in A] for r in R],float); y=np.array([r['ovr'] for r in R],float)
print(len(R))
Xc=np.c_[X,np.ones(len(X))]
w,res,*_=np.linalg.lstsq(Xc,y,rcond=None)
p=Xc@w; print('rmse',np.sqrt(((p-y)**2).mean()))
for a,v in sorted(zip(A+['c'],w),key=lambda t:-abs(t[1])): print('%-22s %.4f'%(a,v))
