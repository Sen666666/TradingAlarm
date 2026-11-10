"""Independent necessary-condition coverage audit; no candidate/account run."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from datetime import datetime
import hashlib,json,math
import pandas as pd

getcontext().prec=60
O=Path(__file__).parent;T=O.parent/'timeline';E=O.parents[1]
M=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/risk_constraints/ma63_information_diagnostic_v1')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
SRC={};FR={};CHECK={};Z=D(0)


def read(p):
 SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 return json.loads(p.read_text())


def at(x):return datetime.fromisoformat(x)


def agg(rr):
 return dict(fills=len(rr),stocks=len({x['sid'] for x in rr}),actual_buycash=sum((D(x['cost']) for x in rr),Z),
             net=sum((D(x['net']) for x in rr),Z),positive=sum((max(Z,D(x['net'])) for x in rr),Z),
             negative=sum((min(Z,D(x['net'])) for x in rr),Z),open_layers=sum(bool(x['qty']) for x in rr))


def chk(rr,saved,label):
 for k,v in agg(rr).items():
  if k in ['fills','stocks','open_layers']:assert v==saved[k],(label,k,v,saved[k])
  else:assert abs(v-D(saved[k]))<D('1e-18'),(label,k,v,saved[k])
 CHECK['money_groups']=CHECK.get('money_groups',0)+1


def frame(sid):
 if sid not in FR:
  p=Path(SM[sid]['refs']['facts']);h=hashlib.sha256(p.read_bytes()).hexdigest()
  assert h==SM[sid]['output_sha256'][str(p)];SRC[str(p)]=h
  FR[sid]=pd.read_parquet(p,columns=['close','segment_id'])
 return FR[sid]


SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
results=read(O/'CEILING_RESULTS.json');alltail=read(M/'ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json')['members']
for ref in ['2022_2024','strong']:
 rr=read(T/(ref+'_DECISION_TIMELINE.json'));old=read(O/(ref+'_CEILING_ROWS.json'));byid={x['layer']:x for x in rr}
 cc=read(T/(ref+'_COMPLETED_STOCK_CYCLES.json'));oo={x['layer']:x for x in old}
 assert len(rr)==len(old)==(2265 if ref=='2022_2024' else 1171)
 for sid,cycles in cc.items():
  seen=set();end=None
  for c in sorted(cycles,key=lambda c:at(c['closed_at'])):
   ids=c['layer_ids'];assert len(ids)==len(set(ids)) and not seen.intersection(ids)
   assert all(byid[lid]['sid']==sid for lid in ids)
   lo=min(at(byid[lid]['actual_fill_at']) for lid in ids)
   hi=at(c['closed_at']);assert lo<hi
   assert all(at(byid[lid]['actual_fill_at'])<hi for lid in ids)
   assert end is None or lo>=end
   end=hi;seen.update(ids)
   CHECK['completed_nonoverlapping_stock_cycles']=CHECK.get('completed_nonoverlapping_stock_cycles',0)+1
 for x in rr:
  sid=x['sid'];y=oo[x['layer']]
  for k in ['layer','sid','role','action','decision_at','actual_fill_at','cost','net','qty']:assert x[k]==y[k],(ref,x['layer'],k)
  # Enumerate completed cycles forward; a nonnegative completion resets the run.
  run=[]
  for c in sorted(cc.get(sid,[]),key=lambda c:at(c['closed_at'])):
   if at(c['closed_at'])>=at(x['decision_at']):continue
   run=run+[c] if D(c['net_trade_cash'])<0 else []
  assert len(run)==y['prior_consecutive_negative_campaigns']
  assert [c['layer_ids'] for c in reversed(run)]==y['prior_negative_cycle_layer_ids']
  assert abs(sum((D(c['net_trade_cash']) for c in run),Z)-D(y['prior_negative_cash']))<D('1e-18')
  CHECK['past_only_streak_rows']=CHECK.get('past_only_streak_rows',0)+1
  if len(run)<2:
   assert y['failure_high_ceiling'] is None and y['no_higher_price_necessary'] is None
   continue
  f=frame(sid);highs=[];segments=[];unknown=False
  for c in run:
   lo=min(byid[lid]['actual_fill_at'][:10] for lid in c['layer_ids']);end=c['closed_at'][:10]
   w=f[(f.index>=pd.Timestamp(lo))&(f.index<pd.Timestamp(end))]
   if w.empty or w.segment_id.nunique()!=1:unknown=True;continue
   assert w.close.notna().all() and all(math.isfinite(float(v)) and float(v)>0 for v in w.close)
   assert w.index[0]>=pd.Timestamp(lo) and w.index[-1]<pd.Timestamp(end)
   assert at(c['closed_at'])<at(x['decision_at'])
   highs.append(float(w.close.max()));segments.append(str(float(w.segment_id.iloc[-1])))
   CHECK['failed_hold_high_windows']=CHECK.get('failed_hold_high_windows',0)+1
  comparable=not unknown and all(seg==x['stock_price_position']['segment_id'] for seg in segments)
  h=max(highs) if comparable else None
  assert y['failure_high_ceiling']==h
  expected=float(x['stock_price_position']['close'])<=h if h is not None else None
  assert y['no_higher_price_necessary']==expected
  CHECK['current_high_comparison_rows']=CHECK.get('current_high_comparison_rows',0)+1
 scopes={'ALL':old}
 if ref=='2022_2024':scopes.update(two_year=[x for x in old if x['actual_fill_at'][:10]<='2023-12-29'],post303=[x for x in old if x['actual_fill_at'][:10]>'2024-10-08'])
 for name,sr in scopes.items():
  s=results[ref][name];two=[x for x in sr if x['prior_consecutive_negative_campaigns']>=2];mobile=[x for x in two if x['role']=='mobile'];nohigh=[x for x in mobile if x['no_higher_price_necessary'] is True]
  assert not any(x['action']=='first_actual_participation' for x in mobile)
  for label,rows in [('all',sr),('at_least_two_completed_negative_all_roles',two),('at_least_two_completed_negative_mobile',mobile),('mobile_current_not_above_failed_high',nohigh),('mobile_unknown_high',[x for x in mobile if x['no_higher_price_necessary'] is None])]:chk(rows,s[label],(ref,name,label))
  for action,v in s['by_action'].items():
   for label,rows in [('all',sr),('two_negative_mobile',mobile),('no_higher_price_mobile',nohigh)]:chk([x for x in rows if x['action']==action],v[label],(ref,name,action,label))
 # Match the authoritative complete original83/94 tail roster using its saved
 # cross-arm correspondence, avoiding the candidate's own control labels.
 controls=read(M/(ref+'_ORIGINAL_FIXED_TAIL_COVERAGE.json'))
 assert len(controls)==len(alltail[ref])==(83 if ref=='2022_2024' else 94)
 for c,t in zip(controls,alltail[ref]):assert c['original']==t
 matched={lid for c in controls for lid in c['matched_No60_layers']}
 s=results[ref]['fixed_tail_correspondence'];assert s['original_members']==len(controls) and s['actual_matches']==len(matched)==(45 if ref=='2022_2024' else 67)
 selected=[x for x in old if x['layer'] in matched and x['role']=='mobile' and x['prior_consecutive_negative_campaigns']>=2]
 chk(selected,s['two_negative_mobile'],(ref,'tail_two_negative'))
 chk([x for x in selected if x['no_higher_price_necessary'] is True],s['no_higher_price_mobile'],(ref,'tail_no_high'))

SRC[str(O/'coverage_ceiling.py')]=hashlib.sha256((O/'coverage_ceiling.py').read_bytes()).hexdigest()
report=dict(status='PASS_WITH_SCOPE_LIMITS',checks=CHECK,selected_stock_facts_read=len(FR),
 summary={r:{k:v for k,v in results[r].items() if k in ['two_year','post303','ALL','fixed_tail_correspondence']} for r in results},
 interpretation='Necessary-condition historical scope only. No admin/giveback/progress exclusions or historical release latch were applied.',
 limitations=['Cannot call these amounts avoidable loss, policy profit, or a mathematical counterfactual upper bound.',
              'Removing fills changes future cash, rank, quantities, ACT, opportunities and cycle identity; original signed PnL is not a feasible policy.',
              'Current price<=failed-held-close high is necessary only under the proposed anchor convention; once previously released a real latch may remain open. No latch replay was tested.',
              'All negative net trade-cash completions count first, including administrative exits or prior profitable progress; tighter valid definitions can only alter this descriptive eligibility set, not guarantee monetary bounds.',
              'A multi-layer stock campaign counts once, not once per loss layer. AR is separate from tradecash.',
              'Held-close high includes first actual fill day close and excludes liquidation OPEN day close; it is not OHLC intraday high or return-normalized proof.',
              'Full fixed original83/94 and45/67 actual matches preserved, including unmatched; no fabricated losses for unmatched tails.',
              'Read only selected-stock facts; no new engine, account, quantity solver or signal. Original development/survivor/execution limitations remain.'],sources=SRC)
with (O/'INDEPENDENT_CEILING_AUDIT.json').open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2,default=str)
print(json.dumps(dict(status=report['status'],checks=CHECK,selected_stock_facts_read=len(FR)),ensure_ascii=False))
