"""Original held CLOSE scope of I on/native E0 negative leg, no alternative exits/returns."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;E=O.parents[1];W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');S={}
def read(p):p=Path(p);S[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
def agg(z):return dict(layers=len(z),stocks=len({e['sid'] for e in z}),cost=sum((D(e['cost']) for e in z),D(0)),net=sum((D(e['net']) for e in z),D(0)),positive_net=sum((D(e['net']) for e in z if D(e['net'])>0),D(0)),negative_net=sum((D(e['net']) for e in z if D(e['net'])<0),D(0)))
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};req=defaultdict(list);mother={};obs=Counter()
for ref in ['2022_2024','strong']:
 mother[ref]={x['layer']:x for x in read(O/(ref+'_NATIVE_EVENT_ROWS.json'))};p=E/'dec2022_authorization_v1/signal_context/held_h2_diagnostic'/(ref+'_ALL_HELD_RS_EMA_CONTEXT.jsonl');S[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 with p.open() as f:
  for line in f:
   x=json.loads(line);obs[ref]+=1;req[x['sid']].append(x)
first=defaultdict(dict);allcounts=defaultdict(Counter)
for sid,requests in sorted(req.items()):
 m=sm[sid];p=next(Path(p) for p in m['source_sha256'] if p.endswith('/events.parquet'));s=hashlib.sha256(p.read_bytes()).hexdigest();assert s==m['source_sha256'][str(p)];S[str(p)]=s;ev=pd.read_parquet(p)
 for x in requests:
  ref=x['window'];dt=pd.Timestamp(x['at'][:10]);c=allcounts[ref];c['held_CLOSEs']+=1
  if dt not in ev.index or pd.isna(ev.loc[dt,'leg_direction']):c['unknown_native_leg']+=1;continue
  r=ev.loc[dt];isnegative=int(r.leg_direction)==-1;Ion=x['context'].get('stock_I_target') is True
  if Ion and isnegative:
   c['I_on_negativeleg_held_CLOSEs']+=1;c['I_on_negativeleg_'+x['original_priority_status']]+=1
   if x['original_priority_status']=='ORIGINAL_ACT_I_ON_LAYER_NOT_PENDING':
    c['conservative_pre_request_negativeleg_CLOSEs']+=1;e=mother[ref][x['layer']]
    if e['layer'] not in first[ref]:first[ref][e['layer']]=dict(window=ref,layer=e['layer'],sid=sid,name=e['name'],role=e['role'],action=e['action'],opened=e['opened'],decision_at=e['decision_at'],cost=e['cost'],net=e['net'],first_original_path_negativeleg_pre_request_CLOSE=x['at'],is_same_day_new_negative_event=int(r.event)==-1,current_event=int(r.event),I_target=True,native_leg_direction=-1,causal_close=x['context']['causal_close'],source_segment=x['context']['source_segment'],original_priority_status=x['original_priority_status'],interpretation='condition/request scope only; future original contribution is not avoidable loss or alternative trade PnL')
summary={};allrows=[]
for ref,mm in first.items():
 z=list(mm.values());allrows+=z;summary[ref]=dict(observations=dict(allcounts[ref]),affected_original_layers=agg(z),by_role={r:agg([x for x in z if x['role']==r]) for r in ['core','mobile']},by_first_event_kind={str(v):agg([x for x in z if x['is_same_day_new_negative_event']==v]) for v in [True,False]})
 for tailname in [ref]:
  cc=[]
  for c in read(E/'local_high'/(ref+'_FIXED_TAILS.json')):
   matching=[x['layer'] for x in c['matched_actual_No60_rows']];hit=[mm[l] for l in matching if l in mm];cc.append(dict(original=c['original'],all_matched_No60_layers=matching,hit_No60=hit))
  save(ref+'_HELD_NEGATIVELEG_FIXED_WINNERS.json',cc);summary[ref]['fixed_original_tail_control']=dict(original_members=len(cc),matched_original_members=sum(bool(c['all_matched_No60_layers']) for c in cc),hit_original_members=sum(bool(c['hit_No60']) for c in cc),hit_original_No60_contribution=agg([x for c in cc for x in c['hit_No60']]))
summary['post_Oct8_303']=dict(affected_original_layers=agg([x for x in first['2022_2024'].values() if x['opened'][:10]>'2024-10-08']))
summary['2022_2023']=dict(affected_original_layers=agg([x for x in first['2022_2024'].values() if x['opened'][:4]<'2024']))
save('HELD_NEGATIVELEG_FIRST_SCOPE.json',allrows);save('HELD_NEGATIVELEG_SUMMARY.json',summary);save('HELD_NEGATIVELEG_SOURCES.json',dict(sources=S,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),original_held_rows=dict(obs),no_new_account=True,unknown_RS_derived_priority_kept_separate=True,request_cutoff='first original specific-layer request including same CLOSE excluded, conservative canceled/revived histories never reconstructed',not_claimed='not actual legal execution, not new strategy economics, no next-positive reentry funded/replayed'))
print(json.dumps(summary,default=str,ensure_ascii=False),flush=True)
