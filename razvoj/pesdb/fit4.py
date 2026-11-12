import json,sys,numpy as np
A=["Offensive Awareness","Ball Control","Dribbling","Tight Possession","Low Pass","Lofted Pass","Finishing","Heading","Place Kicking","Curl","Defensive Awareness","Ball Winning","Aggression","Speed","Acceleration","Kicking Power","Jump","Physical Contact","Balance","Stamina"]
pos=sys.argv[1]
R=[json.loads(l) for l in open('data.jsonl')]; R=[r for r in R if r['pos']==pos]
X=np.array([[r[a] for a in A] for r in R],float); y=np.array([r['ovr'] for r in R],float)
def ev(M,name):
    Mc=np.c_[M,np.ones(len(M))]; w,*_=np.linalg.lstsq(Mc,y,rcond=None); print('%-30s rmse %.3f'%(name,np.sqrt(((Mc@w-y)**2).mean()))); return w
ev(X,'linear')
ev(X**2,'squares only')
ev(np.c_[X,X**2],'lin+sq')
for T in (60,65,70,75,80,85):
    ev(np.c_[X,np.maximum(X-T,0)],'hinge %d'%T)
age=np.array([r['age'] for r in R],float)
ev(np.c_[X,age,age**2],'lin+age')
