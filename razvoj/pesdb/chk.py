import json,struct
d=open('../db/Player.bin.dec','rb').read()
P={struct.unpack_from('<I',d,i*312+8)[0]:d[i*312:(i+1)*312] for i in range(len(d)//312)}
R=[json.loads(l) for l in open('data.jsonl')]
n=0
for r in R:
    pid=int(r['url'].rsplit('-',1)[1])
    if pid in P:
        p=P[pid]; x=int.from_bytes(p,'little')
        print(r['url'].split('/')[-1], 'atk',r['Offensive Awareness'],'bc',r['Ball Control'],'spd',r['Speed'],'h',r['height'],'age',r['age'])
        print('  name',p[68:90]); print('  hex', p[:68].hex(' '))
        print('  f112..',[(x>>b)&127 for b in (112,119,128,135,142,149,160,167,174,181)])
        n+=1
        if n>3: break
print(len(d)/312)
