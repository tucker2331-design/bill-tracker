import sys,pickle,collections,re,numpy as np,datetime; sys.path.insert(0,'/Users/tuckerward/Documents/Projects/bill-tracker/tools/calibration')
import committee_votes as CV, first_vote as FV, stats
from corpus import _party_lookup, load
party,person=_party_lookup()
corpus={(r['session'],r['bill']):r for r in load()['bills']}
d=CV.load()
# LIS ballots per roll call
ball=collections.defaultdict(list)
for v in d['votes']:
    if v['session'] in ('2025',) and v['venue'] in ('subcommittee','committee'): ball[v['vote_id']].append((v['name'],v['opt']))
def seq(vid):
    m=re.search(r'V(\d+)$',vid); return int(m.group(1)) if m else None
ev={}
for (s,vid),e in d['events'].items():
    if s=='2025' and e['venue'] in ('subcommittee','committee') and seq(vid) is not None:
        dt=datetime.datetime.strptime(e['date'],'%m/%d/%Y').date().isoformat()
        ev[vid]=(CV.room_code(vid)+('S' if e['venue']=='subcommittee' else ''),dt,seq(vid),e['bill'],e['desc'])
# per roll call: support share of each party RELATIVE to that bill's patron party (direction from desc)
ANTI=re.compile(r'laying on the table|\btabled?\b|indefinitely|strik|continu',re.I)
def sides(vid):
    room,dt,sq,b,desc=ev[vid]; m=re.match(r'([HS]B)(\d+)',b or '')
    if not m: return None
    cb=corpus.get(('2025',f'{m.group(1)} {int(m.group(2))}'))
    if not cb or cb['chief_party'] not in FV.PARTIES: return None
    anti=bool(ANTI.search(desc)); out={1:[],0:[]}
    for nm,opt in ball.get(vid,[]):
        p=party(nm)
        if p not in FV.PARTIES or opt not in ('yes','no'): continue
        out[int(p==cb['chief_party'])].append((opt=='yes')!=anti)
    return out
byday=collections.defaultdict(list)
for vid,(room,dt,sq,b,desc) in ev.items(): byday[(room,dt)].append((sq,vid))
earlier={}
for k,lst in byday.items():
    lst.sort(); acc={1:[0,0],0:[0,0]}
    for sq,vid in lst:
        earlier[vid]=(acc[1][:],acc[0][:])
        sd=sides(vid)
        if sd:
            for side in (1,0):
                if sd[side]: acc[side][0]+=np.mean(sd[side])>=.5; acc[side][1]+=1
# map our 2025 first votes -> LIS vid (same bill, same date)
rows=pickle.load(open(FV.ROWS,'rb')); va=[r for r in rows if r['yr']==2025]
p25=pickle.load(open('/private/tmp/claude-501/-Users-tuckerward-Documents-Projects-bill-tracker/d2c029e9-acd9-410e-81ec-5347fd755620/scratchpad/p25.pkl','rb')) if False else None
tr=[r for r in rows if r['yr'] in FV.TRAIN_YEARS]
p,_,m=FV.fit_predict('gbm',FV.NUM,tr,va,depth=6,lr=.03)
D=FV.assemble()
idx=collections.defaultdict(list)
for vid,(room,dt,sq,b,desc) in ev.items(): idx[(b,dt)].append(vid)
X=[];Y=[];H=[]
o=np.argsort(np.abs(p-.5)); hard=set(o[:len(o)//3].tolist())
for i,r in enumerate(va):
    s,b=r['bill']; dt=D['rc'][r['bill']][0][0]
    vids=idx.get((b.replace(' ',''),dt),[])
    if not vids: continue
    e1,e0=earlier[min(vids,key=seq)]
    own,oth=(e1,e0) if r['same'] else (e0,e1)
    X.append([np.log(p[i]/(1-p[i]+1e-9)+1e-9), (own[0]+1)/(own[1]+2), (oth[0]+1)/(oth[1]+2), np.log1p(own[1])]); Y.append(r['y']); H.append(i in hard)
X=np.array(X);Y=np.array(Y);H=np.array(H)
print(f'matched {len(Y)} of {len(va)} 2025 first-vote ballots to an ordered LIS roll call')
# 2-fold by bill-free random split (quick estimate)
rng=np.random.default_rng(0); f=rng.random(len(Y))<.5
for cols,lbl in (([0],'model alone'),([0,1,2,3],'model + earlier today in this room')):
    accs=[]; haccs=[]
    for a,b_ in ((f,~f),(~f,f)):
        fit=stats.logit(X[a][:,cols],Y[a],[str(c) for c in cols],ridge=1e-3)
        beta=np.array([fit[k][0] for k in ['const']+[str(c) for c in cols]])
        pr=1/(1+np.exp(-(np.column_stack([np.ones(b_.sum()),X[b_][:,cols]])@beta)))
        accs.append(((pr>=.5)==Y[b_]).mean()); haccs.append(((pr>=.5)==Y[b_])[H[b_]].mean())
    print(f'  {lbl:38s} all {np.mean(accs):.1%}   hardest third {np.mean(haccs):.1%}')
