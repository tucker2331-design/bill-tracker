import sys,pickle,numpy as np,time; sys.path.insert(0,'/Users/tuckerward/Documents/Projects/bill-tracker/tools/calibration')
import content_votes as CVT, stats
rows=pickle.load(open('/private/tmp/claude-501/-Users-tuckerward-Documents-Projects-bill-tracker/d2c029e9-acd9-410e-81ec-5347fd755620/scratchpad/cv_rows2.pkl','rb'))
tr=[r for r in rows if r['yr'] in (2021,2022,2024)]; te=[r for r in rows if r['yr'] in (2025,2026)]
ytr=np.array([r['y'] for r in tr]); yte=np.array([r['y'] for r in te])
G=CVT.GROUPS
def mat(rs,groups): return np.array([[v for g in groups for v in G[g](r)] for r in rs],float)
def auc(p,y):
    idx=np.argsort(p,kind='mergesort'); ranks=np.empty(len(p)); i=0
    while i<len(p):
        j=i
        while j+1<len(p) and p[idx[j+1]]==p[idx[i]]: j+=1
        ranks[idx[i:j+1]]=(i+j)/2+1; i=j+1
    n1=y.sum(); n0=len(y)-n1; return (ranks[y==1].sum()-n1*(n1+1)/2)/(n1*n0)
def bal(p,y,t): pr=p>=t; return 0.5*((pr[y==1]).mean()+(~pr[y==0]).mean())
B=lambda f: np.array([bool(f(r)) for r in te],dtype=bool)
POP={'all votes':np.ones(len(te),bool),
     'other-party legislators':B(lambda r:r['same']==0),
     'other-party, FIRST vote on the bill':B(lambda r:r['same']==0 and r['first_vote']),
     'other-party, contested':B(lambda r:r['same']==0 and .1<=r['opp_actual']<=.9)}
cache={}
def fit(groups):
    key=tuple(groups)
    if key in cache: return cache[key]
    Xtr=mat(tr,groups); Xte=mat(te,groups)
    f=stats.logit(Xtr,ytr,names=[f'x{i}' for i in range(Xtr.shape[1])],ridge=1e-3)
    b=np.array([f[k][0] for k in ['const']+[f'x{i}' for i in range(Xtr.shape[1])]])
    with np.errstate(all='ignore'):
        ptr=1/(1+np.exp(-(np.column_stack([np.ones(len(tr)),Xtr])@b))); pte=1/(1+np.exp(-(np.column_stack([np.ones(len(te)),Xte])@b)))
    ts=np.quantile(ptr,np.linspace(.02,.98,49)); t=max(ts,key=lambda t:bal(ptr,ytr,t))   # threshold chosen on TRAIN
    cache[key]=(pte,t); return cache[key]
def report(label,groups):
    p,t=fit(groups); out=[]
    for k,m in POP.items():
        pp,yy=p[m],yte[m]; out.append((auc(pp,yy),bal(pp,yy,t),((pp>=0.5)==yy).mean(),max(yy.mean(),1-yy.mean())))
    return out
ALL=list(G)
print('POPULATIONS:',{k:int(m.sum()) for k,m in POP.items()}, '| support rate:',{k:round(float(yte[m].mean()),2) for k,m in POP.items()})
full=report('FULL',ALL)
def row(label,res):
    print(f'{label:34s} '+'  '.join(f'{a:.3f}/{b:.1%}' for a,b,c,d in res))
print(f"\n{'':34s} "+'  '.join(f'{k[:22]:>14s}' for k in POP)); print(f"{'':34s} "+'  '.join(f'{"rank/balanced":>14s}' for k in POP))
row('FULL MODEL (all 8 ingredients)',full)
print('\nplain accuracy of the full model vs "always guess the common answer":')
for (k,m),(a,b,c,d) in zip(POP.items(),full): print(f'   {k:36s} {c:.1%}  vs  {d:.1%}')
print('\nREMOVE one ingredient (how much the full model loses):')
for g in ALL: row('  - '+g,report(g,[x for x in ALL if x!=g]))
print('\nADD one ingredient to party & standing alone:')
row('  party & standing only',report('b',['party & standing']))
for g in ALL[1:]: row('  + '+g,report(g,['party & standing',g]))
