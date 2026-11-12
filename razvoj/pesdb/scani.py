import numpy as np
f=open(r'E:/SPFL27/SP Football Life 2027/FL_2027.exe','rb')
SEC=(('.rdata',0x252de00,0xe6bc00,0x252f000),('.data',0x3399a00,0x334800,0x339b000),('.data1',0x38a8200,0x72a00,0x3ca1000))
for name,off,size,va in SEC:
    f.seek(off); b=f.read(size)
    for dt,w in (('<u4',4),('<u2',2)):
      for al in range(0,4,w if w<4 else 4):
        a=np.frombuffer(b[al:al+((len(b)-al)//w)*w],dtype=dt).astype(np.int64)
        ok=a<=100
        i=0;n=len(a)
        d=np.diff(np.r_[0,ok.astype(np.int8),0]); st=np.where(d==1)[0]; en=np.where(d==-1)[0]
        for s,e in zip(st,en):
            L=e-s
            if 250<=L<=2000:
                seg=a[s:e]; nz=(seg>0).mean(); u=len(set(seg.tolist()))
                if nz>0.4 and u>=6 and (seg>=5).mean()>0.25 and np.diff(seg).std()>3:
                    print(name,dt,'va %x'%(0x140000000+va+al+s*w),'len',L,'nz %.2f'%nz,'u',u,seg[:40].tolist())
