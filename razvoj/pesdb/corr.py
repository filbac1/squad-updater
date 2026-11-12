import json,struct,numpy as np
A=["Offensive Awareness","Ball Control","Dribbling","Tight Possession","Low Pass","Lofted Pass","Finishing","Heading","Place Kicking","Curl","Defensive Awareness","Ball Winning","Aggression","GK Awareness","GK Catching","GK Clearing","GK Reflexes","GK Reach","Speed","Acceleration","Kicking Power","Jump","Physical Contact","Balance","Stamina","Weak Foot Usage","Weak Foot Accuracy","Form","Injury Resistance","height","weight","age"]
d=open('../db/Player.bin.dec','rb').read()
P={struct.unpack_from('<I',d,i*312+8)[0]:d[i*312:(i+1)*312] for i in range(len(d)//312)}
R=[json.loads(l) for l in open('data.jsonl')]
M=[(r,int.from_bytes(P[int(r['url'].rsplit('-',1)[1])][:68],'little')) for r in R if int(r['url'].rsplit('-',1)[1]) in P]
print(len(M))
for a in A:
    v=np.array([r[a] for r,_ in M],float)
    best=[]
    for w in (2,3,4,5,6,7,8):
        for b in range(0,544-w+1):
            f=np.array([(x>>b)&((1<<w)-1) for _,x in M],float)
            if f.std()==0: continue
            c=np.corrcoef(f,v)[0,1]
            mad=np.abs(v-f).mean()
            best.append((c,b,w,round(mad,1)))
    best.sort(reverse=True)
    print('%-20s'%a,best[:2])
