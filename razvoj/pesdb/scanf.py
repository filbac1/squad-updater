import numpy as np
f=open(r'E:/SPFL27/SP Football Life 2027/FL_2027.exe','rb')
for name,off,size in (('.rdata',0x252de00,0xe6bc00),('.data',0x3399a00,0x334800),('.data1',0x38a8200,0x72a00)):
    f.seek(off); b=f.read(size)
    for al in range(4):
        a=np.frombuffer(b[al:al+((len(b)-al)//4)*4],dtype='<f4')
        ok=np.isfinite(a)&(a>=0)&(a<=3)&((a==0)|(a>=0.001))
        nice=ok&(np.abs(a*100-np.round(a*100))<1e-3)
        # runs of ok with many nonzero nice values
        i=0;n=len(a)
        while i<n:
            if not ok[i]: i+=1; continue
            j=i
            while j<n and ok[j]: j+=1
            L=j-i
            if L>=150:
                seg=a[i:j]; nz=(seg>0).sum(); nn=nice[i:j].sum()
                if nz>=60 and nn>=0.9*L:
                    print(name,'al',al,'va %x'%(0x140000000+{'.rdata':0x252f000,'.data':0x339b000,'.data1':0x3ca1000}[name]+al+i*4),'len',L,'nz',nz,'sample',np.round(seg[:30],3).tolist())
            i=j
