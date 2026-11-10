from pathlib import Path
import json,sys,hashlib,time,subprocess
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
R=O.parent.parent; E=R/'m3_stock_birth_during_sector_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,d):(O/n).write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n')
def calc(pi,ps):
 ri=np.log(np.asarray(pi[1:])/np.asarray(pi[:-1]));rs=np.log(np.asarray(ps[1:])/np.asarray(ps[:-1]))
 a=ri[:63];b=rs[:63];ac=a-a.mean();bc=b-b.mean();den=float(bc@bc)
 if den==0:return dict(status='ZERO_SECTOR_VARIANCE',beta=np.nan,Q=np.nan,den=den)
 beta=float((ac@bc)/den);Q=float(np.sum(ri[63:]-beta*rs[63:]))
 if not np.isfinite(beta) or not np.isfinite(Q):return dict(status='NONFINITE_MODEL',beta=np.nan,Q=np.nan,den=den)
 return dict(status='KNOWN',beta=beta,Q=Q,den=den,stock_recent=float(ri[63:].sum()),sector_recent=float(rs[63:].sum()),common_component=float(beta*rs[63:].sum()),fit_start_return=0,fit_n=63,recent_n=21)
# Handworked algebra comes before any empirical feature outputs.
b=np.tile([-.01,0,.01],21); recent=np.repeat(.06/21,21)
def prices(r,level=100):return level*np.exp(np.r_[0,np.cumsum(r)])
ps=prices(np.r_[b,recent],1000)
pa=prices(np.r_[2*b,np.repeat(.13/21,21)])
pb=prices(np.r_[.5*b,np.repeat(.05/21,21)])
a=calc(pa,ps);c=calc(pb,ps)
assert abs(a['beta']-2)<1e-12 and abs(c['beta']-.5)<1e-12
assert abs(a['Q']-.01)<1e-12 and abs(c['Q']-.02)<1e-12
sc=calc(pa*7,ps*.3);assert abs(sc['beta']-a['beta'])<1e-11 and abs(sc['Q']-a['Q'])<1e-11
assert calc(pa,np.ones(85)*1000)['status']=='ZERO_SECTOR_VARIANCE'
# Equal beta -> same recent-return ordering. Pure common boom -> scores tied but high-beta absolute winners.
purea=calc(prices(np.r_[2*b,2*recent]),ps);pureb=calc(prices(np.r_[.5*b,.5*recent]),ps)
assert abs(purea['Q'])<1e-12 and abs(pureb['Q'])<1e-12
save('HAND_CHECKS.json',dict(heterogeneous_A=a,heterogeneous_B=c,raw_order='A > B',Q_order='B > A',equal_beta_identity='Q_i-Q_j=R_i21-R_j21 when beta_i=beta_j',scale_invariance=True,zero_sector_variance_unknown=True,pure_common_boom_counterexample=dict(high_beta=purea,low_beta=pureb,meaning='Both Q zero; high-beta absolute boom is intentionally stripped, a real tail-retention risk'),new_rankings=0,new_economics=0))
d=pd.read_csv(E/'lifecycle_v1/DECISIONS.csv',parse_dates=['day'],low_memory=False)
d=d[d.arm.eq('A_UNION_B')&d.window.isin(['2022','2024_924'])&d.decision.isin(['SELECTED_PENDING','PASS_NOT_TOP2'])].copy()
assert not d.event_id.duplicated().any()
sm={z['symbol']:z for z in json.loads((U/'STOCK_MANIFEST.json').read_text())}
im={z['series']:z for z in json.loads((U/'INDUSTRY_MANIFEST.json').read_text())}
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
with np.load(H,allow_pickle=False) as hz: cal=pd.DatetimeIndex(hz['dates'])
cal=cal[cal<=pd.Timestamp('2026-06-30')]
panelcal=pd.DatetimeIndex(sorted(pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet').day.unique()))
assert cal[cal>=pd.Timestamp('2022-01-01')].equals(panelcal)
di={v:j for j,v in enumerate(cal)}
hashes={str(p):sha(p) for p in [H,R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet',E/'entry_quality_2022_v1/CORE_LAYER_RESULTS.csv',Path(__file__),O/'FREEZE.json',E/'lifecycle_v1/DECISIONS.csv',U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json']}
def load(m):
 sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
 digest=sha(sp);assert digest==m['source_sha256'][sp],sp
 hashes[sp]=digest
 p=pd.read_parquet(sp).reindex(cal)
 return p
industry={s:load(im[s]) for s in d.sector.unique()}
def check(z):
 if len(z)!=85:return 'INSUFFICIENT_CALENDAR'
 for c in ['close','raw_close','adjustment_factor']:
  if not np.isfinite(z[c]).all() or not z[c].gt(0).all():return 'INVALID_PRICE_OR_FACTOR'
 for c in ['observed_bar','price_eligible','volume_eligible']:
  if not z[c].eq(True).all():return 'INVALID_FLAGS'
 for c in ['source_invalid','synthetic_event_bar']:
  if not z[c].eq(False).all():return 'INVALID_FLAGS'
 if any(z[c].isna().any() or z[c].nunique()!=1 for c in ['source_kind','source_path','segment_id']):return 'SOURCE_SEGMENT_BREAK'
 if not np.allclose(z.raw_close*z.adjustment_factor,z.close,rtol=1e-9,atol=1e-9):return 'NATIVE_RAW_FACTOR_MISMATCH'
 return 'VALID'
rows=[];start=time.time();prefixchecks=0
for j,(sid,g) in enumerate(d.groupby('sid')):
 p=load(sm[sid])
 for r in g.itertuples(index=False):
  k=di[r.day];s=industry[r.sector];zp=p.iloc[max(0,k-84):k+1];zs=s.iloc[max(0,k-84):k+1]
  cp=check(zp);cs=check(zs)
  out=dict(event_id=r.event_id,window=r.window,day=r.day,sid=sid,name=r.name,sector=r.sector,original_selected=r.selected,original_decision=r.decision,original_PVR=r.PVR_score,stock_validity=cp,sector_validity=cs)
  if cp=='VALID' and cs=='VALID':
   out.update(calc(zp.close.to_numpy(),zs.close.to_numpy()))
   out.update(fit_first_return=cal[k-83],fit_last_return=cal[k-21],recent_first_return=cal[k-20],recent_last_return=cal[k])
   # Truncate source at t and independently slice identical common-calendar window.
   if prefixchecks<100:
    test=calc(p.loc[:r.day].iloc[-85:].close.to_numpy(),s.loc[:r.day].iloc[-85:].close.to_numpy())
    assert test=={key:out[key] for key in test}
    prefixchecks+=1
  else:out['status']='INPUT_UNKNOWN'
  rows.append(out)
 if (j+1)%300==0:print('STOCKS',j+1,round(time.time()-start,1),flush=True)
x=pd.DataFrame(rows);x.to_csv(O/'CAUSAL_FEATURE_COVERAGE.csv',index=False)
coverage=x.groupby(['window','original_selected','status']).size().rename('n').reset_index()
coverage.to_csv(O/'COVERAGE.csv',index=False)
x[x.status.eq('KNOWN')].groupby('window')[['beta','Q','den']].describe(percentiles=[0,.01,.5,.99,1]).to_csv(O/'NUMERIC_RANGES.csv')
# No new candidate ranks or outcomes are calculated. Original tails are looked up separately solely to audit beta coverage/risk.
r=pd.read_csv(E/'entry_quality_2022_v1/CORE_LAYER_RESULTS.csv',usecols=['event_id','arm','window','core_return','core_net','status'])
r=r[r.arm.eq('A_UNION_B')&r.window.isin(['2022','2024_924'])&r.core_return.ge(.3)]
tails=r.merge(x,on=['event_id','window'],how='left',validate='one_to_one')
tails.to_csv(O/'ORIGINAL_TAIL_FEATURE_RISK.csv',index=False)
save('QA.json',dict(feasible=len(d),feature_rows=len(x),known=int(x.status.eq('KNOWN').sum()),unknown=int(x.status.ne('KNOWN').sum()),prefix_checks=prefixchecks,lookback_prices=85,fit_returns=63,recent_returns=21,new_candidate_ranks=0,new_backtests=0,original_tail_rows=len(tails),source_files=len(hashes),seconds=time.time()-start))
save('SOURCE_HASHES.json',hashes)
print(coverage.to_string(index=False));print(x[x.status.eq('KNOWN')].groupby('window')[['beta','Q','den']].agg(['min','median','max']).to_string());print('TAIL_RISK',tails.groupby('window').agg(n=('event_id','size'),known=('beta','count'),beta_median=('beta','median'),beta_max=('beta','max'),negative_Q=('Q',lambda a:(a<0).sum())).to_string())
