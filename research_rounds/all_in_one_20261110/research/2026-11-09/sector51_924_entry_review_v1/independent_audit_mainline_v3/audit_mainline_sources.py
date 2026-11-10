"""Independent source-level M classification; never imports or runs strategy."""
from pathlib import Path
import json,sys,hashlib,warnings
from collections import Counter
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore',message='All-NaN slice encountered')
O=Path(__file__).resolve().parent;P=O.parent;F=Path(sys.argv[1]);read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
ro=pd.read_csv(P/'joint51_candidate_v1/CLASSIFICATION_ALL1709.csv');ro=ro[ro.eligible];ids=sorted(ro.symbol);mapping=ro.set_index('symbol').sector51.to_dict();members={s:[i for i,x in enumerate(ids) if mapping[x]==s] for s in sorted(set(mapping.values()))};ms={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')}
k=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet')[ids];rt=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/RIGHT3.parquet')[ids];pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',columns=['sid','day','state']);pv=pv[pv.sid.isin(ids)].pivot(index='day',columns='sid',values='state').reindex(index=k.index,columns=ids);kn=k&pv.ge(0);rr=kn&rt
last=read(F/'DAY_LEDGER.json')[-1]['day'];cal=k.index[(k.index>=pd.Timestamp('2023-11-01'))&(k.index<=pd.Timestamp(last))];nc=len(cal);ns=len(ids);px=np.full((nc,ns),np.nan);valid=np.zeros((nc,ns),bool);source_change=np.ones((nc,ns),bool)
cols=['raw_open','raw_high','raw_low','raw_close','raw_volume','adjustment_factor','close','observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar','source_kind','source_path','segment_id']
for j,s in enumerate(ids):
 path=next(p for p in ms[s]['source_sha256'] if p.endswith('/signal.parquet'));z=pd.read_parquet(path,columns=cols).reindex(cal);num=z[cols[:6]].to_numpy(float);v=np.isfinite(num).all(1)&(num>0).all(1)
 for c in ['observed_bar','price_eligible','volume_eligible']:v &= z[c].eq(True).to_numpy()
 for c in ['source_invalid','synthetic_event_bar']:v &= z[c].eq(False).to_numpy()
 lin=z[['source_kind','source_path','segment_id']].astype('string');v &= lin.notna().all(axis=1).to_numpy()&lin.ne('').all(axis=1).to_numpy();p=(z.raw_close*z.adjustment_factor).to_numpy(float);v &= np.isclose(p,z.close.to_numpy(float),rtol=1e-10,atol=1e-10);valid[:,j]=v;px[:,j]=np.where(v,p,np.nan)
 arr=lin.fillna('__MISSING__').to_numpy(str);source_change[1:,j]=(arr[1:]!=arr[:-1]).any(axis=1)
rets={};rk={}
for h in [5,10,20]:
 a=np.full((nc,ns),np.nan);b=np.zeros((nc,ns),bool)
 for i in range(h,nc):
  ok=valid[i-h:i+1].all(axis=0)&~source_change[i-h+1:i+1].any(axis=0);b[i]=ok;a[i,ok]=px[i,ok]/px[i-h,ok]-1
 rets[h]=a;rk[h]=b
market={h:np.nanmedian(a,axis=1) for h,a in rets.items()};breakout=np.full((nc,ns),np.nan)
for i in range(20,nc):
 ok=rk[20][i];breakout[i,ok]=(px[i,ok]>np.nanmax(px[i-20:i,ok],axis=0)).astype(float)
def and3(v):return 0 if 0 in v else -1 if -1 in v else 1
def pos(x):return -1 if not np.isfinite(x) else int(x>0)
def half(n,u,N):return 1 if n*2>=N else 0 if (n+u)*2<N else -1
checks=Counter();errors=[];out=[]
def check(c,a,b,ctx):
 checks[c]+=1;ok=(pd.isna(a) and pd.isna(b)) or (np.isclose(a,b,rtol=1e-10,atol=1e-9) if isinstance(b,(float,np.floating)) else a==b)
 if not ok:errors.append(dict(check=c,actual=str(a),expected=str(b),context=ctx))
