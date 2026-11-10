"""All original pause episodes + independent A clauses/context; no account path."""
from pathlib import Path
from collections import Counter,defaultdict
import json,gzip,hashlib
import pandas as pd
import numpy as np
HERE=Path(__file__).resolve().parent;T=HERE.parent;O=T/'pvr_pool_feasibility/a_recovery_full_diagnostic';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stream(p):
 with gzip.open(p,'rt')as f:
  for line in f:yield json.loads(line)
def main():
 frozen=read(O/'PROTOCOL_FREEZE.json');src=read(O/'SOURCE_SHA256.json')
 for p,h in {**frozen['sources'],**src}.items():assert sha(p)==h,p
 f=pd.read_csv(W/'mainline-absolute-Q4-20261031/recovery.csv',index_col=0,parse_dates=True);kpath=next(Path(p)for p in frozen['sources']if p.endswith('/NATIVE1709/market.parquet'));k=pd.read_parquet(kpath).reindex(f.index)
 known=k.price_observed.eq(True)&k.price_input.gt(0)&k.breadth.notna()&k.breadth_industries_ready.ge(8);assert np.max(abs(f.market-k.market_as_run))<1e-12
 clauses={}
 for j,d in enumerate(f.index):
  if j<63:continue
  prior=f.market.iloc[j-63:j];a=bool(known.iloc[j]and known.iloc[j-63:j].all()and f.market.iloc[j]>sum(prior)/63 and f.market.iloc[j]>f.market.iloc[j-1]and f.breadth.iloc[j]>.6);clauses[str(d.date())]=a
 cases=['2022-06-01','2023-07-25','2024-03-01'];metrics={};allcounts={};epcounts={}
 for ref,run in [('2022_2024',T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair'),('strong',T/'pvr_pool_feasibility/runs/2025_26/pair')]:
  with gzip.open(run/'B.json.gz','rt')as h:b=json.load(h)
  rr=[x for x in b['audit']if x['kind']=='risk_checkpoint'];export=read(O/(ref+'_ALL_PAUSED_ROWS.json'));byday={x['day']:x for x in export};episodes=read(O/(ref+'_ALL_EPISODES.json'));assert len(rr)==(726 if ref=='2022_2024'else 242)
  previous=True;active=None;inc=[];derived=[];visited=[]
  for x in rr:
   day=x['at'][:10]
   if x.get('event')=='pause':assert previous and not x['on']and active is None;active={'pause':day,'firstA':None,'resume':None}
   if active is not None:
    r=byday[day];visited.append(day);eligible=not previous and x['flat'];a=clauses[day]
    assert (r['old_pre_on'],r['old_post_on'],r['original_flat'])==(previous,x['on'],x['flat'])
    assert r['A_input']==a and r['eligible_old_paused_flat']==bool(eligible)and r['A_incremental']==bool(eligible and a and not x['breakout'])
    if r['A_incremental']:
     inc.append(day)
     if active['firstA']is None:active['firstA']=day
    if day in cases:
     assert eligible and a and not x['breakout'];j=f.index.get_loc(pd.Timestamp(day));z={'original_pre_on':previous,'original_post_on':x['on'],'original_flat':x['flat'],'original_event':x.get('event'),'episode_pause':active['pause'],'M':float(f.market.iloc[j])}
     for horizon in [21,63]:
      vals=f.market.iloc[j:j+horizon+1].to_numpy(float);assert len(vals)==horizon+1 and known.iloc[j:j+horizon+1].all();rel=vals/vals[0]-1;dd=vals/np.maximum.accumulate(vals)-1;published=r['future_market_context'][str(horizon)]
      values={'end_change':float(rel[-1]),'max_up':float(max(rel)),'max_down':float(min(rel)),'max_peak_drawdown':float(min(dd))}
      for key,value in values.items():assert abs(value-published[key])<1e-12
      z[str(horizon)]=values
     metrics[day]=z
    if x.get('event')=='resume':active['resume']=day;derived.append(active);active=None
   previous=bool(x['on'])
  if active is not None:derived.append(active)
  assert set(visited)==set(byday)and len(visited)==len(byday)
  assert len(derived)==len(episodes)
  for a,b in zip(derived,episodes):assert (a['pause'],a['firstA'],a['resume'])==(b['pause_day'],b['first_incremental_A']['day']if b['first_incremental_A']else None,b['resume_day']);assert b['right_censored']==(a['resume']is None)
  epcounts[ref]=derived;allcounts[ref]={'closes':len(rr),'pause_episodes':len(derived),'incremental_days':len(inc),'right_censored':sum(x['resume']is None for x in derived)}
  # Actual source stock-day counts, independent of derived opportunity exports.
  counts={d:Counter()for d in inc};denom=Counter()
  for q in stream(run/'opportunities.jsonl.gz'):
   d=q['day'];denom[d]+=1
   if d not in counts:continue
   c=counts[d];c['all_stock_days']+=1;c['core_Q_true']+=q['core_Q']is True;c['mobile_Q_true']+=q['mobile_Q']is True;c['raw_fresh_CP1']+=bool(q['CP1_id']);c['fresh_CP1_mobile_Q_true']+=bool(q['CP1_id'])and q['mobile_Q']is True;c['original_core_role']+='core'in q['roles'];c['original_mobile_role']+='mobile'in q['roles'];c['non_ACT_barrier_free_role_events']+=len(q['roles'])if not [a for a in q['barriers']if a!='ACT_paused']else 0
  assert len(denom)==len(rr)and set(denom.values())=={1709}
  for d,c in counts.items():assert +c==+Counter(byday[d]['Q_freshCP1_counts'])
  if ref=='2022_2024':
   for d in cases:metrics[d]['source_opportunity_counts']=dict(counts[d])
 out={'status':'PASS_OBSERVED_EPISODES_CLAUSES_FUTURE_CONTEXT_AND_SOURCE_SIGNAL_COUNTS','all_mothers':allcounts,'episode_firsts':epcounts,'three_priority_cases':metrics,'source_SHA_checks':len({**frozen['sources'],**src}),'reviewer_source_SHA256':sha(__file__),'reviewer_account_events':0,'priority_verdict':'DO_NOT_PROMOTE_A_OR_OPEN_SMALL_ACCOUNT; MOVE_TO_SIGNAL_QUALITY','scope':'All726+242original ACT clocks and3/0pauseepisodes, complete31incremental days, full1709stockday denominators andrawQ/CP1role counts independently checked. Direct63prior mean excludes current; knownmask uses frozen observable coverage. Threepriority21/63futureM summaries independently computed. SyntheticM changes/DD are context, not tradable or account PnL. March1is later in the original July2023pause, not an independent newA recovery after hypotheticalJuly25entry; do not copy originalflat/NAV/ACTfuture. Fullminimumunit/resource admission not proved, no newcandidate account. PositiveJune2022context retained; earlyJuly2023negativecontext plus limited A scope and old12case early-recovery costs justify priority rejection, not proof every causalA portfolio would lose.'}
 (HERE/'A_RECOVERY_FULL_DOMAIN_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items()if k not in ['three_priority_cases']},indent=2));print(json.dumps(metrics,indent=2))
if __name__=='__main__':main()
