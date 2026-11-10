from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal,localcontext
import json,gzip,hashlib
import pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4/reentry_v1');T=O.parent.parent/'task';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');D=Decimal
read=lambda p:json.loads(Path(p).read_text())
features=read(O/'ALL_FEATURES_PRE_OUTCOME.json');cross=read(O/'ACTUAL_REENTRY_CROSS.json');summary=read(O/'ACTUAL_REENTRY_SUMMARY.json');coverage=read(O/'COVERAGE_SUMMARY.json');slots=read(O/'FLAT_INTERVALS.json')
freeze=read(O/'PRE_OUTCOME_FREEZE.json');assert hashlib.sha256((O/'ALL_FEATURES_PRE_OUTCOME.json').read_bytes()).hexdigest()==freeze['feature_sha256']
assert len({(r['window'],r['sid'],r['day'],r['role']) for r in features})==len(features)
roots={'long':T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair','strong':T/'pvr_pool_feasibility/runs/2025_26/pair'}
books={};cals={};nativeflat={}
for label,root in roots.items():
 with gzip.open(root/'B.json.gz','rt') as f:b=json.load(f)
 books[label]=b
 with gzip.open(root/'daily.jsonl.gz','rt') as f:daily=[json.loads(l) for l in f]
 cals[label]=pd.DatetimeIndex([x['at'][:10] for x in daily]);end=str(cals[label][-1].date())+' 23:59:59+08:00'
 # Independent interval sweep from native layer opened/closed, ignoring entry-action labels.
 events=defaultdict(list)
 for l in b['layers']:
  events[l['sid']].append((l['opened'],1,l['id']))
  if l['closed']:events[l['sid']].append((l['closed'],0,l['id']))
 got={}
 for sid,evs in events.items():
  live=set();campaign=set();out=[]
  for at,kind,lid in sorted(evs):
   if kind==1:
    if not live:
     if out:out[-1]['next_actual_buy_at']=at;out[-1]['end_at']=at
     campaign=set()
    live.add(lid);campaign.add(lid)
   else:
    assert lid in live;live.remove(lid)
    if not live:out.append({'flat_at':at,'next_actual_buy_at':None,'end_at':end,'closed_layer_ids':sorted(campaign)})
  got[sid]=out
 for sid,ss in slots[label].items():
  assert len(ss)==len(got.get(sid,[])),(label,sid,'slot count')
  for a,z in zip(ss,got.get(sid,[])):
   for k in ['flat_at','next_actual_buy_at','end_at']:assert a[k]==z[k],(label,sid,k,a[k],z[k])
   assert sorted(a['closed_layer_ids'])==z['closed_layer_ids']
 nativeflat[label]=sum(len(v) for v in got.values())
 assert nativeflat[label]==coverage[label]['all_flat_intervals']
for r in features:
 at=r['day']+' 15:10:00+08:00'
 s=next(z for z in slots[r['window']][r['sid']] if z['flat_at']==r['flat_at'])
 assert s['flat_at']<=at<s['end_at']
for label in roots:
 for role in ['mobile','core']:
  rs=[r for r in features if r['window']==label and r['role']==role]
  assert len(rs)==coverage[label]['by_role'][role]['events']
  assert dict(Counter(r['local_high_status'] for r in rs))==coverage[label]['by_role'][role]['local_high']
with localcontext() as ctx:
 ctx.prec=70
 for s in summary:
  rs=[x for x in cross if (x['window'],x['role'],x['classification'])==(s['window'],s['role'],s['status'])]
  assert len(rs)==s['layers']
  for key,pred in [('original_lifecycle_net',lambda n:True),('original_positive_net',lambda n:n>0),('original_negative_net',lambda n:n<0)]:
   n=sum((D(x['net']) for x in rs if pred(D(x['net']))),D(0));assert abs(n-D(s[key]))<D('1e-19')
  assert len({r['sid'] for r in rs})==s['stocks']
sm={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
# Pick prescribed outcome controls mechanically, do not modify feature definitions.
fail=max((r for r in cross if r['window']=='strong' and r['role']=='mobile' and r['classification']=='FAIL'),key=lambda x:D(x['net']))
passed=min((r for r in cross if r['window']=='strong' and r['role']=='mobile' and r['classification']=='PASS'),key=lambda x:D(x['net']))
controls=[]
for r in [fail,passed]:
 q=r['feature'];sid=r['sid'];cal=cals['strong'];start=pd.Timestamp(q['flat_at'][:10]);day=pd.Timestamp(q['day'])
 f=pd.read_parquet(sm[sid]['refs']['facts'],columns=['close','segment_id']);cp=pd.read_parquet(sm[sid]['refs']['CP1'],columns=['receipt','frontier','reset_reason'])
 observations=cal[(cal>=start)&(cal<day)];h=f.reindex(observations)
 assert len(observations)==q['local_high_observations'] and h.close.notna().all() and h.segment_id.notna().all()
 assert h.segment_id.nunique()==1 and h.segment_id.iloc[0]==f.loc[day].segment_id
 high=float(max(h.close));assert high==q['prior_postexit_high']
 assert float(f.loc[day].close)==q['signal_close']
 status='PASS' if f.loc[day].close>high else 'FAIL';assert status==q['local_high_status']
 assert bool(cp.loc[day].receipt)
 c=cp.reindex(cal[(cal>=start)&(cal<=day)]);reasons=dict(Counter(str(v) for v in c.reset_reason.dropna() if v!='receipt_consumed'))
 assert reasons==q['nonreceipt_CP1_reset_reasons']
 low=bool(((c.frontier<c.frontier.shift(1))|(c.frontier.isna()&c.frontier.shift(1).notna())).any());assert low==q['frontier_cleared_or_lowered_in_postexit_window']
 # Original pre-entry stock has no surviving native layer at decision close.
 timestamp=q['day']+' 15:10:00+08:00'
 live=[l for l in books['strong']['layers'] if l['sid']==sid and l['opened']<=timestamp and (l['closed'] is None or l['closed']>timestamp)]
 assert not live
 native=next(l for l in books['strong']['layers'] if l['id']==r['layer'])
 assert native['opened']==r['opened'] and native['sid']==sid
 controls.append({'layer':r['layer'],'sid':sid,'name':r['name'],'classification':status,'signal_day':q['day'],'actual_flat_at':q['flat_at'],'max_prior_close':high,'max_prior_close_date':str(h.close.idxmax().date()),'signal_close':float(f.loc[day].close),'all_anchor_observations_strictly_before_signal':bool((observations<day).all()),'reset_reasons':reasons,'frontier_lower_or_cleared':low,'original_lifecycle_net':r['net'],'original_still_open_qty':r['qty'],'actual_closed_at':native['closed']})
resetstats={}
for label in roots:
 rs=[r for r in features if r['window']==label and r['role']=='mobile' and r['local_high_status']=='FAIL']
 assert all(r['nonreceipt_CP1_reset_reasons'] for r in rs)
 resetstats[label]={'mobile_FAIL_events':len(rs),'flagged_clear_or_lower':sum(r['frontier_cleared_or_lowered_in_postexit_window'] for r in rs),'window_starts_already_unprepared_or_invalid':sum(not r['frontier_cleared_or_lowered_in_postexit_window'] for r in rs),'all_have_nonreceipt_reset_reasons':True}
# Directly verify one unknown specimen per window with the full common calendar, not compressed valid observations.
unknowns=[]
for label in roots:
 q=next(r for r in features if r['window']==label and r['role']=='mobile' and r['local_high_status']=='UNKNOWN_PRICE_OR_SOURCE')
 f=pd.read_parquet(sm[q['sid']]['refs']['facts'],columns=['close','segment_id']);day=pd.Timestamp(q['day']);cal=cals[label];ix=cal[(cal>=pd.Timestamp(q['flat_at'][:10]))&(cal<day)];h=f.reindex(ix)
 missing=int(h.close.isna().sum());crosssource=bool(h.segment_id.isna().any() or h.segment_id.nunique()!=1 or h.segment_id.iloc[0]!=f.loc[day].segment_id)
 assert missing or crosssource
 unknowns.append({'window':label,'sid':q['sid'],'day':q['day'],'shared_calendar_observations':len(ix),'missing_price_rows':missing,'unknown_or_changed_source':crosssource})
res={'status':'PASS_WITH_SCOPE','native_layer_interval_sweep':nativeflat,'feature_freeze_sha256':freeze['feature_sha256'],'FAIL_reset_summary_from_complete_saved_features':resetstats,'raw_input_counterexamples':controls,'shared_calendar_unknown_specimens':unknowns,'scope':'Native layer open/close interval sweep independently matched all original flat intervals without using entry-action grouping; not a new account replay. Counterexample high/reset tests directly use facts/CP1 with t excluded. Complete saved feature counts and original outcome sums reaggregated. Origin stock-Q/canonical formation and all15311 mobile event highs were not independently regenerated.','conclusion':'Close gate is materially nonredundant on long flat windows spanning resets, but rejects a known strong winner and leaves known failures. It cannot create same-state resource permission; does not support account implementation.','new_accounts':0,'source_sha256':{str(O/n):hashlib.sha256((O/n).read_bytes()).hexdigest() for n in ['PROTOCOL.txt','event_check.py','ALL_FEATURES_PRE_OUTCOME.json','COVERAGE_SUMMARY.json','ACTUAL_REENTRY_CROSS.json','ACTUAL_REENTRY_SUMMARY.json','FLAT_INTERVALS.json','PRE_OUTCOME_FREEZE.json']}}
(O/'review/EVENT_CHECK_RESULT_AUDIT.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps(res,ensure_ascii=False,indent=2))
