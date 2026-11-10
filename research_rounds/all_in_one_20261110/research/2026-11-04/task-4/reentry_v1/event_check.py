"""All saved flat intervals/candidates, no strategy/Account/model imports."""
from pathlib import Path
from collections import defaultdict,Counter
from bisect import bisect_right
from decimal import Decimal as D
import json,gzip,hashlib,time,math
import pandas as pd

O=Path(__file__).resolve().parent;T=O.parent.parent/'task'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SRC={}
ROOTS={'long':T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair',
       'strong':T/'pvr_pool_feasibility/runs/2025_26/pair'}
def bind(p):
 p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def gz(p):
 with gzip.open(bind(p),'rt') as f:return [json.loads(x) for x in f]
def frame(p,cols):return pd.read_parquet(bind(p),columns=cols)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,(D,pd.Timestamp)):return str(x)
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def campaigns(es,end):
 cs=defaultdict(list)
 for x in es:
  sid=x['sid']
  if x['action']!='add_to_existing_stock':cs[sid].append([])
  assert cs[sid];cs[sid][-1].append(x)
 out={}
 for sid,groups in cs.items():
  slots=[]
  for j,g in enumerate(groups):
   if any(x['qty'] for x in g):continue
   start=max(x['closed'] for x in g if x['closed']);finish=min(x['opened'] for x in groups[j+1]) if j+1<len(groups) else end+' 23:59:59+08:00'
   assert start<=finish
   slots.append(dict(sid=sid,flat_at=start,next_actual_buy_at=finish if j+1<len(groups) else None,end_at=finish,
     closed_layer_ids=[x['layer'] for x in g],closed_campaign_net=sum((D(x['net']) for x in g),D(0))))
  out[sid]=slots
 return out
