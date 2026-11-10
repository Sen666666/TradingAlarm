from pathlib import Path
from collections import Counter
from decimal import Decimal,localcontext
import json,hashlib,gzip,math
import numpy as np,pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4')
B=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
T=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
D=Decimal
read=lambda p:json.loads(Path(p).read_text())
manifest=read(O/'SOURCE_SHA256.json')
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in manifest.items())
cat=read(B/'industry-coverage/run-v1/NODE_CATALOGUE.json')
nodes={x['sector']:x for x in cat if x['domain']=='NATIVE1709'}
assert len(nodes)==90
saved=pd.read_parquet(O/'INDUSTRY_DAILY_BEHAVIOR.parquet')
contexts=read(O/'INDUSTRY_CONTEXTS.json')
stats=read(O/'INDUSTRY_BEHAVIOR_SUMMARY.json')
cases={'2022':('2022-01-01','2022-12-31'),'2023':('2023-01-01','2023-12-31'),'POST924':('2024-09-24','2024-12-31'),'2026H1':('2026-01-01','2026-06-30')}
checks={}
for case,(lo,hi) in cases.items():
 a=saved[saved.case.eq(case)]
 assert not a.duplicated(['sector','day']).any()
 assert set(a.sector)==set(nodes)
 counts=a.groupby('sector').size();assert counts.nunique()==1
 assert len(a)==stats[case]['industry_observations']
 assert a.day.nunique()==stats[case]['days']
 for field in ['live_observations','literal_tier_days','literal_tier_days_with_no_new_awarded_high']:
  col={'live_observations':'live_context','literal_tier_days':'literal_tier_event','literal_tier_days_with_no_new_awarded_high':'not_above_last_awarded_high'}[field]
  assert int(a[col].sum())==stats[case][field]
 checks[case]={'rows':len(a),'days':a.day.nunique(),'literal_days':int(a.literal_tier_event.sum()),'recycled_lower_high_days':int(a.not_above_last_awarded_high.sum())}
# Direct manual raw-input windows, all stored semiconductor origins/promotions, plus electronic chemicals.
key=[]
for sector in ['URFI881121','URFI881145']:
 if sector not in nodes:continue
 n=nodes[sector];p=pd.read_parquet(n['input_file']);d=pd.read_parquet(n['daily_result_path']);d.index=pd.DatetimeIndex(d.index)
 cs=[c for c in contexts if c['sector']==sector]
 if sector!='URFI881121':cs=[c for c in cs if c['start']>='2026-01-01']
 for c in cs:
  start=pd.Timestamp(c['start']);i=p.index.get_loc(start)
  assert float(p.iloc[i].price_input)==c['start_price']
  assert float(p.iloc[i].breadth)==c['start_breadth']
  if c['origin']=='break_started':
   history=p.iloc[i-63:i].price_input
   assert len(history)==63 and history.notna().all()
   assert c['start_price']>history.max() and c['start_price']>p.iloc[i-1].price_input and c['start_breadth']>.6
   assert 'break_started' in list(d.loc[start].events)
  # Scan from origin to known end and independently require ACTIVE/no pending, prior20 same source, full20.
  stop=pd.Timestamp(c['ended']) if c['ended'] else d.index[-1]+pd.Timedelta(days=1)
  expected=[]
  for at in d.index[(d.index>start)&(d.index<stop)]:
   j=p.index.get_loc(at);h=p.iloc[max(0,j-20):j]
   row=d.loc[at]
   if len(h)!=20 or h.price_input.isna().any():continue
   if h.price_source_segment_id.isna().any() or any(h.price_source_segment_id != p.iloc[j].price_source_segment_id):continue
   if row['mode']!='ACTIVE' or pd.notna(row.pending_failure_at):continue
   if pd.notna(row.close) and pd.notna(row.breadth) and row.close>max(h.price_input) and row.breadth>=c['start_breadth']:
    expected.append(str(at.date()))
  assert expected==[e['day'] for e in c['literal_events']]
  assert c['first_promotion']==(expected[0] if expected else None)
  if expected:
   first=pd.Timestamp(expected[0]);wait=p.index.get_loc(first)-i
   change=(p.loc[first].price_input/p.loc[start].price_input-1)*100
   assert wait==c['wait_observations'] and abs(change-c['price_change_before_promotion_pct'])<1e-10
  key.append({k:c.get(k) for k in ['industry','start','origin','first_promotion','wait_observations','price_change_before_promotion_pct','ended']})
