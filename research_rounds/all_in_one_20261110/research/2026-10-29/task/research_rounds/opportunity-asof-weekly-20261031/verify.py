"""Independent saved-row as-of reconstruction and bounded clock counterexamples."""
from pathlib import Path
import json,gzip,statistics,hashlib,copy
import pandas as pd
import analyze as A
O=Path(__file__).resolve().parent;W=O.parent
def read(p):return json.loads(p.read_text())
def rows(p):
 with gzip.open(p,'rt') as h:return [json.loads(x) for x in h]
def close(a,b):
 assert (a is None)==(b is None)
 if a is not None:assert abs(a-b)<1e-11,(a,b)
def direct_mean(rs,key):
 buckets={}
 for r in rs:buckets.setdefault(r[key],[]).append(r['return_pct'])
 return statistics.mean(statistics.mean(x) for x in buckets.values()) if buckets else None
def main():
 tests=[];total=0
 for win,(lo,hi) in A.WINDOWS.items():
  cp=W/'opportunity-quality-ranking-20261031'/win;cs=rows(cp/'CANDIDATES.jsonl.gz');ls={(r['sid'],r['day'],r['receipt']):r['labels']['21'] for r in rows(cp/'PRICE_LABELS.jsonl.gz')};weekly=read(O/win/'WEEKLY.json')
  for r in weekly:
   universe=cs if r['variant']=='all_events' else [c for c in cs if c['first_complete_attempt']]
   if r['variant']=='first_new_attempt':assert all(lo<=c['attempt_probe_day']<=hi and not c['attempt_inherited'] for c in universe)
   observed=[];future=[]
   for c in universe:
    label=ls[c['sid'],c['day'],c['receipt']]
    if label['valid'] and label['end_day']<=r['checkpoint'] and label['end_day']>=r['week_start']:
     assert c['day']<label['end_day'];observed.append(dict(return_pct=label['return_pct'],end_day=label['end_day']))
    if r['next_week_start']<=c['day']<=r['next_week_end']:
     future.append((c,label))
   close(direct_mean(observed,'end_day'),r['known']['mean']);assert len(observed)==r['known']['events'];assert A.group(r['known']['mean'])==r['known_group'];assert len(future)==r['future']['events']
   labelled=[dict(day=c['day'],return_pct=l['return_pct']) for c,l in future if l['valid']];close(direct_mean(labelled,'day'),r['future']['mean']);assert len(labelled)==r['future']['labelled']
   assert all(c['day']>r['checkpoint'] for c,l in future)
   if r['future_week_truncated']:assert not r['main_comparison_eligible']
   assert not any('MFE' in k or 'MAE' in k or 'tail' in k for k in r['known'])
   total+=1
  tests.append(dict(window=win,checkpoint_variant_rows_checked=len(weekly),independent_daily_equal_means_match=True,strict_maturity_before_asof=True,future_all_candidates_before_label_availability_filter=True,inherited_not_called_first=True))
 # Delayed observation: receipt authorization is old but its true21st valid
 # price observation is still later. Never substitute a theoretical21st session.
 def sample(day,end,value):return dict(sid='S',sector='G',day=day,label=dict(valid=True,end_day=end,return_pct=value,right_tail_MFE30=True))
 fixtures=[sample('2026-01-01','2026-02-03',-2.),sample('2026-01-02','2026-02-04',4.),sample('2026-01-03','2026-02-10',999.)]
 def known(at,rs):return A.stats([r for r in rs if '2026-02-02'<=r['label']['end_day']<=at],'maturity')
 x=known('2026-02-06',fixtures);close(x['mean'],1.);assert x['events']==2
 changed=copy.deepcopy(fixtures);changed[-1]['label']['return_pct']=-999999.;assert known('2026-02-06',changed)==x
 assert A.group(A.stats([],'maturity')['mean'])=='unknown';assert A.group(0.)=='zero'
 assert A.monday('2026-06-30')=='2026-06-29';assert A.monday('2026-07-03')=='2026-06-29'
 positive=read(O/'2025_26/WEEKLY.json');assert not any(r['checkpoint']=='2026-06-30' for r in positive);assert all(r['future_week_truncated'] for r in positive if r['checkpoint']=='2026-06-26')
 market=pd.read_csv(W/'mainline-absolute-Q4-20261031/recovery.csv',index_col=0,parse_dates=True)
 for win in A.WINDOWS:
  for r in read(O/win/'WEEKLY.json'):
   s=market.loc[:r['checkpoint'],'market'];close(float((s.iloc[-1]/s.iloc[-22]-1)*100),r['market_R21_asof_pct'])
 tests+= [dict(test='late_actual_observation_not_prematurely_mature',passed=True),dict(test='future_return_perturbation_leaves_known_unchanged',passed=True),dict(test='unknown_distinct_from_exact_zero',passed=True),dict(test='midweek_window_boundary_no_false_checkpoint',passed=True),dict(test='current_market_recomputed_from_asof_prefix_only',passed=True)]
 frozen=read(O/'FREEZE.json');changed=[p for p,h in frozen['source_SHA256'].items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h];assert not changed,changed
 A.save('VERIFICATION.json',dict(passed=True,rows_verified=total,checks=tests,all_input_source_hashes_unchanged=True,new_account_runs=0))
 print('VERIFIED rows',total,'checks',len(tests),'account_runs0')
if __name__=='__main__':main()