def main():
 start=time.monotonic();bind(__file__);bind(O/'PROTOCOL.txt')
 sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 im={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
 rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
 allrows=[];allentries={};allslots={};stats={}
 for label,root in ROOTS.items():
  es=read(T/f'loss_correction/entry_risk_commitment_review/{"2022_2024" if label=="long" else "strong"}_ENTRIES.json');allentries[label]=es
  daily=gz(root/'daily.jsonl.gz');dd={x['at'][:10]:x for x in daily};cal=pd.DatetimeIndex(dd);end=cal[-1].strftime('%Y-%m-%d')
  slots=campaigns(es,end);allslots[label]=slots;by=defaultdict(list);st={}
  for x in gz(root/'opportunities.jsonl.gz'):
   if x['sid'] not in slots or not slots[x['sid']]:continue
   if not (x['CP1_id'] and x['mobile_Q'] is True) and 'core' not in x['roles']:continue
   at=x['day']+' 15:10:00+08:00';ss=slots[x['sid']];j=bisect_right([s['flat_at'] for s in ss],at)-1
   if j<0 or at>=ss[j]['end_at']:continue
   assert not x['held'],(label,x,ss[j])
   by[x['sid']].append((x,ss[j]))
  for sid,xx in by.items():
   f=frame(sm[sid]['refs']['facts'],['close','raw_close','factor','segment_id','i_floor'])
   cp=frame(sm[sid]['refs']['CP1'],['receipt','candidate','frontier','reset_reason'])
   for op,slot in xx:
    day=op['day'];dt=pd.Timestamp(day);sec=op['sector']
    if sec not in st:st[sec]=frame(im[sec]['refs']['state'],['day','stage_name']).set_index('day')
    stage=st[sec].loc[day,'stage_name'] if day in st[sec].index else None
    roles=[]
    if op['CP1_id'] and op['mobile_Q'] is True and stage in ['confirmed','expanded']:roles.append('mobile')
    if 'core' in op['roles']:roles.append('core')
    if not roles:continue
    r=f.loc[dt];post=cal[(cal>=pd.Timestamp(slot['flat_at'][:10]))&(cal<dt)];hist=f.reindex(post)
    high=None
    if not len(post):status='UNFORMED_FIRST_CLOSE'
    elif hist.close.isna().any() or hist.segment_id.isna().any() or hist.segment_id.nunique()!=1 or hist.segment_id.iloc[0]!=r.segment_id:status='UNKNOWN_PRICE_OR_SOURCE'
    else:high=float(hist.close.max());status='PASS' if r.close>high else 'FAIL'
    ch=cp.reindex(cal[(cal>=pd.Timestamp(slot['flat_at'][:10]))&(cal<=dt)])
    reasons=Counter(str(x) for x in ch.reset_reason.dropna() if x!='receipt_consumed')
    ff=ch.frontier;lower=bool(((ff<ff.shift(1))|(ff.isna()&ff.shift(1).notna())).any())
    v=[v for v in rules['quantity_versions'][sid] if v['from']<=day and (v['to'] is None or day<=v['to'])];assert len(v)==1
    rule=v[0]['rule'];qmin=rule['buy_minimum'];step=rule['buy_step'];nav=D(dd[day]['nav']);price=D(str(r.raw_close))*D('1.0005')
    for role in roles:
     floor=D(str(r.i_floor))
     if role=='mobile':
      assert bool(cp.loc[dt,'receipt']);floor=max(floor,D(str(cp.loc[dt,'candidate'])))
     floor/=D(str(r.factor));distance=max(D(0),price-floor);riskmin=D(qmin)*distance
     capitalcap=nav*D('.02');riskcap=nav*D('.0025');cap=int(capitalcap/price)
     if distance>0:cap=min(cap,int(riskcap/distance))
     cap=cap//step*step;cap=cap if cap>=qmin else 0
     allrows.append(dict(window=label,sid=sid,sector=sec,day=day,role=role,flat_at=slot['flat_at'],next_actual_buy_at=slot['next_actual_buy_at'],
       original_receipt=op['CP1_id'] if role=='mobile' else None,original_roles=op['roles'],original_barriers=op['barriers'],market_stage=stage,
       local_high_status=status,prior_postexit_high=high,signal_close=float(r.close),local_high_observations=len(post),
       nonreceipt_CP1_reset_reasons=dict(reasons),frontier_cleared_or_lowered_in_postexit_window=lower,
       legal_minimum_quantity=qmin,known_close_buy_reference=price,known_original_floor_raw=floor,minimum_gross=qmin*price,
       minimum_nominal_risk_before_fees=riskmin,decision_NAV=nav,trial_risk025pct=riskcap,original_capital2pct=capitalcap,
       minimum_exceeds_trial_risk=riskmin>riskcap,minimum_exceeds_original_capital=D(qmin)*price>capitalcap,
       feeless_quantity_upper_bound=cap,close_available=D(dd[day]['available']),close_cash_above_original10pct=D(dd[day]['available'])-nav*D('.1'),
       sizing_scope='Necessary signal-CLOSE price-distance and gross bounds only; excludes fees, actual OPEN gaps and serial resources'))
  a=[x for x in allrows if x['window']==label];stats[label]=dict(all_flat_intervals=sum(len(v) for v in slots.values()),
    original_actual_reentry_layers=sum(x['action']=='fresh_reentry_after_actual_flat' for x in es),
    mother_role_events=len(a),by_role={role:dict(events=len([x for x in a if x['role']==role]),
      local_high=Counter(x['local_high_status'] for x in a if x['role']==role),
      legal_minimum_exceeds_trial_risk=sum(x['minimum_exceeds_trial_risk'] for x in a if x['role']==role),
      legal_minimum_exceeds_original2pct=sum(x['minimum_exceeds_original_capital'] for x in a if x['role']==role),
      positive_feeless_quantity_upper_bound=sum(x['feeless_quantity_upper_bound']>0 for x in a if x['role']==role)) for role in ['mobile','core']})
 save('ALL_FEATURES_PRE_OUTCOME.json',allrows);save('FLAT_INTERVALS.json',allslots)
 featurehash=hashlib.sha256((O/'ALL_FEATURES_PRE_OUTCOME.json').read_bytes()).hexdigest();save('PRE_OUTCOME_FREEZE.json',dict(feature_sha256=featurehash,script_sha256=SRC[str(Path(__file__))],protocol_sha256=SRC[str(O/'PROTOCOL.txt')]))
 # Actual original lifecycle outcomes are joined only after feature table freeze.
 cross=[];groups=defaultdict(list)
 bykey={(x['window'],x['sid'],x['day'],x['role']):x for x in allrows};assert len(bykey)==len(allrows)
 for label,es in allentries.items():
  for e in es:
   if e['action']!='fresh_reentry_after_actual_flat':continue
   f=bykey.get((label,e['sid'],e['signal_day'],e['role']))
   row=dict(window=label,layer=e['layer'],sid=e['sid'],name=e['name'],industry=e['industry'],signal_day=e['signal_day'],opened=e['opened'],role=e['role'],cost=e['cost'],net=e['net'],qty=e['qty'],
      feature=f,classification=f['local_high_status'] if f else 'OUTSIDE_MOTHER_or_same_OPEN_reentry')
   cross.append(row);groups[label,e['role'],row['classification']].append(row)
 summary=[]
 for (w,r,g),rs in groups.items():summary.append(dict(window=w,role=r,status=g,layers=len(rs),stocks=len({x['sid'] for x in rs}),original_buycash=sum((D(x['cost']) for x in rs),D(0)),original_lifecycle_net=sum((D(x['net']) for x in rs),D(0)),original_negative_net=sum((D(x['net']) for x in rs if D(x['net'])<0),D(0)),original_positive_net=sum((D(x['net']) for x in rs if D(x['net'])>0),D(0))))
 save('ACTUAL_REENTRY_CROSS.json',cross);save('ACTUAL_REENTRY_SUMMARY.json',summary);save('COVERAGE_SUMMARY.json',stats)
 save('SOURCE_SHA256.json',SRC);save('COMPLETION.json',dict(seconds=time.monotonic()-start,account_runs=0,new_financial_events=0,original_windows={k:[list(v.values())[0]['at'],list(v.values())[-1]['at']] for k,v in []},all_features_sha256=featurehash))
 print(json.dumps(clean(stats),ensure_ascii=False,indent=2));print(json.dumps(clean(summary),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
