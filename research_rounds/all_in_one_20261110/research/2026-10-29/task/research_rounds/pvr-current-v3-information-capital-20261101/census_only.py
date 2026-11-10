"""Receipt census after matching; existing funding only, never forward labels."""
from pathlib import Path
import json,gzip,collections,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;OLD=W/'opportunity-quality-ranking-20261031'
ROOTS={'2022':W/'2022-normal-reference-20261031/runs/B_diag/pair','2025_26':W/'q2-normal-continuation-20261031/runs/B_diag/pair'}
def rows(p):
 with gzip.open(p,'rt') as f:
  for l in f:yield json.loads(l)
def key(x):return x['sid'],x['day'],x['receipt']
result={}
for win,root in ROOTS.items():
 rs=list(rows(OLD/win/'CANDIDATES.jsonl.gz'));ks={key(r) for r in rs};ops={}
 for r in rows(root/'opportunities.jsonl.gz'):
  k=r['sid'],r['day'],r['CP1_id']
  if k in ks:ops[k]=r
 ds={r['at'][:10]:r['on'] for r in rows(root/'daily.jsonl.gz')};dates=list(ds);nxt=dict(zip(dates,dates[1:]));fm=collections.defaultdict(list)
 for i,r in enumerate(rows(root/'funding.jsonl.gz')):fm[r['sid'],r['at'][:10]].append((i,r))
 ff=pd.read_parquet(O/win/'FEATURES.parquet');pairs=pd.read_parquet(O/win/'PAIRS_PRE_OUTCOMES.parquet');featurekeys={(r.symbol,str(r.date.date())):(r.symbol,str(r.date.date()),r.receipt) for r in ff.itertuples()}
 matched={featurekeys[s,p.date] for p in pairs.itertuples() for s in [p.h1_symbol,p.other_symbol]};conflict={featurekeys[s,p.date] for p in pairs.itertuples() if p.pair_kind=='conflict' for s in [p.h1_symbol,p.other_symbol]};census={};details={};counts={a:collections.Counter() for a in ['all','matched_members','conflict_members']}
 for r in rs:
  k=key(r);op=ops[k];nd=nxt.get(r['day']);opening=[(i,x) for i,x in fm[r['sid'],nd] if '09:30:00' in x['at']] if nd else [];mm=[(i,x) for i,x in opening if x['role']=='mobile'];core=[(i,x) for i,x in opening if x['role']=='core' and x['result']=='reserved'];close=[x for i,x in fm[r['sid'],r['day']] if x['role']=='mobile' and '15:10:00' in x['at']];assert len(mm)<=1 and len(close)<=1
  if not ds[r['day']]:stage='ACT_paused'
  elif op['barriers']:stage='authorization_barrier:'+','.join(op['barriers'])
  elif close:stage='authorization_size:'+close[0]['result']
  elif not nd:stage='right_boundary_no_saved_next_open'
  elif core and not mm:stage='core_reserved_suppresses_mobile'
  elif mm:
   x=mm[0][1]
   if x['result']=='reserved':
    confirmed=r['B_diag']['selected'];probe=r['B_diag']['probe_mobile_funded'];assert not(confirmed and probe)
    stage='reserved_confirmed_fill' if confirmed else 'reserved_probe_fill' if probe else 'reserved_no_mobile_fill'
   else:stage='opening:'+x['result']
  else:stage='unknown_no_mobile_funding_record'
  census[k]=stage;details[k]=dict(mobile_open_index=mm[0][0] if mm else None,mobile_result=mm[0][1]['result'] if mm else None,core_reserved=bool(core),next_open=nd)
  for group in ['all']+(['matched_members'] if k in matched else [])+(['conflict_members'] if k in conflict else []):counts[group][stage]+=1
 assert sum(counts['all'].values())==len(rs);assert sum(counts['matched_members'].values())==2*len(pairs)
 pairscontext=collections.Counter();perpair=[]
 for p in pairs.itertuples():
  a,b=featurekeys[p.h1_symbol,p.date],featurekeys[p.other_symbol,p.date];x,y=details[a],details[b];tag='other_observed_context'
  for left,right in [(a,b),(b,a)]:
   xx,yy=details[left],details[right]
   if xx['mobile_result']=='reserved' and yy['mobile_result'] and any(s in yy['mobile_result'] for s in ['pool_capital','probe_risk','sector_capital','sector_risk','confirmed_unfunded','cash']) and xx['mobile_open_index']<yy['mobile_open_index']:
    tag='one_member_mobile_reserved_before_other_resource_rejection';break
  if tag=='other_observed_context' and (x['core_reserved'] or y['core_reserved']):tag='same_stock_core_reservation_channel_present'
  pairscontext[tag]+=1;perpair.append(dict(pair_id=p.pair_id,pair_kind=p.pair_kind,h1_member_stage=census[a],other_member_stage=census[b],context=tag,actionable_fixed_state_substitution_proven=False))
 result[win]=dict(receipts=len(rs),mutually_exclusive_mobile_chain={k:dict(v) for k,v in counts.items()},pair_observed_contexts=dict(pairscontext),validated_substitutions=0,context_is_not_causality=True)
 d=O/win/'PAIRED_CAPITAL_CONTEXT_PRE_OUTCOMES.json';d.write_text(json.dumps(perpair,ensure_ascii=False,indent=2)+'\n')
(O/'MOBILE_CHAIN_CENSUS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
