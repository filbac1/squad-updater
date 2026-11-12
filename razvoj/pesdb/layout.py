import json,struct,numpy as np
A=["Offensive Awareness","Ball Control","Dribbling","Tight Possession","Low Pass","Lofted Pass","Finishing","Heading","Place Kicking","Curl","Defensive Awareness","Ball Winning","Aggression","GK Awareness","GK Catching","GK Clearing","GK Reflexes","GK Reach","Speed","Acceleration","Kicking Power","Jump","Physical Contact","Balance","Stamina","Weak Foot Usage","Weak Foot Accuracy","Form","Injury Resistance","height","weight","age"]
d=open('../db/Player.bin.dec','rb').read()
P={}
for i in range(len(d)//312):
    r=d[i*312:(i+1)*312]; P[struct.unpack_from('<I',r,8)[0]]=r
R=[json.loads(l) for l in open('data.jsonl')]
M=[(r,P[int(r['url'].rsplit('-',1)[1])]) for r in R if int(r['url'].rsplit('-',1)[1]) in P]
print('matched',len(M),'of',len(R))
bits=[int.from_bytes(p[:68],'little') for _,p in M]
for a in A:
    v=np.array([r[a] for r,_ in M])
    best=None
    for w in (2,3,4,5,6,7,8,9):
        for b in range(0,544-w):
            f=np.array([(x>>b)&((1<<w)-1) for x in bits])
            for off in (0,):
                ex=(f==v).mean()
                if ex>0.5 and (best is None or ex>best[0]): best=(ex,b,w,'eq')
            dd=v-f
            if len(set(dd))==1 and best is None: best=(1,b,w,'off%d'%dd[0])
    print('%-22s'%a,best)
