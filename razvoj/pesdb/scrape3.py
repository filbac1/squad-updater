import re,html,json,time,os,sys,urllib.request,urllib.parse
OUT=sys.argv[1]; UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
import urllib.error
DELAY=float(os.environ.get('DELAY','2.5'))
def get(url):
    wait=60
    for a in range(12):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=30) as r: return r.read().decode('utf-8','replace')
        except urllib.error.HTTPError as e:
            if e.code==429:
                print('429, cekam',wait,'s',flush=True); time.sleep(wait); wait=min(wait*2,900); continue
            if e.code==404: return ''
            time.sleep(10)
        except Exception as e:
            time.sleep(10)
    return ''
def text(t):
    s=re.sub(r'<script.*?</script>|<style.*?</style>','',t,flags=re.S)
    s=html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','|',s))); return re.sub(r'(\|\s*)+','|',s)
STATS=['Offensive Awareness','Ball Control','Dribbling','Tight Possession','Low Pass','Lofted Pass','Finishing','Heading','Place Kicking','Curl','Defensive Awareness','Ball Winning','Aggression','GK Awareness','GK Catching','GK Clearing','GK Reflexes','GK Reach','Speed','Acceleration','Kicking Power','Jump','Physical Contact','Balance','Stamina','Weak Foot Usage','Weak Foot Accuracy','Form','Injury Resistance']
def parse(t,url):
    s=text(t); d={'url':url}
    for k in STATS:
        m=re.search(r'\|'+re.escape(k)+r'\|(\d+)\|',s); d[k]=int(m.group(1)) if m else None
    for k,pat in (('ovr',r'\|Overall Rating\|(\d+)\|'),('height',r'\|Height\|(\d+)\|'),('weight',r'\|Weight\|(\d+)\|'),('age',r'\|Age\|(\d+)\|'),('pos',r'\|Primary Position\|(\w+)\|'),('style',r'\|Playing Style\|([^|]+)\|'),('foot',r'\|Stronger Foot\|(\w+) foot')):
        m=re.search(pat,s); d[k]=(int(m.group(1)) if m.group(1).isdigit() else m.group(1)) if m else None
    m=re.search(r'\|Secondary Positions\|(.*?)\|Player Details',s); d['sec']=re.findall(r'[A-Z]{2,3}',m.group(1)) if m else []
    m=re.search(r'\|Player Skills\|(.*?)\|(?:COM Playing Styles|Find Similar)',s); d['skills']=[x for x in m.group(1).split('|') if x.strip()] if m else []
    # position familiarity classes in raw html
    d['posclass']=re.findall(r'class="[^"]*\b(pos[-_][a-z0-9_-]+)[^"]*"[^>]*>\s*(?:<[^>]+>\s*)*([A-Z]{2,3})\b',t)[:40]
    return d
done=set()
if os.path.exists(OUT):
    for l in open(OUT,encoding='utf-8'): done.add(json.loads(l)['url'])
f=open(OUT,'a',encoding='utf-8')
POSL=[int(x) for x in sys.argv[2].split(',')] if len(sys.argv)>2 else range(13)
for pos in POSL:
    base='https://pesdb.net/pes2021/players/?pos%5B%5D='+str(pos)
    first=get(base); m=re.search(r'Page 1 of ([\d,]+)',first); n=int(m.group(1).replace(',','')) if m else 1
    pages=sorted(set([1]+[max(1,round(n*q)) for q in (0.08,0.2,0.35,0.5,0.65,0.8,0.95)]))
    ids=[]
    for p in pages:
        t=first if p==1 else get(base+'&page=%d'%p); time.sleep(DELAY)
        for slug in re.findall(r'href="/pes2021/players/([a-z0-9-]+-(\d+))"',t):
            if int(slug[1])<1000000: ids.append(slug[0])
    ids=list(dict.fromkeys(ids))
    print('pos',pos,'pages',n,'ids',len(ids),flush=True)
    for slug in ids:
        url='https://pesdb.net/pes2021/players/'+slug
        if url in done: continue
        t=get(url); time.sleep(DELAY)
        if not t: continue
        d=parse(t,url); d['qpos']=pos
        f.write(json.dumps(d,ensure_ascii=False)+'\n'); f.flush(); done.add(url)
print('DONE',flush=True)