semi=[c for c in contexts if c['industry']=='半导体' and c['start']>='2026-01-01']
assert [(c['start'],c['first_promotion']) for c in semi]==[('2026-01-07','2026-01-09'),('2026-04-27','2026-05-06'),('2026-06-17','2026-06-18')]
old=next(c for c in contexts if c['industry']=='半导体' and c['start']=='2024-09-30')
assert old['first_promotion']=='2024-10-08' and old['ended']=='2024-10-11' and abs(old['price_change_before_promotion_pct']-18.19690534953997)<1e-12
assert saved[saved.case.eq('2022')&saved.industry.eq('半导体')&saved.day.eq('2022-01-04')].iloc[0].context_start=='2021-11-19'
# All126 group denominator and exact layer purchase/net arithmetic against previous independently checked source.
stock=read(O/'SEMICONDUCTOR_ALL126_COMPARISON.json');groups=read(O/'SEMICONDUCTOR_GROUP_SUMMARY.json')
summary=read(T/'loss_correction/no60_behavior_v1/SEMICONDUCTOR_HOLD_EXIT_REENTRY_SUMMARY.json')
weekly=read(O/'SEMICONDUCTOR_WEEKLY_CHAIN.json');daily=read(O/'SEMICONDUCTOR_DAILY_MONEY.json')
financial={}
with localcontext() as ctx:
 ctx.prec=70
 for pol in ['PVR_BASELINE','PVR_NO60']:
  a=[r for r in stock if r['policy']==pol];assert len(a)==126 and len({x['sid'] for x in a})==126
  ss=[r for r in groups if r['policy']==pol];assert sum(x['stocks'] for x in ss)==126
  orig=summary[pol]['all_actual_layers']
  buy=sum((D(x['buy_cost']) for x in orig),D(0));net=sum((D(x['net']) for x in orig),D(0))
  ww=[r for r in weekly if r['policy']==pol]
  assert sum(r['actual_all_role_filled_layers'] for r in ww)==len(orig)
  assert abs(sum(D(str(r['actual_buy_cost'])) for r in ww)-buy)<D('.0000001')
  assert abs(D(str(daily[pol][-1]['cumulative_H1_wealth']))-net)<D('.0000001')
  assert len(daily[pol])==116 and len({r['day'] for r in daily[pol]})==116
  for g in ss:
   rows=[r for r in a if r['group']==g['group']]
   assert len(rows)==g['stocks']
   labels=[r['H1_price_return_pct'] for r in rows if r['H1_price_return_pct'] is not None]
   assert len(labels)==g['known_H1_price_labels']
   if labels:assert abs(float(np.median(labels))-g['H1_price_return_median_pct'])<1e-10
  financial[pol]={'layers':len(orig),'filled_stocks':len({r['sid'] for r in orig}),'buy_cost':str(buy),'derived_net':str(net),'full126':len(a),'weekly_rows':len(ww)}
res={'status':'PASS_WITH_SCOPE','source_manifest_files_checked':len(manifest),'full_domain_denominators':checks,'manual_raw_window_contexts':key,'semiconductor_financial_reaggregation':financial,'scope':'No rerun of F1 algorithm or financial account. Native saved inputs/states directly recomputed selected origins and all semiconductor event conditions; complete saved output census and derived financial aggregation checked. Market-layer evidence does not imply account permission, returns, or deleted-trade savings.','new_accounts':0}
res['reviewed_source_sha256']={str(O/n):hashlib.sha256((O/n).read_bytes()).hexdigest() for n in ['short_verify.py','INDUSTRY_BEHAVIOR_SUMMARY.json','INDUSTRY_CONTEXTS.json','SEMICONDUCTOR_WEEKLY_CHAIN.json','SEMICONDUCTOR_GROUP_SUMMARY.json','SOURCE_SHA256.json']}
(O/'review/SHORT_VERIFY_RESULT_AUDIT.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
print(json.dumps(res,ensure_ascii=False,indent=2))
