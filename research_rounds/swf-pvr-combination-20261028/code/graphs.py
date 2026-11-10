from study import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
cases=[]
for c in STARTS:
 a=read(O/'RS'/c/'technical/short-v2/SW10F__S0_base.json');seen=set()
 for r in a['audit_log']:
  if r['kind']!='waiting_support_raise':continue
  key=(r['sid'],r['origin'])
  if key in seen:continue
  seen.add(key);cases.append((c,key,a['audit_log']))
  if len(seen)==2:break
fig,axes=plt.subplots(2,len(cases),figsize=(4*len(cases),7),squeeze=False,gridspec_kw={'height_ratios':[3,1]})
snap=Path(read(PRIOR/'input.json')['snapshot']['path'])
for k,(c,(sid,origin),logs) in enumerate(cases):
 lo=pd.Timestamp(origin)-pd.Timedelta(days=8);hi=pd.Timestamp(origin)+pd.Timedelta(days=18);f=pd.read_parquet(snap/'signals'/f'{sid}.parquet').loc[lo:hi];ax=axes[0,k];ax.plot(f.index,f.close,color='black');ax.fill_between(f.index,f.low,f.high,color='grey',alpha=.15)
 rr=[r for r in logs if r.get('sid')==sid and ((r['kind']=='intent_create' and r.get('day')==origin) or (r['kind']=='waiting_support_raise' and r.get('origin')==origin))];ax.step([pd.Timestamp(r['at'][:10]) for r in rr],[r['floor'] for r in rr],where='post',color='orange',label='等待F保护')
 end=[r for r in logs if r['kind']=='intent_end' and r.get('sid')==sid and r.get('origin')==origin]
 if end:ax.axvline(pd.Timestamp(end[0]['at'][:10]),color='red',ls=':');ax.set_xlabel(end[0]['reason'])
 ax.set_title(c+' '+sid+'\nW起点 '+origin);ax.legend();axes[1,k].bar(f.index,f.amount/1e8,color='steelblue');axes[1,k].set_ylabel('成交金额/亿元')
 for aa in axes[:,k]:aa.tick_params(axis='x',rotation=60)
fig.tight_layout();fig.savefig(O/'waiting-graph-review.png',dpi=120);save(O/'graph-cases.json',{'cases':[dict(cohort=c,symbol=key[0],origin=key[1]) for c,key,_ in cases]})