ref=pd.read_csv(P/'mainline_candidate_v1/ALL50_MAINLINE_EVIDENCE.csv',parse_dates=['day']).set_index(['day','sector51'])
for sec,ii in members.items():
 N=len(ii);ss=[ids[i] for i in ii];n=rr[ss].sum(axis=1);K=kn[ss].sum(axis=1);Uu=N-K;paired=kn[ss]&kn[ss].shift(3,fill_value=False);J=paired.sum(axis=1);diff=((paired&rr[ss]&~rr[ss].shift(3,fill_value=False)).sum(axis=1)-(paired&~rr[ss]&rr[ss].shift(3,fill_value=False)).sum(axis=1));lo=(n>=3)&(((3*n>=N)&(J>0)&(diff>0))|(2*n>=N));hi=(n+Uu>=3)&(((3*(n+Uu)>=N)&((diff>0)|(J==0)))|(2*(n+Uu)>=N));state=np.where(lo,1,np.where(hi,-1,0));states=pd.Series(state,index=k.index);med={h:np.nanmedian(rets[h][:,ii],axis=1) for h in rets};rs={h:100*(med[h]-market[h]) for h in rets};streak=0
 for i,d in enumerate(cal):
  if i==0:Q=-1
  else:Q=and3([int(states.at[d]),half(n.at[d],Uu.at[d],N),half(n.at[cal[i-1]],Uu.at[cal[i-1]],N)])
  cnt=float(np.nansum(breakout[i,ii])) if np.isfinite(breakout[i,ii]).any() else np.nan;bk=int(rk[20][i,ii].sum());br=-1 if not np.isfinite(cnt) else half(cnt,N-bk,N)
  S=and3([Q,pos(rs[10][i]),pos(rs[20][i]),pos(med[10][i])]);Ff=and3([Q,pos(rs[5][i]),-1 if i==0 or not np.isfinite(rs[5][i-1]) or not np.isfinite(rs[5][i]) else int(rs[5][i]>rs[5][i-1]),pos(med[5][i]),br]);M=1 if 1 in [S,Ff] else -1 if -1 in [S,Ff] else 0
  if M==1 and not np.isfinite(rs[5][i]):M=-1
  streak=streak+1 if M==1 else 0;E=max(rs[5][i],0)*n.at[d]/N;W=i>0 and ((rs[5][i]<0 and rs[10][i]<0 and rs[5][i-1]<0 and rs[10][i-1]<0) or (states.at[d]==0 and states.at[cal[i-1]]==0))
  if d<pd.Timestamp('2024-09-02'):continue
  z=dict(day=str(d.date()),sector51=sec,N=N,n=int(n.at[d]),K=int(K.at[d]),U=int(Uu.at[d]),state=int(states.at[d]),diff=int(diff.at[d]),Q=Q,S=S,F=Ff,M=M,M_streak=streak,E=E,W=bool(W),breakout20_count=cnt,breakout20_K=bk)
  for h in rets:z.update({f'rs{h}':rs[h][i],f'return{h}_median':med[h][i],f'return{h}_K':int(rk[h][i,ii].sum()),f'market{h}_K':int(rk[h][i].sum())})
  for c,v in z.items():
   if c not in ['day','sector51']:check('source_'+c,({'True':1.0,'False':0.0}.get(str(ref.at[(d,sec),c]),pd.to_numeric(ref.at[(d,sec),c],errors='coerce'))) if c=='breakout20_count' else ref.at[(d,sec),c],v,[z['day'],sec])
  out.append(z)
expect={(x['day'],x['sector51']):x for x in out}
for x in read(F/'FUNDING_REQUESTS.json'):
 t=x['plan_day'];e=expect[(t,mapping[x['sid']])]
 for c in ['M','M_streak','E']:check('OPEN_uses_prior_CLOSE_'+c,float(x[c]) if c=='E' else x[c],e[c],[x['day'],x['sid']])
 check('no_same_day_or_future_M',x['plan_day']<x['day'],True,[x['day'],x['sid']])
report=dict(status='PASS' if not errors else 'FAIL',run=str(F),checks=dict(checks),check_count=sum(checks.values()),errors=errors,independent_source_symbols=len(ids),sector_day_rows=len(out),scope='Full fixed-roster source windows and common-known breadth, independently rebuilt. No engine import or alternative strategy run.',source_sha=sha(Path(__file__)))
(O/(F.name+'_SOURCE_M_QSF_AUDIT.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');pd.DataFrame(out).to_csv(O/(F.name+'_INDEPENDENT_M_EVIDENCE.csv'),index=False)
print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False,indent=2))
