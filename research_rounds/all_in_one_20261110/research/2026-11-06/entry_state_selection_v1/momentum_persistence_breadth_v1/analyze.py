"""Frozen mu5 positive for three common sessions, descriptive breadth only."""
from pathlib import Path
import json, hashlib, time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent; R=O.parent
M=Path('/Users/bytedance/Documents/ChatGPT/money')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
U=W/'universe-cp1-inputs-20261031'
IX=M/'research_rounds/ix-a-share-entry-20261025/signals'
OLD=M/'research_rounds/a-share-selection-e0-20261024/prepared-v2'
START='2022-01-04'; END='2026-06-30'; WARM=64
FIXED=['2022-01-11','2022-03-03','2022-07-25','2022-10-14','2022-12-01','2024-09-20','2024-09-23','2024-09-24','2024-09-25','2024-09-26','2024-09-27','2024-09-30','2024-10-08','2026-01-05','2026-01-15','2026-01-30','2026-03-03','2026-04-08','2026-04-17','2026-05-15','2026-05-29','2026-06-11','2026-06-16','2026-06-30']
def norm(x):
 if isinstance(x,dict):return {str(k):norm(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [norm(v)for v in x]
 if isinstance(x,np.generic):return norm(x.item())
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 if isinstance(x,float)and not np.isfinite(x):return None
 return x
def dump(n,x):(O/n).write_text(json.dumps(norm(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def calc(f,calendar):
 q=f.reindex(calendar); c=q.close.to_numpy(float); v=q.volume.to_numpy(float)
 seg=q.segment_id.to_numpy(); valid=q.valid_strength_observation.eq(True).to_numpy()&np.isfinite(c)&(c>0)&np.isfinite(v)&(v>0)&q.segment_id.notna().to_numpy()
 n=len(q); mu=np.full(n,np.nan); block=np.full(n,-1,dtype=np.int32); age=np.zeros(n,dtype=np.int16); b=-1; a=0; m=np.nan; previous_p=np.nan; anchor=np.nan
 for i in range(n):
  if not valid[i]:a=0;m=np.nan;previous_p=np.nan;continue
  reset=i==0 or not valid[i-1] or seg[i]!=seg[i-1]
  if reset:b+=1;a=0;m=np.nan;anchor=c[i];previous_p=0.
  else:
   p=float(np.log(c[i]/anchor));ret=p-previous_p;previous_p=p;m=ret if a==0 else (1/3)*ret+(1-1/3)*m;a+=1
  block[i]=b;age[i]=a
  if a>=WARM:mu[i]=m
 known=np.isfinite(mu); positive=known&(mu>0)
 k3=known.copy();r3=positive.copy()
 for lag in (1,2):
  k3[lag:] &= known[:-lag] & (block[lag:]==block[:-lag]);k3[:lag]=False
  r3[lag:] &= positive[:-lag];r3[:lag]=False
 r3 &= k3
 return pd.DataFrame(dict(mu5=mu,known=k3,right=r3,mu_known=known,mu_positive=positive,block=block,warm_returns=age,source_valid=valid),index=calendar)
def breadth(sid,cols,known,right):
 k=known[cols];r=right[cols];N=len(cols);K=k.sum(axis=1);n=r.sum(axis=1)
 pair=k&k.shift(3,fill_value=False);pk=pair.sum(axis=1);prior=r.shift(3,fill_value=False)
 enters=(pair&r&~prior).sum(axis=1);leaves=(pair&~r&prior).sum(axis=1)
 return pd.DataFrame(dict(sector=sid,N=N,K=K,n=n,U=N-K,known_fraction=K/N,right_known=n/K.replace(0,np.nan),right_fixed_lower=n/N,right_fixed_upper=(n+N-K)/N,common3_K=pk,common3_current_n=(r&pair).sum(axis=1),common3_prior_n=(prior&pair).sum(axis=1),entered3=enters,left3=leaves,delta3=(enters-leaves)/pk.replace(0,np.nan)),index=known.index)
def main():
 start=time.monotonic(); sm=json.load(open(U/'STOCK_MANIFEST.json')); im=json.load(open(U/'INDUSTRY_MANIFEST.json'));ids=sorted(x['symbol']for x in sm);assert len(ids)==1709
 rosterpath=M/'research_rounds/candidate-snapshot-20261023/full-roster.csv';roster=pd.read_csv(rosterpath);roster=roster[roster.symbol.isin(ids)][['symbol','name','sector_id','sector_name']].copy();assert len(roster)==1709 and not roster.symbol.duplicated().any();assert roster.sector_id.nunique()==90
 industry={x['series']:x for x in im}; calendar=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(x['refs']['CP1_input']).index)for x in im])));calendar=calendar[calendar<=END]
 rows={};audit=[];sources={str(p):sha(p)for p in [Path(__file__),rosterpath,U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',M/'research_rounds/pv-strength-b4-20261025/code/model.py',M/'research_rounds/b5-g1-20261025/code/grade.py']}
 dump('PROTOCOL.json',dict(frozen_before_new_run=True,formula='mu5 EMA of log close returns; alpha=1/3; initialize first return; inherit original G publication warm-up of 64 returns; right iff all three consecutive common-session published mu5 > 0',missing='Any absent/invalid price-volume bar or source segment change resets all EMA/warm-up. No forward fill. UNKNOWN until 64 new contiguous returns and 3 known mu5 observations. Nonpositive including exact zero fails.',diffusion='t versus t-3 on identical member intersection with known three-day status at both endpoints; report entered and left separately; not subtraction of varying-denominator fractions',clock='Union of actual 90-industry index source dates, not weekday calendar; close-known only; raw next-session executions not generated',scope=[START,END],fixed_cases=FIXED,N=1709,industries=90,limitation=['Static current survivors/membership not PIT','Original causal-adjusted source prices; corporate-action announcement availability not verified','mu5 is price-only pace from G, not full price-volume G grade; volume is validity only','Three overlapping days not three independent forecasts','No CP/authorization/order/account or claim of net round win rate'],quick_start='Existing original I/fast-launch probe route is retained unchanged, never gated on waiting for three positive days. New breadth is observation only.',input_hashes=sources))
 roster.to_csv(O/'FIXED_ROSTER.csv',index=False)
 priority=roster[roster.sector_id.eq('URFI881121')].symbol.tolist();ordered=priority+[s for s in ids if s not in priority]
 for ix,sid in enumerate(ordered):
  p=IX/(sid+'.parquet');f=pd.read_parquet(p,columns=['close','volume','segment_id','valid_strength_observation','z5','grade','phase','fresh_up','strength_ready','ix_target']);f=f.loc[:END];sources[str(p)]=sha(p)
  z=calc(f,calendar);native=np.full(len(f),np.nan)
  for _,g in f.groupby('segment_id',sort=False):
   good=g[g.valid_strength_observation];p0=np.log(good.close.to_numpy()/good.close.iloc[0]);r=np.r_[np.nan,np.diff(p0)];vals=pd.Series(r).ewm(alpha=1/3,adjust=False).mean().to_numpy();vals[:64]=np.nan;native[f.index.get_indexer(good.index)]=vals
  cmp=np.isfinite(native)&np.isfinite(f.z5);bad=int(np.sum(np.sign(native[cmp])!=np.sign(f.z5.to_numpy()[cmp])));assert bad==0,(sid,bad)
  # Exact scalar recurrence equivalent to original alpha expression. Sign identity is checked, not claimed bitwise mu identity to absent cache.
  for cut in ['2022-12-01','2024-09-24','2026-05-15']:
   pc=calc(f.loc[:cut],calendar[calendar<=cut]);pd.testing.assert_frame_equal(pc,z.loc[:cut],check_exact=True)
  z['G_grade']=f.grade.reindex(calendar);z['G_fast_launch']=f.phase.eq('fast_launch').reindex(calendar,fill_value=False);z['G_fresh_up']=f.fresh_up.reindex(calendar,fill_value=False);z['original_I']=f.ix_target.reindex(calendar)
  rows[sid]=z.loc[START:END]
  validg=f.reindex(calendar).valid_strength_observation.eq(True);gaps=int((validg&~validg.shift(fill_value=False)).sum())
  audit.append(dict(sid=sid,native_mu_sign_compared=int(cmp.sum()),native_mu_sign_differences=bad,common_blocks=gaps,prefix_cuts=3,prefix_exact=True))
  if ix+1==len(priority):
   k=pd.DataFrame({s:x.known for s,x in rows.items()});r=pd.DataFrame({s:x.right for s,x in rows.items()});b=breadth('URFI881121',priority,k,r);b.index.name='day';b.to_csv(O/'FIRST_SEMICONDUCTOR_DAILY.csv');print('FIRST SEMICONDUCTOR',b.loc[b.index.isin(pd.to_datetime(FIXED))].to_string(),flush=True)
  if (ix+1)%300==0:print('PROGRESS',ix+1,round(time.monotonic()-start,2),flush=True)
 known=pd.DataFrame({s:rows[s].known for s in ids});right=pd.DataFrame({s:rows[s].right for s in ids});mu=pd.DataFrame({s:rows[s].mu5 for s in ids});known.to_parquet(O/'KNOWN3.parquet');right.to_parquet(O/'RIGHT3.parquet');mu.to_parquet(O/'MU5.parquet')
 for col in ['source_valid','warm_returns','block','G_grade','G_fast_launch','original_I']:
  pd.DataFrame({s:rows[s][col] for s in ids}).to_parquet(O/(col.upper()+'.parquet'))
 allb=[]
 for sec,g in roster.groupby('sector_id',sort=True):
  b=breadth(sec,g.symbol.tolist(),known,right);state=pd.read_parquet(industry[sec]['refs']['state']);state=state.set_index(pd.to_datetime(state.day));state=state.reindex(b.index)
  for c in ['E0_valid','E0_episode','stage','stage_before','action','authorization_usable','receipt','new_receipt']:b['sector_'+c]=state[c].to_numpy()
  b['sector_name']=g.sector_name.iloc[0];allb.append(b)
 market=breadth('MARKET1709',ids,known,right);market.index.name='day';market.to_csv(O/'MARKET_DAILY.csv');b=pd.concat(allb);b.index.name='day';b.reset_index().to_parquet(O/'SECTOR_DAILY.parquet',index=False);b[b.index.isin(pd.to_datetime(FIXED))].to_csv(O/'FIXED_DATE_ALL_SECTORS.csv')
 semi=b[b.sector.eq('URFI881121')];semi.to_csv(O/'SEMICONDUCTOR_DAILY.csv');semi[semi.index.isin(pd.to_datetime(FIXED))].to_csv(O/'FIXED_SEMICONDUCTOR.csv')
 snaps=[]
 for sid in ids:
  x=rows[sid];q=x[x.index.isin(pd.to_datetime(FIXED))].copy();q['sid']=sid;snaps.append(q)
 sn=pd.concat(snaps);sn.index.name='day';sn.reset_index().merge(roster,left_on='sid',right_on='symbol',how='left').to_csv(O/'FIXED_DATE_ALL_STOCKS.csv',index=False)
 pd.DataFrame(audit).to_csv(O/'EXACT_AUDITS.csv',index=False)
 yearly=[]
 for sec,gg in [('MARKET1709',market),('URFI881121',semi)]:
  for year,g in gg.groupby(gg.index.year):yearly.append(dict(sector=sec,year=year,days=len(g),mean_known_fraction=g.known_fraction.mean(),mean_right_known=g.right_known.mean(),median_right_known=g.right_known.median(),mean_right_fixed_lower=g.right_fixed_lower.mean(),mean_right_fixed_upper=g.right_fixed_upper.mean(),positive_diffusion_days=int((g.delta3>0).sum()),negative_diffusion_days=int((g.delta3<0).sum())))
 pd.DataFrame(yearly).to_csv(O/'YEARLY_DESCRIPTIVE.csv',index=False)
 bf=b.reset_index();stats=bf.groupby(['sector_stage',bf.day.dt.year]).agg(industry_days=('n','size'),mean_right_known=('right_known','mean'),median_right_known=('right_known','median'),mean_K=('K','mean'),mean_delta3=('delta3','mean')).reset_index();stats.to_csv(O/'STAGE_DESCRIPTIVE.csv',index=False)
 dump('SOURCE_HASHES.json',sources);dump('SUMMARY.json',dict(status='COMPLETE_SIGNAL_BREADTH_ONLY',seconds=time.monotonic()-start,stocks=len(ids),industries=90,dates=len(known),stockdays=known.size,known3=int(known.values.sum()),right3=int(right.values.sum()),native_sign_checks=sum(x['native_mu_sign_compared']for x in audit),native_sign_differences=0,exact_physical_prefixes=3*len(ids),account_runs=0,parameter_searches=0,sources_unchanged=all(sha(p)==h for p,h in sources.items())))
 print('FIXED MARKET',market.loc[market.index.isin(pd.to_datetime(FIXED))].to_string(),flush=True);print('COMPLETE',round(time.monotonic()-start,2),flush=True)
if __name__=='__main__':main()
