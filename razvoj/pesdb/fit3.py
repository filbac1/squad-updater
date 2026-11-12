import json,sys,numpy as np
A=["Offensive Awareness","Ball Control","Dribbling","Tight Possession","Low Pass","Lofted Pass","Finishing","Heading","Place Kicking","Curl","Defensive Awareness","Ball Winning","Aggression","Speed","Acceleration","Kicking Power","Jump","Physical Contact","Balance","Stamina"]
pos=sys.argv[1]
R=[json.loads(l) for l in open('data.jsonl')]; R=[r for r in R if r['pos']==pos]
X=np.array([[r[a] for a in A] for r in R],float); y=np.array([r['ovr'] for r in R],float)
Xc=np.c_[X,np.ones(len(X))]; w,*_=np.linalg.lstsq(Xc,y,rcond=None); p=Xc@w; res=y-p
print(len(R),'rmse',np.sqrt((res**2).mean()))
feats={'nskills':[len(r['skills']) for r in R],'nsec':[len(r['sec']) for r in R],'height':[r['height'] for r in R],'weight':[r['weight'] for r in R],'age':[r['age'] for r in R],'form':[r['Form'] for r in R],'inj':[r['Injury Resistance'] for r in R],'wfu':[r['Weak Foot Usage'] for r in R],'wfa':[r['Weak Foot Accuracy'] for r in R],'pred':list(p),'maxattr':list(X.max(1))}
for k,v in feats.items(): print('%-8s corr %.3f'%(k,np.corrcoef(np.array(v,float),res)[0,1]))
import collections
st=collections.defaultdict(list)
for r,e in zip(R,res): st[r['style']].append(e)
for k,v in st.items(): print(k,len(v),round(np.mean(v),2))
sk=collections.defaultdict(list)
for r,e in zip(R,res):
    for s in r['skills']: sk[s].append(e)
for k,v in sorted(sk.items(),key=lambda t:-abs(np.mean(t[1]))):
    if len(v)>=5: print('  skill',k,len(v),round(np.mean(v),2))
