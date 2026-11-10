"""Frozen fixed-case M3 birth-progress breadth diagnostic. No account or future labels."""
from pathlib import Path
import json, hashlib, time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
R=O.parent
B=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
IX=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/ix-a-share-entry-20261025/signals')
CASES=[('600186.SH','2022-11-03','A_B_CASE'),('000921.SZ','2022-11-03','A_B_CASE'),('000603.SZ','2022-03-24','A_B_CASE'),('600301.SH','2022-03-22','A_B_CASE'),('300570.SZ','2024-09-25','A_B_CASE'),('002423.SZ','2024-10-30','A_B_CASE'),('000833.SZ','2024-09-26','A_B_CASE'),('300666.SZ','2024-09-30','A_B_CASE'),('300666.SZ','2025-12-15','EARLY_CONTEXT_ONLY'),('300666.SZ','2025-12-17','EARLY_CONTEXT_ONLY'),('300666.SZ','2026-01-05','EARLY_CONTEXT_ONLY'),('300666.SZ','2026-01-15','EARLY_CONTEXT_ONLY')]
SEMI_DATES=['2024-09-24','2024-09-26','2026-04-08','2026-04-17','2026-06-11','2026-06-16']
SOURCES={}
def sha(p):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest();SOURCES[str(p)]=h;return h
def readp(p,**kw):sha(p);return pd.read_parquet(p,**kw)
def readj(p):sha(p);return json.loads(Path(p).read_text())
def norm(x):
 if isinstance(x,dict):return {str(k):norm(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [norm(v)for v in x]
 if isinstance(x,np.generic):return norm(x.item())
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 if isinstance(x,float)and not np.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(norm(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def native_mu(g):
 out=pd.Series(np.nan,index=g.index)
 for _,gg in g.groupby('segment_id',sort=False):
  a=gg[gg.valid_strength_observation];c=a.close.to_numpy();v=np.full(len(c),np.nan);mu=np.nan
  if not len(c):continue
  x=np.log(c/c[0])
  for j in range(1,len(c)):
   r=x[j]-x[j-1];mu=r if j==1 else r/3+(1-1/3)*mu
   if j>=64:v[j]=mu
  out.loc[a.index]=v
 return out
def warm_birth(raw,g,cal,start):
 mu=native_mu(g).reindex(cal);p=raw.reindex(cal);gg=g.reindex(cal)
 identity=p.segment_id.astype('string')+'|'+p.source_kind.astype('string')+'|'+p.source_path.astype('string')
 valid=gg.valid_strength_observation.eq(True)&p.observed_bar.eq(True)&p.price_eligible.eq(True)&p.volume_eligible.eq(True)&~p.source_invalid.eq(True)&p.close.gt(0)&p.volume.gt(0)&np.isfinite(mu)
 kk=valid&valid.shift(1,fill_value=False)&valid.shift(2,fill_value=False)&identity.eq(identity.shift(1)).fillna(False)&identity.eq(identity.shift(2)).fillna(False)
 rr=kk&mu.gt(0)&mu.shift(1).gt(0)&mu.shift(2).gt(0)
 state=np.where(kk,rr.astype(int),-1)
 j=cal.get_loc(start)
 if state[j]!=1:return None
 q=j
 while q>0 and state[q-1]==1:q-=1
 return cal[q] if q>0 and state[q-1]==0 else None
def anchored(states,prices,identities,dates,seed=None):
 out=np.full(len(states),-1,dtype=np.int8);birth=[pd.NaT]*len(states);anchors=np.full(len(states),np.nan)
 b=seed;anchor=float(prices[0]) if False else None;source=None
 if seed is not None:anchor=seed[1];source=seed[2];b=seed[0]
 for j,(state,c,identity) in enumerate(zip(states,prices,identities)):
  if state<0:b=None;anchor=None;source=None;continue
  if state==0:out[j]=0;b=None;anchor=None;source=None;continue
  if j>0 and states[j-1]==0:
   b=dates[j];anchor=c;source=identity
  if b is None or anchor is None or not np.isfinite(anchor)or anchor<=0 or not np.isfinite(c)or c<=0 or identity!=source:continue
  out[j]=int(c>=anchor);birth[j]=b;anchors[j]=anchor
 return out,birth,anchors
def aggregate(states,sector):
 known=states.ge(0);N=states.shape[1];K=known.sum(axis=1);n=states.eq(1).sum(axis=1);Uu=N-K
 both=known&known.shift(3,fill_value=False);J=both.sum(axis=1)
 now=(states.eq(1)&both).sum(axis=1);past=(states.shift(3).eq(1)&both).sum(axis=1);d=now-past
 rule=lambda nn,den,up:(nn>=3)&(((nn*3>=den)&up)|(nn*2>=den))
 lo=rule(n,N,J.gt(0)&d.gt(0));hi=rule(n+Uu,N,d.gt(0)|J.eq(0))
 return pd.DataFrame(dict(sector=sector,N=N,K=K,n=n,U=Uu,share=n/K.replace(0,np.nan),lower=n/N,upper=(n+Uu)/N,J=J,prior_n=past,current_n=now,delta=d,candidate=np.where(lo,1,np.where(~hi,0,-1))),index=states.index)
def main():
 t0=time.monotonic();assert not (O/'DONE.json').exists()
 save('PROTOCOL.json',dict(formula='Q=M3 AND close_t>=close_at_latest_known_0_to_1_M3_birth; missing anchor/source/price =>UNKNOWN. Reset birth only on original known0to1. Birth-day equality passes.',consumer='Only gate an ORIGINAL A/B invitation with Q breadth true; original S, births, ranking, I, sizes, stops, profit ADD unchanged. No new invitation, fallback or stale replay.',industry='Original fixed N and original M3/PVR both-known domain; old n>=3 AND [(share>=1/3 AND same-member delta3>0) OR share>=1/2], robust fixedN bounds. Recompute known intersections for Q.',cases=CASES,semiconductor_dates=SEMI_DATES,initial_day='25 actually bought original PVR sectors on2022-01-04, descriptive different account only',limitations=['Static future membership NON-PIT','native causal adjusted close, announcement availability not certified','development cases already seen','no economics, parameter search, future outcome computation','not dealer inventory cost or flow'],frozen_in_parent_conversation_before_resumption=True))
 meta=pd.read_csv(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').set_index('sid');sha(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv')
 groups=readj(R/'first_day_20220105_roster_v1/INDUSTRY_GROUPS.json')
 points=[dict(sid=s,day=d,kind=k,sector=meta.at[s,'sector_id'])for s,d,k in CASES]
 points += [dict(sid='',day=d,kind='EARLY_SECTOR_ONLY',sector='URFI881121')for d in SEMI_DATES]
 points += [dict(sid='',day='2022-01-04',kind='OLD_PVR_DAY_ONLY',sector=g['sector_id'])for g in groups]
 sectors=sorted(set(p['sector']for p in points));ids=sorted(meta.index[meta.sector_id.isin(sectors)])
 k=pd.concat([readp(B/'WARM_PREFIX_M_K.parquet'),readp(B/'KNOWN3.parquet')])[ids]
 rr=pd.concat([readp(B/'WARM_PREFIX_M_R.parquet'),readp(B/'RIGHT3.parquet')])[ids]
 ps=readp(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',columns=['sid','day','state']);ps=ps[ps.sid.isin(ids)].pivot(index='day',columns='sid',values='state')
 ps=pd.concat([readp(B/'WARM_PREFIX_P_STATE.parquet')[ids],ps]).reindex(k.index)
 baseknown=k&ps.ge(0);base=pd.DataFrame(np.where(baseknown,rr.astype(int),-1),index=k.index,columns=ids)
 manifests={x['symbol']:x for x in readj(U/'STOCK_MANIFEST.json')}
 ims=readj(U/'INDUSTRY_MANIFEST.json')
 fullpre=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(x['refs']['CP1_input'],columns=[]).index)for x in ims])))
 fullpre=fullpre[fullpre<=pd.Timestamp('2021-12-31')]
 for x in ims:sha(x['refs']['CP1_input'])
 qd={};bd={};ad={};prices={};aud=[]
 for n,s in enumerate(ids):
  rec=manifests[s];path=next(p for p in rec['source_sha256']if p.endswith('/signal.parquet'))
  raw=readp(path,columns=['close','volume','segment_id','source_kind','source_path','observed_bar','price_eligible','volume_eligible','source_invalid'])
  assert SOURCES[path]==rec['source_sha256'][path]
  mstate=np.where(k[s],rr[s].astype(int),-1)
  p=raw.reindex(k.index);identity=p.segment_id.astype('string')+'|'+p.source_kind.astype('string')+'|'+p.source_path.astype('string')
  seed=None
  if mstate[0]==1:
   g=readp(IX/(s+'.parquet'),columns=['close','volume','segment_id','valid_strength_observation']).loc[:'2021-12-31']
   b=warm_birth(raw.loc[:'2021-12-31'],g,fullpre,k.index[0])
   if b is not None:
    a=raw.loc[b];seed=(b,float(a.close),str(a.segment_id)+'|'+str(a.source_kind)+'|'+str(a.source_path))
    # Identity uses nullable string conversion, avoid float/int spelling differences.
    seed=(b,float(a.close),(raw.segment_id.astype('string')+'|'+raw.source_kind.astype('string')+'|'+raw.source_path.astype('string')).loc[b])
  q,birth,anc=anchored(mstate,p.close.to_numpy(),identity.to_numpy(),k.index,seed)
  qd[s]=np.where(baseknown[s],q,-1);bd[s]=birth;ad[s]=anc;prices[s]=p.close.to_numpy()
  # Cut at every fixed target day for this sector: calculation sees only prefix arrays.
  cuts=sorted({pd.Timestamp(v['day'])for v in points if v['sector']==meta.at[s,'sector_id']})
  for cut in cuts:
   stop=k.index.get_loc(cut)+1;small=anchored(mstate[:stop],p.close.to_numpy()[:stop],identity.to_numpy()[:stop],k.index[:stop],seed)
   np.testing.assert_equal(small[0],q[:stop])
  aud.append(dict(sid=s,sector=meta.at[s,'sector_id'],warm_birth=str(seed[0])if seed else '',prefix_cuts=len(cuts),prefix_exact=True))
  if (n+1)%100==0:print('SOURCE_PROGRESS',n+1,len(ids),round(time.monotonic()-t0,2),flush=True)
 q=pd.DataFrame(qd,index=k.index);birth=pd.DataFrame(bd,index=k.index);anc=pd.DataFrame(ad,index=k.index);price=pd.DataFrame(prices,index=k.index)
 orig=readp(B/'COMMON_K_COMPARISON.parquet').set_index(['day','sector'])
 allbase={};allq={};rows=[];members=[]
 for sector in sectors:
  cols=meta.index[meta.sector_id.eq(sector)].tolist();allbase[sector]=aggregate(base[cols],sector);allq[sector]=aggregate(q[cols],sector)
 for point in points:
  day=pd.Timestamp(point['day']);sec=point['sector'];a=allbase[sec].loc[day];z=allq[sec].loc[day];old=orig.loc[(day,sec)]
  for field,oc in [('N','N'),('K','K'),('n','M3_n'),('U','U'),('candidate','M3_candidate')]:assert a[field]==old[oc],(point,field,a[field],old[oc])
  row=dict(**point,industry=meta[meta.sector_id.eq(sec)].industry.iloc[0])
  for label,x in [('M3',a),('Q',z)]:
   for field in ['N','K','n','U','share','lower','upper','J','prior_n','current_n','delta','candidate']:row[label+'_'+field]=x[field]
  row['gate_effect']='BASE_NOT_ON'if a.candidate!=1 else 'ALLOW'if z.candidate==1 else 'DENY'if z.candidate==0 else 'UNKNOWN'
  rows.append(row)
  for sid in meta.index[meta.sector_id.eq(sec)]:
   members.append(dict(point_kind=point['kind'],target_sid=point['sid'],day=point['day'],sector=sec,sid=sid,name=meta.at[sid,'name'],base_state=int(base.at[day,sid]),Q=int(q.at[day,sid]),birth_day=birth.at[day,sid],anchor_close=anc.at[day,sid],current_close=price.at[day,sid]))
 out=pd.DataFrame(rows);out.to_csv(O/'FIXED_SECTOR_RESULTS.csv',index=False);pd.DataFrame(members).to_csv(O/'MEMBER_CONTRIBUTIONS.csv',index=False);pd.DataFrame(aud).to_csv(O/'PREFIX_CHECKS.csv',index=False)
 # Preserve only selected sector daily signal diagnostics; no trade or performance calculation.
 pd.concat([x.assign(day=x.index,model='M3')for x in allbase.values()]+[x.assign(day=x.index,model='Q')for x in allq.values()]).to_parquet(O/'SELECTED_SECTOR_DAILY.parquet',index=False)
 birth.to_parquet(O/'BIRTH_ANCHORS_DATES.parquet');anc.to_parquet(O/'BIRTH_ANCHORS_PRICES.parquet');q.to_parquet(O/'Q_STATE.parquet')
 save('SOURCE_HASHES.json',SOURCES)
 save('DONE.json',dict(status='FIXED_SIGNAL_ONLY',seconds=time.monotonic()-t0,stocks=len(ids),sectors=len(sectors),points=len(points),member_rows=len(members),prefix_checks=sum(x['prefix_cuts']for x in aud),economic_runs=0,formula_searches=0,old_case_performance_not_recomputed=True))
 print(out[['sid','day','kind','industry','M3_n','M3_K','M3_U','M3_candidate','Q_n','Q_K','Q_U','Q_candidate','gate_effect']].to_string(index=False),flush=True)
 print('DONE',json.dumps(json.loads((O/'DONE.json').read_text())),flush=True)
if __name__=='__main__':main()
